#!/usr/bin/env python3
"""Generate attenuator.kicad_sch for the 75-ohm composite-video T-pad attenuator.

Topology (T-pad, symmetric series arms):

    IN o--[J1.2]--[R1 wiper]
                    R1: pin1 -> MID, pin2 (wiper) -> IN, pin3 -> NC
    MID o- R1.1 ----- R2.1 ----- R3.1
                    R2: pin1 -> MID, pin2 (wiper) -> GND, pin3 -> NC   (shunt)
                    R3: pin1 -> MID, pin2 (wiper) -> OUT, pin3 -> NC
    OUT o- R3.2 (wiper) --[J2.2]
    GND : J1.1, J2.1, R2.2 (wiper), TP4

Each trimmer is used as a two-terminal variable resistor (wiper + one end);
the unused end (pin3) is no-connect. A DMM across the two relevant test points
reads the set series/shunt resistance directly.

Nets:
    IN  : J1.2, R1.2, TP1
    MID : R1.1, R2.1, R3.1, TP2
    OUT : J2.2, R3.2, TP3
    GND : J1.1, J2.1, R2.2, TP4
"""
import os
import uuid

PROJ = "/Users/kulp/Documents/Projects/attenuator"
GEN = os.path.join(PROJ, "_gen")


def U():
    return str(uuid.uuid4())


def fmt(v):
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return ("%.4f" % v).rstrip("0").rstrip(".")


def read_block(fname):
    with open(os.path.join(GEN, fname)) as f:
        return f.read().strip()


def prefixed(block, lib, name):
    old = '(symbol "%s"' % name
    new = '(symbol "%s:%s"' % (lib, name)
    assert old in block, "%s not found for %s:%s" % (old, lib, name)
    return block.replace(old, new, 1)


# --- embedded symbol library definitions -------------------------------
lib_symbol_blocks = [
    prefixed(read_block("sym_Device__R_Potentiometer_Trim.txt"), "Device", "R_Potentiometer_Trim"),
    prefixed(read_block("sym_Connector__TestPoint.txt"), "Connector", "TestPoint"),
    prefixed(read_block("sym_power__GND.txt"), "power", "GND"),
    prefixed(read_block("sym_attenuator__RCJ-044.txt"), "attenuator", "RCJ-044"),
]

# --- component placement ------------------------------------------------
# (ref, lib_id, value, footprint, x, y, mirror, {pin: net})
FP_TRIM = "attenuator:Potentiometer_Bourns_3296W_Vertical"
FP_RCA = "attenuator:SAMESKY_RCJ-044"
FP_TP = "attenuator:TestPoint_Pad_D1.5mm"

# Grid: every coordinate is an integer multiple of the 0.254 mm (10 mil)
# connection grid. u(n) converts grid units n to millimetres.
#   y=-15u: signal row (jack center pins, trimmer wipers, TP1, TP3)
#   y=   0u: MID bus (trimmer end pins, TP2)
#   y=-50u: GND bus (jack shell drops, TP4, GND symbols)
def u(n):
    return round(n * 0.254, 4)

# Trimmer (Device:R_Potentiometer_Trim) pins relative to the origin:
#   pin1 (end) (0, +3.81) -> MID bus; pin2 (wiper) (+3.81, 0) -> signal row;
#   pin3 (end) (0, -3.81) -> NC.
# RCA (RCJ-044) pins: center (7.62, +2.54), shell (7.62, -2.54); J1 is
# unmirrored (left), J2 is mirror y (right, center pin facing the trimmers).
components = [
    ("J1", "attenuator:RCJ-044", "RCJ-044", FP_RCA, u(33), u(-25), False, {1: "GND", 2: "IN"}),
    ("J2", "attenuator:RCJ-044", "RCJ-044", FP_RCA, u(250), u(-25), "y", {1: "GND", 2: "OUT"}),
    ("R1", "Device:R_Potentiometer_Trim", "50", FP_TRIM, u(79), u(-15), False, {1: "MID", 2: "IN", 3: "NC"}),
    ("R2", "Device:R_Potentiometer_Trim", "1000", FP_TRIM, u(126), u(-15), False, {1: "MID", 2: "GND", 3: "NC"}),
    ("R3", "Device:R_Potentiometer_Trim", "50", FP_TRIM, u(173), u(-15), False, {1: "MID", 2: "OUT", 3: "NC"}),
    ("TP1", "Connector:TestPoint", "IN", FP_TP, u(75), u(-15), False, {1: "IN"}),
    ("TP2", "Connector:TestPoint", "MID", FP_TP, u(103), u(0), False, {1: "MID"}),
    ("TP3", "Connector:TestPoint", "OUT", FP_TP, u(204), u(-15), False, {1: "OUT"}),
    ("TP4", "Connector:TestPoint", "GND", FP_TP, u(103), u(-50), False, {1: "GND"}),
]

PINCOUNT = {
    "attenuator:RCJ-044": [1, 2],
    "Device:R_Potentiometer_Trim": [1, 2, 3],
    "Connector:TestPoint": [1],
    "power:GND": [1],
}

