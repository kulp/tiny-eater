#!/usr/bin/env python3
"""Render PNG cutaways of the attenuator enclosure.

For each view, generates a small OpenSCAD file that imports the enclosure()
and lid() modules from enclosure.scad, subtracts a half-space box to reveal
the interior, and also shows the physical PCB as a translucent box in the
channel (so its position and the way the RCA bores locate it are visible).
Each view is rendered to a PNG with the openscad CLI using a vector camera
(eye + look-at center) passed via --camera; the in-file camera() module is
ignored for PNG export, so the view is set on the command line. Intermediate
.scad files are written to a temp dir and removed on exit; pass --keep to
retain them alongside the PNGs.

The cut planes, cameras, and board position use coordinates that match
enclosure.scad: the box spans X[0, 31.3] (the lid extends to X = -1.5),
Y[0, 26.8], Z[0, 19.6]; the cavity floor is at Z = wall = 1.5; the RCA barrel
axis is at (Y = 13.4, Z = 9.6); the board is 29.0 x 23.0 x 1.6.

Usage:
  python3 render_cutaways.py [--out DIR] [--size W,H] [--keep]
                             [--no-board] [--board-color R,G,B,A]
                             [--openscad PATH]
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENCLOSURE = HERE / "enclosure.scad"

# Physical PCB box: origin (X, Y, Z) and size (X, Y, Z). It sits on the cavity
# floor (Z = wall = 1.5), centered in the channel with the board's Y center on
# the RCA barrel axis (Y = 13.4).
BOARD = (0.4, 1.9, 1.5, 29.0, 23.0, 1.6)

# Default board appearance: a semi-transparent blue that reads against the
# green enclosure.
DEFAULT_BOARD_COLOR = (0.15, 0.35, 0.85, 0.4)

# Each view: a "cut" box subtracted from the parts (revealing the interior on
# the kept side of the plane) and a "cam" (eye + look-at center, the OpenSCAD
# vector camera).
VIEWS = [
    {
        # Mid-length section: remove the front half (Y > 13.4), then look
        # straight at the cut plane along -Y. Shows the board in the channel,
        # the lid's castellations seated in the wall sockets, and both RCA bores
        # (J1 in the lid, J2 in the right wall).
        "name": "section-long-front",
        "cut": dict(origin=(-5.0, 13.4, -5.0), size=(41.3, 26.8, 29.6)),
        "cam": dict(eye=(14.9, 90.0, 9.8), center=(14.9, 13.4, 9.8)),
    },
    {
        # Same section, viewed isometrically for 3-D context.
        "name": "section-long-iso",
        "cut": dict(origin=(-5.0, 13.4, -5.0), size=(41.3, 26.8, 29.6)),
        "cam": dict(eye=(65.0, 63.4, 44.0), center=(14.9, 13.4, 9.8)),
    },
    {
        # Mid-height section: remove the top half (Z > 9.8), then look
        # straight down the Z axis at the cut plane. The board is below the cut
        # plane, so it shows whole as a translucent footprint in the channel.
        "name": "section-top",
        "cut": dict(origin=(-5.0, -5.0, 9.8), size=(41.3, 36.8, 19.6)),
        "cam": dict(eye=(14.9, 13.4, 90.0), center=(14.9, 13.4, 9.8)),
    },
]

SCAD_TMPL = """\
use <{enclosure}>;

// The physical PCB, rendered translucent so it is visible in the cutaway.
module board() {{
  translate([{bx:g}, {by:g}, {bz:g}])
    cube([{bw:g}, {bh:g}, {bd:g}]);
}}

