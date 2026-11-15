# Attenuator

This is a hobby electronics project to reduce the power of a composite video
signal by 1dB-10dB, to compensate for equipment that is overdriving the signal.

## What it does

A [composite video signal](https://en.wikipedia.org/wiki/Composite_video) entering
one RCA jack passes through a [T-pad](https://en.wikipedia.org/wiki/T_pad)
and leaves through the other RCA jack. Three trimmer potentiometers set the
attenuation level; with 50Ω series trimmers and a 1000Ω shunt trimmer, the
range covers 1dB to 10dB, plus a bit extra.

`sim/resistor_table.csv` lists the trimmer settings for each dB. Four test
points (IN, MID, OUT, GND) let the settings be checked with a multimeter.

## The repository

- `attenuator.kicad_sch`, `attenuator.kicad_pcb`: the [KiCad](https://www.kicad.org) schematic and board.
- `sim/`: [ngspice](https://ngspice.sourceforge.io) netlists demonstrating pad settings at 1dB increments.
- `enclosure/`: a 3D-printed case in [OpenSCAD](https://openscad.org) format.
- `models/`: datasheets and 3D models for the parts (or links to them).
- `test/`: design checks.

Run `make test` to run the checks, and `make` to build the production board and
its renders.

![Attenuator board, component side](build/attenuator_3d_front.png)

![Attenuator board, solder side](build/attenuator_3d_back.png)

![The printed enclosure standing next to its lid, with the castellation tabs on top of the body](build/enclosure.png)
