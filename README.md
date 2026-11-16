# Attenuator

This is a hobby electronics project to reduce the power of a composite video
signal by 1dB-10dB, to compensate for equipment that is overdriving the signal.

## What it does

A [composite video signal](https://en.wikipedia.org/wiki/Composite_video) entering
one RCA jack passes through a [T-pad](https://en.wikipedia.org/wiki/T_pad)
and leaves through the other RCA jack. Three trimmer potentiometers set the
attenuation level; with 50 Ohm series trimmers and a 1000 Ohm shunt trimmer, the
range covers 1dB to 10dB, plus a bit extra.

`sim/resistor_table.csv` lists the trimmer settings for each dB. Four test
points (IN, MID, OUT, GND) let the settings be checked with a multimeter.

## The repository

- `attenuator.kicad_sch`, `attenuator.kicad_pcb`: the [KiCad](https://www.kicad.org) schematic and board.  The RCA jack footprint lives inside the board file rather than in a footprint library: the vendor licence bars redistributing its footprint package as a standalone file, but allows board designs that combine it with other elements.
- `sim/`: `resistor_table.csv` plus the [ngspice](https://ngspice.sourceforge.io)
  netlists generated from it for each 1dB step.
- `enclosure/`: a 3D-printed case in [OpenSCAD](https://openscad.org) format.
- `models/`: datasheets and 3D models for the parts (or links to them).
- `test/`: design checks.

The jack's silkscreen dot overlaps the trimmer silkscreen, so `attenuator.kicad_pro`
sets the `silk_overlap` rule to `ignore`.  The jack's footprint is named in the
schematic but sits in no library, so ERC's `footprint_link_issues` check is
ignored too.  Everything else the check suite looks at reports no violations.

Run `make test` to run the checks, and `make` to build the gerbers, the
zone-filled board and its renders.  `make gerbers` alone writes the fabrication
files into `build/gerbers/`.  The CI build publishes the renders as a rolling
release named `latest-<branch>`, one per branch; the pictures below are the
newest `main` build.

![Attenuator board, component side](https://github.com/kulp/tiny-eater/releases/download/latest-main/attenuator_3d_front.png)

![Attenuator board, solder side](https://github.com/kulp/tiny-eater/releases/download/latest-main/attenuator_3d_back.png)

![The printed enclosure standing next to its lid, with the castellation tabs on top of the body](https://github.com/kulp/tiny-eater/releases/download/latest-main/enclosure.png)
