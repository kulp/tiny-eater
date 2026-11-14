#!/usr/bin/env python3
"""Check that the castellation tabs fit the lid's notches.

The ends of the four enclosure walls carry tabs that stick out by cast_d, and
the lid is a plate of uniform thickness with matching notches cut out of its rim
that those tabs pass through. This script builds CSG intersections with OpenSCAD
(see enclosure.scad for the geometry) and measures, in cubic millimetres:

  1. the seated overlap of lid and enclosure: it must be zero, otherwise the
     notches do not clear the tabs;
  2. the volume of the tabs and of the notches, so the interface really exists
     on both sides;
  3. that the lid is still one thickness: nothing may cross the mating plane
     (x = 0), and no tab may poke through the outside of the lid.

Volumes come from the exported ASCII STL via the divergence theorem, so the
only dependencies are OpenSCAD and the standard library.

Usage:
  python3 check_castellations.py [--openscad PATH] [--out DIR] [--verbose]
Exit status is 0 when every check passes, 1 otherwise.
"""
import argparse
import atexit
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCAD = HERE / "enclosure.scad"

CONTACT_EPS = 0.01   # mm^3: anything above this is solid material overlapping
MIN_TAB = 20.0       # mm^3: wall material the tabs must add
MIN_NOTCH = 20.0     # mm^3: lid area the notches must remove


def run_scad(scad_text, out_stl, openscad):
    """Render scad_text to out_stl and return its facets as vertex triples."""
    src = out_stl.with_suffix(".scad")
    src.write_text(scad_text)
    proc = subprocess.run(
        [openscad, "-o", str(out_stl), str(src)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        if "top level object is empty" in proc.stderr:
            # A CSG intersection with nothing in common: zero overlap.
            return []
        raise RuntimeError(f"openscad failed on {src}: {proc.stderr.strip()}")
    text = out_stl.read_text()
    if not text.startswith("solid"):
        raise RuntimeError(f"{out_stl} is not an ASCII STL")
    verts = []
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] == "vertex":
            verts.append(tuple(float(f) for f in fields[1:4]))
    if len(verts) % 3:
        raise RuntimeError(f"{out_stl} has a partial facet")
    return [verts[i:i + 3] for i in range(0, len(verts), 3)]


def volume(facets):
    """Volume of a closed mesh, via the divergence theorem."""
    total = 0.0
    for a, b, c in facets:
        total += (a[0] * (b[1] * c[2] - b[2] * c[1])
                  - a[1] * (b[0] * c[2] - b[2] * c[0])
                  + a[2] * (b[0] * c[1] - b[1] * c[0])) / 6.0
    return abs(total)


def bounding_box(facets):
    xs = [p[0] for tri in facets for p in tri]
    ys = [p[1] for tri in facets for p in tri]
    zs = [p[2] for tri in facets for p in tri]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def render_scad(modules):
    """A scad file rendering the given enclosure.scad module calls."""
    return f"use <{SCAD}>;\n" + "\n".join(f"{m};" for m in modules) + "\n"


def intersection_scad(first, second):
    """A scad file intersecting two module calls."""
    return (
        f"use <{SCAD}>;\n"
        "intersection() {\n"
        f"  {first};\n"
        f"  {second};\n"
        "}\n"
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--openscad", default="openscad", help="openscad executable")
    ap.add_argument("--out", default=None, help="keep the rendered STLs in DIR")
    ap.add_argument("--verbose", action="store_true", help="print every measurement")
    args = ap.parse_args()

    if not SCAD.exists():
        print(f"FAIL: {SCAD} not found", file=sys.stderr)
        return 1

    work = Path(args.out) if args.out else Path(tempfile.mkdtemp(prefix="castellations-"))
    work.mkdir(parents=True, exist_ok=True)
    if not args.out:
        atexit.register(shutil.rmtree, work, ignore_errors=True)

    enclosure = run_scad(render_scad(["enclosure()"]),
                         work / "enclosure.stl", args.openscad)
    lid = run_scad(render_scad(["lid()"]), work / "lid.stl", args.openscad)
    enclosure_plain = run_scad(render_scad(["enclosure(false)"]),
                               work / "enclosure_plain.stl", args.openscad)
    lid_plain = run_scad(render_scad(["lid(false)"]),
                         work / "lid_plain.stl", args.openscad)

    enc_x_min, _, _, _, _, _ = bounding_box(enclosure)
    lid_x_min, lid_x_max, _, _, _, _ = bounding_box(lid)

    results = []

    def record(name, value, expect, ok):
        results.append((name, value, ok(value)))
        if args.verbose:
            print(f"{name:34s} {value:9.3f}  (expect {expect})")

    def measure(name, scad_text, expect, ok):
        out = work / f"{name.replace(' ', '_')}.stl"
        record(name, volume(run_scad(scad_text, out, args.openscad)), expect, ok)

    # 1. Seated: the tabs must pass through the notches without touching anything.
    measure("seated overlap",
            intersection_scad("enclosure()", "lid()"),
            "< 0.01 mm^3", lambda v: v < CONTACT_EPS)

    # 2. Both sides of the interface must actually be there.
    record("tab volume", volume(enclosure) - volume(enclosure_plain),
           "> 20 mm^3", lambda v: v > MIN_TAB)
    record("notch volume", volume(lid_plain) - volume(lid),
           "> 20 mm^3", lambda v: v > MIN_NOTCH)

    # 3. The lid stays a plate of uniform thickness: it must not cross the mating
    # plane, and the tabs must be fully inside the lid's thickness.
    record("lid past the mating plane", lid_x_max, "<= 0 mm",
           lambda v: v <= 0.0)
    record("tab short of the lid's outer face", enc_x_min - lid_x_min, ">= 0 mm",
           lambda v: v >= 0.0)
    record("tabs reach into the lid", -enc_x_min, "> 0 mm",
           lambda v: v > 0.0)

    failed = [(name, value) for name, value, ok in results if not ok]
    print(f"lid volume          {volume(lid):9.3f} mm^3")
    print(f"enclosure volume    {volume(enclosure):9.3f} mm^3")
    for name, value, ok in results:
        unit = "mm^3" if "volume" in name or "overlap" in name else "mm"
        print(f"{'ok' if ok else 'FAIL':4s} {name:34s} {value:9.3f} {unit}")
    if failed:
        print(f"FAIL: {len(failed)} check(s) failed")
        return 1
    print("PASS: the castellations seat cleanly")
    return 0


if __name__ == "__main__":
    try:
        code = main()
    except RuntimeError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        code = 1
    sys.exit(code)
