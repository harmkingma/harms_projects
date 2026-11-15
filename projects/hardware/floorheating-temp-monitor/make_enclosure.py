"""Snap-fit enclosure for the Adafruit ESP32-S3 TFT Feather (product 5483).

Run inside FreeCAD (Macro > Execute, or exec from the Python console). Creates the document
"FeatherEnclosure" with the parts Box, Lid, ButtonCap_Reset, ButtonCap_Boot and a reference
model of the board, then saves the .FCStd and print-oriented STL + STEP files next to this script.

Frame: x/y are the Adafruit STEP model coordinates (board 0..50.8 x 0..22.86, USB-C at +x),
z = 0 is the outside of the front panel (display side, on the print bed), z grows towards the lid.
"""
import os

import FreeCAD as App
import Import
import Mesh
import MeshPart
import Part
from FreeCAD import Vector as V

HERE = os.path.dirname(os.path.abspath(globals().get("__file__", "")))
BOARD_STEP = os.path.join(HERE, "reference", "5483_Feather_ESP32-S3_TFT.step")
DOC_NAME = "FeatherEnclosure"

# --- board (Adafruit STEP model, PCB front face at model z=0) --------------------------------
PCB_L, PCB_W, PCB_T = 50.8, 22.86, 1.57
USB_X_MAX = 51.88                    # USB-C receptacle front face
USB_Y, USB_Z = 11.43, -1.1           # receptacle centre (model z)
FRONT_TALLEST = 4.8                  # JST-PH LiPo connector below the PCB front face
DISPLAY_FRONT = 1.52                 # display surface below the PCB front face
ACTIVE = (8.78, 33.69, 3.92, 18.78)  # visible display area x0, x1, y0, y1
BTN_RST, BTN_BOOT = (41.78, 6.22), (37.08, 6.22)
BTN_TOP = 1.9                        # button actuator below the PCB front face
MOUNT_HOLES = [(2.54, 2.54), (2.54, 20.32), (48.26, 2.54), (48.26, 20.32)]   # Ø2.5 mm
MODULE_TOP = 4.12                    # ESP32 module, model z (back side)

# --- enclosure parameters (mm) ----------------------------------------------------------------
WALL, FLOOR = 1.6, 1.4
CLR = 0.3                            # board-to-wall clearance
Z_PCB = FLOOR + FRONT_TALLEST + 0.4  # PCB front face height in the box
BAY = 12.0                           # wire / resistor bay at the display end
IN_X0, IN_X1 = -BAY, 52.0
IN_Y0, IN_Y1 = -CLR, PCB_W + CLR
OUT_X0, OUT_X1, OUT_Y0, OUT_Y1 = IN_X0 - WALL, IN_X1 + WALL, IN_Y0 - WALL, IN_Y1 + WALL
H_BOX = 14.5                         # rim height (leaves ~6 mm above the PCB back for wires)
LID_T = 1.6
R_OUT = 2.0

LIP_CLR, LIP_T, LIP_Z0 = 0.15, 1.0, H_BOX - 5.5
SNAP_Z0, SNAP_Z1 = H_BOX - 5.2, H_BOX - 4.2   # groove in the box wall / bump on the lid tabs
SNAP_DEPTH, BUMP = 0.4, 0.45
TAB_LEN, SLOT_W = 10.0, 1.0
TAB_X = (2.0, 38.0)

CAP_SHAFT_R, CAP_FLANGE_R, CAP_PLUNGER_R = 1.3, 2.1, 0.8
CAP_PROTRUDE, CAP_GAP = 0.6, 0.25
HOLE_CLR = 0.2

WIRE_SLOT_W, WIRE_SLOT_Z = 4.5, 8.0  # U-slot for the 3 sensor wires, open to the rim


# --- helpers ------------------------------------------------------------------------------
def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def rbox(x0, y0, z0, x1, y1, z1, r):
    b = box(x0, y0, z0, x1, y1, z1)
    if r <= 0:
        return b
    vertical = [e for e in b.Edges if abs(e.Vertexes[0].Point.z - e.Vertexes[1].Point.z) > 1e-6]
    return b.makeFillet(r, vertical)


def cyl(r, x, y, z0, z1):
    return Part.makeCylinder(r, z1 - z0, V(x, y, z0))


