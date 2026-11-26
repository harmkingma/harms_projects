"""Render PNG previews of the radiator fan booster parts and assembly (matplotlib, no FreeCAD GUI).

Usage (from the repo root):
    .venvs\\cad-tools\\Scripts\\python.exe projects\\hardware\\radiator-fan-booster\\render_previews.py
Runs FreeCAD headless with RFB_ASSEMBLY_STL_DIR set, then writes previews\\*.png.
"""
import os
import struct
import subprocess
import sys
import tempfile

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PRINT_DIR = os.path.join(HERE, "print")
OUT_DIR = os.path.join(HERE, "previews")
FREECADCMD = os.environ.get(
    "FREECADCMD", os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "FreeCAD 1.1", "bin", "freecadcmd.exe"))
LIGHT = np.array([0.4, -0.6, 0.7]) / np.linalg.norm([0.4, -0.6, 0.7])


def load_stl(path):
    with open(path, "rb") as f:
        data = f.read()
    if data[:5] == b"solid" and b"facet" in data[:400]:
        verts = [list(map(float, line.split()[1:4])) for line in data.decode(errors="ignore").splitlines()
                 if line.strip().startswith("vertex")]
        return np.array(verts, dtype=float).reshape(-1, 3, 3)
    count = struct.unpack("<I", data[80:84])[0]
    rec = np.frombuffer(data[84:84 + count * 50], dtype=np.dtype([("n", "<3f4"), ("v", "<9f4"), ("a", "<u2")]))
    return rec["v"].reshape(-1, 3, 3).astype(float)


def shaded(tris, rgb, alpha=1.0):
    n = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    k = 0.35 + 0.65 * np.abs(n @ LIGHT)
    cols = np.clip(np.outer(k, rgb), 0, 1)
    return Poly3DCollection(tris, facecolors=np.c_[cols, np.full(len(cols), alpha)], edgecolors="none")


def set_equal(ax, pts):
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    span = np.maximum(hi - lo, 1e-3)
    ax.set_xlim(lo[0], hi[0])
    ax.set_ylim(lo[1], hi[1])
    ax.set_zlim(lo[2], hi[2])
    ax.set_box_aspect(tuple(span), zoom=1.2)
    ax.set_axis_off()


def render_parts():
    names = ["fan_module_t3", "fan_module", "t3_intake_probe", "pipe_clip", "t4_grille_probe",
             "controller_box", "controller_lid"]
    fig = plt.figure(figsize=(16, 9), dpi=110)
    for i, name in enumerate(names):
        tris = load_stl(os.path.join(PRINT_DIR, name + ".stl"))
        ax = fig.add_subplot(2, 4, i + 1, projection="3d")
        ax.add_collection3d(shaded(tris, (0.85, 0.55, 0.15)))
        set_equal(ax, tris.reshape(-1, 3))
        ax.view_init(elev=35, azim=-60)
        bb = np.ptp(tris.reshape(-1, 3), axis=0)
        ax.set_title(f"{name}\n{bb[0]:.0f} x {bb[1]:.0f} x {bb[2]:.0f} mm (print orientation)", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT_DIR, "parts.png"))
    plt.close(fig)


def render_assembly(stl_dir):
    colors = {"FanModule": (0.85, 0.55, 0.15), "Fan": (0.2, 0.2, 0.2), "T": (0.1, 0.6, 0.9),
              "Controller": (0.2, 0.7, 0.3), "Pipe": (0.6, 0.6, 0.65), "Radiator": (0.92, 0.92, 0.92)}
    shapes = []
    for fn in sorted(os.listdir(stl_dir)):
        name = fn[:-4]
        if name in ("Wall", "Floor"):
            continue
        rgb = next((c for key, c in colors.items() if name.startswith(key)), (0.7, 0.7, 0.7))
        alpha = 0.18 if name == "Radiator" else 1.0
        shapes.append((name, load_stl(os.path.join(stl_dir, fn)), rgb, alpha))
    views = [("assembly_front.png", 20, -65, None),
             ("assembly_below.png", -28, -62, (-60, 640, -100, 200, -95, 140)),
             ("assembly_left_end.png", 12, -150, (-80, 180, -40, 160, -95, 140))]
    for fname, elev, azim, crop in views:
        fig = plt.figure(figsize=(13, 8), dpi=110)
        ax = fig.add_subplot(projection="3d")
        pts = []
        for name, tris, rgb, alpha in shapes:
            if crop:
                c = tris.mean(axis=1)
                keep = ((c[:, 0] > crop[0]) & (c[:, 0] < crop[1]) & (c[:, 1] > crop[2]) & (c[:, 1] < crop[3])
                        & (c[:, 2] > crop[4]) & (c[:, 2] < crop[5]))
                tris = tris[keep]
            if len(tris):
                ax.add_collection3d(shaded(tris, rgb, alpha))
                if name != "Radiator" or not crop:
                    pts.append(tris.reshape(-1, 3))
        set_equal(ax, np.vstack(pts))
        ax.view_init(elev=elev, azim=azim)
        fig.tight_layout()
        fig.savefig(os.path.join(OUT_DIR, fname))
        plt.close(fig)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, RFB_ASSEMBLY_STL_DIR=tmp)
        subprocess.run([FREECADCMD, os.path.join(HERE, "radiator_fan_booster.py")], env=env, check=True,
                       stdout=subprocess.DEVNULL)
        render_parts()
        render_assembly(tmp)
    print("Wrote", ", ".join(sorted(os.listdir(OUT_DIR))))


if __name__ == "__main__":
    sys.exit(main())
