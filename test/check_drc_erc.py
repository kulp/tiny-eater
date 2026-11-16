#!/usr/bin/env python3
"""Summarize a kicad-cli DRC or ERC JSON report and cross-check the kicad exit code.

Usage:
    check_drc_erc.py --kind drc|erc REPORT_JSON --kicad-exit N

REPORT_JSON is written by:
    kicad-cli pcb drc --format json ... -o REPORT_JSON   (kind: drc)
    kicad-cli sch erc --format json ... -o REPORT_JSON   (kind: erc)

A DRC report counts entries in "violations", "unconnected_items", and
"schematic_parity". An ERC report counts entries in sheets[].violations.

The kicad-cli exit code (from a run with --exit-code-violations) is
cross-checked against the report: a non-zero exit code must correspond to at
least one finding, and vice versa. A disagreement is itself a finding.

Exit codes:
  0  no findings
  1  one or more findings (printed to stdout)
  2  usage or parsing error
"""

import argparse
import json
import sys


def item_descs(items):
    descs = []
    for item in items:
        if isinstance(item, dict) and item.get("description"):
            descs.append(item["description"])
    return "; ".join(descs)


def drc_findings(report):
    findings = []
    for v in report.get("violations", []):
        sev = v.get("severity", "?")
        typ = v.get("type", v.get("description", "?"))
        extra = item_descs(v.get("items", []))
        line = f"[{sev}] {typ}"
        if extra:
            line += f": {extra}"
        findings.append(line)
    for u in report.get("unconnected_items", []):
        extra = item_descs(u.get("items", []))
        line = u.get("description", "missing connection")
        if extra:
            line += f": {extra}"
        findings.append(f"[unconnected] {line}")
    for p in report.get("schematic_parity", []):
        if isinstance(p, dict):
            sev = p.get("severity", "?")
            typ = p.get("type", "schematic parity")
            desc = p.get("description", "")
            extra = item_descs(p.get("items", []))
            line = f"[{sev}] {typ}"
            if desc:
                line += f": {desc}"
            if extra:
                line += f" ({extra})"
            findings.append(line)
        else:
            findings.append(f"[parity] {p}")
    return findings


def erc_findings(report):
    findings = []
    for sheet in report.get("sheets", []):
        path = sheet.get("path", "/")
        for v in sheet.get("violations", []):
            sev = v.get("severity", "?")
            typ = v.get("type", "?")
            desc = v.get("description", "")
            extra = item_descs(v.get("items", []))
            line = f"[{sev}] {typ}"
            if desc:
                line += f": {desc}"
            if extra:
                line += f" ({extra})"
            findings.append(f"{path} {line}")
    return findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("drc", "erc"), required=True)
    parser.add_argument("report", help="path to the JSON report")
    parser.add_argument("--kicad-exit", type=int, required=True,
                        help="exit code of the kicad-cli run with --exit-code-violations")
    args = parser.parse_args()

    try:
        with open(args.report, encoding="utf-8") as f:
            report = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"{args.kind} check: error: cannot read report: {exc}", file=sys.stderr)
        return 2

    findings = drc_findings(report) if args.kind == "drc" else erc_findings(report)

    label = "DRC" if args.kind == "drc" else "ERC"
    has_findings = bool(findings)
    kicad_said_violations = args.kicad_exit != 0
    if has_findings != kicad_said_violations:
        n = len(findings)
        findings.append(
            f"cross-check: kicad-cli exited with {args.kicad_exit} "
            f"({'violations' if kicad_said_violations else 'no violations'}) "
            f"but the report has {n} finding(s)"
        )

    print(f"{label} check: {len(findings)} finding(s)")
    for line in findings:
        print(f"  - {line}")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
