# Design checks

Automated design checks for this project, driven by `kicad-cli`, OpenSCAD and
Python. The entry point is `test/run_tests.sh`; it prints a human-readable report
to stdout, plus machine-readable JSON reports in `test/out/`.

## Usage

```
./test/run_tests.sh [PROJECT_DIR]
```

`PROJECT_DIR` defaults to the repository root (the parent of `test/`). The
directory must contain exactly one `.kicad_sch` file and one `.kicad_pcb`
file at its top level.

## Checks

1. **PCB DRC** - `kicad-cli pcb drc` with `--severity-error
   --severity-warning --schematic-parity --refill-zones`. Reports violations,
   unconnected items, and schematic-parity mismatches (e.g. a pad net that
   does not match the net in the schematic, a missing footprint, an extra
   footprint). `--refill-zones` is required: without it the GND zone copper
   is stale and the GND pads are reported as unconnected.
2. **Schematic ERC** - `kicad-cli sch erc` with `--severity-error
   --severity-warning`. Reports errors and warnings.
3. **Connectivity/footprint parity** - exports the schematic netlist
   (`kicad-cli sch export netlist`) and compares it with the PCB file:
   missing footprints, extra footprints, duplicate references, pad/net
   mismatches, and missing pads.
4. **Enclosure fit** - runs `enclosure/check_castellations.py`, which renders
   the enclosure and lid with OpenSCAD and measures that the wall tabs pass
   through the lid notches with no contact, that the interface exists on both
   parts, and that the lid is a single uniform thickness with every tab inside
   it. The check is skipped (reported as SKIP, not as a failure) when the project
   directory has no `enclosure/` directory.

Each kicad-cli run also uses `--exit-code-violations`, and
`check_drc_erc.py` cross-checks that exit code against the JSON report: a
disagreement is reported as a finding of its own.

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | all checks that ran report no violations |
| 1    | one or more checks report violations |
| 2    | setup error (missing kicad-cli, missing project files, unreadable report) |

A run against the repository root exits 1 on a fresh clone: ERC and DRC each
report two warnings, one per RCA symbol, because `attenuator.pretty/` is not
committed and the RCJ-044 footprint has to be downloaded by hand. Once
`tools/fetch_footprints.py` has populated the library, the design is expected
to report no violations and the suite exits 0.

## Files

| File | Role |
|------|------|
| `run_tests.sh`       | entry point; orchestrates the checks |
| `check_drc_erc.py`   | parses the DRC/ERC JSON reports and prints findings |
| `check_connectivity.py` | netlist vs PCB parity checker |
| `out/`               | generated reports (`drc.json`, `erc.json`, `netlist.net`); regenerated on every run |

## Requirements

- `kicad-cli` (KiCad 10). The runner defaults to
  `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`; override with
  the `KICAD_CLI` environment variable.
- `python3` (override with the `PYTHON` environment variable).
- `openscad` for the enclosure check (override with the `OPENSCAD` environment
  variable). The check is skipped when the project directory has no
  `enclosure/` directory.
