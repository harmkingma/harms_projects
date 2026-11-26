"""Radiator fan booster - 3D-printable parts (FreeCAD 1.1, Part workbench).

Run headless:  build_radiator_fan_booster.bat
or in the FreeCAD GUI Python console:
    exec(open(r"C:/gpub/harms_projects/projects/hardware/radiator-fan-booster/radiator_fan_booster.py").read())

Writes print/*.stl (print orientation), radiator_fan_booster.step and radiator_fan_booster.FCStd
(assembly with a simple radiator / wall / floor model for the fit check) next to this file.

Global coordinates (assembly):
    x = along the radiator, 0 = left end (pipe side), +x to the right
    y = depth, 0 = radiator front face, +y towards the wall (wall at y = RAD_D + WALL_GAP)
    z = up, 0 = radiator bottom (= magnet contact plane), floor at z = -FLOOR_GAP

Parts (print in PETG or ASA, not PLA):
    fan_module      x3  plate + plenum, 4 magnet pads, slanted rear deflector, fan hangs below
    fan_module_t3   x1  same + slot for the T3 intake-air probe (leftmost module)
    t3_intake_probe x1  hangs through the module plate, holds a bare TO-92 DS18B20 in the intake air
    pipe_clip       x2  snap-on clip for the 15 mm supply (T1) and return (T2) pipes
    t4_grille_probe x1  rests on the top grille, holds T4 in the outflow just below the grille
    controller_box  x1  base for perfboard 70x50 + ESP32-C3 SuperMini, 4 magnets in the floor
    controller_lid  x1
Magnets: 20 x Tonzon block 8 x 4 x 3 mm (16 in the fan modules, 4 in the controller box).
"""
import math
import os

import FreeCAD as App
import Part

try:
    import MeshPart
except ImportError:  # pragma: no cover - only when FreeCAD lacks the Mesh workbench
    MeshPart = None

V = App.Vector

# --- Radiator / room (measured 2026-11-26) ------------------------------------------------
RAD_W, RAD_D, RAD_H = 600.0, 100.0, 750.0   # Radson type 22, 600 wide, 750 high
PANEL_D = 22.0             # footprint of each panel seen from below (magnet contact zone)
FLOOR_GAP = 90.0           # floor -> radiator bottom
WALL_GAP = 20.0            # rear panel -> wall
PIPE_D = 15.0              # supply + return pipes
GRILLE_SLOT_W = 5.0        # top-grille slot width - VERIFY before printing t4_grille_probe
T4_DEPTH = 12.0            # how far the T4 probe hangs below the grille top - VERIFY (fins below)

# --- Fan: ARCTIC P12 Slim PWM PST (set FAN_T = 25 for a 25 mm fan) ------------------------
FAN = 120.0
FAN_T = 15.0
FAN_HOLE_PITCH = 105.0
FAN_OPEN_D = 116.0
FAN_SCREW_PILOT_D = 3.2    # fan screws go up through the fan frame into the plate (6-32 / M3.5)

# --- Magnets: Tonzon block 8 x 4 x 3 mm ---------------------------------------------------
MAG_L, MAG_W, MAG_T = 8.0, 4.0, 3.0
MAG_CLEAR = 0.25           # per dimension; glue the magnet with a drop of CA
MAG_SKIN = 0.6             # plastic between magnet and radiator paint (3 layers @ 0.2 mm)

# --- Fan module -------------------------------------------------------------------------
N_MODULES = 4
MOD_W = 136.0              # along x; 4 x 136 = 544 mm under a 600 mm radiator
WALL = 2.0
PLATE_T = 3.0
PLENUM_H = 18.0            # plate top -> contact plane; room for the rear deflector slope
TOP_GAP = 1.0              # walls stay below the contact plane, only the magnet pads touch
MOD_Y0 = -2.0              # module front edge (2 mm proud of the radiator front face)
MOD_Y1 = RAD_D + WALL_GAP - 2.0   # module rear edge, 2 mm from the wall
FAN_CY = (MOD_Y0 + MOD_Y1) / 2.0
PAD_W = 8.0                # magnet pad width along x (inside the side walls)
FRONT_PAD_Y = (MOD_Y0, PANEL_D - 4.0)
REAR_PAD_Y = (RAD_D - PANEL_D + 3.0, RAD_D - 1.0)
SLANT_T = 2.8              # horizontal thickness of the slanted rear deflector
BOSS_R = 4.0
ZIP_SLOT_Y = (27.0, 33.0, 67.0, 73.0)
MODULES_X0 = (RAD_W - N_MODULES * MOD_W) / 2.0   # centred under the radiator