def rect_wire(x0, y0, x1, y1, z):
    return Part.makePolygon([V(x0, y0, z), V(x1, y0, z), V(x1, y1, z), V(x0, y1, z), V(x0, y0, z)])


def fuse_all(base, parts):
    return base.fuse(parts).removeSplitter() if parts else base


# --- box --------------------------------------------------------------------------------------
def make_box():
    shell = rbox(OUT_X0, OUT_Y0, 0, OUT_X1, OUT_Y1, H_BOX, R_OUT).cut(
        rbox(IN_X0, IN_Y0, FLOOR, IN_X1, IN_Y1, H_BOX + 1, R_OUT - WALL))

    z_display = Z_PCB - DISPLAY_FRONT
    adds = [
        box(3.2, IN_Y0, FLOOR, 34.6, IN_Y1, z_display - 0.3),       # display bezel (raised floor)
        box(0.0, IN_Y0, FLOOR, 3.2, IN_Y1, Z_PCB),                  # PCB rest, display end
        box(46.6, IN_Y0, FLOOR, IN_X1, 4.6, Z_PCB),                 # PCB rests, USB end
        box(46.6, 18.2, FLOOR, IN_X1, IN_Y1, Z_PCB),
    ]
    adds += [cyl(1.0, x, y, Z_PCB - 0.1, Z_PCB + 1.2) for x, y in MOUNT_HOLES if x > 40]   # locating pegs
    cradle = box(-8.0, 5.0, FLOOR, -4.0, 18.0, FLOOR + 3.0)                       # resistor cradle
    cradle = cradle.cut(Part.makeCylinder(1.5, 14.0, V(-6.0, 4.5, FLOOR + 3.0), V(0, 1, 0)))
    adds.append(cradle)
    body = fuse_all(shell, adds)

    # display window: straight part in front of the display, bevel towards the outside
    # (right side kept straight because the button holes are next to it)
    ax0, ax1, ay0, ay1 = ACTIVE[0] - 1.0, ACTIVE[1] + 1.0, ACTIVE[2] - 1.0, ACTIVE[3] + 1.0
    z_ch, bevel = z_display - 0.8, 3.0
    outer = rect_wire(ax0 - bevel, ay0 - bevel, ax1 + 0.3, ay1 + bevel, -0.01)
    inner = rect_wire(ax0, ay0, ax1, ay1, z_ch)
    cuts = [Part.makeLoft([outer, inner], True),
            box(ax0, ay0, z_ch - 0.01, ax1, ay1, z_display + 0.5)]

    # button holes with a 45 deg countersink on the inside that seats the cap cone
    hr = CAP_SHAFT_R + HOLE_CLR
    for x, y in (BTN_RST, BTN_BOOT):
        cuts.append(cyl(hr, x, y, -1.0, FLOOR + 1.0))
        cuts.append(Part.makeCone(hr, CAP_FLANGE_R + HOLE_CLR, 0.8, V(x, y, FLOOR - 0.8)))

    # USB-C opening in the end wall
    usb_z = Z_PCB + USB_Z
    usb = box(IN_X1 - 0.5, USB_Y - 6.5, usb_z - 3.75, OUT_X1 + 1.0, USB_Y + 6.5, usb_z + 3.75)
    usb = usb.makeFillet(1.5, [e for e in usb.Edges
                               if abs(e.Vertexes[0].Point.x - e.Vertexes[1].Point.x) > 1e-6])
    cuts.append(usb)

    # sensor cable slot in the bay end wall, open to the rim so pre-soldered wires can be laid in
    hw = WIRE_SLOT_W / 2
    cuts.append(Part.makeCylinder(hw, WALL + 2.0, V(OUT_X0 - 1.0, USB_Y, WIRE_SLOT_Z), V(1, 0, 0)))
    cuts.append(box(OUT_X0 - 1.0, USB_Y - hw, WIRE_SLOT_Z, IN_X0 + 0.01, USB_Y + hw, H_BOX + 1.0))

    # snap groove all around the inside, and a pry notch for opening the lid
    groove = rbox(IN_X0 - SNAP_DEPTH, IN_Y0 - SNAP_DEPTH, SNAP_Z0, IN_X1 + SNAP_DEPTH, IN_Y1 + SNAP_DEPTH,
                  SNAP_Z1, R_OUT - WALL + SNAP_DEPTH)
    cuts.append(groove)
    cuts.append(box(16.0, OUT_Y0 - 1.0, H_BOX - 1.2, 24.0, IN_Y0 + 0.01, H_BOX + 1.0))

    body = body.cut(Part.makeCompound(cuts)).removeSplitter()
    return engrave_labels(body)


