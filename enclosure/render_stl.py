#!/usr/bin/env python3
"""Render an enclosure STL as a PNG, for the README and for eyeballing the print.

Usage:
  python3 render_stl.py [STL] [--out PNG] [--size W,H] [--azimuth A]
                        [--elevation E] [--distance D]
                        [--projection ortho|perspective]
                        [--color R,G,B] [--opacity A] [--colorscheme NAME]
                        [--openscad PATH]

STL defaults to build/enclosure_and_lid.stl (the body and the lid side by side,
as build_parts.sh writes them) and PNG to build/enclosure.png.

The view is set with the OpenSCAD vector camera (--camera=eye_x,y,z,center_x,y,z),
which is the only way to steer the PNG export: a camera() call inside the .scad
file is ignored when the output is a PNG.  The eye is placed on a sphere around
the model's bounding box center, so the two angles are all that matters:

  azimuth    0 looks at the model from +Y (the "front"), 90 from +X
  elevation  how far above the XY plane the eye sits, 0 = level with the model

The default (azimuth 0, elevation 30) shows the body standing upright with the
ring of castellation tabs on its top rim and the lid lying beside it with the
notches those tabs pass through.  Azimuth 0 is deliberate: the two parts are 2 mm
apart along X, and any larger azimuth makes their silhouettes overlap in the
image.  OpenSCAD scales an orthographic PNG export with the camera distance, so
--distance is also the zoom: 120 mm fills the default 800 x 800 frame with a
margin, while 250 mm leaves the model small in the middle of the frame.

The material color is --color when it is given, and otherwise the color that the
--colorscheme palette paints solid objects with, read from the palette JSON that
OpenSCAD ships (the search covers the macOS app bundle and the usual Linux
locations; OPENSCAD_COLOR_SCHEMES points at the directory explicitly).  --opacity
is that color's alpha: 1 is solid, 0.5 lets the background show through the walls,
and 0 renders nothing.  Setting --opacity therefore keeps the palette material
instead of replacing it; if the palette file cannot be found the translucent
material falls back to white.  A translucent render is a quick way to look at the
wall thickness and the tab/notch interface without cutting the model open, which
is what enclosure/render_cutaways.py does with cut planes.

--colorscheme chooses one of OpenSCAD's built-in palettes.  That is the only
configuration-level way to change the background, because the PNG exporter has
no background setting of its own; the palette also supplies the default material
color, which --color overrides.  The script prints the openscad command line it
runs, so a render can be reproduced by hand.

The STL is imported into a one-line OpenSCAD file written to a temp directory,
shifted so that its bounding box center sits at the origin.  OpenSCAD reports a
render status; a missing or unreadable STL, or a PNG that OpenSCAD does not
write, is an error.

Exit codes:
  0  the PNG was written
  1  OpenSCAD failed or wrote nothing
  2  setup error (missing openscad, missing STL, bad arguments)
"""
import argparse
import json
import math
import os
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_DIR = HERE.parent

# The view that reads best as a thumbnail: the body standing upright with the
# ring of castellation tabs on its top rim, and the lid lying beside it.  The
# azimuth is 0 because the two parts sit 2 mm apart along X and any larger
# azimuth makes their silhouettes overlap in the image.  In orthographic
# projection OpenSCAD scales the view with the camera distance, so 120 mm is
# what fills an 800 x 800 frame with a little margin.
DEFAULT_VIEW = dict(azimuth=0.0, elevation=30.0, distance=120.0)


def read_triangles(path):
    """Return the triangle vertices of an STL as a list of (x, y, z) triples.

    Handles both ASCII and binary STL.  OpenSCAD writes ASCII by default, so
    the ASCII branch is the common one.
    """
    data = path.read_bytes()
    if data[:5] == b"solid" and b"vertex" in data[:2000]:
        verts = []
        for line in data.split(b"\n"):
            parts = line.split()
            if parts[:1] == [b"vertex"] and len(parts) >= 4:
                try:
                    verts.append(tuple(float(v) for v in parts[1:4]))
                except ValueError:
                    continue
        return verts

    # Binary STL: 80 byte header, 4 byte triangle count, then 50 bytes per
    # triangle (normal plus three vertices).
    count = struct.unpack("<I", data[80:84])[0]
    verts = []
    for i in range(count):
        chunk = data[84 + 50 * i: 84 + 50 * (i + 1)]
        if len(chunk) < 50:
            break
        vs = struct.unpack("<9f", chunk[4:40])
        verts.extend(((vs[0], vs[1], vs[2]), (vs[3], vs[4], vs[5]), (vs[6], vs[7], vs[8])))
    return verts


