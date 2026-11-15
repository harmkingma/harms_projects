"""Wall-mounted presence + room-temperature sensor box (FreeCAD, Part workbench).

Electronics: ESP32-C3 SuperMini Plus, Hi-Link HLK-LD1125H-24G radar, DS18B20 (TO-92).
Run inside FreeCAD:  exec(open(r"c:/github/espcam/hardware/presence_box.py").read())
Creates document "PresenceBox" and exports STL + STEP next to this file.

Coordinates: base floor on the wall (z = 0), lid faces the room (+z), +y = UP on the wall.
Layout (front view):
    +--------------------------------+  <- exhaust slots (top wall)
    |  LD1125H radar   |   ESP32-C3   |     ESP antenna end up
    |  (antenna->lid)  |  USB-C down  |
    |                  |  USB plug in |
    |                  |  cradle      |
    | [double wall]    |   cable      |
    |  DS18B20 chamber |      |       |  <- intake slots (right wall)
    +--------------------------------+
         chamber vents      cable exit (bottom)
Heat from the ESP/radar rises away from the sensor chamber, which is isolated by two walls
with an air gap and has its own vents (bottom wall, left wall, lid).
The radar sees the room through a thin 1.2 mm lid window, half a wavelength (6.2 mm at 24 GHz)
above the antenna. Print in PLA/PETG/ASA; no carbon-fibre or metal-filled filament (radar/WiFi).

Parts:
  Base - floor on the bed, no supports.
  Lid  - exported outer face down; four snap tabs click into grooves in the side walls,
         pry open at the notches in the left/right rim.
"""
import math
import os

import FreeCAD as App
import Part

V = App.Vector

# --- Components (nominal datasheet sizes - measure yours and adjust) ---------------
ESP_W, ESP_L, ESP_PCB_T = 18.0, 22.52, 1.0
USB_ABOVE_PCB = 1.6        # USB-C receptacle axis above the PCB top (3.2 mm top-mount)
USB_OVERHANG = 0.8         # receptacle front beyond the PCB edge
RADAR_W, RADAR_L, RADAR_PCB_T = 16.0, 31.0, 1.0
RADAR_BACK_H = 2.0         # component height on the radar back side (check only)
PLUG_W, PLUG_T, PLUG_L = 12.5, 7.0, 38.0   # USB-C plug overmold incl. boot, excl. metal tongue
CABLE_D = 4.0              # braided cable
TO92_W, TO92_L, TO92_T = 4.8, 4.6, 3.7

# --- Box -----------------------------------------------------------------------------
WALL = 2.0
FLOOR = 2.0
LID_T = 2.0
WINDOW_T = 1.2             # lid thickness over the radar antenna
RADAR_GAP = 6.2            # antenna face -> window inner face (lambda/2 at 24 GHz)
CLEAR = 0.3                # board <-> pocket, per side
MARGIN = 2.5               # pocket <-> inner wall (room for the lid snap tabs)
COL_GAP = 7.0              # radar <-> ESP pocket (wiring + RF separation)
L_IN_MIN = 64.0            # interior height (wall up/down); grows for long plugs
CABLE_IN = 8.0             # straight cable between plug end and exit slot
R_OUT = 3.0
ESP_STANDOFF = 2.5         # central pedestal; pin rows stay free for solder joints
RADAR_STANDOFF = 3.5       # corner posts; back-side parts hang free
LIP_H = 1.2                # locating lips above the PCB underside
CH_W, CH_L = 22.0, 14.0    # DS18B20 chamber interior
DIV_T, DIV_GAP = 1.2, 2.0  # double divider wall with closed air gap
SENSOR_XY = (11.0, 6.0)
WIRE_NOTCH_X = (12.0, 15.0)
SLOT_W, SLOT_PITCH = 1.6, 3.2

# Snap fit (lid tabs into grooves on the inner side walls)
SNAP_CLEAR = 0.2
SNAP_T = 1.2
SNAP_LEN = 6.0
SNAP_BUMP = 0.65           # engages SNAP_BUMP - SNAP_CLEAR = 0.45 mm
GROOVE_D = 0.6
SNAP_Y = ((20.0, 28.0), (40.0, 54.0))
LOCATOR_X = (20.5, 24.5)   # lid rib against the top wall