def engrave_labels(body):
    """Mirrored text on the outside of the front panel so it reads correctly from the front."""
    try:
        import Draft
        font = r"C:\Windows\Fonts\arialbd.ttf"
        if not os.path.exists(font):
            return body
        tmp = App.ActiveDocument
        cuts = []
        for text, (x, y) in (("R", (BTN_RST[0], 10.0)), ("B", (BTN_BOOT[0], 10.0))):
            ss = Draft.make_shapestring(String=text, FontFile=font, Size=2.5, Tracking=0)
            tmp.recompute()
            face = ss.Shape.copy()
            tmp.removeObject(ss.Name)
            bb = face.BoundBox
            face.translate(V(-(bb.XMin + bb.XMax) / 2, -(bb.YMin + bb.YMax) / 2, 0))
            face = face.mirror(V(0, 0, 0), V(1, 0, 0))
            face.translate(V(x, y, -0.01))
            cuts.append(face.extrude(V(0, 0, 0.41)))
        return body.cut(Part.makeCompound(cuts))
    except Exception as exc:  # labels are cosmetic
        App.Console.PrintWarning(f"Label engraving skipped: {exc}\n")
        return body


# --- lid --------------------------------------------------------------------------------------
def make_lid():
    plate = rbox(OUT_X0, OUT_Y0, H_BOX, OUT_X1, OUT_Y1, H_BOX + LID_T, R_OUT)
    lx0, ly0, lx1, ly1 = IN_X0 + LIP_CLR, IN_Y0 + LIP_CLR, IN_X1 - LIP_CLR, IN_Y1 - LIP_CLR
    lip = rbox(lx0, ly0, LIP_Z0, lx1, ly1, H_BOX + 0.01, R_OUT - WALL).cut(
        box(lx0 + LIP_T, ly0 + LIP_T, LIP_Z0 - 1, lx1 - LIP_T, ly1 - LIP_T, H_BOX + 1))

    # flexible snap tabs on both long sides: slots either side + a triangular bump
    slots, bumps = [], []
    zc = (SNAP_Z0 + SNAP_Z1) / 2
    for xc in TAB_X:
        for xs in (xc - TAB_LEN / 2 - SLOT_W, xc + TAB_LEN / 2):
            slots.append(box(xs, ly0 - 1, LIP_Z0 - 1, xs + SLOT_W, ly0 + LIP_T + 0.5, H_BOX))
            slots.append(box(xs, ly1 - LIP_T - 0.5, LIP_Z0 - 1, xs + SLOT_W, ly1 + 1, H_BOX))
        for y_face, sgn in ((ly0, -1), (ly1, 1)):
            tri = Part.Face(Part.makePolygon([V(xc - TAB_LEN / 2 + 1, y_face, SNAP_Z0),
                                              V(xc - TAB_LEN / 2 + 1, y_face + sgn * BUMP, zc),
                                              V(xc - TAB_LEN / 2 + 1, y_face, SNAP_Z1),
                                              V(xc - TAB_LEN / 2 + 1, y_face, SNAP_Z0)]))
            bumps.append(tri.extrude(V(TAB_LEN - 2, 0, 0)))
    lip = lip.cut(Part.makeCompound(slots)).fuse(bumps)

    # hold-down posts: on the PCB next to the USB-end mounting holes and on the ESP32 module
    z_pcb_back = Z_PCB + PCB_T
    posts = [cyl(1.5, x, y, z_pcb_back + 0.3, H_BOX + 0.01) for x, y in MOUNT_HOLES if x > 40]
    posts.append(cyl(2.0, 10.2, USB_Y, Z_PCB + MODULE_TOP + 0.3, H_BOX + 0.01))
    return plate.fuse([lip] + posts).removeSplitter()