# --- Probes (bare TO-92 DS18B20) ----------------------------------------------------------
TO92_T, TO92_W, TO92_H = 3.6, 4.6, 4.8   # flat face -> round back, width, body height
T3_STEM = (5.0, 6.0)       # x, y cross-section of the intake probe stem
T3_SLOT_CLEAR = 0.2
T3_Y = 50.0
T3_BELOW_FAN = 14.0        # probe tip below the fan intake face
CLIP_H = 12.0
CLIP_WALL = 2.4
CLIP_OPEN = 12.0           # snap opening (< PIPE_D)

# --- Controller box ----------------------------------------------------------------------
BOARD_L, BOARD_W = 70.0, 50.0          # 5 x 7 cm perfboard
BOARD_HOLE_INSET = 2.0                 # VERIFY on your board; pilot holes for M2 x 5 machine screws
BOX_L, BOX_W, BOX_H = 84.0, 56.0, 28.0 # interior; long side vertical on the radiator side panel
BOX_FLOOR = 4.0
STANDOFF_H = 4.0
DC_JACK_D = 8.2                        # DC-099 panel jack 5.5 x 2.1 - VERIFY thread diameter

out_dir = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
print_dir = os.path.join(out_dir, "print")
os.makedirs(print_dir, exist_ok=True)


# --- Helpers ----------------------------------------------------------------------------
def box(x0, y0, z0, x1, y1, z1):
    return Part.makeBox(x1 - x0, y1 - y0, z1 - z0, V(x0, y0, z0))


def cyl_z(cx, cy, z0, z1, r):
    return Part.makeCylinder(r, z1 - z0, V(cx, cy, z0))


def prism_x(pts_yz, x0, x1):
    """Extrude a closed polygon given in the y-z plane from x0 to x1."""
    poly = Part.makePolygon([V(x0, y, z) for y, z in pts_yz] + [V(x0, *pts_yz[0])])
    return Part.Face(poly).extrude(V(x1 - x0, 0, 0))


def fuse(base, parts):
    return base.fuse(parts).removeSplitter() if parts else base


def cut(base, parts):
    return base.cut(parts).removeSplitter() if parts else base


def to_bed(shape):
    s = shape.copy()
    bb = s.BoundBox
    s.translate(V(-bb.Center.x, -bb.Center.y, -bb.ZMin))
    return s


def flip_x(shape):
    s = shape.copy()
    s.rotate(V(0, 0, 0), V(1, 0, 0), 180)
    return s


# --- Fan module ---------------------------------------------------------------------------
Z_PLATE_TOP = -PLENUM_H
Z_PLATE_BOT = Z_PLATE_TOP - PLATE_T
Z_FAN_BOT = Z_PLATE_BOT - FAN_T
HW = MOD_W / 2.0
PAD_XI = HW - WALL - PAD_W               # inner face of the magnet pads
T3_X = -(HW - WALL - T3_STEM[0] / 2.0 - 0.5)
FAN_HOLES = [(sx * FAN_HOLE_PITCH / 2.0, FAN_CY + sy * FAN_HOLE_PITCH / 2.0)
             for sx in (-1, 1) for sy in (-1, 1)]


def slant_inner_z(y):
    """Height of the deflector's inner (front) face above y."""
    y_bot, y_top = MOD_Y1 - SLANT_T, RAD_D - SLANT_T
    return Z_PLATE_TOP + (y_bot - y) * (-TOP_GAP - Z_PLATE_TOP) / (y_bot - y_top)