# Wall mounting tabs (countersunk 3-3.5 mm wood screws + wall plugs)
TAB_T = 3.0
TAB_R = 6.0
TAB_HOLE_D = 3.8
CSK_D = 7.2

out_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"c:/github/espcam/hardware"

# --- Derived layout ---------------------------------------------------------------------
esp_pw, esp_pl = ESP_W + 2 * CLEAR, ESP_L + 2 * CLEAR
rad_pw, rad_pl = RADAR_W + 2 * CLEAR, RADAR_L + 2 * CLEAR
W_IN = MARGIN + rad_pw + COL_GAP + esp_pw + MARGIN
L_IN = max(L_IN_MIN, MARGIN + esp_pl - CLEAR + USB_OVERHANG + PLUG_L + CABLE_IN)

rad_x0, rad_y0 = MARGIN, L_IN - MARGIN - rad_pl
esp_x0, esp_y0 = W_IN - MARGIN - esp_pw, L_IN - MARGIN - esp_pl
esp_cx, esp_cy = esp_x0 + esp_pw / 2, esp_y0 + esp_pl / 2

z_esp_pcb = FLOOR + ESP_STANDOFF
z_usb = z_esp_pcb + ESP_PCB_T + USB_ABOVE_PCB
z_rad_pcb = FLOOR + RADAR_STANDOFF
z_antenna = z_rad_pcb + RADAR_PCB_T
RIM = z_antenna + RADAR_GAP - (LID_T - WINDOW_T)
TOP = RIM + LID_T

plug_y1 = esp_y0 + CLEAR - USB_OVERHANG
plug_y0 = plug_y1 - PLUG_L
div_out_x = CH_W + 2 * DIV_T + DIV_GAP       # outer face of the double wall
div_out_y = CH_L + 2 * DIV_T + DIV_GAP
cable_w = CABLE_D + 0.4

assert plug_y0 - CABLE_D > 0, "USB plug too long for L_IN"
assert esp_cx - PLUG_W / 2 - 2.0 > div_out_x, "plug collides with the sensor chamber"
assert z_usb + PLUG_T / 2 < RIM, "plug too thick for the box depth"


def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def rbox(x0, y0, z0, x1, y1, z1, r):
    b = box(x0, y0, z0, x1, y1, z1)
    vertical = [e for e in b.Edges if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1e-6]
    return b.makeFillet(r, vertical) if r > 0 else b


def corner_lips(x0, y0, w, l, z1, leg=3.0, t=0.8):
    """L-shaped locating lips just outside the corners of a pocket."""
    parts = []
    for cx, sx in ((x0, 1), (x0 + w, -1)):
        for cy, sy in ((y0, 1), (y0 + l, -1)):
            xo, yo = cx - sx * t, cy - sy * t
            parts.append(box(min(xo, xo + sx * (leg + t)), min(yo, cy), FLOOR - 0.01,
                             max(xo, xo + sx * (leg + t)), max(yo, cy), z1))
            parts.append(box(min(xo, cx), min(yo, yo + sy * (leg + t)), FLOOR - 0.01,
                             max(xo, cx), max(yo, yo + sy * (leg + t)), z1))
    return parts


def bump(face_x, direction, y0, y1, z0):
    """Snap bump on a tab face: gentle lead-in below, steeper retention face above."""
    pts = [(-0.1, z0), (SNAP_BUMP, z0 + 1.2), (SNAP_BUMP, z0 + 1.6), (-0.1, z0 + 2.0)]
    poly = Part.makePolygon([V(face_x + direction * d, y0, z) for d, z in pts + pts[:1]])
    return Part.Face(poly).extrude(V(0, y1 - y0, 0))


def slots_x(x_from, x_to, y0, y1, z0, z1, skip=None):
    out, x = [], x_from
    while x + SLOT_W <= x_to:
        if not (skip and x + SLOT_W > skip[0] - 0.5 and x < skip[1] + 0.5):
            out.append(box(x, y0, z0, x + SLOT_W, y1, z1))
        x += SLOT_PITCH
    return out


def slots_y(y_from, y_to, x0, x1, z0, z1):
    out, y = [], y_from
    while y + SLOT_W <= y_to:
        out.append(box(x0, y, z0, x1, y + SLOT_W, z1))
        y += SLOT_PITCH
    return out