# --- wires --------------------------------------------------------------
wires = [
    ((u(79), u(0)), (u(173), u(0))),      # MID bus (R1.1 - R2.1 - R3.1)
    ((u(63), u(-15)), (u(94), u(-15))),   # IN: J1.2 (center) - TP1 - R1.2 (wiper)
    ((u(188), u(-15)), (u(220), u(-15))), # OUT: R3.2 (wiper) - TP3 - J2.2 (center)
    ((u(63), u(-35)), (u(63), u(-50))),   # J1.1 (shell) -> GND bus
    ((u(141), u(-15)), (u(141), u(-50))), # R2.2 (wiper) -> GND bus
    ((u(220), u(-35)), (u(220), u(-50))), # J2.1 (shell) -> GND bus
    ((u(63), u(-50)), (u(220), u(-50))),  # GND bus (TP4, PWR flags sit on it)
]

# junction dots: where a pin or PWR flag meets the middle of a wire
junctions = [
    (u(75), u(-15)),    # TP1 on IN wire
    (u(103), u(0)),     # TP2 on MID bus
    (u(126), u(0)),     # R2.1 on MID bus
    (u(204), u(-15)),   # TP3 on OUT wire
    (u(103), u(-50)),   # TP4 on GND bus
    (u(63), u(-50)),    # PWR01 on GND bus
    (u(141), u(-50)),   # PWR02 on GND bus
    (u(220), u(-50)),   # PWR03 on GND bus
]

# NC markers on the unused trimmer end terminals (pin3)
no_connects = [
    (u(79), u(-30)),    # R1.3
    (u(126), u(-30)),   # R2.3
    (u(173), u(-30)),   # R3.3
]

# GND power symbols at the GND-bus drops
gnd_syms = [("#PWR01", u(63), u(-50)), ("#PWR02", u(141), u(-50)), ("#PWR03", u(220), u(-50))]

# net-name labels placed on the corresponding wires
labels = [("IN", u(69), u(-15)), ("MID", u(87), u(0)), ("OUT", u(197), u(-15))]


def prop(out, name, value, at, hide=False, size="1.27"):
    out.append('\t\t(property "%s" "%s"' % (name, value))
    out.append("\t\t\t(at %s %s 0)" % (fmt(at[0]), fmt(at[1])))
    if hide:
        out.append("\t\t\t(show_name no)")
    out.append("\t\t\t(effects (font (size %s %s)))" % (size, size))
    out.append("\t\t)")


def symbol_instance(out, ref, lib_id, value, fp, x, y, mirror, is_power=False):
    out.append('\t(symbol (lib_id "%s")' % lib_id)
    out.append("\t\t(at %s %s 0)" % (fmt(x), fmt(y)))
    if mirror:
        out.append("\t\t(mirror %s)" % mirror)
    out.append("\t\t(unit 1)")
    out.append("\t\t(in_bom yes)")
    out.append("\t\t(on_board yes)")
    out.append("\t\t(dnp no)")
    out.append('\t\t(uuid "%s")' % U())
    if is_power:
        prop(out, "Reference", ref, (x, y - 4.34), hide=True)
        prop(out, "Value", "GND", (x, y - 3.17))
        prop(out, "Footprint", "", (0, 0), hide=True)
        prop(out, "Datasheet", "", (0, 0), hide=True)
    else:
        prop(out, "Reference", ref, (x, y - 9.5))
        prop(out, "Value", value, (x, y - 11.0))
        prop(out, "Footprint", fp, (0, 0), hide=True)
        prop(out, "Datasheet", "", (0, 0), hide=True)
    out.append("\t)")


out = []
out.append("(kicad_sch")
out.append("\t(version 20250114)")
out.append('\t(generator "eeschema")')
out.append('\t(generator_version "9.0")')
out.append('\t(uuid "%s")' % U())
out.append('\t(paper "A4")')
out.append("\t(lib_symbols")
for blk in lib_symbol_blocks:
    out.append("\t" + blk.replace("\n", "\n\t"))
out.append("\t)")

for ref, lib_id, value, fp, x, y, mirror, _pinmap in components:
    symbol_instance(out, ref, lib_id, value, fp, x, y, mirror, is_power=False)
for ref, x, y in gnd_syms:
    symbol_instance(out, ref, "power:GND", "GND", "", x, y, False, is_power=True)

for (x1, y1), (x2, y2) in wires:
    out.append("\t(wire")
    out.append("\t\t(pts (xy %s %s) (xy %s %s))" % (fmt(x1), fmt(y1), fmt(x2), fmt(y2)))
    out.append("\t\t(stroke (width 0) (type default) (color 0 0 0 0))")
    out.append('\t\t(uuid "%s")' % U())
    out.append("\t)")

for x, y in junctions:
    out.append("\t(junction")
    out.append("\t\t(at %s %s)" % (fmt(x), fmt(y)))
    out.append('\t\t(uuid "%s")' % U())
    out.append("\t)")

for x, y in no_connects:
    out.append("\t(no_connect")
    out.append("\t\t(at %s %s)" % (fmt(x), fmt(y)))
    out.append('\t\t(uuid "%s")' % U())
    out.append("\t)")

for name, x, y in labels:
    out.append('\t(label "%s"' % name)
    out.append("\t\t(at %s %s 0)" % (fmt(x), fmt(y)))
    out.append("\t\t(effects (font (size 1.27 1.27)))")
    out.append("\t)")

out.append("\t(sheet_instances")
out.append('\t\t(path "/"')
out.append('\t\t\t(page "1")')
out.append("\t\t)")
out.append("\t)")
out.append("\t(embedded_fonts no)")
out.append(")")

path = os.path.join(PROJ, "attenuator.kicad_sch")
with open(path, "w") as f:
    f.write("\n".join(out) + "\n")
print("wrote %s (%d lines)" % (path, len(out)))
