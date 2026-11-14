# Attenuator

Inline composite-video T-pad attenuator for a 75 ohm line. The signal path
runs between two RCA jacks (center = signal, shell = ground) through a T-pad
whose three arms are all adjustable:

| Ref | Connection | Part | Range |
|-----|------------|------|-------|
| R1 | IN to MID (series) | Bourns 3296W-1-0050L | 2 to 50 ohm |
| R2 | MID to GND (shunt) | Bourns 3296W-1-0102L | 10 to 1000 ohm |
| R3 | MID to OUT (series) | Bourns 3296W-1-0050L | 2 to 50 ohm |

At the matched design points the pad delivers 1 to 10 dB of attenuation with
75 ohm port impedance at both ports. The matched trimmer settings for each
target attenuation are in `sim/resistor_table.csv`; the minimum setting
(2 ohm series each, 1000 ohm shunt) gives 0.47 dB, so the full 1 to 10 dB
range is reachable. Test points TP1 (IN), TP2 (MID), TP3 (OUT), and TP4
(GND) are provided for setting the trimmers with a scope and a 75 ohm
termination.

## Files

- `attenuator.kicad_sch`, `attenuator.kicad_pcb`, `attenuator.kicad_sym`,
  `attenuator.kicad_pro`: the KiCad project (KiCad 10.0.7).
- `attenuator.pretty/`: project footprints (RCA jack, 3296W vertical,
  test point). The geometry is third-party, so it is not committed: run
  `python3 tools/fetch_footprints.py` to rebuild it from the sources recorded
  in `models/`.  Files are written as upstream ships them (legacy sexpr is
  converted with `kicad-cli fp upgrade`), so the copies placed in
  `attenuator.kicad_pcb` carry the same graphic items, down to the two dots
  the vendor draws outside the RCJ-044 courtyard.  That silkscreen dot crosses
  the silkscreen box of R1, so `silk_overlap` is set to "ignore" in
  `attenuator.kicad_pro`.
- `sim/`: ngspice netlists (`tpad_*.sp`) and `resistor_table.csv`
  (matched 75 ohm T-pad values per dB of attenuation).
- `models/`: vendor reference data (3296 datasheet and step file,
  SAMESKY RCJ-044 RCA jack documentation).
- `tools/gen_schematic.py`: regenerates the schematic.
- `tools/fetch_footprints.py`: downloads the footprints and the RCJ-044 STEP
  from the vendor and KiCad library URLs recorded in `models/`, upgrades
  legacy footprint files with `kicad-cli fp upgrade`, and prints the manual
  download steps for sources a plain GET cannot reach.
- `test/`: the design check suite described in `test/README.md`.
- `Makefile`: runs the design checks with `make test`, and regenerates the
  resistor table, the production board and the 3D PCB renders with `make`.
- `scripts/build_production_pcb.py`: builds `build/attenuator.kicad_pcb`
  with all copper zones filled, for gerber export and fabrication. The
  committed board carries no zone fill data; the script refills every zone,
  writes the output, and verifies the fills persisted.
- `scripts/gen_resistor_table.py`: computes the T-pad resistor table
  (closed form) and prints it; pass `--write` to simulate the T-pad at each
  attenuation step and write the per-D netlists, logs, and
  `sim/resistor_table.csv`. The default range is 1 to 10 dB in 1 dB steps
  (which reproduces the committed table); `--start`, `--stop`, and `--step`
  configure the range and the step size.
- `enclosure/`: the printed snap-fit enclosure and lid (`enclosure.scad`), PNG
  cutaways (`render_cutaways.py`), the castellation fit check
  (`check_castellations.py`) and `build_parts.sh`, which writes the lid, the
  enclosure body and a combined both-parts-in-one-file STL to `build/`.

## PCB renders

`./scripts/render_pcb_3d.sh`, also run by `make pcb-renders`, ray-traces the
board with `kicad-cli pcb render` and writes one PNG per side into `build/`.
`make pcb-renders` waits on the RCJ-044 STEP model that
`tools/fetch_footprints.py` downloads, because the RCA jacks do not appear in
the render without it. Neither `build/` nor `models/Same_Sky_RCJ-044/` is
committed, so the images below only appear once you have generated them
locally.

![Attenuator board, component side](build/attenuator_3d_front.png)

![Attenuator board, solder side, carrying the silkscreen resistor table](build/attenuator_3d_back.png)

## Verification

Run `make test` (which calls `test/run_tests.sh`) to do several checks in one
pass.

- `kicad-cli sch erc attenuator.kicad_sch`: no violations once
  `attenuator.pretty/` has been built. On a fresh clone it reports two
  warnings, one per RCA symbol, because the gated RCJ-044 footprint is not
  in the project library yet.
- `kicad-cli pcb drc attenuator.kicad_pcb`: no copper edge clearance
  violations, no silkscreen-to-edge violations, and no schematic parity
  issues; the RCA shell pads clear the board edge. The unconnected item
  check needs `--refill-zones`, otherwise the GND zone copper is stale and
  the four GND pads read as unconnected. The one silkscreen overlap finding,
  J1's vendor dot against R1's silkscreen box, is suppressed by the
  `silk_overlap` setting described above.
- `ngspice sim/tpad_01dB.sp` through `sim/tpad_10dB.sp`: each run confirms
  the target attenuation (1.000 dB through 10.000 dB) and 75.00 ohm input
  impedance at the matched values in `sim/resistor_table.csv`.
- `python3 enclosure/check_castellations.py`, also run by `make test`: the tabs
  on the enclosure's wall ends pass through the notches cut in the lid with zero
  interference, and the lid stays a single thickness with every tab inside it.
  Prints PASS and exits 0.
