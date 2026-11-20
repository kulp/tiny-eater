# tiny-eater

This is a hobby electronics project to reduce the power of a composite video
signal by 1dB-10dB, to compensate for equipment that is overdriving the signal.
It is an attenuator, a "tiny eater" of signal power.

## What it does

A [composite video signal](https://en.wikipedia.org/wiki/Composite_video) entering
one RCA jack passes through a [T-pad](https://en.wikipedia.org/wiki/T_pad)
and leaves through the other RCA jack. Three trimmer potentiometers set the
attenuation level; with 50 Ohm series trimmers and a 1000 Ohm shunt trimmer, the
range covers 1dB to 10dB, plus a bit extra.

`sim/resistor_table.csv` lists the trimmer settings for each dB. Four test
points (IN, MID, OUT, GND) let the settings be checked with a multimeter.

## The repository

- `attenuator.kicad_sch`, `attenuator.kicad_pcb`: the [KiCad](https://www.kicad.org) schematic and board.
- `sim/`: `resistor_table.csv` plus the [ngspice](https://ngspice.sourceforge.io) netlists generated from it for each 1dB step.
- `enclosure/`: a 3D-printed case in [OpenSCAD](https://openscad.org) format.
- `models/`: datasheets and 3D models for the parts (or links to them).
- `test/`: design checks.

Run `make` to build production files and renders; run `make test` for
engineering and design checks.

![Attenuator board, component side](https://github.com/kulp/tiny-eater/releases/download/latest-main/attenuator_3d_front.png)

![Attenuator board, solder side](https://github.com/kulp/tiny-eater/releases/download/latest-main/attenuator_3d_back.png)

![The printed enclosure standing next to its lid, with the castellation tabs on top of the body](https://github.com/kulp/tiny-eater/releases/download/latest-main/enclosure.png)

## LLM usage

The PCB design itself was modified heavily in KiCad 10 by a human, but an
original version was drafted by Qwen3.8-27B. Test and build support was drafted
by several Qwen3.8 models.
