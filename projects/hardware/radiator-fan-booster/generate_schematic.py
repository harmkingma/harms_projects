"""Generate the KiCad 10 schematic for the radiator fan booster (no third-party dependencies).

    python projects/hardware/radiator-fan-booster/generate_schematic.py

Writes next to this file:
    radiator_fan_booster.kicad_sch   schematic (A3, net-label style)
    radiator_fan_booster.kicad_sym   project symbols: ESP32-C3 SuperMini, 12->5 V buck module
    radiator_fan_booster.kicad_pro   minimal project file
    sym-lib-table                    makes the project library available in eeschema
Standard symbols are copied (flattened) from the installed KiCad library so the schematic is
self-contained. Check it with:  kicad-cli sch erc radiator_fan_booster.kicad_sch
"""
import copy
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
NAME = "radiator_fan_booster"
KICAD_SYMBOLS = os.environ.get(
    "KICAD_SYMBOL_DIR",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "KiCad", "10.0", "share", "kicad", "symbols"))
SCH_VERSION = "20250610"


# --- Minimal s-expression reader/writer ------------------------------------------------------
class Q(str):
    """A quoted string atom."""


def parse(text):
    tokens = re.finditer(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+', text)
    stack = [[]]
    for m in tokens:
        tok = m.group(0)
        if tok == "(":
            stack.append([])
        elif tok == ")":
            node = stack.pop()
            stack[-1].append(node)
        elif tok.startswith('"'):
            stack[-1].append(Q(tok[1:-1].replace('\\"', '"').replace("\\\\", "\\")))
        else:
            stack[-1].append(tok)
    return stack[0][0]


def dump(node, indent=0):
    if isinstance(node, Q):
        return '"' + node.replace("\\", "\\\\").replace('"', '\\"') + '"'
    if not isinstance(node, list):
        return str(node)
    if all(not isinstance(n, list) for n in node):
        return "(" + " ".join(dump(n) for n in node) + ")"
    pad = "\t" * (indent + 1)
    head = [dump(n) for n in node if not isinstance(n, list)]
    body = [pad + dump(n, indent + 1) for n in node if isinstance(n, list)]
    return "(" + " ".join(head) + "\n" + "\n".join(body) + "\n" + "\t" * indent + ")"


def children(node, key):
    return [n for n in node if isinstance(n, list) and n and n[0] == key]


def child(node, key):
    found = children(node, key)
    return found[0] if found else None


_lib_cache = {}


def lib_root(lib):
    if lib not in _lib_cache:
        with open(os.path.join(KICAD_SYMBOLS, lib + ".kicad_sym"), encoding="utf-8") as f:
            _lib_cache[lib] = parse(f.read())
    return _lib_cache[lib]


def find_symbol(root, name):
    for s in children(root, "symbol"):
        if s[1] == name:
            return s
    raise KeyError(name)


def flattened(lib, name):
    """Library symbol with any `extends` resolved, renamed to "lib:name" for the schematic cache."""
    root = lib_root(lib)
    sym = copy.deepcopy(find_symbol(root, name))
    ext = child(sym, "extends")
    if ext:
        base = copy.deepcopy(find_symbol(root, ext[1]))
        if child(base, "extends"):
            raise ValueError(f"nested extends not supported: {lib}:{name}")
        props = children(sym, "property")
        merged = [n for n in base if not (isinstance(n, list) and n and n[0] == "property")]
        merged[1] = Q(name)
        idx = next(i for i, n in enumerate(merged) if isinstance(n, list) and n[0] == "symbol")
        merged[idx:idx] = props
        for unit in children(merged, "symbol"):
            unit[1] = Q(str(unit[1]).replace(ext[1] + "_", name + "_", 1))
        sym = merged
    sym[1] = Q(f"{lib}:{name}")
    return sym


def pins_of(sym):
    """[(number, name, type, x, y, angle)] from all units of a (flattened) symbol."""
    out = []
    for unit in children(sym, "symbol"):
        for p in children(unit, "pin"):
            at = child(p, "at")
            out.append((str(child(p, "number")[1]), str(child(p, "name")[1]), p[1],
                        float(at[1]), float(at[2]), int(float(at[3]))))
    return out


# --- Project symbol library -------------------------------------------------------------------
FONT = ["effects", ["font", ["size", "1.27", "1.27"]]]


def prop(name, value, x, y, hide=False):
    eff = copy.deepcopy(FONT)
    if hide:
        eff.append(["hide", "yes"])
    return ["property", Q(name), Q(value), ["at", f"{x:g}", f"{y:g}", "0"], eff]


def pin(ptype, x, y, angle, name, number):
    return ["pin", ptype, "line", ["at", f"{x:g}", f"{y:g}", str(angle)], ["length", "2.54"],
            ["name", Q(name), copy.deepcopy(FONT)], ["number", Q(number), copy.deepcopy(FONT)]]


def custom_symbol(name, ref, value, desc, half_w, half_h, left, right):
    """left/right: [(type, name, number)] from top to bottom, 2.54 mm pitch."""
    pins = []
    for side, entries in ((-1, left), (1, right)):
        for i, (ptype, pname, num) in enumerate(entries):
            y = half_h - 2.54 * (i + 1)
            pins.append(pin(ptype, side * (half_w + 2.54), y, 0 if side < 0 else 180, pname, num))
    return ["symbol", Q(name), ["pin_names", ["offset", "1.016"]], ["exclude_from_sim", "no"],
            ["in_bom", "yes"], ["on_board", "yes"],
            prop("Reference", ref, 0, half_h + 1.27), prop("Value", value, 0, -half_h - 1.27),
            prop("Footprint", "", 0, 0, True), prop("Datasheet", "", 0, 0, True),
            prop("Description", desc, 0, 0, True),
            ["symbol", Q(name + "_0_1"),
             ["rectangle", ["start", f"{-half_w:g}", f"{half_h:g}"], ["end", f"{half_w:g}", f"{-half_h:g}"],
              ["stroke", ["width", "0.254"], ["type", "default"]], ["fill", ["type", "background"]]]],
            ["symbol", Q(name + "_1_1")] + pins]


ESP_SYM = custom_symbol(
    "ESP32-C3_SuperMini", "U", "ESP32-C3 SuperMini",
    "ESP32-C3 SuperMini (USB-C up, components up). On-board: GPIO8 blue LED (active low), GPIO9 BOOT button.",
    7.62, 11.43,
    [("power_in", "5V", "1"), ("power_in", "GND", "2"), ("power_out", "3V3", "3"), ("bidirectional", "GPIO4", "4"),
     ("bidirectional", "GPIO3", "5"), ("bidirectional", "GPIO2", "6"), ("bidirectional", "GPIO1", "7"),
     ("bidirectional", "GPIO0", "8")],
    [("bidirectional", "GPIO5", "9"), ("bidirectional", "GPIO6", "10"), ("bidirectional", "GPIO7", "11"),
     ("bidirectional", "GPIO8", "12"), ("bidirectional", "GPIO9", "13"), ("bidirectional", "GPIO10", "14"),
     ("bidirectional", "GPIO20", "15"), ("bidirectional", "GPIO21", "16")])
BUCK_SYM = custom_symbol(
    "Buck_5V_Module", "U", "DC-DC buck 5V 1.5A",
    "Fixed 5 V step-down module, 7-26 V in (Tinytronics 1.5A 5V output).", 7.62, 3.81,
    [("power_in", "VIN", "1"), ("passive", "GND", "2")],
    [("power_out", "VOUT", "3"), ("passive", "GND", "4")])


def write_project_library():
    ver = child(lib_root("Device"), "version")[1]
    lib = ["kicad_symbol_lib", ["version", ver], ["generator", Q("radiator_fan_booster_generator")],
           ["generator_version", Q("10.0")], copy.deepcopy(ESP_SYM), copy.deepcopy(BUCK_SYM)]
    with open(os.path.join(HERE, NAME + ".kicad_sym"), "w", encoding="utf-8", newline="\n") as f:
        f.write(dump(lib) + "\n")
    with open(os.path.join(HERE, "sym-lib-table"), "w", encoding="utf-8", newline="\n") as f:
        f.write('(sym_lib_table\n\t(version 7)\n\t(lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")'
                '(options "")(descr "Radiator fan booster project symbols"))\n)\n' % (NAME, NAME))
    pro = {"meta": {"filename": NAME + ".kicad_pro", "version": 3}, "schematic": {"legacy_lib_dir": "",
           "legacy_lib_list": []}, "sheets": [], "boards": [], "text_variables": {}}
    with open(os.path.join(HERE, NAME + ".kicad_pro"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")


# --- Schematic builder ------------------------------------------------------------------------------
class Sheet:
    def __init__(self):
        self.lib_symbols = {}
        self.items = []
        self.uid = 0
        self.root = self.new_uuid()
        self.pwr = 0

    def new_uuid(self):
        self.uid += 1
        return f"b2000000-0000-4000-8000-{self.uid:012d}"

    def lib(self, lib_id):
        if lib_id not in self.lib_symbols:
            lib, name = lib_id.split(":")
            if lib == NAME:
                sym = copy.deepcopy({"ESP32-C3_SuperMini": ESP_SYM, "Buck_5V_Module": BUCK_SYM}[name])
                sym[1] = Q(lib_id)
            else:
                sym = flattened(lib, name)
            self.lib_symbols[lib_id] = sym
        return self.lib_symbols[lib_id]

    def symbol(self, lib_id, ref, value, x, y, footprint="", in_bom=True, ref_xy=None, val_xy=None, hide_ref=False,
               angle=0, val_justify="left"):
        sym = self.lib(lib_id)
        pins = pins_of(sym)
        rx, ry = ref_xy if ref_xy else (x + 3.81, y - 5.08)
        vx, vy = val_xy if val_xy else (x + 3.81, y + 5.08)
        node = ["symbol", ["lib_id", Q(lib_id)], ["at", f"{x:g}", f"{y:g}", str(angle)], ["unit", "1"],
                ["exclude_from_sim", "no"], ["in_bom", "yes" if in_bom else "no"], ["on_board", "yes"],
                ["dnp", "no"], ["uuid", Q(self.new_uuid())],
                self._prop("Reference", ref, rx, ry, hide_ref),
                self._prop("Value", value, vx, vy, False, val_justify, (-angle) % 360),
                self._prop("Footprint", footprint, x, y, True), self._prop("Datasheet", "", x, y, True)]
        for number, *_ in pins:
            node.append(["pin", Q(number), ["uuid", Q(self.new_uuid())]])
        node.append(["instances", ["project", Q(NAME), ["path", Q("/" + self.root),
                                                       ["reference", Q(ref)], ["unit", "1"]]]])
        self.items.append(node)
        return {(n, nm): (x + px, y - py, ang) for n, nm, _t, px, py, ang in pins}

    @staticmethod
    def _prop(name, value, x, y, hide=False, justify="left", angle=0):
        eff = ["effects", ["font", ["size", "1.27", "1.27"]]]
        if justify != "center":
            eff.append(["justify", justify])
        if hide:
            eff.append(["hide", "yes"])
        return ["property", Q(name), Q(value), ["at", f"{x:g}", f"{y:g}", str(angle)], eff]

    def wire(self, x1, y1, x2, y2):
        self.items.append(["wire", ["pts", ["xy", f"{x1:g}", f"{y1:g}"], ["xy", f"{x2:g}", f"{y2:g}"]],
                           ["stroke", ["width", "0"], ["type", "default"]], ["uuid", Q(self.new_uuid())]])

    def label(self, net, x, y, direction):
        angle, justify = {"left": (180, "right"), "right": (0, "left"),
                          "up": (90, "left"), "down": (270, "right")}[direction]
        self.items.append(["label", Q(net), ["at", f"{x:g}", f"{y:g}", str(angle)],
                           ["effects", ["font", ["size", "1.27", "1.27"]], ["justify", justify, "bottom"]],
                           ["uuid", Q(self.new_uuid())]])

    def power(self, net, x, y, direction="up"):
        """Power symbol whose body points `direction` (away from the pin it is attached to)."""
        self.pwr += 1
        lib_id = "power:PWR_FLAG" if net == "PWR_FLAG" else f"power:{net}"
        ref = f"#FLG0{self.pwr:02d}" if net == "PWR_FLAG" else f"#PWR0{self.pwr:02d}"
        if net == "GND":
            angle = {"down": 0, "right": 90, "up": 180, "left": 270}[direction]
        else:
            angle = {"up": 0, "left": 90, "down": 180, "right": 270}[direction]
        val_xy, justify = {"up": ((x, y - 3.81), "center"), "down": ((x, y + 5.08), "center"),
                           "left": ((x - 3.81, y + 0.635), "right"), "right": ((x + 3.81, y + 0.635), "left")}[direction]
        self.symbol(lib_id, ref, net, x, y, in_bom=False, hide_ref=True, val_xy=val_xy, angle=angle,
                    val_justify=justify)

    def no_connect(self, x, y):
        self.items.append(["no_connect", ["at", f"{x:g}", f"{y:g}"], ["uuid", Q(self.new_uuid())]])

    def text(self, s, x, y, size=1.27):
        self.items.append(["text", Q(s), ["exclude_from_sim", "no"], ["at", f"{x:g}", f"{y:g}", "0"],
                           ["effects", ["font", ["size", f"{size:g}", f"{size:g}"]], ["justify", "left", "bottom"]],
                           ["uuid", Q(self.new_uuid())]])

    def connect(self, pinmap, nets, stub=2.54):
        """nets: {pin number or name: net}. Power nets get a power symbol, 'NC' a no-connect flag."""
        for (number, pname), (px, py, ang) in pinmap.items():
            net = nets.get(number, nets.get(pname))
            if net is None:
                raise KeyError(f"pin {number}/{pname} not assigned")
            if net == "NC":
                self.no_connect(px, py)
                continue
            dx, dy, direction = {0: (-stub, 0, "left"), 180: (stub, 0, "right"),
                                 90: (0, stub, "down"), 270: (0, -stub, "up")}[ang]
            if net in POWER_NETS and direction in ("left", "right"):
                dx *= 3
            ex, ey = px + dx, py + dy
            self.wire(px, py, ex, ey)
            if net in POWER_NETS:
                self.power(net, ex, ey, direction)
            else:
                self.label(net, ex, ey, direction)

    def write(self, path, title, date, rev, comments):
        tb = ["title_block", ["title", Q(title)], ["date", Q(date)], ["rev", Q(rev)],
              ["company", Q("harms_projects")]]
        for i, c in enumerate(comments, start=1):
            tb.append(["comment", str(i), Q(c)])
        doc = ["kicad_sch", ["version", SCH_VERSION], ["generator", Q("eeschema")], ["generator_version", Q("10.0")],
               ["uuid", Q(self.root)], ["paper", Q("A3")], tb, ["lib_symbols"] + list(self.lib_symbols.values())]
        doc += self.items
        doc += [["sheet_instances", ["path", Q("/"), ["page", Q("1")]]], ["embedded_fonts", "no"]]
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(dump(doc) + "\n")


POWER_NETS = {"+12V", "+5V", "+3V3", "GND"}
G = 2.54   # grid


def build():
    s = Sheet()

    # --- Power: 12 V jack -> bulk cap -> buck 5 V -> Schottky -> C3 5V ------------------------
    s.text("POWER  12 V adapter (2 A) -> fans + buck converter -> ESP32-C3 SuperMini", 25.4, 30.48, 2.0)
    s.connect(s.symbol("Connector:Barrel_Jack", "J1", "DC-099 5.5x2.1 (12V)", 38.1, 50.8,
                       ref_xy=(30.48, 41.91), val_xy=(30.48, 59.69)), {"1": "+12V", "2": "GND"})
    s.connect(s.symbol("Device:C_Polarized", "C1", "470uF 25V", 68.58, 50.8),
              {"1": "+12V", "2": "GND"})
    s.connect(s.symbol(f"{NAME}:Buck_5V_Module", "U1", "DC-DC buck 5V 1.5A", 101.6, 50.8,
                       ref_xy=(96.52, 44.45), val_xy=(93.98, 58.42)),
              {"VIN": "+12V", "2": "GND", "VOUT": "5V_BUCK", "4": "GND"})
    s.connect(s.symbol("Device:D_Schottky", "D1", "1N5819", 149.86, 50.8, ref_xy=(146.05, 45.72),
                       val_xy=(146.05, 55.88)), {"K": "+5V", "A": "5V_BUCK"})
    for i, net in enumerate(("+12V", "GND", "+5V")):   # +3V3 is driven by U2's 3V3 output
        x, y = 182.88 + i * 20.32, 50.8
        s.power(net, x, y, "down" if net == "GND" else "up")
        s.wire(x, y, x + 7.62, y)
        s.power("PWR_FLAG", x + 7.62, y)

    # --- Controller ---------------------------------------------------------------------------------
    s.text("CONTROLLER  ESP32-C3 SuperMini (ESPHome)", 25.4, 81.28, 2.0)
    s.connect(s.symbol(f"{NAME}:ESP32-C3_SuperMini", "U2", "ESP32-C3 SuperMini", 76.2, 111.76,
                       ref_xy=(71.12, 99.06), val_xy=(66.04, 124.46)),
              {"5V": "+5V", "GND": "GND", "3V3": "+3V3", "GPIO4": "TACH4", "GPIO3": "TACH3", "GPIO2": "NC",
               "GPIO1": "TACH2", "GPIO0": "TACH1", "GPIO5": "FAN_PWM_GATE", "GPIO6": "NC", "GPIO7": "NC",
               "GPIO8": "NC", "GPIO9": "NC", "GPIO10": "ONEWIRE", "GPIO20": "NC", "GPIO21": "NC"})

    # --- Fan PWM driver (open drain, inverting) --------------------------------------------------------
    s.text("FAN PWM DRIVER (open drain)", 129.54, 81.28, 2.0)
    s.connect(s.symbol("Device:R", "R1", "4.7k", 134.62, 100.33), {"1": "+3V3", "2": "FAN_PWM_GATE"})
    s.connect(s.symbol("Transistor_FET:2N7000", "Q1", "2N7000", 170.18, 111.76, ref_xy=(175.26, 107.95),
                       val_xy=(175.26, 115.57)), {"G": "FAN_PWM_GATE", "D": "FAN_PWM", "S": "GND"})

    # --- Tach pull-ups + 1-Wire pull-up -----------------------------------------------------------------
    s.text("PULL-UPS (tach + 1-Wire)", 205.74, 81.28, 2.0)
    for i in range(4):
        s.connect(s.symbol("Device:R", f"R{i + 2}", "4.7k", 213.36 + i * 12.7, 100.33),
                  {"1": "+3V3", "2": f"TACH{i + 1}"})
    s.connect(s.symbol("Device:R", "R6", "4.7k", 271.78, 100.33), {"1": "+3V3", "2": "ONEWIRE"})
    s.text("R6 = 1-Wire pull-up", 266.7, 124.46)

    # --- 1-Wire terminals ---------------------------------------------------------------------------------
    s.text("1-WIRE TERMINALS (2 sensors each)", 297.18, 81.28, 2.0)
    for i, (ref, label) in enumerate((("J2", "T1 supply + T2 return"), ("J3", "T3 intake + T4 outlet"))):
        s.connect(s.symbol("Connector:Screw_Terminal_01x03", ref, label, 309.88 + i * 50.8, 104.14,
                           ref_xy=(312.42 + i * 50.8, 99.06), val_xy=(312.42 + i * 50.8, 110.49)),
                  {"1": "GND", "2": "ONEWIRE", "3": "+3V3"})

    # --- Fans ---------------------------------------------------------------------------------------------------
    s.text("FANS  4 x ARCTIC P12 Slim PWM PST, each on its own 4-pin 2.54 mm header (GND, +12V, TACH, PWM)",
           25.4, 149.86, 2.0)
    for i in range(4):
        s.connect(s.symbol("Motor:Fan_4pin", f"M{i + 1}", "P12 Slim PWM PST", 50.8 + i * 63.5, 177.8,
                           ref_xy=(55.88 + i * 63.5, 171.45), val_xy=(55.88 + i * 63.5, 184.15)),
                  {"1": "GND", "2": "+12V", "3": f"TACH{i + 1}", "4": "FAN_PWM"})

    # --- Sensors -------------------------------------------------------------------------------------------------
    s.text("TEMPERATURE SENSORS  bare DS18B20 TO-92, powered from 3V3 (not parasitic)", 25.4, 205.74, 2.0)
    for i, label in enumerate(("T1 supply pipe", "T2 return pipe", "T3 intake air", "T4 outlet grille")):
        s.connect(s.symbol("Sensor_Temperature:DS18B20", f"U{i + 3}", f"DS18B20 {label}", 50.8 + i * 63.5, 231.14,
                           ref_xy=(57.15 + i * 63.5, 224.79), val_xy=(57.15 + i * 63.5, 237.49)),
                  {"1": "GND", "2": "ONEWIRE", "3": "+3V3"})

    notes = [
        "NOTES",
        "1. ESPHome pins: GPIO5 = fan PWM (ledc 25 kHz, inverted: true, open-drain stage Q1);"
        " GPIO0/1/3/4 = tach FAN1..4 (pulse_counter, open collector, 2 pulses/rev); GPIO10 = 1-Wire.",
        "2. R1 pulls the 2N7000 gate high while the C3 boots or is dead: FAN_PWM is held low = 0 % duty ="
        " fans stopped (0 RPM mode).",
        "3. Fans pull their own PWM input up internally; the C3 never sees more than 3.3 V on any GPIO.",
        "4. D1 lets you plug in USB while 12 V is connected (SuperMini ties USB VBUS directly to its 5V pin)."
        " Without D1: never connect both.",
        "5. DS18B20 TO-92, flat face towards you, leads down: pin 1 = GND, pin 2 = DQ, pin 3 = VDD.",
        "6. Unused: GPIO2/8/9 are strapping pins (GPIO8 = on-board LED, GPIO9 = BOOT button);"
        " GPIO6/7/20/21 are spare.",
        "7. Fan headers are 2.54 mm male pin headers; mark pin 1 (GND). FAN3/FAN4 use 30 cm 4-pin extensions.",
    ]
    for i, line in enumerate(notes):
        s.text(line, 25.4, 256.54 + i * 3.81, 1.6 if i == 0 else 1.27)

    s.write(os.path.join(HERE, NAME + ".kicad_sch"), "Radiator fan booster - controller",
            "2026-11-26", "1.0",
            ["ESP32-C3 SuperMini, 4 x 120 mm PWM fan, 4 x DS18B20 on 1-Wire",
             "Generated by generate_schematic.py - edit the generator, not the schematic"])


if __name__ == "__main__":
    write_project_library()
    build()
    print("Wrote", NAME + ".kicad_sch,", NAME + ".kicad_sym,", NAME + ".kicad_pro, sym-lib-table")
