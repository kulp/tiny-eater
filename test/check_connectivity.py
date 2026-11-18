#!/usr/bin/env python3
"""Check the two things DRC's schematic parity does not report.

Usage:
    check_connectivity.py NETLIST_NET PCB_KICAD_PCB

NETLIST_NET is a kicadsexpr netlist exported with:
    kicad-cli sch export netlist --format kicadsexpr -o NETLIST_NET SCH_FILE

Everything else -- missing or extra footprints, pad/net mismatches, unconnected
pins -- is reported by `kicad-cli pcb drc --schematic-parity`, which
test/run_tests.sh already runs.  This script only adds:

  1. duplicate_reference  the same reference appears on more than one PCB
                          footprint.
  2. missing_pad          a schematic pin is assigned to a net but the PCB
                          footprint for that reference has no such pad.

Both are read with line-oriented regexes rather than a sexpr parser: the
netlist writes one property per line, and the PCB is split on top-level
`(footprint "..."` starts.

Exit codes:
  0  no findings
  1  one or more findings (printed to stdout)
  2  usage or file error
"""

import re
import sys

REF = re.compile(r'\(ref "([^"]+)"\)')
FOOTPRINT = re.compile(r'\(footprint "([^"]+)"')
NET_NAME = re.compile(r'\(name "([^"]+)"\)')
PIN = re.compile(r'\(pin "([^"]+)"\)')
PAD = re.compile(r'\(pad "([^"]+)"')
REFERENCE = re.compile(r'\(property "Reference" "([^"]+)"')


def parse_netlist(text):
    """Return (comps, pin_nets): ref -> footprint, (ref, pin) -> net name."""
    comps = {}
    pin_nets = {}
    section = None
    current_comp = None
    current_net = None
    current_node = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("(components"):
            section = "components"
        elif line.startswith("(nets"):
            section = "nets"
            current_net = None
            current_node = None
        elif line.startswith("(libparts"):
            section = None
        elif section == "components":
            match = REF.fullmatch(line)
            if match:
                current_comp = match.group(1)
                comps.setdefault(current_comp, "")
            elif line.startswith('(footprint "') and current_comp:
                comps[current_comp] = FOOTPRINT.search(line).group(1)
        elif section == "nets":
            if (match := NET_NAME.fullmatch(line)):
                current_net = match.group(1)
            elif (match := REF.fullmatch(line)):
                current_node = match.group(1)
            elif (match := PIN.fullmatch(line)) and current_node and current_net:
                pin_nets[(current_node, match.group(1))] = current_net
    return comps, pin_nets


def parse_pcb(text):
    """Return a list of (ref, footprint_id, pads)."""
    footprints = []
    for part in re.split(r'(?=^\t\(footprint ")', text, flags=re.M):
        header = FOOTPRINT.match(part.lstrip())
        if not header:
            continue
        reference = REFERENCE.search(part)
        footprints.append((reference.group(1) if reference else "",
                           header.group(1),
                           PAD.findall(part)))
    return footprints


def main():
    if len(sys.argv) != 3:
        print(__doc__.strip().splitlines()[0], file=sys.stderr)
        return 2
    try:
        with open(sys.argv[1], encoding="utf-8") as f:
            comps, pin_nets = parse_netlist(f.read())
        with open(sys.argv[2], encoding="utf-8") as f:
            footprints = parse_pcb(f.read())
    except OSError as exc:
        print(f"connectivity check: error: {exc}", file=sys.stderr)
        return 1

    findings = []

    counts = {}
    for ref, _fid, _pads in footprints:
        if ref:
            counts[ref] = counts.get(ref, 0) + 1
    for ref in sorted(counts):
        if counts[ref] > 1:
            findings.append(
                f"duplicate_reference: reference {ref} appears on "
                f"{counts[ref]} footprints on the PCB"
            )

    pcb_pads = {}
    for ref, _fid, pads in footprints:
        if ref:
            pcb_pads.setdefault(ref, set()).update(pads)
    for ref, pin in sorted(pin_nets, key=lambda k: (k[0], int(k[1]) if k[1].isdigit() else 0)):
        if ref in pcb_pads and pin not in pcb_pads[ref]:
            findings.append(
                f"missing_pad: {ref} pin {pin} is on net {pin_nets[(ref, pin)]} in the "
                f"schematic but the PCB footprint has no pad {pin}"
            )

    print(f"connectivity/footprint check: {len(findings)} finding(s)")
    for finding in findings:
        print(f"  - {finding}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