def fuse_all(base_shape, parts):
    return base_shape.fuse(parts) if parts else base_shape


# --- Base -----------------------------------------------------------------------------
base = rbox(-WALL, -WALL, 0, W_IN + WALL, L_IN + WALL, RIM, R_OUT).cut(
    rbox(0, 0, FLOOR, W_IN, L_IN, RIM + 1, R_OUT - WALL))

adds = []
# Sensor chamber: inner + outer wall, closed air gap between them.
adds += [box(CH_W, -0.01, FLOOR - 0.01, CH_W + DIV_T, CH_L + DIV_T, RIM),
         box(-0.01, CH_L, FLOOR - 0.01, CH_W + DIV_T, CH_L + DIV_T, RIM),
         box(div_out_x - DIV_T, -0.01, FLOOR - 0.01, div_out_x, div_out_y, RIM),
         box(-0.01, div_out_y - DIV_T, FLOOR - 0.01, div_out_x, div_out_y, RIM)]
# DS18B20 saddle: body rests in a groove, free air all around.
sx, sy = SENSOR_XY
saddle_top = FLOOR + 3.0
adds.append(box(sx - 3, sy - 1, FLOOR - 0.01, sx + 3, sy + 1, saddle_top).cut(
    box(sx - TO92_W / 2 - 0.2, sy - 2, saddle_top - 1.0, sx + TO92_W / 2 + 0.2, sy + 2, saddle_top + 1)))
# Radar: corner posts + lips.
for cx, cy in ((rad_x0, rad_y0), (rad_x0 + rad_pw - 3.3, rad_y0), (rad_x0, rad_y0 + rad_pl - 3.3),
               (rad_x0 + rad_pw - 3.3, rad_y0 + rad_pl - 3.3)):
    adds.append(box(cx, cy, FLOOR - 0.01, cx + 3.3, cy + 3.3, z_rad_pcb))
adds += corner_lips(rad_x0, rad_y0, rad_pw, rad_pl, z_rad_pcb + LIP_H)
# ESP: central pedestal (pin rows free) + corner lips.
adds.append(box(esp_cx - 5, esp_cy - 7, FLOOR - 0.01, esp_cx + 5, esp_cy + 7, z_esp_pcb))
adds += corner_lips(esp_x0, esp_y0, esp_pw, esp_pl, z_esp_pcb + 0.8, leg=1.5)
# USB plug cradle (U-channel, plug glued in).
cw = PLUG_W + 0.8
cr_y0 = max(plug_y0 + 3.0, div_out_y + 1.0)
adds.append(box(esp_cx - cw / 2 - 1.6, cr_y0, FLOOR - 0.01, esp_cx + cw / 2 + 1.6, plug_y1 - 4.0, z_usb).cut(
    box(esp_cx - cw / 2, cr_y0 - 1, z_usb - PLUG_T / 2 - 0.2, esp_cx + cw / 2, plug_y1, z_usb + 1)))
# Wall mounting tabs, top and bottom centre.
tab_holes = []
for y_face, d in ((L_IN + WALL, 1), (-WALL, -1)):
    hx, hy = W_IN / 2, y_face + d * TAB_R
    adds.append(box(hx - TAB_R, min(y_face - d, hy), 0, hx + TAB_R, max(y_face - d, hy), TAB_T))
    adds.append(Part.makeCylinder(TAB_R, TAB_T, V(hx, hy, 0)))
    csk_h = (CSK_D - TAB_HOLE_D) / 2
    tab_holes += [Part.makeCylinder(TAB_HOLE_D / 2, TAB_T + 2, V(hx, hy, -1)),
                  Part.makeCone(TAB_HOLE_D / 2, CSK_D / 2, csk_h, V(hx, hy, TAB_T - csk_h)),
                  Part.makeCylinder(CSK_D / 2, 1, V(hx, hy, TAB_T - 0.001))]
base = fuse_all(base, adds)

