"""Parametric ESP32-CAM holder for the Siemens water meter (FreeCAD, Part workbench).

Run inside FreeCAD:  exec(open(r"c:/github/espcam/hardware/camera_holder.py").read())
Creates document "CameraHolder" with two parts and exports STL + STEP next to this file.

Parts (print without supports, PETG/ASA recommended for the humid pit):
  Shroud   - collar that slips over the meter ring + light-blocking cone; print collar down.
  Plate    - camera plate with ESP32-CAM pocket; drops into the shroud top, can be
             rotated to move the flash hotspot; print flat side down.
  TestRing - bottom of the shroud only, for a quick fit test on the meter ring.
ESP32CAM is an approximate board model for checking the fit; it is not exported to STL.
"""
import math
import os

import FreeCAD as App
import Part

# --- Meter / camera ---------------------------------------------------------------
METER_D = 83.1          # outer diameter of the meter ring the collar slips over
COLLAR_CLEAR = 0.5      # diametral clearance
LENS_DISTANCE = 150.0   # lens tip to top of meter ring
PCB_T = 1.6
LENS_FROM_PCB_BACK = 9.0  # measured: non-component side of the PCB to lens tip
SOLDER_STANDOFF = 1.0   # header solder joints the face-down PCB rests on

# --- Shroud -----------------------------------------------------------------------
WALL = 2.0
SLEEVE_H = 15.0         # collar sleeve height below the seating chamfer
LIP = 3.3               # 45 deg seating chamfer width (also its height)
TOP_OD = 68.4           # shroud outer diameter at the top
PLATE_D = 64.0
PLATE_T = 3.0
RECESS_CLEAR = 0.3      # diametral clearance plate <-> recess
LEDGE = 2.15            # ledge the plate rests on
HINGE_NOTCH_W = 30.0    # notch for the lid hinge (+Y side)
HINGE_NOTCH_H = 25.0
SCREW_HOLE_D = 2.5      # M3 self-tapping clamp screws
SCREW_ANGLES = (0, 180, 270)

# --- ESP32-CAM pocket (board face down, wires soldered to the header pins) ---------
PCB_W, PCB_L = 27.0, 40.5
PCB_CLEAR = 0.4
POCKET_WALL = 2.0
POCKET_H = 6.0
RAIL = 2.5              # PCB rests on its long edges only (SD slot sits at a short end)
END_OPENING = 20.0      # open short ends for the wires / SD access
ZIP_SLOT = (2.2, 4.5)   # zip-tie slots, strap goes over the board
ZIP_Y = 10.0
TEST_RING_H = 22.0

# Approximate AI-Thinker layout (board coords, +Y = antenna end, component side down).
CAM_XY = (0.0, 5.0)
LED_XY = (-9.5, -14.0)

out_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else r"c:/github/espcam/hardware"

r_sleeve_in = (METER_D + COLLAR_CLEAR) / 2
r_out = r_sleeve_in + WALL
r_lip_in = r_sleeve_in - LIP
z_lip_top = SLEEVE_H + LIP
# Ring top touches the chamfer where the chamfer radius equals the meter radius.
z_ref = SLEEVE_H + (r_sleeve_in - METER_D / 2)
z_lens = z_ref + LENS_DISTANCE
z_face = z_lens + LENS_FROM_PCB_BACK - PCB_T   # component-side PCB face
H = z_face - SOLDER_STANDOFF                    # shroud height = plate top surface
r_top_out = TOP_OD / 2
r_top_in = r_top_out - WALL
r_recess = (PLATE_D + RECESS_CLEAR) / 2
r_ledge = r_recess - LEDGE
z_cone_top = H - 8.0


def revolve_profile(pts):
    poly = Part.makePolygon([App.Vector(r, 0, z) for r, z in pts] + [App.Vector(pts[0][0], 0, pts[0][1])])
    return Part.Face(poly).revolve(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 360)


profile = [
    (r_sleeve_in, 0.0),
    (r_out, 0.0),
    (r_out, z_lip_top),
    (r_top_out, z_cone_top),
    (r_top_out, H),
    (r_recess, H),
    (r_recess, H - PLATE_T),
    (r_ledge, H - PLATE_T),
    (r_ledge, H - PLATE_T - 1.0),
    (r_top_in, H - PLATE_T - 1.0 - (r_top_in - r_ledge)),   # 45 deg underside, no support
    (r_top_in, z_cone_top),
    (r_out - WALL, z_lip_top),
    (r_lip_in, z_lip_top),
    (r_sleeve_in, SLEEVE_H),
]
shroud = revolve_profile(profile)

notch = Part.makeBox(HINGE_NOTCH_W, 2 * WALL + 10, HINGE_NOTCH_H + 1,
                     App.Vector(-HINGE_NOTCH_W / 2, r_sleeve_in - 5, -1))
shroud = shroud.cut(notch)
for a in SCREW_ANGLES:
    d = App.Vector(math.cos(math.radians(a)), math.sin(math.radians(a)), 0)
    hole = Part.makeCylinder(SCREW_HOLE_D / 2, 3 * WALL, d * (r_sleeve_in - WALL), d)
    hole.translate(App.Vector(0, 0, SLEEVE_H / 2))
    shroud = shroud.cut(hole)
shroud = shroud.removeSplitter()

# Plate in its assembled position (bottom at H - PLATE_T).
z0 = H - PLATE_T
plate = Part.makeCylinder(PLATE_D / 2, PLATE_T, App.Vector(0, 0, z0))
pw, pl = PCB_W + PCB_CLEAR, PCB_L + PCB_CLEAR
ow, ol = pw + 2 * POCKET_WALL, pl + 2 * POCKET_WALL
walls = Part.makeBox(ow, ol, POCKET_H, App.Vector(-ow / 2, -ol / 2, H)).cut(
    Part.makeBox(pw, pl, POCKET_H + 1, App.Vector(-pw / 2, -pl / 2, H - 0.5)))