// Solid cutaway of the enclosure + lid: subtract a half-space to reveal the
// interior.
module housing() {{
  difference() {{
    union() {{
      enclosure();
      lid();
    }}
    translate([{ox:g}, {oy:g}, {oz:g}])
      cube([{sx:g}, {sy:g}, {sz:g}]);
  }}
}}
housing();
{board_render}"""


def board_scad(color, origin, size):
    r, g, b, a = color
    return (
        "// Translucent PCB in the channel, cut by the same half-space.\n"
        "color([{r:g}, {g:g}, {b:g}, {a:g}]) difference() {{\n"
        "  board();\n"
        "  translate([{ox:g}, {oy:g}, {oz:g}])\n"
        "    cube([{sx:g}, {sy:g}, {sz:g}]);\n"
        "}}\n"
    ).format(r=r, g=g, b=b, a=a,
             ox=origin[0], oy=origin[1], oz=origin[2],
             sx=size[0], sy=size[1], sz=size[2])


def scad_text(view, board_on, board_color):
    o, s = view["cut"]["origin"], view["cut"]["size"]
    board_render = board_scad(board_color, o, s) if board_on else ""
    return SCAD_TMPL.format(
        enclosure=ENCLOSURE,
        bx=BOARD[0], by=BOARD[1], bz=BOARD[2],
        bw=BOARD[3], bh=BOARD[4], bd=BOARD[5],
        ox=o[0], oy=o[1], oz=o[2], sx=s[0], sy=s[1], sz=s[2],
        board_render=board_render,
    )


def render(openscad, scad_path, png_path, size, cam):
    e, c = cam["eye"], cam["center"]
    cmd = [
        openscad, "-o", str(png_path),
        "--imgsize={0},{1}".format(size[0], size[1]),
        "--camera={0},{1},{2},{3},{4},{5}".format(
            e[0], e[1], e[2], c[0], c[1], c[2]),
        str(scad_path),
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def parse_board_color(text):
    try:
        vals = tuple(float(x) for x in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(
            "--board-color must be R,G,B,A (e.g. 0.15,0.35,0.85,0.4)")
    if len(vals) != 4 or any(v < 0 or v > 1 for v in vals):
        raise argparse.ArgumentTypeError(
            "--board-color must be four values in [0,1]: R,G,B,A")
    return vals


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--out", type=Path, default=HERE / "cutaways",
                    help="output directory for the PNGs (default: ./cutaways)")
    ap.add_argument("--size", default="1280,960",
                    help="PNG size as W,H (default: 1280,960)")
    ap.add_argument("--keep", action="store_true",
                    help="keep the generated .scad files next to the PNGs")
    ap.add_argument("--no-board", action="store_true",
                    help="render the enclosure/lid only, without the PCB")
    ap.add_argument("--board-color", default=None, type=parse_board_color,
                    metavar="R,G,B,A",
                    help="translucent PCB color (default: 0.15,0.35,0.85,0.4)")
    ap.add_argument("--openscad", default="openscad",
                    help="openscad executable (default: openscad)")
    args = ap.parse_args()

    if not ENCLOSURE.exists():
        sys.exit("error: %s not found" % ENCLOSURE)

    try:
        w, h = (int(x) for x in args.size.split(","))
    except ValueError:
        sys.exit("error: --size must be W,H (e.g. 1280,960)")

    board_on = not args.no_board
    board_color = args.board_color or DEFAULT_BOARD_COLOR

    args.out.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.TemporaryDirectory(prefix="enclosure-cutaway-")
    scad_dir = args.out if args.keep else Path(tmp.name)

    failures = 0
    try:
        for view in VIEWS:
            scad_path = scad_dir / (view["name"] + ".scad")
            png_path = args.out / (view["name"] + ".png")
            scad_path.write_text(scad_text(view, board_on, board_color))
            r = render(args.openscad, scad_path, png_path, (w, h), view["cam"])
            if r.returncode == 0:
                print("OK   %s" % png_path)
            else:
                failures += 1
                print("FAIL %s\n%s" % (view["name"], r.stderr), file=sys.stderr)
    finally:
        if not args.keep:
            tmp.cleanup()

    if failures:
        sys.exit("error: %d/%d views failed" % (failures, len(VIEWS)))
    print("Rendered %d cutaway PNG(s) to %s%s" % (
        len(VIEWS), args.out,
        "" if board_on else " (no board)"))


if __name__ == "__main__":
    main()