def make_fan_module(with_t3_slot):
    plate = box(-HW, MOD_Y0, Z_PLATE_BOT, HW, MOD_Y1, Z_PLATE_TOP)
    front = box(-HW, MOD_Y0, Z_PLATE_TOP, HW, MOD_Y0 + WALL, -TOP_GAP)
    side_profile = [(MOD_Y0, Z_PLATE_TOP), (MOD_Y1, Z_PLATE_TOP), (RAD_D, -TOP_GAP), (MOD_Y0, -TOP_GAP)]
    sides = [prism_x(side_profile, -HW, -HW + WALL), prism_x(side_profile, HW - WALL, HW)]
    slant = prism_x([(MOD_Y1, Z_PLATE_TOP), (RAD_D, -TOP_GAP), (RAD_D - SLANT_T, -TOP_GAP),
                     (MOD_Y1 - SLANT_T, Z_PLATE_TOP)], -HW, HW)
    pads = []
    for s in (-1, 1):
        xa, xb = sorted((s * PAD_XI, s * (HW - WALL + 0.5)))
        for y0, y1 in (FRONT_PAD_Y, REAR_PAD_Y):
            pads.append(box(xa, y0, Z_PLATE_TOP, xb, y1, 0.0))
    bosses, boss_tops = [], {}
    for hx, hy in FAN_HOLES:
        top = Z_PLATE_TOP + 6.0 if hy < FAN_CY else slant_inner_z(hy) + 1.0
        boss_tops[(hx, hy)] = top
        bosses.append(cyl_z(hx, hy, Z_PLATE_TOP - 0.01, top, BOSS_R))
    shape = fuse(plate, [front] + sides + [slant] + pads + bosses)

    cuts = [cyl_z(0, FAN_CY, Z_PLATE_BOT - 1, Z_PLATE_TOP + 0.01, FAN_OPEN_D / 2.0)]
    for s in (-1, 1):
        for y0, y1 in (FRONT_PAD_Y, REAR_PAD_Y):
            yc = (y0 + y1) / 2.0
            xa, xb = sorted((s * (PAD_XI - 0.5), s * (PAD_XI + MAG_W + MAG_CLEAR)))
            cuts.append(box(xa, yc - (MAG_L + MAG_CLEAR) / 2, -MAG_SKIN - MAG_T - MAG_CLEAR,
                            xb, yc + (MAG_L + MAG_CLEAR) / 2, -MAG_SKIN))
        xa, xb = sorted((s * (HW - WALL - 5.5), s * (HW - WALL - 2.0)))
        for y in ZIP_SLOT_Y:
            cuts.append(box(xa, y - 0.9, Z_PLATE_BOT - 1, xb, y + 0.9, Z_PLATE_TOP + 0.5))
    for (hx, hy), top in boss_tops.items():
        cuts.append(cyl_z(hx, hy, Z_PLATE_BOT - 1, top + 0.1, FAN_SCREW_PILOT_D / 2.0))
    if with_t3_slot:
        hx, hy = T3_STEM[0] / 2 + T3_SLOT_CLEAR, T3_STEM[1] / 2 + T3_SLOT_CLEAR
        cuts.append(box(T3_X - hx, T3_Y - hy, Z_PLATE_BOT - 1, T3_X + hx, T3_Y + hy, Z_PLATE_TOP + 0.5))
    return cut(shape, cuts)


def make_fan_dummy():
    frame = box(-FAN / 2, FAN_CY - FAN / 2, Z_FAN_BOT, FAN / 2, FAN_CY + FAN / 2, Z_PLATE_BOT)
    return frame.cut(cyl_z(0, FAN_CY, Z_FAN_BOT - 1, Z_PLATE_BOT + 1, FAN_OPEN_D / 2 - 1))


# --- T3 intake probe (print orientation: flange on the bed, stem up) ----------------------
def make_t3_probe():
    sx, sy = T3_STEM[0] / 2, T3_STEM[1] / 2
    flange_t = 1.5
    stem_l = PLATE_T + FAN_T + T3_BELOW_FAN
    top = flange_t + stem_l
    flange = box(-sx - 0.3, -7.0, 0, sx + 2.5, 7.0, flange_t)
    stem = box(-sx, -sy, flange_t - 0.01, sx, sy, top)
    pocket = box(-(TO92_T + 0.2) / 2, -(TO92_W + 0.2) / 2, top - TO92_H - 0.6,
                 (TO92_T + 0.2) / 2, (TO92_W + 0.2) / 2, top + 1)
    window = box(-sx - 1, -1.6, top - TO92_H + 0.2, sx + 1, 1.6, top - 1.0)
    return cut(fuse(flange, [stem]), [pocket, window])


