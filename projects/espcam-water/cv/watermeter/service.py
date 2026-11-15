"""Home Assistant add-on service: capture -> read -> track -> publish over MQTT, plus an Ingress page.

Run: python -m watermeter.service  (inside the add-on; options from /data/options.json)
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import html
import io
import json
import logging
import os
import pathlib
import threading
import time
import urllib.request
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np

from .camera import Camera
from .draws import DrawDetector
from .hpboiler import HomeAssistant, params_from_states, year_summary
from .learning import DigitLearner
from .pipeline import MeterReader
from .tracker import MeterTracker

log = logging.getLogger("water_meter")
TOPIC = "water_meter"
DISCOVERY = "homeassistant"
INGRESS_PEER = "172.30.32.2"   # Supervisor ingress proxy; the only client allowed on the web port
DEVICE = {"identifiers": ["water_meter_reader"], "name": "Water meter", "manufacturer": "espcam",
          "model": "ESP32-CAM dial reader"}


@dataclasses.dataclass
class Options:
    camera_host: str = "192.168.68.76"
    flash_brightness: int = 140
    settle_s: float = 1.5
    interval_s: int = 30
    flow_interval_s: int = 10   # while a draw is open: places start/stop and pauses within seconds
    draw_gap_s: int = 120       # a draw ends after this long without flow
    start_value: float | None = None
    keep_rejected: int = 50
    export_statistic: str | None = None  # grid export kWh statistic; auto-detected when empty

    @classmethod
    def load(cls, path: str | pathlib.Path) -> Options:
        p = pathlib.Path(path)
        data = json.loads(p.read_text()) if p.exists() else {}
        names = {f.name for f in dataclasses.fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in names})


def iso(ts: float | None) -> str | None:
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat() if ts else None


class WaterMeterService:
    def __init__(self, opts: Options, config_path: pathlib.Path, data_dir: pathlib.Path,
                 share_dir: pathlib.Path, camera, mqtt):
        self.opts, self.camera, self.mqtt = opts, camera, mqtt
        self.share_dir = share_dir
        self.learner = DigitLearner(share_dir)
        self.reader = MeterReader(config_path, self.learner.digits_dir)
        self.tracker = MeterTracker(self.reader, data_dir / "state.json", self.learner)
        self.rejected_dir = share_dir / "rejected"
        self.rejected_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.pending_value: float | None = None
        self.last_image: bytes | None = None
        self.last_state: dict = {}
        self.flow = 0.0
        if self.tracker.apply_start_value(opts.start_value):
            log.info("start value %.4f m3 applied from add-on options", opts.start_value)
        # Longer reading gaps (outage) make a draw's timing a guess; it is then flagged incomplete.
        self.draws = DrawDetector(opts.draw_gap_s, max(3 * opts.interval_s, 90), data_dir / "draw.json")
        self.draws.seed(self.tracker.state.ts, self.tracker.state.total)

    @property
    def drawing(self) -> bool:
        return self.draws.open

    # --- MQTT -------------------------------------------------------------------------------
    def discovery(self) -> None:
        state = f"{TOPIC}/state"
        common = {"device": DEVICE, "availability_topic": f"{TOPIC}/availability"}
        entities = {
            ("sensor", "total"): {"name": "Total", "state_topic": state, "value_template": "{{ value_json.total }}",
                                  "unit_of_measurement": "m³", "device_class": "water",
                                  "state_class": "total_increasing", "suggested_display_precision": 4},
            ("sensor", "flow"): {"name": "Flow", "state_topic": state, "value_template": "{{ value_json.flow }}",
                                 "unit_of_measurement": "L/min", "device_class": "volume_flow_rate",
                                 "state_class": "measurement", "suggested_display_precision": 1},
            ("binary_sensor", "drawing"): {"name": "Drawing", "state_topic": state,
                                           "value_template": "{{ 'ON' if value_json.get('drawing') else 'OFF' }}",
                                           "device_class": "running", "icon": "mdi:water-pump"},
            ("sensor", "status"): {"name": "Status", "state_topic": state, "value_template": "{{ value_json.status }}",
                                   "json_attributes_topic": state, "icon": "mdi:list-status"},
            ("sensor", "confidence"): {"name": "Confidence", "state_topic": state,
                                       "value_template": "{{ value_json.confidence }}",
                                       "state_class": "measurement", "entity_category": "diagnostic"},
            ("sensor", "last_valid"): {"name": "Last valid reading", "state_topic": state,
                                       "value_template": "{{ value_json.last_valid }}", "device_class": "timestamp",
                                       "entity_category": "diagnostic"},
            ("number", "set_value"): {"name": "Set meter value", "command_topic": f"{TOPIC}/set_value",
                                      "state_topic": state, "value_template": "{{ value_json.total }}",
                                      "min": 0, "max": 99999, "step": 0.001, "mode": "box",
                                      "unit_of_measurement": "m³", "entity_category": "config",
                                      "icon": "mdi:counter"},
            ("camera", "image"): {"name": "Last image", "topic": f"{TOPIC}/image"},
            ("sensor", "boiler_solar_share"): {
                "name": "Boiler solar share year", "state_topic": f"{TOPIC}/boiler",
                "value_template": "{{ value_json.solar_share }}", "json_attributes_topic": f"{TOPIC}/boiler",
                "unit_of_measurement": "%", "state_class": "measurement", "icon": "mdi:solar-power-variant"},
        }
        for (component, key), cfg in entities.items():
            entity_id = f"{component}.water_meter_{cfg['name'].lower().replace(' ', '_')}"
            payload = {**common, **cfg, "unique_id": f"water_meter_{key}", "default_entity_id": entity_id}
            self.mqtt.publish(f"{DISCOVERY}/{component}/water_meter/{key}/config", json.dumps(payload), retain=True)

    def on_set_value(self, payload: bytes) -> None:
        try:
            value = float(payload)
        except ValueError:
            log.warning("ignored set_value %r", payload)
            return
        with self.lock:
            self.pending_value = value

    # --- one reading cycle --------------------------------------------------------------------
    def step(self, now: float | None = None) -> dict:
        """One reading cycle. `now` fixes the reading time (tests); else the frame's capture time."""
        with self.lock:
            pending, self.pending_value = self.pending_value, None
        if pending is not None:
            self.tracker.apply_start_value(pending, ts=now or time.time(), force=True)
            self.flow = 0.0
            log.info("meter value set to %.4f m3 via MQTT", pending)
        prev_total, prev_ts = self.tracker.state.total, self.tracker.state.ts
        anchored = self.tracker.state.pending_start
        try:
            jpeg = self.camera.capture()
            img = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                raise RuntimeError("snapshot is not a JPEG")
        except Exception as exc:  # camera offline/rebooting: keep the last value, report status
            log.warning("capture failed: %s", exc)
            return self._publish({"status": "camera_error", "detail": str(exc)[:200]})

        # A capture takes 2.5-10 s; timing the cycle start instead would put that jitter into the flow.
        now = now or getattr(self.camera, "frame_ts", None) or time.time()
        res = self.tracker.process(img, now)
        rd = res.reading
        annotated = cv2.imencode(".jpg", self.reader.annotate(res), [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()
        with self.lock:
            self.last_image = annotated
        self.mqtt.publish(f"{TOPIC}/image", annotated)
        if rd.total is not None and anchored:
            self._publish_draws(self.draws.reset(now, rd.total))
        elif rd.total is not None:
            if prev_total is not None and prev_ts and now > prev_ts:
                self.flow = round(max(rd.total - prev_total, 0.0) * 1000 / ((now - prev_ts) / 60), 2)
            self._publish_draws(self.draws.add(now, rd.total))
        if rd.total is None:
            self._keep_rejected(jpeg, annotated, now)
        conf = [d.confidence for d in res.dials]
        return self._publish({
            "status": rd.status, "detail": rd.detail, "digits": rd.digits,
            "dials": [round(v, 3) for v in rd.dials],
            "confidence": round(min(conf), 2) if conf else 0.0,
        })

    def _publish(self, state: dict) -> dict:
        state = {"total": self.tracker.state.total, "flow": self.flow, "drawing": self.draws.open,
                 "last_valid": iso(self.tracker.state.ts), "updated": iso(time.time()), "confidence": 0.0,
                 **state}
        with self.lock:
            self.last_state = state
        self.mqtt.publish(f"{TOPIC}/state", json.dumps(state), retain=True)
        return state

    def _publish_draws(self, events: list[dict]) -> None:
        # Not retained: a retained message would replay the draw into HA's totals on every reconnect.
        for event in events:
            self.mqtt.publish(f"{TOPIC}/draw", json.dumps(event))
            if event["event"] == "end":
                log.info("draw %s-%s: %s L, main %s L flowing %s min = %s L/min", event["start"], event["end"],
                         event["volume_l"], event["main_volume_l"], event["main_flowing_min"], event["main_flow"])

    # --- heat-pump boiler year simulation --------------------------------------------------
    def run_boiler_sim(self, ha: HomeAssistant, today: dt.date | None = None) -> dict:
        stat = self.opts.export_statistic
        if not stat:
            found = ha.export_statistics()
            # P1 meters also publish per-tariff splits of the same total.
            totals = [s for s in found if "tariff" not in s] or found
            if len(totals) != 1:
                payload = {"solar_share": None, "status": "set export_statistic",
                           "detail": f"export statistics found: {found}"}
                self.mqtt.publish(f"{TOPIC}/boiler", json.dumps(payload), retain=True)
                return payload
            stat = totals[0]
        params, notes = params_from_states(ha.states())
        summary = year_summary(ha.hourly_export(stat), params, today or dt.date.today())
        payload = {"solar_share": None, "status": "waiting for 7 days of export history", **(summary or {}),
                   "export_statistic": stat, "heat_kwh_day": round(params.heat_kwh_day, 2),
                   "notes": notes, "last_run": iso(time.time())}
        if summary:
            payload["status"] = "ok"
        self.mqtt.publish(f"{TOPIC}/boiler", json.dumps(payload), retain=True)
        return payload

    def _keep_rejected(self, jpeg: bytes, annotated: bytes, now: float) -> None:
        if self.opts.keep_rejected <= 0:
            return
        stamp = dt.datetime.fromtimestamp(now).strftime("%Y%m%d_%H%M%S")
        (self.rejected_dir / f"{stamp}.jpg").write_bytes(jpeg)
        (self.rejected_dir / f"{stamp}_read.jpg").write_bytes(annotated)
        files = sorted(self.rejected_dir.glob("*.jpg"))
        for old in files[:max(len(files) - 2 * self.opts.keep_rejected, 0)]:
            old.unlink(missing_ok=True)

    # --- Ingress page --------------------------------------------------------------------------
    def samples_zip(self) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for sub in ("digits", "review", "rejected"):
                for f in sorted((self.share_dir / sub).rglob("*")):
                    if f.is_file():
                        zf.write(f, f.relative_to(self.share_dir).as_posix())
        return buf.getvalue()

    def page(self) -> str:
        with self.lock:
            s = dict(self.last_state)
        counts = {d: len(list((self.learner.digits_dir / str(d)).glob("*.png"))) for d in range(10)}
        rows = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(str(v))}</td></tr>" for k, v in s.items())
        learned = " ".join(f"{d}:{n}" for d, n in counts.items())
        return (f"<!doctype html><html><head><meta charset=utf-8><meta http-equiv=refresh content=30>"
                f"<title>Water meter</title><style>body{{font-family:sans-serif;margin:1em}}"
                f"img{{max-width:100%;height:auto}}th{{text-align:left;padding-right:1em}}</style></head><body>"
                f"<h2>Water meter reader</h2><table>{rows}</table>"
                f"<p>Learned digit samples: {html.escape(learned)}</p>"
                f"<p><a href='samples.zip'>Download samples (digits, review, rejected) as zip</a> · "
                f"<a href='state.json'>state.json</a></p><img src='image.jpg' alt='last reading'></body></html>")


def make_handler(service: WaterMeterService):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.client_address[0] != INGRESS_PEER and not os.environ.get("WATER_METER_ALLOW_ANY"):
                self._send(403, b"forbidden", "text/plain")
                return
            path = self.path.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
            if path in ("", "index.html"):
                self._send(200, service.page().encode(), "text/html; charset=utf-8")
            elif path == "image.jpg":
                with service.lock:
                    img = service.last_image
                if img:
                    self._send(200, img, "image/jpeg")
                else:
                    self._send(404, b"no image yet", "text/plain")
            elif path == "state.json":
                with service.lock:
                    body = json.dumps(service.last_state).encode()
                self._send(200, body, "application/json")
            elif path == "samples.zip":
                self._send(200, service.samples_zip(), "application/zip",
                           {"Content-Disposition": "attachment; filename=water_meter_samples.zip"})
            else:
                self._send(404, b"not found", "text/plain")

        def log_message(self, fmt, *args) -> None:
            log.debug("http: " + fmt, *args)

    return Handler


def supervisor_mqtt() -> dict:
    """Broker credentials from the Supervisor (add-on config: services: mqtt:need)."""
    req = urllib.request.Request("http://supervisor/services/mqtt",
                                 headers={"Authorization": f"Bearer {os.environ['SUPERVISOR_TOKEN']}"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.load(resp)["data"]


def next_sim_time(ha: HomeAssistant, at: dt.time = dt.time(3, 30)) -> float:
    """Next local `at` (HA's time zone) as a timestamp."""
    now = dt.datetime.now(ha.time_zone())
    target = now.replace(hour=at.hour, minute=at.minute, second=0, microsecond=0)
    return (target if target > now else target + dt.timedelta(days=1)).timestamp()


def main() -> None:
    import paho.mqtt.client as mqtt

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if hasattr(os, "nice"):
        os.nice(10)
    cv2.setNumThreads(1)
    opts = Options.load(os.environ.get("WATER_METER_OPTIONS", "/data/options.json"))
    app = pathlib.Path(__file__).resolve().parents[1]
    broker = supervisor_mqtt() if "SUPERVISOR_TOKEN" in os.environ else {
        "host": os.environ.get("MQTT_HOST", "localhost"), "port": int(os.environ.get("MQTT_PORT", 1883)),
        "username": os.environ.get("MQTT_USER"), "password": os.environ.get("MQTT_PASSWORD")}

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="water_meter_reader")
    camera = Camera(opts.camera_host, opts.flash_brightness, opts.settle_s)
    service = WaterMeterService(opts, app / "cv" / "meter.yaml",
                                pathlib.Path(os.environ.get("WATER_METER_DATA", "/data")),
                                pathlib.Path(os.environ.get("WATER_METER_SHARE", "/share/water_meter")),
                                camera, client)

    def on_connect(c, userdata, flags, reason_code, properties):
        log.info("MQTT connected (%s)", reason_code)
        service.discovery()
        c.publish(f"{TOPIC}/availability", "online", retain=True)
        c.subscribe(f"{TOPIC}/set_value")

    client.on_connect = on_connect
    client.on_message = lambda c, u, msg: service.on_set_value(msg.payload)
    if broker.get("username"):
        client.username_pw_set(broker["username"], broker.get("password"))
    client.will_set(f"{TOPIC}/availability", "offline", retain=True)
    client.connect_async(broker["host"], int(broker["port"]))
    client.loop_start()

    server = ThreadingHTTPServer(("0.0.0.0", 8099), make_handler(service))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # config.yaml homeassistant_api: true gives the add-on Core API access via the Supervisor.
    ha = HomeAssistant("http://supervisor/core/api", "ws://supervisor/core/websocket",
                       os.environ["SUPERVISOR_TOKEN"]) if "SUPERVISOR_TOKEN" in os.environ else None
    next_sim = time.time() + 180
    log.info("reading %s every %ss, every %ss while water runs", opts.camera_host, opts.interval_s,
             opts.flow_interval_s)
    while True:
        t0 = time.monotonic()
        try:
            state = service.step()
            log.info("%s %s %s", state.get("total"), state.get("status"), state.get("detail", ""))
        except Exception:
            log.exception("reading cycle failed")
        if ha and time.time() >= next_sim:
            try:
                sim = service.run_boiler_sim(ha)
                log.info("boiler simulation: %s, solar share %s %%", sim["status"], sim.get("solar_share"))
                next_sim = next_sim_time(ha)
            except Exception:
                log.exception("boiler simulation failed; retrying in 1 h")
                next_sim = time.time() + 3600
        time.sleep(max((opts.flow_interval_s if service.drawing else opts.interval_s)
                       - (time.monotonic() - t0), 1.0))


if __name__ == "__main__":
    main()