# --- button caps ------------------------------------------------------------------------------
def make_cap(x, y):
    z_flange = FLOOR
    shaft = cyl(CAP_SHAFT_R, x, y, -CAP_PROTRUDE, z_flange - 0.8)
    cone = Part.makeCone(CAP_SHAFT_R, CAP_FLANGE_R, 0.8, V(x, y, z_flange - 0.8))
    flange = cyl(CAP_FLANGE_R, x, y, z_flange, z_flange + 0.6)
    plunger = cyl(CAP_PLUNGER_R, x, y, z_flange + 0.6, Z_PCB - BTN_TOP - CAP_GAP)
    cap = shaft.fuse([cone, flange, plunger]).removeSplitter()
    edge = [e for e in cap.Edges if isinstance(e.Curve, Part.Circle)
            and abs(e.Curve.Center.z + CAP_PROTRUDE) < 1e-6]
    return cap.makeFillet(0.3, edge)


# --- board reference --------------------------------------------------------------------------
def board_reference():
    ref = App.newDocument("FeatherRefTmp", hidden=True)
    Import.insert(BOARD_STEP, ref.Name)
    ref.recompute()
    shapes = [o.Shape.copy() for o in ref.Objects if o.TypeId == "Part::Feature" and o.Shape.Solids]
    App.closeDocument(ref.Name)
    comp = Part.makeCompound(shapes)
    comp.translate(V(0, 0, Z_PCB))
    return comp


# --- build ------------------------------------------------------------------------------------
def build():
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)
    doc = App.newDocument(DOC_NAME)

    parts = {
        "Box": (make_box(), (0.25, 0.27, 0.30)),
        "Lid": (make_lid(), (0.55, 0.58, 0.62)),
        "ButtonCap_Reset": (make_cap(*BTN_RST), (0.95, 0.55, 0.10)),
        "ButtonCap_Boot": (make_cap(*BTN_BOOT), (0.95, 0.55, 0.10)),
    }
    for name, (shape, color) in parts.items():
        obj = doc.addObject("Part::Feature", name)
        obj.Shape = shape
        if App.GuiUp:
            obj.ViewObject.ShapeColor = color
    ref = doc.addObject("Part::Feature", "Feather_Reference")
    ref.Shape = board_reference()
    if App.GuiUp:
        ref.ViewObject.ShapeColor = (0.45, 0.20, 0.65)
        ref.ViewObject.Transparency = 40
    doc.recompute()
    return doc


def check(doc):
    """Interference volumes between the board and every printed part (should all be ~0)."""
    board = doc.getObject("Feather_Reference").Shape
    report = {}
    for name in ("Box", "Lid", "ButtonCap_Reset", "ButtonCap_Boot"):
        part = doc.getObject(name).Shape
        report[name] = sum(s.common(part).Volume for s in board.Solids
                           if s.BoundBox.intersect(part.BoundBox))
    report["Lid_vs_Box"] = doc.getObject("Lid").Shape.common(doc.getObject("Box").Shape).Volume
    for n in ("ButtonCap_Reset", "ButtonCap_Boot"):
        report[n + "_vs_Box"] = doc.getObject(n).Shape.common(doc.getObject("Box").Shape).Volume
    return report


def export(doc):
    out = os.path.join(HERE, "print")
    os.makedirs(out, exist_ok=True)
    # print orientation: box on its front, lid on its outside face, caps on the shaft end
    orient = {
        "Box": App.Placement(),
        "Lid": App.Placement(V(0, 0, H_BOX + LID_T), App.Rotation(V(1, 0, 0), 180)),
        "ButtonCap_Reset": App.Placement(V(0, 0, CAP_PROTRUDE), App.Rotation()),
        "ButtonCap_Boot": App.Placement(V(0, 0, CAP_PROTRUDE), App.Rotation()),
    }
    for name, plc in orient.items():
        s = doc.getObject(name).Shape.copy()
        s.Placement = plc.multiply(s.Placement)
        mesh = MeshPart.meshFromShape(Shape=s, LinearDeflection=0.02, AngularDeflection=0.1, Relative=False)
        mesh.write(os.path.join(out, f"{name}.stl"))
    Import.export([doc.getObject(n) for n in orient], os.path.join(out, "FeatherEnclosure_parts.step"))
    doc.saveAs(os.path.join(HERE, "FeatherEnclosure.FCStd"))
    return out


if __name__ == "__main__":
    d = build()
    print(check(d))
    print(export(d))