# --- Pipe clip T1/T2 (print orientation as modelled: pipe axis = z) -------------------------
def make_pipe_clip():
    r_pipe = PIPE_D / 2.0
    r_in = r_pipe + 0.15
    r_out = r_in + CLIP_WALL
    pocket_x1 = r_pipe + TO92_T - 0.1        # 0.1 mm preload on the sensor's round back
    house_x1 = pocket_x1 + 1.6
    ring = cyl_z(0, 0, 0, CLIP_H, r_out)
    housing = box(r_in - 1.0, -4.1, 0, house_x1, 4.1, CLIP_H)
    tab = box(pocket_x1 + 0.4, -4.1, CLIP_H - 0.01, house_x1 + 0.4, 4.1, CLIP_H + 10.0)
    shape = fuse(ring, [housing, tab])
    bore = cyl_z(0, 0, -1, CLIP_H + 1, r_in)
    opening = box(-r_out - 1, -CLIP_OPEN / 2, -1, -3.5, CLIP_OPEN / 2, CLIP_H + 1)
    pocket = box(r_pipe - 1.0, -(TO92_W + 0.4) / 2, CLIP_H - TO92_H - 0.6,
                 pocket_x1, (TO92_W + 0.4) / 2, CLIP_H + 1)
    zip_window = box(pocket_x1, -2.6, CLIP_H + 4.0, house_x1 + 1.0, 2.6, CLIP_H + 6.5)
    return cut(shape, [bore, opening, pocket, zip_window])


# --- T4 grille probe (modelled as installed: saddle on the grille top at z = 0) -------------
def make_t4_probe():
    stem_t = min(2.8, GRILLE_SLOT_W - 2.0)
    saddle = box(-12.0, -8.0, 0, 12.0, 8.0, 1.6)
    stem = box(-stem_t / 2, -5.0, -T4_DEPTH - 1.0, stem_t / 2, 5.0, 0.01)
    window = box(-stem_t, -(TO92_W + 0.3) / 2, -T4_DEPTH, stem_t, (TO92_W + 0.3) / 2,
                 -T4_DEPTH + TO92_H + 0.2)
    groove = box(stem_t / 2 - 0.8, -1.8, -T4_DEPTH + TO92_H, stem_t / 2 + 0.1, 1.8, 0.02)
    wire_exit = box(stem_t / 2 - 0.8, -1.8, -0.5, stem_t / 2 + 2.0, 1.8, 2.0)
    return cut(fuse(saddle, [stem]), [window, groove, wire_exit])


# --- Controller box -----------------------------------------------------------------------
BOX_TOP = BOX_FLOOR + BOX_H
BOX_BOSSES = [(3.0, 20.0), (BOX_L - 3.0, 12.0)]   # clear of the jack, cable slot and USB slot
JACK_Y = 10.0
CABLE_SLOT_Y = (25.0, 53.0)
BOARD_X0, BOARD_Y0 = (BOX_L - BOARD_L) / 2, (BOX_W - BOARD_W) / 2
BOARD_HOLES = [(BOARD_X0 + dx, BOARD_Y0 + dy)
               for dx in (BOARD_HOLE_INSET, BOARD_L - BOARD_HOLE_INSET)
               for dy in (BOARD_HOLE_INSET, BOARD_W - BOARD_HOLE_INSET)]
BOX_MAGNETS = [(18.0, 15.0), (BOX_L - 18.0, 15.0), (18.0, BOX_W - 15.0), (BOX_L - 18.0, BOX_W - 15.0)]


def make_box_base():
    shell = box(-WALL, -WALL, 0, BOX_L + WALL, BOX_W + WALL, BOX_TOP)
    shell = shell.cut(box(0, 0, BOX_FLOOR, BOX_L, BOX_W, BOX_TOP + 1))
    adds = [cyl_z(x, y, BOX_FLOOR - 0.01, BOX_TOP, 3.25) for x, y in BOX_BOSSES]
    adds += [cyl_z(x, y, BOX_FLOOR - 0.01, BOX_FLOOR + STANDOFF_H, 2.5) for x, y in BOARD_HOLES]
    shape = fuse(shell, adds)
    cuts = [cyl_z(x, y, BOX_TOP - 10, BOX_TOP + 1, 1.25) for x, y in BOX_BOSSES]
    cuts += [cyl_z(x, y, 1.0, BOX_FLOOR + STANDOFF_H + 1, 0.85) for x, y in BOARD_HOLES]  # M2 x 5..8
    cuts += [box(x - (MAG_L + MAG_CLEAR) / 2, y - (MAG_W + MAG_CLEAR) / 2, MAG_SKIN,
                 x + (MAG_L + MAG_CLEAR) / 2, y + (MAG_W + MAG_CLEAR) / 2, BOX_FLOOR + 0.1)
             for x, y in BOX_MAGNETS]
    jack_z = BOX_FLOOR + 14.0
    cuts.append(Part.makeCylinder(DC_JACK_D / 2, WALL + 2, V(-WALL - 1, JACK_Y, jack_z), V(1, 0, 0)))
    cuts.append(box(-WALL - 1, CABLE_SLOT_Y[0], BOX_FLOOR + 9.0, 1.0, CABLE_SLOT_Y[1],
                    BOX_FLOOR + 16.0))                                                    # cables
    cuts.append(box(BOX_L - 1, BOX_W / 2 - 6.5, BOX_FLOOR + 12.0, BOX_L + WALL + 1,
                    BOX_W / 2 + 6.5, BOX_FLOOR + 20.0))                                   # USB-C
    return cut(shape, cuts)


