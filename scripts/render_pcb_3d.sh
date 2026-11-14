#!/usr/bin/env bash
# Render the PCB in 3D (front and back) using KiCad's own 3D view.
#
# Usage:
#   scripts/render_pcb_3d.sh [PROJECT_DIR]
#
# PROJECT_DIR defaults to the project root (the parent of this script's
# directory).
#
# The script invokes `kicad-cli pcb render`, which ray-traces the board the
# same way KiCad's 3D viewer does, and writes one PNG per side to build/ under
# the project root:
#   - <board>_3d_front.png  the component (top) side,  --side top
#   - <board>_3d_back.png   the solder (bottom) side,  --side bottom
#                        (this is the side carrying the silkscreen resistor table)
#
# By default the script renders the production board in build/ (the output of
# build_production_pcb.py, which carries filled copper zones); if no board is
# present there it falls back to the committed board at the project root.
#
# Both views are tilted -30 degrees about the X axis so the board reads in 3D
# instead of as a flat top-down image.
#
# Exit codes:
#   0  both renders succeeded
#   2  setup error (missing kicad-cli, missing board, or a render failed)
#
# kicad-cli defaults to the macOS KiCad app bundle; override with KICAD_CLI.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"
KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
OUT_DIR="$PROJECT_DIR/build"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

command -v "$KICAD_CLI" >/dev/null || die "kicad-cli not found or not executable at: $KICAD_CLI"
[ -d "$PROJECT_DIR" ] || die "project directory not found: $PROJECT_DIR"
mkdir -p "$OUT_DIR"

# Prefer the production board in build/ (filled copper zones); fall back to
# the committed board at the project root if no production build is present.
PCB="$(find "$OUT_DIR" -maxdepth 1 -name '*.kicad_pcb' -print -quit)"
if [ -z "$PCB" ]; then
    PCB="$(find "$PROJECT_DIR" -maxdepth 1 -name '*.kicad_pcb' -print -quit)"
fi
[ -n "$PCB" ] || die "no .kicad_pcb file found in build/ or the project root"
BOARD="$(basename "$PCB" .kicad_pcb)"

echo "== KiCad 3D renders =="
echo "project: $PROJECT_DIR"
echo "pcb:     ${PCB#"$PROJECT_DIR"/}"
echo "output:  $OUT_DIR"
echo

# Render one side. $1 is the output label (front/back), $2 the --side value.
render_side() {
    local label="$1" side="$2"
    local out="$OUT_DIR/${BOARD}_3d_${label}.png"
    echo "[render] $label (--side $side) -> $(basename "$out")"
    "$KICAD_CLI" pcb render \
        -o "$out" \
        --define-var KIPRJMOD="$PROJECT_DIR" \
        --side "$side" \
        --rotate '-30,0,0' \
        --quality high \
        --background opaque \
        --use-board-stackup-colors \
        --zoom "${ZOOM:-0.7}" \
        "$PCB" || die "kicad-cli pcb render failed for the $label side"
}

render_side front top
render_side back bottom

echo
echo "Wrote:"
echo "  $OUT_DIR/${BOARD}_3d_front.png"
echo "  $OUT_DIR/${BOARD}_3d_back.png"
