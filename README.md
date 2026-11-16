# tiny-eater

This is a hobby electronics project to reduce the power of a composite video
signal by 1dB-10dB, to compensate for equipment that is overdriving the signal.
It is an attenuator, a "tiny eater" of signal power.

## What it does

A [composite video signal](https://en.wikipedia.org/wiki/Composite_video) entering
one RCA jack passes through a [T-pad](https://en.wikipedia.org/wiki/T_pad)
and leaves through the other RCA jack. Three trimmer potentiometers set the
attenuation level; with 50 Ohm series trimmers and a 1000 Ohm shunt trimmer, the
range covers 1dB to 10dB, plus a bit extra. Four test points (IN, MID, OUT, GND)
let the settings be checked with a multimeter.

`sim/resistor_table.csv` lists the trimmer settings for each dB.

## The repository

- `attenuator.kicad_sch`, `attenuator.kicad_sym`: the [KiCad](https://www.kicad.org) schematic and the RCJ-044 symbol for the RCA jack.
- `attenuator.kicad_pro`: the KiCad project.  The jack's footprint is named in the schematic but lives in no library, so ERC's `footprint_link_issues` check is set to `ignore`.
- `attenuator.kicad_pcb`: the board.  The RCA jack footprint lives inside the board file rather than in a footprint library: the vendor licence bars redistributing its footprint package as a standalone file, but allows board designs that combine it with other elements.
- `sim/`: `resistor_table.csv` plus the [ngspice](https://ngspice.sourceforge.io)
  netlists generated from it for each 1dB step.
- `enclosure/`: a 3D-printed case in [OpenSCAD](https://openscad.org) format.
- `models/`: datasheets and 3D models for the parts, or links to them.
- `test/`: design checks.

The jack's silkscreen dot overlaps the trimmer silkscreen, so `attenuator.kicad_pro`
sets the `silk_overlap` rule to `ignore`.  Everything else the check suite looks at
reports no violations.

Run `make` to plot the gerbers into `build/gerbers/`, and `make test` to run the
design checks.