def make_box_lid():
    lid = box(-WALL, -WALL, 0, BOX_L + WALL, BOX_W + WALL, 2.0)
    lip = box(0.3, 0.3, 1.99, BOX_L - 0.3, BOX_W - 0.3, 4.0).cut(
        box(1.5, 1.5, 1.9, BOX_L - 1.5, BOX_W - 1.5, 4.1))
    lip = lip.cut([cyl_z(x, BOX_W - y, 1.0, 5.0, 3.7) for x, y in BOX_BOSSES])
    shape = fuse(lid, [lip])
    return cut(shape, [cyl_z(x, BOX_W - y, -1, 3, 1.7) for x, y in BOX_BOSSES])


# --- Build parts ----------------------------------------------------------------------------
module = make_fan_module(False)
module_t3 = make_fan_module(True)
t3_probe = make_t3_probe()
pipe_clip = make_pipe_clip()
t4_probe = make_t4_probe()
box_base = make_box_base()
box_lid = make_box_lid()

# --- Assembly (fit check) ---------------------------------------------------------------------
radiator = box(0, 0, 0, RAD_W, RAD_D, RAD_H)
wall = box(-200, RAD_D + WALL_GAP, -FLOOR_GAP, RAD_W + 200, RAD_D + WALL_GAP + 20, RAD_H + 100)
floor = box(-200, -200, -FLOOR_GAP - 10, RAD_W + 200, RAD_D + WALL_GAP, -FLOOR_GAP)
SUPPLY_XY, RETURN_XY = (-45.0, 95.0), (-12.0, 95.0)   # illustrative pipe positions
supply_pipe = cyl_z(*SUPPLY_XY, -FLOOR_GAP, 700.0, PIPE_D / 2)
return_pipe = cyl_z(*RETURN_XY, -FLOOR_GAP, 40.0, PIPE_D / 2)

asm = {}
for i in range(N_MODULES):
    cx = MODULES_X0 + MOD_W * (i + 0.5)
    m = (module_t3 if i == 0 else module).copy()
    m.translate(V(cx, 0, 0))
    asm[f"FanModule{i + 1}"] = m
    f = make_fan_dummy()
    f.translate(V(cx, 0, 0))
    asm[f"Fan{i + 1}"] = f
t3 = flip_x(t3_probe)
t3.translate(V(MODULES_X0 + HW + T3_X, T3_Y, Z_PLATE_TOP + 1.5))
asm["T3IntakeProbe"] = t3
for name, (px, py), z in (("T1SupplyClip", SUPPLY_XY, 600.0), ("T2ReturnClip", RETURN_XY, -45.0)):
    c = pipe_clip.copy()
    c.rotate(V(0, 0, 0), V(0, 0, 1), 90)    # snap opening towards the room, sensor towards the wall
    c.translate(V(px, py, z))
    asm[name] = c
t4 = t4_probe.copy()
t4.translate(V(RAD_W / 2, RAD_D / 2, RAD_H))
asm["T4GrilleProbe"] = t4
box_place = V(0, RAD_D / 2 - BOX_W / 2, 30.0)
b = box_base.copy()
b.rotate(V(0, 0, 0), V(0, 1, 0), -90)
b.translate(box_place)
asm["ControllerBox"] = b
lid = box_lid.copy()
lid.rotate(V(0, BOX_W / 2, 0), V(1, 0, 0), 180)
lid.translate(V(0, 0, BOX_TOP + 2.0))
lid.rotate(V(0, 0, 0), V(0, 1, 0), -90)
lid.translate(box_place)
asm["ControllerLid"] = lid

# --- Document + export --------------------------------------------------------------------------
DOC = "RadiatorFanBooster"
doc = App.getDocument(DOC) if DOC in App.listDocuments() else App.newDocument(DOC)
for o in list(doc.Objects):
    doc.removeObject(o.Name)