cuts = list(tab_holes)
# Wire pass-through to the chamber (seal with hot glue after wiring).
cuts.append(box(WIRE_NOTCH_X[0], CH_L - 0.1, FLOOR + 2.0, WIRE_NOTCH_X[1], div_out_y + 0.1, RIM + 1))
# Cable exit: U-slot open to the rim, lid tongue clamps the cable.
cuts.append(box(esp_cx - cable_w / 2, -WALL - 1, z_usb, esp_cx + cable_w / 2, 0.5, RIM + 1))
cuts.append(Part.makeCylinder(cable_w / 2, WALL + 1.5, V(esp_cx, -WALL - 1, z_usb), V(0, 1, 0)))
# Vents: chamber (bottom + left wall), main intake (right wall), exhaust (top wall).
vz0, vz1 = FLOOR + 1.5, RIM - 1.5
cuts += slots_x(3.0, CH_W - 1.5, -WALL - 1, 1.0, vz0, vz1)
cuts += slots_y(2.5, CH_L - 1.5, -WALL - 1, 1.0, vz0, vz1)
cuts += slots_y(3.0, SNAP_Y[0][0] - 1.5, W_IN - 1, W_IN + WALL + 1, vz0, vz1)
cuts += slots_x(4.0, W_IN - 4.0, L_IN - 1, L_IN + WALL + 1, FLOOR + 2.5, vz1, skip=LOCATOR_X)
# Snap grooves and pry notches.
g_z0, g_z1 = RIM - SNAP_LEN, RIM - SNAP_LEN + 2.2
for y0, y1 in SNAP_Y:
    cuts.append(box(-GROOVE_D, y0 - 0.5, g_z0, 0.1, y1 + 0.5, g_z1))
    cuts.append(box(W_IN - 0.1, y0 - 0.5, g_z0, W_IN + GROOVE_D, y1 + 0.5, g_z1))
pry_y = (SNAP_Y[1][0] + SNAP_Y[1][1]) / 2
cuts.append(box(-WALL - 1, pry_y - 3, RIM - 1.0, -WALL + 0.8, pry_y + 3, RIM + 1))
cuts.append(box(W_IN + WALL - 0.8, pry_y - 3, RIM - 1.0, W_IN + WALL + 1, pry_y + 3, RIM + 1))
base = base.cut(cuts).removeSplitter()

# --- Lid ------------------------------------------------------------------------------
lid = rbox(-WALL, -WALL, RIM, W_IN + WALL, L_IN + WALL, TOP, R_OUT)
ladds = []
for y0, y1 in SNAP_Y:
    for face_x, d in ((SNAP_CLEAR, -1), (W_IN - SNAP_CLEAR, 1)):
        inner_x = face_x - d * SNAP_T
        ladds.append(box(min(face_x, inner_x), y0, RIM - SNAP_LEN, max(face_x, inner_x), y1, RIM + 0.5))
        ladds.append(bump(face_x, d, y0, y1, RIM - SNAP_LEN + 0.2))
ladds.append(box(LOCATOR_X[0], L_IN - SNAP_CLEAR - SNAP_T, RIM - 3.0, LOCATOR_X[1], L_IN - SNAP_CLEAR, RIM + 0.5))
ladds.append(box(esp_cx - cable_w / 2 + 0.15, -WALL, z_usb + CABLE_D / 2 - 0.3,
                 esp_cx + cable_w / 2 - 0.15, 0, RIM + 0.5))
lid = fuse_all(lid, ladds)
lcuts = [box(rad_x0, rad_y0, RIM - 1, rad_x0 + rad_pw, rad_y0 + rad_pl, TOP - WINDOW_T)]
lcuts += slots_x(3.0, CH_W - 2.0, 3.0, CH_L - 3.0, RIM - 1, TOP + 1)
lid = lid.cut(lcuts).removeSplitter()

# --- Approximate component models (fit check only, not exported) ----------------------
pcb_x0, pcb_y0 = esp_x0 + CLEAR, esp_y0 + CLEAR
esp = [box(pcb_x0, pcb_y0, z_esp_pcb, pcb_x0 + ESP_W, pcb_y0 + ESP_L, z_esp_pcb + ESP_PCB_T),
       box(esp_cx - 4.5, pcb_y0 - USB_OVERHANG, z_esp_pcb + ESP_PCB_T, esp_cx + 4.5, pcb_y0 - USB_OVERHANG + 7.4,
           z_esp_pcb + ESP_PCB_T + 3.2),
       box(esp_cx - 6, pcb_y0 + 9, z_esp_pcb + ESP_PCB_T, esp_cx + 6, pcb_y0 + 21, z_esp_pcb + ESP_PCB_T + 1.8)]