for sy in (-1, 1):
    walls = walls.cut(Part.makeBox(END_OPENING, POCKET_WALL + 2, POCKET_H + 1,
                                   App.Vector(-END_OPENING / 2, sy * (ol / 2) - (POCKET_WALL + 2) / 2, H)))
plate = plate.fuse(walls)
win_w, win_l = pw - 2 * RAIL, pl + 2
plate = plate.cut(Part.makeBox(win_w, win_l, PLATE_T + 2, App.Vector(-win_w / 2, -win_l / 2, z0 - 1)))
zx = ow / 2 + 1.0 + ZIP_SLOT[0] / 2
for sx in (-1, 1):
    for sy in (-1, 1):
        plate = plate.cut(Part.makeBox(ZIP_SLOT[0], ZIP_SLOT[1], PLATE_T + 2,
                                       App.Vector(sx * zx - ZIP_SLOT[0] / 2, sy * ZIP_Y - ZIP_SLOT[1] / 2, z0 - 1)))
plate = plate.removeSplitter()

test_ring = shroud.common(Part.makeCylinder(r_out + 5, TEST_RING_H, App.Vector(0, 0, -1)))


def box_c(sx, sy, sz, cx, cy, z_top):
    """Box centred on (cx, cy) hanging down from z_top."""
    return Part.makeBox(sx, sy, sz, App.Vector(cx - sx / 2, cy - sy / 2, z_top - sz))


# ESP32-CAM, face down: PCB above z_face, components hang below it into the shroud.
pcb = Part.makeBox(PCB_W, PCB_L, PCB_T, App.Vector(-PCB_W / 2, -PCB_L / 2, z_face))
esp_module = box_c(18.0, 25.5, 3.9, 0.0, PCB_L / 2 - 25.5 / 2, z_face)
cx, cy = CAM_XY
z_shield = z_face - 3.9
cam_holder = box_c(8.5, 8.5, z_shield - (z_lens + 1.0), cx, cy, z_shield)
lens_barrel = Part.makeCylinder(3.5, 1.0, App.Vector(cx, cy, z_lens))
sd_slot = box_c(14.0, 15.0, 2.0, 0.0, -PCB_L / 2 + 15.0 / 2, z_face)
led = box_c(3.0, 3.0, 1.0, LED_XY[0], LED_XY[1], z_face)
pins = [Part.makeBox(0.64, 0.64, 8.5, App.Vector(sx * 12.2 - 0.32, -17.0 + i * 2.54 - 0.32, z_face + PCB_T))
        for sx in (-1, 1) for i in range(8)]
board = Part.makeCompound([pcb, esp_module, cam_holder, lens_barrel, sd_slot, led] + pins)

doc = App.getDocument("CameraHolder") if "CameraHolder" in App.listDocuments() else App.newDocument("CameraHolder")
for o in list(doc.Objects):
    doc.removeObject(o.Name)
s_obj = doc.addObject("Part::Feature", "Shroud")
s_obj.Shape = shroud
p_obj = doc.addObject("Part::Feature", "Plate")
p_obj.Shape = plate
b_obj = doc.addObject("Part::Feature", "ESP32CAM")
b_obj.Shape = board
t_obj = doc.addObject("Part::Feature", "TestRing")
t_obj.Shape = test_ring
t_obj.Placement.Base = App.Vector(120, 0, 0)
lens = doc.addObject("Part::Feature", "LensTipMarker")
lens.Shape = Part.makeSphere(1.5, App.Vector(cx, cy, z_lens))
ring = doc.addObject("Part::Feature", "MeterRingRef")
ring.Shape = Part.makeCylinder(METER_D / 2, 1.0, App.Vector(0, 0, z_ref - 1.0))
doc.recompute()
if App.GuiUp:
    import FreeCADGui as Gui
    Gui.getDocument(doc.Name).getObject("Shroud").Transparency = 60
    Gui.getDocument(doc.Name).getObject("ESP32CAM").ShapeColor = (0.1, 0.5, 0.2)
    Gui.getDocument(doc.Name).getObject("LensTipMarker").ShapeColor = (1.0, 0.0, 0.0)
    Gui.getDocument(doc.Name).getObject("MeterRingRef").ShapeColor = (0.2, 0.4, 1.0)

# Export in print orientation: shroud collar-down, plate flat-side down.
plate_print = plate.copy()
plate_print.translate(App.Vector(0, 0, -z0))
shroud.exportStl(os.path.join(out_dir, "shroud.stl"))
plate_print.exportStl(os.path.join(out_dir, "plate.stl"))
test_ring.exportStl(os.path.join(out_dir, "test_ring.stl"))
Part.export([s_obj, p_obj], os.path.join(out_dir, "camera_holder.step"))
doc.saveAs(os.path.join(out_dir, "camera_holder.FCStd"))

print(f"ring top z={z_ref:.2f}  lens tip z={z_lens:.2f}  distance={z_lens - z_ref:.1f} mm")
print(f"shroud height={H:.2f} mm, assembled height={H + POCKET_H:.2f} mm, max OD={2 * r_out:.1f} mm")
print(f"shroud volume={shroud.Volume / 1000:.1f} cm3, plate volume={plate.Volume / 1000:.1f} cm3")
print(f"shroud valid={shroud.isValid()}; plate valid={plate.isValid()} solids={len(plate.Solids)}; test ring valid={test_ring.isValid()} h={TEST_RING_H}")
print(f"board/plate interference={board.common(plate).Volume:.2f} mm3, board/shroud interference={board.common(shroud).Volume:.2f} mm3")
