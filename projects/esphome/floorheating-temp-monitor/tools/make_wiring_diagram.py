"""Render ../wiring_diagram.png: Adafruit ESP32-S2 TFT Feather + 2x DS18B20 (1-Wire bus on A0/GPIO18).

Board geometry follows the Adafruit product 5483 photo/PrettyPins (front view, USB-C left).
Run:  .venv\\Scripts\\python.exe tools\\make_wiring_diagram.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.colors import to_rgb  # noqa: E402
from matplotlib.patches import Circle, Ellipse, FancyBboxPatch, Rectangle  # noqa: E402
from matplotlib.transforms import Affine2D  # noqa: E402

OUT = Path(__file__).resolve().parent.parent / "wiring_diagram.png"

W, H = 210, 126          # canvas in drawing units (1 unit = 0.1 inch)
K = 1.8                  # drawing units per board millimetre
BX, BY = 13.0, 68.0      # board lower-left corner
BOARD_W_MM, BOARD_H_MM = 50.8, 22.9
PITCH_MM = 2.54

RED, BLACK, YELLOW = "#d62828", "#262626", "#f5c400"
AMBER = "#b38600"
SILVER = "#c3c9d0"

BOTTOM_PINS = ["RST", "3V", "3V", "GND", "A0", "A1", "A2", "A3", "A4", "A5",
               "SCK", "MO", "MI", "RX", "TX", "DBG"]
TOP_PINS = ["BAT", "EN", "USB", "13", "12", "11", "10", "9", "6", "5", "SCL", "SDA"]
USED = {1: ("3V", RED, "white"), 3: ("GND", BLACK, "white"), 4: ("A0", YELLOW, "black")}

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]


# ---------------------------------------------------------------- helpers
def mm(x: float, t: float) -> tuple[float, float]:
    """Board mm (x from left edge, t from top edge) -> drawing units."""
    return BX + x * K, BY + (BOARD_H_MM - t) * K


def shade(color, f: float):
    c = np.array(to_rgb(color))
    return tuple(np.clip(c * f, 0, 1)) if f <= 1 else tuple(c + (1 - c) * min(f - 1, 1))


def rbox(x, y, w, h, r, **kw) -> FancyBboxPatch:
    return FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", **kw)


def soft_shadow(ax, x, y, w, h, r, z, layers=7, off=(0.7, -0.9), alpha=0.05):
    for i in range(layers):
        g = i * 0.3
        ax.add_patch(rbox(x + off[0] - g, y + off[1] - g, w + 2 * g, h + 2 * g, r + g,
                          fc="black", ec="none", alpha=alpha, zorder=z))


def gradient_rect(ax, x, y, w, h, r, c1, c2, z, ec="none", lw=0.0, horizontal=False):
    """Rounded rectangle filled with a linear gradient (c1 = top/left, c2 = bottom/right)."""
    patch = rbox(x, y, w, h, r, fc="none", ec=ec, lw=lw, zorder=z + 0.01)
    ax.add_patch(patch)
    g = np.linspace(0, 1, 256)[:, None]
    ramp = np.array(to_rgb(c1)) * (1 - g) + np.array(to_rgb(c2)) * g
    img = ramp[None, :, :] if horizontal else ramp[:, None, :]
    im = ax.imshow(img, extent=(x, x + w, y, y + h), origin="upper", aspect="auto",
                   zorder=z, interpolation="bilinear")
    im.set_clip_path(patch)
    return patch


def smooth(pts, n=28) -> np.ndarray:
    """Catmull-Rom spline through the control points."""
    p = np.asarray(pts, float)
    if len(p) == 2:
        return p
    p = np.vstack([2 * p[0] - p[1], p, 2 * p[-1] - p[-2]])
    out = []
    t = np.linspace(0, 1, n, endpoint=False)[:, None]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        out.append(0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t ** 2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(p[-2][None, :])
    return np.vstack(out)


def wire(ax, pts, color, lw=8.5, z=6.0, port=None, start_blob=False):
    """Insulated wire through pts; optional stripped metal end into `port`."""
    xy = smooth(pts)
    if port is not None:
        ax.plot([pts[-1][0], port[0]], [pts[-1][1], port[1]], color="#9aa3ad", lw=lw * 0.42,
                solid_capstyle="round", zorder=z - 0.05,
                path_effects=[pe.Stroke(linewidth=lw * 0.42 + 1.2, foreground="#5d646c"), pe.Normal()])
    ax.plot(xy[:, 0], xy[:, 1], color=color, lw=lw, solid_capstyle="round", zorder=z,
            path_effects=[pe.Stroke(linewidth=lw + 2.4, foreground=shade(color, 0.45)), pe.Normal()])
    ax.plot(xy[:, 0] - 0.12, xy[:, 1] + 0.12, color=shade(color, 1.6), lw=lw * 0.25, alpha=0.6,
            solid_capstyle="round", zorder=z + 0.01)
    if start_blob:
        ax.add_patch(Circle(pts[0], 1.05, fc="#d7dce1", ec="#7d858e", lw=1.0, zorder=z + 0.02))


def chip(ax, x, y, text, bg, fg, z=9, fs=10):
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, fontweight="bold", color=fg, zorder=z,
            bbox=dict(boxstyle="round,pad=0.28,rounding_size=0.5", fc=bg, ec=shade(bg, 0.55), lw=1.2))


# ---------------------------------------------------------------- board
def pin_xy(row: str, i: int) -> tuple[float, float]:
    if row == "bottom":
        return mm(6.3 + PITCH_MM * i, BOARD_H_MM - 2.0)
    return mm(6.3 + PITCH_MM * (4 + i), 2.0)


def draw_display(ax):
    x0, y0 = mm(15.0, 20.0)
    x1, y1 = mm(45.8, 2.6)
    gradient_rect(ax, x0, y0, x1 - x0, y1 - y0, 0.6, "#26262c", "#0b0b0e", z=3, ec="#000000", lw=1.0)
    fx0, _ = mm(43.9, 0)
    ax.add_patch(Rectangle((fx0, y0 + 0.4), x1 - fx0 - 0.4, y1 - y0 - 0.8, fc="#3a3b40", ec="none", zorder=3.2))
    ax0, ay0 = mm(16.6, 18.0)
    ax1, ay1 = mm(41.5, 4.0)
    ax.add_patch(Rectangle((ax0, ay0), ax1 - ax0, ay1 - ay0, fc="#000000", ec="#15161a", lw=0.8, zorder=3.3))
    upx = (ax1 - ax0) / 240.0             # units per display pixel
    ptpx = upx * 7.2                      # points per display pixel
    def disp(px, py):
        return ax0 + px * upx, ay1 - py * upx
    rows = [(4, "Sensor 1", "21.4 °C", "#ff9600"), (70, "Sensor 2", "19.8 °C", "#00c8ff")]
    for py, label, value, col in rows:
        ax.text(*disp(8, py), label, fontsize=16 * ptpx * 0.78, color="#a0a0a0", va="top", ha="left", zorder=3.5)
        ax.text(*disp(8, py + 18), value, fontsize=34 * ptpx * 0.78, color=col, fontweight="bold",
                va="top", ha="left", zorder=3.5)
    # glass glare
    ax.fill([x0 + 2, x0 + 9, x0 + 20, x0 + 8], [y1 - 0.5, y1 - 0.5, y0 + 0.5, y0 + 0.5],
            color="white", alpha=0.045, zorder=3.6, lw=0)


def draw_board(ax):
    w, h = BOARD_W_MM * K, BOARD_H_MM * K
    soft_shadow(ax, BX, BY, w, h, 2.4, z=1)
    gradient_rect(ax, BX, BY, w, h, 2.4, "#7a3fb0", "#4b1f73", z=2, ec="#33134f", lw=1.4)

    for hx, ht in [(3.2, 2.5), (3.2, 20.4), (47.4, 2.5), (47.4, 20.4)]:
        c = mm(hx, ht)
        ax.add_patch(Circle(c, 1.95 * K, fc="#d9a441", ec="#9c7020", lw=1.0, zorder=2.5))
        ax.add_patch(Circle(c, 1.3 * K, fc="#eef2f5", ec="#8b6a2b", lw=0.8, zorder=2.6))

    # USB-C receptacle
    ux0, uy0 = mm(-1.3, 15.7)
    ux1, uy1 = mm(6.4, 6.8)
    gradient_rect(ax, ux0, uy0, ux1 - ux0, uy1 - uy0, 1.6, "#f4f6f8", "#8d949c", z=3, ec="#5f666e", lw=1.0)
    ax.add_patch(rbox(ux0 + 0.9, uy0 + 4.2, (ux1 - ux0) - 3.0, (uy1 - uy0) - 8.4, 1.2,
                      fc="#3d4248", ec="#24282c", lw=0.8, zorder=3.1))
    # LiPo JST connector
    jx0, jy0 = mm(6.6, 6.9)
    jx1, jy1 = mm(14.8, 0.3)
    gradient_rect(ax, jx0, jy0, jx1 - jx0, jy1 - jy0, 0.5, "#4a4a4f", "#1f1f22", z=3, ec="#111", lw=0.8)
    for sx in (0.22, 0.58):
        ax.add_patch(Rectangle((jx0 + (jx1 - jx0) * sx, jy0 + 1.2), (jx1 - jx0) * 0.2, (jy1 - jy0) * 0.45,
                               fc="#0e0e10", ec="none", zorder=3.1))
    # STEMMA QT
    sx0, sy0 = mm(7.8, 13.0)
    sx1, sy1 = mm(13.3, 8.6)
    gradient_rect(ax, sx0, sy0, sx1 - sx0, sy1 - sy0, 0.4, "#fbf3df", "#d9cba8", z=3, ec="#a89466", lw=0.8)
    ax.add_patch(Rectangle((sx0 + 1.0, sy0 + 1.4), sx1 - sx0 - 2.0, sy1 - sy0 - 2.8, fc="#efe2c0",
                           ec="#b8a77c", lw=0.6, zorder=3.1))
    # Rst / Boot buttons
    for bx, name in ((7.9, "Rst"), (12.2, "Boot")):
        b0x, b0y = mm(bx, 18.6)
        b1x, b1y = mm(bx + 2.7, 14.0)
        gradient_rect(ax, b0x, b0y, b1x - b0x, b1y - b0y, 0.4, "#eceff2", "#9aa1a9", z=3, ec="#646b73", lw=0.8)
        ax.add_patch(Circle(((b0x + b1x) / 2, (b0y + b1y) / 2), 1.3, fc="#55595f", ec="#2e3134", lw=0.8, zorder=3.2))
        ax.text((b0x + b1x) / 2, b0y - 0.25, name, ha="center", va="top", fontsize=8.5, color="white",
                fontweight="bold", zorder=3.3)
    # status LEDs
    cx, cy = mm(1.6, 16.6)
    ax.add_patch(Rectangle((cx, cy), 1.4, 0.9, fc="#ffb347", ec="#a8661a", lw=0.5, zorder=3))
    ax.text(cx + 1.9, cy + 0.45, "CHG", fontsize=6.5, color="white", va="center", zorder=3)
    nx, ny = mm(4.4, 6.3)
    ax.add_patch(Rectangle((nx, ny), 2.0, 2.0, fc="#f7f7f7", ec="#999", lw=0.5, zorder=3))
    ax.add_patch(Circle((nx + 1.0, ny + 1.0), 0.45, fc="#b0b8ff", ec="none", zorder=3.1))

    draw_display(ax)

    tx, ty = mm(48.9, 11.4)
    ax.text(tx, ty, "Feather TFT\nESP32-S2", rotation=90, ha="center", va="center", fontsize=10.5,
            color="white", fontweight="bold", linespacing=1.0, zorder=3)

    # header pads + outside labels (as printed on the board)
    for i, name in enumerate(BOTTOM_PINS):
        x, y = pin_xy("bottom", i)
        _pad(ax, x, y, highlight=USED.get(i, (None, None, None))[1])
        if i not in USED:
            ax.text(x, BY - 0.6, name, rotation=90, ha="center", va="top", fontsize=8.5, color="#59606a")
    for j, name in enumerate(TOP_PINS):
        x, y = pin_xy("top", j)
        _pad(ax, x, y)
        ax.text(x, BY + h + 0.6, name, rotation=90, ha="center", va="bottom", fontsize=8.5, color="#59606a")


def _pad(ax, x, y, highlight=None):
    if highlight:
        for r, a in ((2.6, 0.18), (2.1, 0.3)):
            ax.add_patch(Circle((x, y), r, fc=highlight, ec="none", alpha=a, zorder=2.7))
    ax.add_patch(Circle((x, y), 0.85 * K, fc="#e2b04f", ec="#9c7020", lw=0.9, zorder=2.8))
    ax.add_patch(Circle((x, y), 0.5 * K, fc="#2a1d10", ec="none", zorder=2.9))


# ---------------------------------------------------------------- off-board parts
LEG_PITCH = PITCH_MM * K
BODY_LEG_PITCH = 1.27 * K                  # TO-92 leads exit the body at 1.27 mm and are bent apart
LEG_BEND = (1.2, 3.2)                      # bend start/end below the body
PINS_L2R = ("GND", "DQ", "VDD")            # front (flat) view, legs pointing down
PIN_COLOR = {"GND": BLACK, "DQ": YELLOW, "VDD": RED}
PIN_TEXT = {"GND": BLACK, "DQ": AMBER, "VDD": RED}


def to92(ax, cx, cy, legs="down", z=6.4, leg_len=11.0, sleeve=(6.0, 12.5)):
    """Bare DS18B20 seen on its flat side; each leg has a heat-shrink sleeve.

    Returns {pin: [wire start inside sleeve, sleeve exit, guide point]} in drawing units.
    """
    rot = Affine2D().rotate_deg_around(cx, cy, {"down": 0, "up": 180, "left": -90}[legs])
    half = 4.15
    base = cy - half
    for i in range(4):
        g = i * 0.3
        ax.add_patch(rbox(cx - half - g, cy - half - g, 2 * (half + g), 2 * (half + g), 0.9 + g, fc="black",
                          ec="none", alpha=0.06, zorder=z - 0.1,
                          transform=rot + Affine2D().translate(0.6, -0.8) + ax.transData))
    (ldx, ldy), lrot = {"down": ((1.9, 0.0), 90), "up": ((1.9, 0.0), 90), "left": ((0.0, 1.35), 0)}[legs]
    pts = {}
    for k, name in enumerate(PINS_L2R):
        lx = cx + (k - 1) * LEG_PITCH
        lx0 = cx + (k - 1) * BODY_LEG_PITCH
        col = PIN_COLOR[name]
        leg = rot.transform([(lx0, base + 0.5), (lx0, base - LEG_BEND[0]), (lx, base - LEG_BEND[1]),
                             (lx, base - leg_len)])
        ax.plot(leg[:, 0], leg[:, 1], color="#b9c0c8", lw=3.2, solid_capstyle="round", solid_joinstyle="round",
                zorder=z, path_effects=[pe.Stroke(linewidth=4.6, foreground="#6b737c"), pe.Normal()])
        s0, s1 = rot.transform([(lx, base - sleeve[0]), (lx, base - sleeve[1])])
        ax.plot(*zip(s0, s1), color=col, lw=15, solid_capstyle="butt", zorder=z + 0.1,
                path_effects=[pe.Stroke(linewidth=17, foreground=shade(col, 0.45)), pe.Normal()])
        ax.plot(*zip(s0, s1), color=shade(col, 1.6), lw=3, alpha=0.45, solid_capstyle="butt", zorder=z + 0.11)
        start, exit_, guide = rot.transform([(lx, base - leg_len + 1.2), (lx, base - sleeve[1] + 0.3),
                                             (lx, base - sleeve[1] - 2.5)])
        pts[name] = [tuple(start), tuple(exit_), tuple(guide)]
        mid = rot.transform([(lx, base - (LEG_BEND[1] + sleeve[0]) / 2)])[0]
        ax.text(mid[0] + ldx, mid[1] + ldy, name, rotation=lrot, ha="center", va="center", fontsize=7.5,
                fontweight="bold", color=PIN_TEXT[name], zorder=z + 0.2)
    tr = rot + ax.transData
    ax.add_patch(rbox(cx - half, cy - half, 2 * half, 2 * half, 0.9, fc="#26262b", ec="#09090b", lw=1.1,
                      zorder=z + 0.3, transform=tr))
    ax.add_patch(Rectangle((cx - half + 0.7, cy + half - 1.7), 2 * half - 1.4, 0.8, fc="white", alpha=0.10,
                           ec="none", zorder=z + 0.31, transform=tr))
    ax.text(cx, cy, "DS18B20", ha="center", va="center", fontsize=7.5, color="#d7d7dc", fontweight="bold",
            zorder=z + 0.4)
    return pts


def splice(ax, x, y, z=8.0):
    """Soldered joint inside a (semi-transparent) heat-shrink tube."""
    ax.add_patch(Ellipse((x, y), 2.6, 3.8, fc="#d3d8dd", ec="#7f8790", lw=0.9, zorder=z))
    ax.add_patch(Ellipse((x - 0.4, y + 0.6), 0.9, 1.4, fc="white", ec="none", alpha=0.7, zorder=z + 0.01))
    ax.add_patch(rbox(x - 2.3, y - 4.6, 4.6, 9.2, 2.0, fc="#1f2328", ec="#0d0f12", lw=1.0, alpha=0.55,
                      zorder=z + 0.1))
    ax.plot([x - 1.2, x - 1.2], [y - 3.2, y + 3.2], color="white", lw=1.6, alpha=0.35, solid_capstyle="round",
            zorder=z + 0.11)


def resistor(ax, x0, x1, y, z=8.2):
    ax.plot([x0, x1], [y, y], color="#aab1b9", lw=2.6, solid_capstyle="round", zorder=z,
            path_effects=[pe.Stroke(linewidth=3.8, foreground="#6b737c"), pe.Normal()])
    mid = (x0 + x1) / 2
    bx0, bw, bh = mid - 3.8, 7.6, 2.8
    gradient_rect(ax, bx0, y - bh / 2, bw, bh, 1.3, "#f6e2bb", "#c9a56d", z=z + 0.1, ec="#8c6a3a", lw=0.9)
    for off, col in ((1.4, YELLOW), (2.6, "#7b3fb5"), (3.8, RED), (6.1, "#c9a24a")):
        ax.add_patch(Rectangle((bx0 + off - 0.35, y - bh / 2 + 0.12), 0.7, bh - 0.24, fc=col, ec="none",
                               zorder=z + 0.2))
    # clear heat-shrink over the whole resistor
    ax.add_patch(rbox(mid - 12.5, y - 2.1, 25.0, 4.2, 1.6, fc="#cfe3f5", ec="#7fa6c9", lw=0.9, alpha=0.35,
                      zorder=z + 0.3))


# ---------------------------------------------------------------- panels
def panel(ax, x, y, w, h, title):
    soft_shadow(ax, x, y, w, h, 1.6, z=0.5, layers=6, alpha=0.035)
    ax.add_patch(rbox(x, y, w, h, 1.6, fc="white", ec="#d3d9e0", lw=1.2, zorder=0.6))
    ax.text(x + 2.5, y + h - 2.3, title, fontsize=15, fontweight="bold", color="#1f2a37", va="top", zorder=1)


def draw_pinout_panel(ax):
    x, y, w, h = 112, 78, 95, 44
    panel(ax, x, y, w, h, "DS18B20 pinout (TO-92 package)")
    ax.text(x + 3, y + h - 8.2, "Front view", fontsize=11, fontweight="bold", color="#334155", va="top")
    ax.text(x + 3, y + h - 11.0, "flat side with text facing you,\nlegs pointing down", fontsize=9,
            color="#64748b", va="top", linespacing=1.15)
    bx, by, bw, bh = x + 7, y + 13.5, 13.0, 12.0
    leg_x = [bx + bw / 2 - 4.1, bx + bw / 2, bx + bw / 2 + 4.1]
    for lx in leg_x:
        ax.plot([lx, lx], [by + 0.5, y + 7.2], color="#aeb5bd", lw=3.0, solid_capstyle="round", zorder=2,
                path_effects=[pe.Stroke(linewidth=4.2, foreground="#6b737c"), pe.Normal()])
    soft_shadow(ax, bx, by, bw, bh, 1.0, z=2.2, layers=4)
    gradient_rect(ax, bx, by, bw, bh, 1.0, "#3a3a40", "#121214", z=2.3, ec="#000", lw=0.9)
    ax.text(bx + bw / 2, by + bh / 2, "DS18B20", ha="center", va="center", fontsize=8.5, color="#d7d7dc",
            fontweight="bold", zorder=2.5)
    for lx, (num, name, col) in zip(leg_x, [("1", "GND", BLACK), ("2", "DQ", AMBER), ("3", "VDD", RED)]):
        ax.text(lx, y + 6.4, f"{num}\n{name}", ha="center", va="top", fontsize=10, fontweight="bold",
                color=col, linespacing=1.0)

    # soldered and insulated close-up
    px = x + 44
    ax.text(px, y + h - 8.2, "Soldered and insulated", fontsize=11, fontweight="bold", color="#334155", va="top")
    ax.text(px, y + h - 11.0, "wire soldered to each leg,\nheat-shrink over every joint", fontsize=9,
            color="#64748b", va="top", linespacing=1.15)
    cx, cy = x + 58, y + 21
    leads = to92(ax, cx, cy, legs="down", z=2.0, leg_len=9.0, sleeve=(5.0, 10.5))
    for name, pts in leads.items():
        wire(ax, pts + [(pts[-1][0], y + 3.0)], PIN_COLOR[name], lw=6.5, z=1.9)
    sx = cx + LEG_PITCH + 1.6
    ax.annotate("heat-shrink\non each leg", xy=(sx, cy - 4.15 - 7.75), xytext=(sx + 6.0, cy - 4.15 - 4.5),
                fontsize=9, color="#334155", va="center",
                arrowprops=dict(arrowstyle="->", color="#64748b", lw=1.2))
    ax.text(sx + 6.0, y + 5.5, "wires go to\nthe 3 splices", fontsize=9, color="#334155", va="center")


def draw_table_panel(ax):
    x, y, w, h = 112, 44, 95, 31
    panel(ax, x, y, w, h, "Connection table")
    ax.text(x + 2.5, y + h - 6.6, "Each row is one soldered splice: all wires in a row are soldered together.",
            fontsize=9.5, color="#64748b", va="top")
    cols = [("Feather pin", 17), ("Sensor 1", 23), ("Sensor 2", 23), ("4.7 kΩ resistor", 27)]
    rows = [(("3V", RED), "VDD  pin 3", "VDD  pin 3", "one leg"),
            (("A0", YELLOW), "DQ  pin 2", "DQ  pin 2", "other leg"),
            (("GND", BLACK), "GND  pin 1", "GND  pin 1", "-")]
    tx, ty, rh = x + 2.5, y + h - 11.2, 4.6
    cx = tx
    for name, cw in cols:
        ax.add_patch(Rectangle((cx, ty - rh), cw, rh, fc="#eef2f7", ec="#cbd5e1", lw=0.8, zorder=1))
        ax.text(cx + 1.2, ty - rh / 2, name, fontsize=10.5, fontweight="bold", color="#1f2a37", va="center", zorder=2)
        cx += cw
    for r, row in enumerate(rows):
        ry = ty - rh * (r + 1)
        cx = tx
        for c, (_, cw) in enumerate(cols):
            ax.add_patch(Rectangle((cx, ry - rh), cw, rh, fc="white", ec="#cbd5e1", lw=0.8, zorder=1))
            if c == 0:
                (pin, col) = row[0]
                chip(ax, cx + 4.5, ry - rh / 2, pin, col, "black" if col == YELLOW else "white", z=2, fs=10)
            else:
                ax.text(cx + 1.2, ry - rh / 2, row[c], fontsize=10.5, color="#1f2a37", va="center", zorder=2)
            cx += cw


def draw_notes_panel(ax):
    x, y, w, h = 112, 3, 95, 38
    panel(ax, x, y, w, h, "Good to know")
    notes = [
        "Unplug the USB cable while you are wiring.",
        "Use a pin printed 3V (either of the two). Never use USB or BAT:\n"
        "those carry 5 V / battery voltage and can damage the sensors.",
        "Slide heat-shrink onto the wire BEFORE soldering: one piece per sensor\n"
        "leg, one per splice, one over the resistor. Shrink it after soldering.",
        "Only ONE 4.7 kΩ resistor for both sensors (yellow-violet-red-gold),\n"
        "soldered into the 3.3 V splice and the DATA splice.",
        "Check the flat side! VDD and GND swapped = sensor gets hot within\n"
        "seconds. Unplug immediately if that happens.",
        "Flash mode: hold Boot, tap Rst, then release Boot.",
    ]
    ty = y + h - 7.5
    for n in notes:
        ax.text(x + 3.0, ty, "•", fontsize=12, color="#475569", va="top", fontweight="bold")
        ax.text(x + 5.5, ty, n, fontsize=10.2, color="#1f2a37", va="top", linespacing=1.2)
        ty -= 1.5 + 2.1 * (n.count("\n") + 1)


# ---------------------------------------------------------------- main
def main():
    fig = plt.figure(figsize=(W / 10, H / 10), dpi=110)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.set_autoscale_on(False)
    ax.axis("off")
    bg = np.linspace(0, 1, 256)[:, None]
    ramp = np.array(to_rgb("#f3f6f9")) * (1 - bg) + np.array(to_rgb("#e3e9ef")) * bg
    ax.imshow(ramp[:, None, :], extent=(0, W, 0, H), origin="upper", aspect="auto", zorder=-10)

    ax.text(4, H - 2.2, "Wiring: 2 × DS18B20 temperature sensors  →  Adafruit ESP32-S2 TFT Feather",
            fontsize=21, fontweight="bold", color="#0f172a", va="top")
    ax.text(4, H - 6.6, "Wire colours:  red = 3.3 V   ·   black = GND   ·   yellow = DATA (pin A0 = GPIO18)   ·   "
            "4.7 kΩ pull-up resistor between 3.3 V and DATA", fontsize=12, color="#475569", va="top")

    draw_board(ax)

    # USB-C cable to laptop
    ux, uy = mm(-1.3, 11.25)
    gradient_rect(ax, ux - 7.2, uy - 3.3, 7.6, 6.6, 1.2, "#5c6168", "#2a2d31", z=4, ec="#1a1c1f", lw=0.9)
    xy = smooth([(ux - 7.0, uy), (4.5, uy - 4), (3.8, 72), (3.8, 60)])
    ax.plot(xy[:, 0], xy[:, 1], color="#2a2d31", lw=11, solid_capstyle="round", zorder=3.9,
            path_effects=[pe.Stroke(linewidth=13, foreground="#0e0f11"), pe.Normal()])
    ax.text(6.8, 61.5, "USB-C cable\nto laptop", fontsize=9.5, color="#475569", va="bottom", ha="left")

    # soldered splices (one per signal), resistor between the 3.3 V and DATA splices
    jy = 47.0
    sx = {"3V": 29.0, "DATA": 59.0, "GND": 89.0}
    resistor(ax, sx["3V"] + 0.6, sx["DATA"] - 0.6, jy)
    ax.text(44.0, jy + 2.4, "4.7 kΩ", ha="center", va="bottom", fontsize=11, fontweight="bold", color="#5b4a2a")
    for key, label, col, ha, dx in (("3V", "3.3 V", RED, "right", -3.0), ("DATA", "DATA", AMBER, "left", 3.0),
                                    ("GND", "GND", BLACK, "left", 3.0)):
        ax.text(sx[key] + dx, jy, label, ha=ha, va="center", fontsize=13, fontweight="bold", color=col, zorder=9)
    ax.annotate("soldered splice,\ncovered with\nheat-shrink", xy=(91.4, 44.0), xytext=(95.5, 37.5), fontsize=9,
                color="#334155", va="top", arrowprops=dict(arrowstyle="->", color="#64748b", lw=1.2))

    # board -> splices
    p3v = pin_xy("bottom", 1)
    pgnd = pin_xy("bottom", 3)
    pa0 = pin_xy("bottom", 4)
    top_in = jy + 3.6
    wire(ax, [p3v, (p3v[0], 66), (29.0, 58), (29.0, 54.0), (29.0, top_in)], RED,
         port=(29.0, jy + 0.6), start_blob=True)
    wire(ax, [pa0, (pa0[0], 61.5), (45.5, 57.6), (54.0, 57.0), (59.0, 55.0), (59.0, top_in)], YELLOW,
         port=(59.0, jy + 0.6), start_blob=True)
    wire(ax, [pgnd, (pgnd[0], 63.5), (41.5, 60.2), (62.0, 60.0), (84.0, 59.0), (89.0, 55.5), (89.0, top_in)],
         BLACK, z=6.2, port=(89.0, jy + 0.6), start_blob=True)
    chip(ax, p3v[0], 64.6, "3V", RED, "white")
    chip(ax, pgnd[0], 66.2, "GND", BLACK, "white")
    chip(ax, pa0[0], 65.0, "A0", YELLOW, "black")

    # sensors: bare DS18B20 (TO-92), heat-shrink on every leg
    s1 = to92(ax, 46.0, 15.0, legs="up")
    ax.text(40.0, 16.4, "Sensor 1", ha="right", fontsize=12.5, fontweight="bold", color="#0f172a", va="bottom")
    ax.text(40.0, 16.1, "(DS18B20)", ha="right", fontsize=9, color="#64748b", va="top")
    s2 = to92(ax, 103.0, 11.0, legs="left")
    ax.text(93.0, 18.6, "Sensor 2", fontsize=12.5, fontweight="bold", color="#0f172a", va="bottom")
    ax.text(103.4, 18.85, "(DS18B20)", fontsize=9, color="#64748b", va="bottom")

    bot_in = jy - 3.8
    def into(xp, side):
        return [(xp, bot_in - 3.3), (xp, bot_in)], (xp + 0.5 * side, jy - 0.6)

    for name, x_in, side, route in (
            ("VDD", 29.9, -1, [(36.0, 37.4)]),
            ("DQ", 58.1, 1, [(52.0, 37.4)]),
            ("GND", 88.1, 1, [(60.0, 35.6), (78.0, 36.2)])):
        tail, port = into(x_in, side)
        wire(ax, s1[name] + route + tail, PIN_COLOR[name], z=6.0 if name != "GND" else 6.1, port=port)
    for name, x_in, side, route in (
            ("VDD", 28.1, 1, [(60.0, 6.0), (20.0, 6.0), (12.0, 10.0), (11.0, 26.0), (17.0, 35.0)]),
            ("DQ", 59.9, -1, [(70.0, 11.2), (62.5, 15.0), (60.2, 26.0)]),
            ("GND", 89.9, -1, [(82.5, 19.0), (85.0, 30.0)])):
        tail, port = into(x_in, side)
        wire(ax, s2[name] + route + tail, PIN_COLOR[name], z=5.8, port=port)

    for x in sx.values():
        splice(ax, x, jy)

    draw_pinout_panel(ax)
    draw_table_panel(ax)
    draw_notes_panel(ax)

    ax.text(4, 1.2, "Board layout and pin names: Adafruit ESP32-S2 TFT Feather (product 5300; same pins as the S3 version 5483). "
            "Illustration, not to scale for wires.", fontsize=8.5, color="#94a3b8", va="bottom")

    fig.savefig(OUT, dpi=110)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