objs = {}
for name, shape in list(asm.items()) + [("Radiator", radiator), ("Wall", wall), ("Floor", floor),
                                        ("SupplyPipe", supply_pipe), ("ReturnPipe", return_pipe)]:
    objs[name] = doc.addObject("Part::Feature", name)
    objs[name].Shape = shape
doc.recompute()
if App.GuiUp:
    import FreeCADGui as Gui
    gd = Gui.getDocument(doc.Name)
    for name in ("Radiator", "Wall", "Floor"):
        gd.getObject(name).Transparency = 80
    for i in range(N_MODULES):
        gd.getObject(f"Fan{i + 1}").ShapeColor = (0.15, 0.15, 0.15)

prints = {
    "fan_module": to_bed(module),
    "fan_module_t3": to_bed(module_t3),
    "t3_intake_probe": to_bed(t3_probe),
    "pipe_clip": to_bed(pipe_clip),
    "t4_grille_probe": to_bed(flip_x(t4_probe)),
    "controller_box": to_bed(box_base),
    "controller_lid": to_bed(box_lid),
}
for name, shape in prints.items():
    path = os.path.join(print_dir, name + ".stl")
    if MeshPart is not None:
        MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.05, AngularDeflection=0.2,
                               Relative=False).write(path)
    else:
        shape.exportStl(path)
Part.export([objs[n] for n in asm], os.path.join(out_dir, "radiator_fan_booster.step"))
doc.saveAs(os.path.join(out_dir, "radiator_fan_booster.FCStd"))
preview_dir = os.environ.get("RFB_ASSEMBLY_STL_DIR")   # used by render_previews.py
if preview_dir and MeshPart is not None:
    os.makedirs(preview_dir, exist_ok=True)
    for name, obj in objs.items():
        MeshPart.meshFromShape(Shape=obj.Shape, LinearDeflection=0.3, AngularDeflection=0.5,
                               Relative=False).write(os.path.join(preview_dir, name + ".stl"))

# --- Report ----------------------------------------------------------------------------------------
for name, shape in prints.items():
    bb = shape.BoundBox
    print(f"{name:16s} {bb.XLength:6.1f} x {bb.YLength:6.1f} x {bb.ZLength:5.1f} mm  "
          f"valid={shape.isValid()} solids={len(shape.Solids)} vol={shape.Volume / 1000:6.1f} cm3")
print(f"module row x {MODULES_X0:.1f}..{MODULES_X0 + N_MODULES * MOD_W:.1f}; "
      f"plate z {Z_PLATE_BOT:.1f}..{Z_PLATE_TOP:.1f}; fan bottom z {Z_FAN_BOT:.1f}; "
      f"intake gap {Z_FAN_BOT + FLOOR_GAP:.1f} mm; rear edge to wall {RAD_D + WALL_GAP - MOD_Y1:.1f} mm")
print(f"T3 probe tip z {asm['T3IntakeProbe'].BoundBox.ZMin:.1f}; fan screw length ~{FAN_T + PLATE_T + 4:.0f} mm")
checks = {
    "modules/radiator": sum(asm[f"FanModule{i + 1}"].common(radiator).Volume for i in range(N_MODULES)),
    "modules/wall": sum(asm[f"FanModule{i + 1}"].common(wall).Volume for i in range(N_MODULES)),
    "fans/modules": sum(asm[f"Fan{i + 1}"].common(asm[f"FanModule{i + 1}"]).Volume for i in range(N_MODULES)),
    "fans/floor": sum(asm[f"Fan{i + 1}"].common(floor).Volume for i in range(N_MODULES)),
    "t3/module1": asm["T3IntakeProbe"].common(asm["FanModule1"]).Volume,
    "t3/fan1": asm["T3IntakeProbe"].common(asm["Fan1"]).Volume,
    "t1clip/pipe": asm["T1SupplyClip"].common(supply_pipe).Volume,
    "t2clip/pipe": asm["T2ReturnClip"].common(return_pipe).Volume,
    "box/radiator": asm["ControllerBox"].common(radiator).Volume,
    "box/lid": asm["ControllerBox"].common(asm["ControllerLid"]).Volume,
    "box/pipes": asm["ControllerBox"].common(supply_pipe).Volume + asm["ControllerBox"].common(return_pipe).Volume,
    "box/floor": asm["ControllerBox"].common(floor).Volume,
}
print("interference (mm3): " + ", ".join(f"{k}={v:.3f}" for k, v in checks.items()))
