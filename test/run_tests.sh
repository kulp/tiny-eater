#!/usr/bin/env bash
# Run schematic and PCB design checks on a KiCad project.
#
# Usage:
#   test/run_tests.sh [PROJECT_DIR]
#
# PROJECT_DIR defaults to the project root (the parent of this script's
# directory). The directory must contain exactly one .kicad_sch file and one
# .kicad_pcb file at its top level.
#
# Checks:
#   1. DRC: kicad-cli pcb drc (violations, unconnected items, schematic parity).
#   2. ERC: kicad-cli sch erc (errors and warnings).
#   3. Connectivity/footprint parity: the schematic netlist is compared with
#      the PCB file (missing/extra footprints, duplicate references, pad net
#      mismatches, missing pads).
#
# Exit codes:
#   0  all checks report no violations
#   1  one or more checks report violations
#   2  setup error (missing kicad-cli, missing files, unreadable reports)
#
# Machine-readable JSON reports are written to test/out/.
# kicad-cli defaults to the macOS KiCad app bundle; override with KICAD_CLI.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"
KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
PYTHON="${PYTHON:-python3}"
OUT_DIR="$SCRIPT_DIR/out"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

command -v "$KICAD_CLI" >/dev/null || die "kicad-cli not found or not executable at: $KICAD_CLI"
command -v "$PYTHON" >/dev/null 2>&1 || die "python interpreter not found: $PYTHON"
[ -d "$PROJECT_DIR" ] || die "project directory not found: $PROJECT_DIR"
mkdir -p "$OUT_DIR"

SCH="$(find "$PROJECT_DIR" -maxdepth 1 -name '*.kicad_sch' -print -quit)"
PCB="$(find "$PROJECT_DIR" -maxdepth 1 -name '*.kicad_pcb' -print -quit)"
[ -n "$SCH" ] || die "no .kicad_sch file found in: $PROJECT_DIR"
[ -n "$PCB" ] || die "no .kicad_pcb file found in: $PROJECT_DIR"

echo "== KiCad design checks =="
echo "project:   $PROJECT_DIR"
echo "schematic: $(basename "$SCH")"
echo "pcb:       $(basename "$PCB")"
echo

drc_exit=1
erc_exit=1
conn_exit=1

# --- 1/3: DRC ---------------------------------------------------------------
echo "[1/3] PCB DRC (kicad-cli pcb drc)"
"$KICAD_CLI" pcb drc --format json --severity-error --severity-warning \
    --schematic-parity --exit-code-violations \
    --refill-zones \
    -o "$OUT_DIR/drc.json" "$PCB"
drc_cli=$?
if [ ! -f "$OUT_DIR/drc.json" ]; then
    die "kicad-cli pcb drc exited $drc_cli without writing a report"
fi
"$PYTHON" "$SCRIPT_DIR/check_drc_erc.py" --kind drc \
    "$OUT_DIR/drc.json" --kicad-exit "$drc_cli"
drc_exit=$?
echo

# --- 2/3: ERC ---------------------------------------------------------------
echo "[2/3] Schematic ERC (kicad-cli sch erc)"
"$KICAD_CLI" sch erc --format json --severity-error --severity-warning \
    --exit-code-violations \
    -o "$OUT_DIR/erc.json" "$SCH"
erc_cli=$?
if [ ! -f "$OUT_DIR/erc.json" ]; then
    die "kicad-cli sch erc exited $erc_cli without writing a report"
fi
"$PYTHON" "$SCRIPT_DIR/check_drc_erc.py" --kind erc \
    "$OUT_DIR/erc.json" --kicad-exit "$erc_cli"
erc_exit=$?
echo

# --- 3/3: connectivity / footprint parity -----------------------------------
echo "[3/3] Connectivity/footprint parity (netlist vs PCB)"
if ! "$KICAD_CLI" sch export netlist --format kicadsexpr \
        -o "$OUT_DIR/netlist.net" "$SCH" >/dev/null; then
    die "kicad-cli sch export netlist failed on: $SCH"
fi
"$PYTHON" "$SCRIPT_DIR/check_connectivity.py" "$OUT_DIR/netlist.net" "$PCB"
conn_exit=$?
echo

# --- summary ------------------------------------------------------------------
echo "== Summary =="
for name in drc erc conn; do
    case "$name" in
        drc) label="DRC" ;;
        erc) label="ERC" ;;
        conn) label="connectivity/footprint" ;;
    esac
    var="${name}_exit"
    code="${!var}"
    if [ "$code" -eq 0 ]; then
        echo "  PASS  $label"
    else
        echo "  FAIL  $label (exit $code)"
    fi
done

if [ "$drc_exit" -eq 0 ] && [ "$erc_exit" -eq 0 ] && [ "$conn_exit" -eq 0 ]; then
    echo "== Result: PASS (no violations found) =="
    exit 0
fi
echo "== Result: FAIL (violations found, see reports above and $OUT_DIR) =="
exit 1
