#!/usr/bin/env python3
"""Build a production .kicad_pcb with all copper zones filled.

The committed board file intentionally carries no zone fill data: the
filled_polygon entries are regenerated for every production run instead of
being committed to the repository. This script loads the board, refills
every copper zone, and writes the result to build/<board name>.kicad_pcb.
That output is the file to use for gerber export and fabrication.

(The test suite's DRC check already refills zones in memory via
kicad-cli's --refill-zones flag; this script persists the same result
into a file.)

Usage:
  scripts/build_production_pcb.py [--project-dir DIR] [--board FILE] [--out FILE]

Defaults: the project root is the parent of this script's directory, the
board is the single .kicad_pcb file at the project root, and the output is
build/<board name> under the project root.

The script must run under the Python that ships inside the KiCad app
bundle, because it imports pcbnew. When started with a plain python3 that
lacks the module, it re-executes itself with the bundle interpreter,
looked up under $KICAD_APP_DIR (default /Applications/KiCad).

pcbnew's C++ layer writes a wx traits assert and wx registration messages
straight to the process's file descriptors while a board is loaded or
saved. Those calls run with the C-level stdout and stderr redirected to
/dev/null; real failures are still caught by the explicit checks (load
result, save result, reload verification) that run with the streams
restored.

Exit codes:
  0  board built and verified
  1  build or verification failure
  2  setup error (board not found, no KiCad bundle Python)
"""
import argparse
import contextlib
import glob
import os
import sys


def die_setup(msg):
    print("error: %s" % msg, file=sys.stderr)
    sys.exit(2)


def die_build(msg):
    print("error: %s" % msg, file=sys.stderr)
    sys.exit(1)


class BuildError(Exception):
    pass


def kicad_python():
    app_dir = os.environ.get("KICAD_APP_DIR", "/Applications/KiCad")
    pattern = os.path.join(
        app_dir, "KiCad.app", "Contents", "Frameworks",
        "Python.framework", "Versions", "*", "bin", "python3")
    for path in sorted(glob.glob(pattern), reverse=True):
        if os.access(path, os.X_OK):
            return path
    return None


try:
    import pcbnew
except ImportError:
    interpreter = kicad_python()
    if interpreter is None:
        die_setup("pcbnew is not importable and no KiCad bundle Python was found "
                  "under KICAD_APP_DIR (default /Applications/KiCad)")
    os.execv(interpreter, [interpreter, os.path.abspath(__file__)] + sys.argv[1:])


@contextlib.contextmanager
def c_streams_quiet():
    """Silence the C-level stdout and stderr while pcbnew's C++ layer is
    active (see the module docstring)."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved_out, saved_err = os.dup(1), os.dup(2)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, 1)
    os.dup2(devnull, 2)
    os.close(devnull)
    try:
        yield
    finally:
        os.dup2(saved_out, 1)
        os.dup2(saved_err, 2)
        os.close(saved_out)
        os.close(saved_err)


def count_filled_polygons(path):
    with open(path) as f:
        return f.read().count("filled_polygon")


def discover_board(project_dir):
    boards = sorted(glob.glob(os.path.join(project_dir, "*.kicad_pcb")))
    if not boards:
        die_setup("no .kicad_pcb file at project root: %s" % project_dir)
    if len(boards) > 1:
        die_setup("multiple .kicad_pcb files at project root: %s "
                  "(pass --board to choose)" % ", ".join(os.path.basename(b) for b in boards))
    return boards[0]


def build(board_path, out_path):
    """Load the board, refill all copper zones, save to out_path.

    Returns a list of (name, net, layer, filled, polygon_count) tuples,
    one per zone. Raises BuildError on failure.
    """
    zone_reports = []
    with c_streams_quiet():
        board = pcbnew.LoadBoard(board_path)
        if board is None:
            raise BuildError("failed to load board: %s" % board_path)
        zones = list(board.Zones())
        if zones:
            pcbnew.ZONE_FILLER(board).Fill(zones)
            for zone in zones:
                polys = zone.GetFilledPolysList(zone.GetLayer())
                zone_reports.append(
                    (zone.GetZoneName(), zone.GetNetname(), zone.GetLayerName(),
                     zone.IsFilled(), polys.OutlineCount()))
        saved = board.Save(out_path)
    if saved is False or not os.path.isfile(out_path):
        raise BuildError("save failed: output file was not written: %s" % out_path)

    # Reload the written file and verify the fills persisted.
    with c_streams_quiet():
        reloaded = pcbnew.LoadBoard(out_path)
    if reloaded is None:
        raise BuildError("verification failed: could not reload %s" % out_path)
    reloaded_zones = list(reloaded.Zones())
    if len(reloaded_zones) != len(zone_reports):
        raise BuildError("output has %d zones, expected %d"
                         % (len(reloaded_zones), len(zone_reports)))
    for zone in reloaded_zones:
        if not zone.IsFilled():
            raise BuildError("output zone %s is not filled" % zone.GetZoneName())
    if zone_reports and count_filled_polygons(out_path) == 0:
        raise BuildError("output file contains no filled_polygon data")

    return zone_reports


def main():
    default_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    parser = argparse.ArgumentParser(
        description="Build a production .kicad_pcb with all copper zones filled.")
    parser.add_argument("--project-dir", default=default_root,
                        help="project root (default: parent of this script's directory)")
    parser.add_argument("--board", default=None,
                        help="input .kicad_pcb (default: the one at the project root)")
    parser.add_argument("--out", default=None,
                        help="output path (default: build/<board name> under the project root)")
    args = parser.parse_args()

    if not os.path.isdir(args.project_dir):
        die_setup("project directory not found: %s" % args.project_dir)
    board_path = args.board or discover_board(args.project_dir)
    if not os.path.isfile(board_path):
        die_setup("board file not found: %s" % board_path)
    out_path = args.out or os.path.join(args.project_dir, "build",
                                        os.path.basename(board_path))

    print("== Production PCB build ==")
    print("kicad:   %s" % pcbnew.GetBuildVersion())
    print("board:   %s" % board_path)
    print("out:     %s" % out_path)

    if out_path == board_path:
        print("note: overwriting the board file in place")
    prior = count_filled_polygons(board_path)
    if prior:
        print("note: input already contains %d filled_polygon entries (stale fills); refilling" % prior)

    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    try:
        zone_reports = build(board_path, out_path)
    except BuildError as exc:
        die_build(str(exc))

    if zone_reports:
        for name, net, layer, filled, count in zone_reports:
            if not filled:
                die_build("zone %s (net %s, layer %s) did not fill" % (name, net, layer))
            print("filled:  %s (net %s, %s), %d filled polygons" % (name, net, layer, count))
    else:
        print("no copper zones on board; wrote a copy without fills")

    print("wrote:   %s (%d filled_polygon entries)" % (out_path, count_filled_polygons(out_path)))
    print("== Result: OK ==")


if __name__ == "__main__":
    main()