def bbox(verts):
    """Return (min, max) corners of a vertex list, or None if it is empty."""
    if not verts:
        return None
    lo = [min(v[i] for v in verts) for i in range(3)]
    hi = [max(v[i] for v in verts) for i in range(3)]
    return tuple(lo), tuple(hi)


def camera(center, azimuth, elevation, distance):
    """Eye and look-at point for a camera `distance` mm from `center`."""
    az, el = math.radians(azimuth), math.radians(elevation)
    eye = (
        center[0] + distance * math.cos(el) * math.sin(az),
        center[1] + distance * math.cos(el) * math.cos(az),
        center[2] + distance * math.sin(el),
    )
    return eye, center


# OpenSCAD ships its render palettes as JSON files, and the entry it paints
# solid objects with is the "face front" color.  The search covers the macOS app
# bundle and the usual Linux/Homebrew locations; OPENSCAD_COLOR_SCHEMES overrides.
SCHEME_DIRS = (
    os.environ.get("OPENSCAD_COLOR_SCHEMES", ""),
    "/Applications/OpenSCAD.app/Contents/Resources/color-schemes/render",
    "/usr/share/openscad/color-schemes/render",
    "/opt/homebrew/share/openscad/color-schemes/render",
)


def parse_hex(text):
    """Turn "#rrggbb" into an (r, g, b) triple in [0,1]."""
    text = text.strip().lstrip("#")
    if len(text) != 6:
        return None
    try:
        return tuple(int(text[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        return None


def palette_color(scheme):
    """Return the color a colorscheme paints solid objects with, or None.

    OpenSCAD's PNG exporter offers no way to ask the palette what its object
    color is, so it is read from the palette file: the "opencsg-face-front"
    entry, which the renderer uses verbatim (verified against a solid render of
    the same scheme).
    """
    if not scheme:
        return None
    slug = scheme.strip().lower().replace(" ", "-")
    for directory in SCHEME_DIRS:
        path = Path(directory) / (slug + ".json")
        if not path.is_file():
            continue
        try:
            colors = json.loads(path.read_text()).get("colors", {})
        except (ValueError, OSError):
            continue
        for key in ("opencsg-face-front", "cgal-face-front", "object"):
            if colors.get(key):
                return parse_hex(colors[key])
    return None


def parse_color(text):
    """Parse an R,G,B triple with each value in [0,1]."""
    try:
        vals = tuple(float(x) for x in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("--color must be R,G,B (values in [0,1])")
    if len(vals) != 3 or any(v < 0 or v > 1 for v in vals):
        raise argparse.ArgumentTypeError(
            "--color must be three values in [0,1], for example 0.2,0.5,0.8")
    return vals


def parse_opacity(text):
    """Parse an alpha value in [0,1]."""
    try:
        alpha = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError("--opacity must be a number in [0,1]")
    if not 0.0 <= alpha <= 1.0:
        raise argparse.ArgumentTypeError("--opacity must be in [0,1]")
    return alpha


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stl", nargs="?", default=str(PROJECT_DIR / "build/enclosure_and_lid.stl"),
                    help="STL to render (default: build/enclosure_and_lid.stl)")
    ap.add_argument("--out", default=str(PROJECT_DIR / "build/enclosure.png"),
                    help="PNG to write (default: build/enclosure.png)")
    ap.add_argument("--size", default="800,800", help="PNG width,height (default: 800,800)")
    ap.add_argument("--azimuth", type=float, default=DEFAULT_VIEW["azimuth"])
    ap.add_argument("--elevation", type=float, default=DEFAULT_VIEW["elevation"])
    ap.add_argument("--distance", type=float, default=DEFAULT_VIEW["distance"],
                    help="eye distance from the model center; in orthographic "
                         "projection this is also the zoom")
    ap.add_argument("--projection", choices=("ortho", "perspective"), default="ortho",
                    help="ortho (default) keeps the outline undistorted; perspective "
                         "adds depth but needs a sensible --distance")
    ap.add_argument("--color", type=parse_color, default=None,
                    help="material color as R,G,B with values in [0,1], "
                         "for example 0.2,0.5,0.8 (default: OpenSCAD's own color)")
    ap.add_argument("--opacity", type=parse_opacity, default=1.0,
                    help="material alpha, 1 = solid, 0 = invisible (default: 1). "
                         "The alpha is applied to --color, or to the --colorscheme "
                         "material color when --color is not given.")
    ap.add_argument("--colorscheme", default=None,
                    help="OpenSCAD colorscheme, which sets the background and the "
                         "material color, for example Starnight or DeepOcean "
                         "(default: OpenSCAD's own, Cornfield)")
    ap.add_argument("--openscad", default=os.environ.get("OPENSCAD", "openscad"))
    args = ap.parse_args()

    stl = Path(args.stl)
    if not stl.is_file():
        print("ERROR: no such STL: %s" % stl, file=sys.stderr)
        return 2

    verts = read_triangles(stl)
    bounds = bbox(verts)
    if bounds is None:
        print("ERROR: %s has no triangles" % stl, file=sys.stderr)
        return 2

    (lo, hi) = bounds
    center = tuple((a + b) / 2.0 for a, b in zip(lo, hi))
    size = tuple(b - a for a, b in zip(lo, hi))
    # The model is translated below, so its center is at the origin and the
    # camera looks at the origin.
    eye, look = camera((0.0, 0.0, 0.0), args.azimuth, args.elevation, args.distance)

    if shutil.which(args.openscad) is None:
        print("ERROR: openscad not found: %s" % args.openscad, file=sys.stderr)
        return 2

    # OpenSCAD paints an imported STL with the palette's own material color, and
    # color() is the only way to get alpha into the render.  So a requested
    # opacity means restating the palette color rather than replacing it, which
    # is what keeps --opacity from flattening the material to white.
    material = ""
    color = args.color
    if color is None and args.opacity != 1.0:
        color = palette_color(args.colorscheme)
        if color is None:
            print("warning: cannot read the material color of colorscheme %s; "
                  "the translucent material will be white"
                  % (args.colorscheme or "Cornfield"), file=sys.stderr)
            color = (1.0, 1.0, 1.0)
    if args.color is not None or args.opacity != 1.0:
        material = "color([%.4f, %.4f, %.4f, %.4f])\n" % (color[0], color[1], color[2], args.opacity)

    scad = material + "translate([%.3f, %.3f, %.3f])\nimport(\"%s\");\n" % (
        -center[0], -center[1], -center[2], stl.resolve())

    tmp = tempfile.mkdtemp(prefix="render_stl_")
    scad_path = Path(tmp) / "view.scad"
    try:
        scad_path.write_text(scad)
        cmd = [
            args.openscad,
            "-o", str(args.out),
            "--imgsize=%s" % args.size,
            "--projection=%s" % ("o" if args.projection == "ortho" else "p"),
            "--camera=%.3f,%.3f,%.3f,%.3f,%.3f,%.3f" % (eye[0], eye[1], eye[2], look[0], look[1], look[2]),
        ]
        if args.colorscheme:
            cmd.append("--colorscheme=%s" % args.colorscheme)
        cmd.append(str(scad_path))
        print("command:  %s" % " ".join(shlex.quote(part) for part in cmd))
        r = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("model:  %s" % stl)
    print("size:   %.1f x %.1f x %.1f mm" % size)
    print("view:   azimuth %.1f, elevation %.1f, %s projection" % (
        args.azimuth, args.elevation, args.projection))
    if args.color is None and args.opacity == 1.0:
        print("material: colorscheme default, solid")
    else:
        print("material: %.3f,%.3f,%.3f at opacity %.2f" % (color[0], color[1], color[2], args.opacity))
    for line in (r.stdout + r.stderr).splitlines():
        line = line.strip()
        if line.startswith(("Compiling", "Rendering", "Geometry", "Object", "File saved")):
            print("      " + line)

    if r.returncode != 0 or not Path(args.out).is_file():
        print(r.stdout + r.stderr, file=sys.stderr)
        print("ERROR: openscad wrote no PNG", file=sys.stderr)
        return 1

    print("wrote:  %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
