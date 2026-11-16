#!/usr/bin/env bash
# Write the two enclosure parts as separate STL files, oriented for printing.
#
# Usage:
#   enclosure/build_parts.sh [OUT_DIR]
#
# OUT_DIR defaults to <project root>/build. Outputs:
#   build/enclosure.stl             the enclosure body
#   build/lid.stl                   the castellated lid
#   build/enclosure_and_lid.stl     both parts side by side in one file, ready
#                                   for a single print job
#
# Both parts are turned so the castellation interface faces up (+Z): the body
# stands on its solid far end wall with the sockets opening at the top, and the
# lid lies flat on its plate with the teeth pointing up. In that orientation the
# RCA barrel bores run vertically with their outer openings downward. The
# rotations live in enclosure.scad as enclosure_print(), lid_print() and
# print_all().
#
# OpenSCAD renders both parts into a single file by default, so the script writes
# a wrapper .scad per part that `use`s enclosure.scad and calls just that module.
#
# Exit codes:
#   0  all three files written
#   1  openscad failed
#   2  setup error (missing openscad, missing enclosure.scad, empty output)
#
# OPENSCAD defaults to `openscad`; override with the environment variable.

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SCAD="$SCRIPT_DIR/enclosure.scad"
OUT_DIR="${1:-$PROJECT_DIR/build}"
OPENSCAD="${OPENSCAD:-openscad}"

die() {
    echo "ERROR: $*" >&2
    exit 2
}

command -v "$OPENSCAD" >/dev/null 2>&1 || die "openscad not found: $OPENSCAD"
[ -f "$SCAD" ] || die "enclosure source not found: $SCAD"
mkdir -p "$OUT_DIR"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Bounding box of an ASCII STL, as W x H x D in millimetres.
dims() {
    awk '/vertex/ {
        for (i = 1; i <= 3; i++) {
            v = $(i + 1)
            if (mn[i] == "" || v < mn[i]) mn[i] = v
            if (mx[i] == "" || v > mx[i]) mx[i] = v
        }
    }
    END { printf "%.1f x %.1f x %.1f mm", mx[1] - mn[1], mx[2] - mn[2], mx[3] - mn[3] }' "$1"
}

# Render one part. $1 is the output label, $2 the enclosure.scad module to draw.
build_part() {
    local label="$1" module="$2"
    local wrapper="$TMP_DIR/$label.scad" out="$OUT_DIR/$label.stl" log="$TMP_DIR/$label.log"

    cat > "$wrapper" <<EOF
use <$SCAD>;
$module();
EOF

    echo "[stl] $label"
    if ! "$OPENSCAD" -o "$out" "$wrapper" > "$log" 2>&1; then
        cat "$log" >&2
        die "openscad failed rendering $module"
    fi
    grep -E "Status:|Genus:" "$log" | sed 's/^ *//' | sed 's/^/      /'
    [ -s "$out" ] || die "openscad wrote no geometry for $module"
    echo "      size:   $(dims "$out")"
}

build_part enclosure enclosure_print
build_part lid lid_print
build_part enclosure_and_lid print_all

echo
echo "Wrote:"
echo "  $OUT_DIR/enclosure.stl"
echo "  $OUT_DIR/lid.stl"
echo "  $OUT_DIR/enclosure_and_lid.stl"