rx0, ry0 = rad_x0 + CLEAR, rad_y0 + CLEAR
radar = [box(rx0, ry0, z_rad_pcb, rx0 + RADAR_W, ry0 + RADAR_L, z_antenna),
         box(rx0 + 3.5, ry0 + 3.5, z_rad_pcb - RADAR_BACK_H, rx0 + RADAR_W - 3.5, ry0 + RADAR_L - 3.5, z_rad_pcb)]
plug = [box(esp_cx - PLUG_W / 2, plug_y0, z_usb - PLUG_T / 2, esp_cx + PLUG_W / 2, plug_y1, z_usb + PLUG_T / 2)]
cable = Part.makeCylinder(CABLE_D / 2, plug_y0 + WALL + 8, V(esp_cx, plug_y0, z_usb), V(0, -1, 0))
sensor = box(sx - TO92_W / 2, sy - TO92_L / 2, saddle_top - 1.0, sx + TO92_W / 2, sy + TO92_L / 2,
             saddle_top - 1.0 + TO92_T)
parts = Part.makeCompound(esp + radar + plug + [sensor])

# --- Document + export -----------------------------------------------------------------
doc = App.getDocument("PresenceBox") if "PresenceBox" in App.listDocuments() else App.newDocument("PresenceBox")
for o in list(doc.Objects):
    doc.removeObject(o.Name)
objs = {}
for name, shape in (("Base", base), ("Lid", lid), ("Electronics", parts), ("UsbCable", cable)):
    objs[name] = doc.addObject("Part::Feature", name)
    objs[name].Shape = shape
doc.recompute()
if App.GuiUp:
    import FreeCADGui as Gui
    gd = Gui.getDocument(doc.Name)
    gd.getObject("Lid").Transparency = 70
    gd.getObject("Electronics").ShapeColor = (0.1, 0.5, 0.2)
    gd.getObject("UsbCable").ShapeColor = (0.1, 0.1, 0.1)

lid_print = lid.copy()
lid_print.rotate(V(0, 0, 0), V(1, 0, 0), 180)
lid_print.translate(V(0, 0, -lid_print.BoundBox.ZMin))
base.exportStl(os.path.join(out_dir, "presence_box_base.stl"))
lid_print.exportStl(os.path.join(out_dir, "presence_box_lid.stl"))
Part.export([objs["Base"], objs["Lid"]], os.path.join(out_dir, "presence_box.step"))
doc.saveAs(os.path.join(out_dir, "presence_box.FCStd"))

bb = base.BoundBox
print(f"outer box {W_IN + 2 * WALL:.1f} x {L_IN + 2 * WALL:.1f} x {TOP:.1f} mm (with tabs {bb.YLength:.1f} long)")
print(f"interior {W_IN:.1f} x {L_IN:.1f} x {RIM - FLOOR:.1f} mm; rim z={RIM:.2f}")
print(f"radar antenna z={z_antenna:.2f}, window inner z={TOP - WINDOW_T:.2f} (gap {TOP - WINDOW_T - z_antenna:.2f})")
print(f"USB axis z={z_usb:.2f}; plug y {plug_y0:.1f}..{plug_y1:.1f}; cable inside {plug_y0:.1f} mm")
print(f"sensor chamber {CH_W} x {CH_L}; radar bottom to chamber wall {rad_y0 - div_out_y:.1f} mm; "
      f"ESP to sensor {math.hypot(esp_cx - sx, esp_y0 - sy):.1f} mm")
print(f"base valid={base.isValid()} solids={len(base.Solids)} vol={base.Volume / 1000:.1f} cm3; "
      f"lid valid={lid.isValid()} solids={len(lid.Solids)} vol={lid.Volume / 1000:.1f} cm3")
print(f"interference base/lid={base.common(lid).Volume:.3f} mm3, parts/base={parts.common(base).Volume:.3f}, "
      f"parts/lid={parts.common(lid).Volume:.3f}, cable/base={cable.common(base).Volume:.3f}, "
      f"cable/lid (intended clamp)={cable.common(lid).Volume:.3f}")
