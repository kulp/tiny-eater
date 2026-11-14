#!/usr/bin/env python3
"""Check connectivity and footprint parity between a KiCad netlist export and a PCB file.

Usage:
    check_connectivity.py NETLIST_NET PCB_KICAD_PCB

NETLIST_NET is a kicadsexpr netlist exported with:
    kicad-cli sch export netlist --format kicadsexpr -o NETLIST_NET SCH_FILE

Checks performed:
  1. missing_footprint   a schematic component with a footprint assigned has no
                         matching footprint (by reference) on the PCB.
  2. extra_footprint     a footprint with a reference on the PCB has no matching
                         schematic component in the netlist.
  3. duplicate_reference the same reference appears on more than one PCB footprint.
  4. net_mismatch        a PCB pad net does not match the schematic netlist
                         assignment for the same ref/pin (both directions,
                         including unconnected pads vs connected pins).
  5. missing_pad         a schematic pin is assigned to a net in the netlist but
                         the PCB footprint for that ref has no such pad.

Exit codes:
  0  no findings
  1  one or more findings (printed to stdout)
  2  usage or parsing error
"""

import sys


def tokenize(text):
    """Tokenize an S-expression file into (kind, value) pairs."""
    tokens = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in " \t\r\n":
            i += 1
        elif c == ";":
            while i < n and text[i] != "\n":
                i += 1
        elif c == "(":
            tokens.append(("open", "("))
            i += 1
        elif c == ")":
            tokens.append(("close", ")"))
            i += 1
        elif c == '"':
            j = i + 1
            buf = []
            while j < n and text[j] != '"':
                if text[j] == "\\" and j + 1 < n:
                    buf.append(text[j + 1])
                    j += 2
                else:
                    buf.append(text[j])
                    j += 1
            tokens.append(("str", "".join(buf)))
            i = j + 1
        else:
            j = i
            while j < n and text[j] not in " \t\r\n();\"":
                j += 1
            tokens.append(("sym", text[i:j]))
            i = j
    return tokens


def parse(tokens):
    """Parse tokens into nested lists; atoms are plain strings."""
    pos = 0

    def read_node():
        nonlocal pos
        kind, value = tokens[pos]
        pos += 1
        if kind == "open":
            node = []
            while tokens[pos][0] != "close":
                node.append(read_node())
            pos += 1
            return node
        return value

    root = read_node()
    if pos != len(tokens):
        raise ValueError("trailing tokens after top-level expression")
    return root


def children(node):
    """Direct children of a list node (skip the head atom)."""
    if not isinstance(node, list):
        return []
    return node[1:]


def attr(node, key):
    """Return the string value of a (key "value") child, or '' if absent."""
    for child in children(node):
        if isinstance(child, list) and len(child) >= 2 and child[0] == key:
            return child[1] if isinstance(child[1], str) else ""
    return ""


def parse_netlist(text):
    """Return (comps, pin_nets):
    comps:    ref -> footprint string (may be empty)
    pin_nets: (ref, pin) -> net name
    """
    root = parse(tokenize(text))
    comps = {}
    pin_nets = {}
    for section in children(root):
        if not isinstance(section, list):
            continue
        if section[0] == "components":
            for comp in children(section):
                if isinstance(comp, list) and comp[0] == "comp":
                    ref = attr(comp, "ref")
                    if ref:
                        comps[ref] = attr(comp, "footprint")
        elif section[0] == "nets":
            for net in children(section):
                if not isinstance(net, list) or net[0] != "net":
                    continue
                name = attr(net, "name")
                for node in children(net):
                    if isinstance(node, list) and node[0] == "node":
                        ref = attr(node, "ref")
                        pin = attr(node, "pin")
                        if ref and pin:
                            pin_nets[(ref, pin)] = name
    return comps, pin_nets


def parse_pcb(text):
    """Return a list of (ref, footprint_id, pads); pads is a list of (pad, net)."""
    root = parse(tokenize(text))
    footprints = []
    for fp in children(root):
        if not isinstance(fp, list) or fp[0] != "footprint":
            continue
        ref = ""
        fid = fp[1] if len(fp) > 1 and isinstance(fp[1], str) else ""
        pads = []
        for child in fp:
            if not isinstance(child, list):
                continue
            if child[0] == "property" and len(child) >= 2 and child[1] == "Reference":
                ref = child[2] if len(child) > 2 else ""
            elif child[0] == "pad" and len(child) > 1:
                net = ""
                for pc in child:
                    if isinstance(pc, list) and pc[0] == "net" and len(pc) > 1:
                        net = pc[1]
                pads.append((child[1], net))
        footprints.append((ref, fid, pads))
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
    except (OSError, ValueError, IndexError) as exc:
        print(f"connectivity check: error: {exc}", file=sys.stderr)
        return 2
    findings = []

    pcb_refs = {}
    for ref, _fid, _pads in footprints:
        if ref:
            pcb_refs[ref] = pcb_refs.get(ref, 0) + 1
    for ref in sorted(pcb_refs):
        if pcb_refs[ref] > 1:
            findings.append(
                f"duplicate_reference: reference {ref} appears on "
                f"{pcb_refs[ref]} footprints on the PCB"
            )

    for ref in sorted(comps):
        if comps[ref] and ref not in pcb_refs:
            findings.append(
                f"missing_footprint: schematic component {ref} "
                f"(footprint {comps[ref]}) has no matching footprint on the PCB"
            )

    for ref in sorted(pcb_refs):
        if ref not in comps:
            findings.append(
                f"extra_footprint: PCB footprint {ref} has no matching "
                f"schematic component in the netlist"
            )

    for ref, _fid, pads in footprints:
        if not ref or ref not in comps:
            continue
        for pad, net in pads:
            sch_net = pin_nets.get((ref, pad))
            if sch_net is not None and net == sch_net:
                continue
            pcb_unconnected = net.startswith("unconnected-")
            if pcb_unconnected:
                if sch_net is not None:
                    findings.append(
                        f"net_mismatch: {ref} pad {pad} is unconnected on the PCB "
                        f"({net}) but pin {pad} is on net {sch_net} in the schematic"
                    )
            elif not net:
                if sch_net is not None:
                    findings.append(
                        f"net_mismatch: {ref} pad {pad} has no net on the PCB "
                        f"but pin {pad} is on net {sch_net} in the schematic"
                    )
            elif sch_net is None:
                findings.append(
                    f"net_mismatch: {ref} pad {pad} is on net {net} on the PCB "
                    f"but pin {pad} is unconnected in the schematic"
                )
            elif net != sch_net:
                findings.append(
                    f"net_mismatch: {ref} pad {pad} is on net {net} on the PCB "
                    f"but pin {pad} is on net {sch_net} in the schematic"
                )

    pcb_pads = {}
    for ref, _fid, pads in footprints:
        if ref:
            for pad, _net in pads:
                pcb_pads.setdefault(ref, set()).add(pad)
    for (ref, pin) in sorted(pin_nets, key=lambda k: (k[0], int(k[1]) if k[1].isdigit() else 0)):
        if ref in pcb_pads and pin not in pcb_pads[ref]:
            findings.append(
                f"missing_pad: {ref} pin {pin} is on net {pin_nets[(ref, pin)]} in the "
                f"schematic but the PCB footprint has no pad {pin}"
            )

    print(f"connectivity/footprint check: {len(findings)} finding(s)")
    for f in findings:
        print(f"  - {f}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
