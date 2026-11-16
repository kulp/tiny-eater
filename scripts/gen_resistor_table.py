#!/usr/bin/env python3
"""Compute the T-pad resistor table, optionally simulating it with ngspice.

By default this script only prints the table to stdout and writes no files.
Pass --netlists to write the per-dB netlists to sim/ without running ngspice,
or --write to run ngspice for each step and write the netlists, logs, and
sim/resistor_table.csv to the project's sim/ directory.

For each attenuation N (dB) from --start to --stop (inclusive) in --step
increments, this script:

1. Computes the matched series and shunt resistor values for a Z0-ohm T-pad
   attenuator (closed form, exact match).
2. (With --netlists or --write) writes an ngspice netlist to sim/tpad_<N>dB.sp.
3. (With --write) runs ngspice in batch mode, capturing the log to
   sim/tpad_<N>dB.log.
4. (With --write) parses v(out) and i(v1) from the log.
5. (With --write) records the simulated attenuation (20*log10(1/v(out))) and
   input impedance (1/|i(v1)|).
6. (With --write) writes sim/resistor_table.csv with the computed resistor
   values and the simulated verification columns. The per-dB netlists and
   logs are regenerated in place; with the defaults (start=1, stop=10,
   step=1) the existing table is reproduced. Requires ngspice on the PATH.

Usage:
    python3 scripts/gen_resistor_table.py [--start 1] [--stop 10] [--step 1]
                                          [--netlists | --write]
"""
import argparse
import csv
import math
import os
import re
import subprocess

Z0 = 75.0  # system impedance (ohms)


def tpad_resistors(n_db, z0=Z0):
    """Return (R_series, R_shunt) for a matched T-pad attenuator at n_db.

    With voltage ratio K = 10**(n_db/20) and system impedance z0, the series
    and shunt values that give exactly n_db of attenuation and a z0-ohm input
    impedance (output terminated in z0) are:
        R_series = z0 * (K - 1) / (K + 1)
        R_shunt  = z0 * 2K / (K**2 - 1)
    """
    k = 10.0 ** (n_db / 20.0)
    r_series = z0 * (k - 1.0) / (k + 1.0)
    r_shunt = z0 * 2.0 * k / (k * k - 1.0)
    return r_series, r_shunt


def _db_tag(n_db):
    """Filename tag for an attenuation: 1.0 -> 01, 10.0 -> 10, 1.5 -> 1.5."""
    if abs(n_db - round(n_db)) < 1e-9:
        return "%02d" % int(round(n_db))
    return "%g" % n_db


def netlist_path(sim_dir, n_db):
    return os.path.join(sim_dir, "tpad_%sdB.sp" % _db_tag(n_db))


def log_path(sim_dir, n_db):
    return os.path.join(sim_dir, "tpad_%sdB.log" % _db_tag(n_db))


def write_netlist(path, n_db, r_series, r_shunt, z0=Z0):
    """Write an ngspice netlist for the T-pad at n_db."""
    lines = [
        "* T-pad attenuator at %g dB, Z0=%.1f" % (n_db, z0),
        "V1 in 0 DC 1",
        "R1 in mid %.6f" % r_series,
        "R3 mid out %.6f" % r_series,
        "R2 mid 0 %.6f" % r_shunt,
        "Rload out 0 %.1f" % z0,
        ".op",
        ".control",
        "run",
        "print v(out)",
        "print i(v1)",
        ".endc",
        ".end",
    ]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def run_ngspice(netlist, log):
    """Run ngspice in batch mode on netlist, capturing the log to log."""
    with open(log, "w") as f:
        proc = subprocess.run(["ngspice", "-b", netlist],
                              stdout=f, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError("ngspice failed on %s (exit %d):\n%s"
                           % (netlist, proc.returncode, proc.stderr))


def parse_log(log):
    """Return (v_out, i_in) parsed from an ngspice log (last match wins)."""
    v_out = i_in = None
    with open(log) as f:
        for line in f:
            m = re.match(r"^v\(out\) = (\S+)", line)
            if m:
                v_out = float(m.group(1))
                continue
            m = re.match(r"^i\(v1\) = (\S+)", line)
            if m:
                i_in = float(m.group(1))
    if v_out is None or i_in is None:
        raise RuntimeError("could not parse v(out)/i(v1) from %s" % log)
    return v_out, i_in


def attenuations(start, stop, step):
    """Attenuations from start to stop (inclusive) in step increments."""
    if step <= 0:
        raise ValueError("step must be positive, got %r" % step)
    vals = []
    n = start
    while n <= stop + 1e-9:
        vals.append(round(n, 9))
        n += step
    return vals


def generate(project_dir, start=1.0, stop=10.0, step=1.0, write=False,
             netlists_only=False):
    """Compute the resistor table.

    rows is a list of (n_db, r_series, r_shunt, sim_atten_db, sim_zin_ohm).
    When neither write nor netlists_only is given, only the closed-form
    resistor values are computed; sim_atten_db and sim_zin_ohm are None and no
    files are written.  With netlists_only, sim/tpad_<N>dB.sp is written for
    each step and ngspice is not run.  With write, ngspice is run for each
    step and the netlists, logs, and sim/resistor_table.csv are written.
    Returns (rows, csv_path); csv_path is None when write is False.
    """
    sim_dir = os.path.join(project_dir, "sim")
    csv_path = os.path.join(sim_dir, "resistor_table.csv")
    rows = []
    for n in attenuations(start, stop, step):
        r_series, r_shunt = tpad_resistors(n)
        if write or netlists_only:
            sp = netlist_path(sim_dir, n)
            write_netlist(sp, n, r_series, r_shunt)
        if write:
            log = log_path(sim_dir, n)
            run_ngspice(sp, log)
            v_out, i_in = parse_log(log)
            sim_atten = 20.0 * math.log10(1.0 / v_out)
            sim_zin = 1.0 / abs(i_in)
            rows.append((n, r_series, r_shunt, sim_atten, sim_zin))
            print("%6s dB   Rs=%9.4f  Rsh=%10.4f   sim: %7.3f dB, %7.3f ohm"
                  % (_db_tag(n), r_series, r_shunt, sim_atten, sim_zin))
        else:
            rows.append((n, r_series, r_shunt, None, None))
            print("%6s dB   Rs=%9.4f  Rsh=%10.4f"
                  % (_db_tag(n), r_series, r_shunt))
    if write:
        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["attenuation_db", "R_series_ohm_each", "R_shunt_ohm",
                        "simulated_attenuation_db", "simulated_Zin_ohm"])
            for n, rs, rsh, sa, sz in rows:
                w.writerow(["%g" % n, "%.3f" % rs, "%.3f" % rsh,
                            "%.3f" % sa, "%.2f" % sz])
    return rows, csv_path if write else None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=float, default=1.0,
                        help="first attenuation in dB (default: 1)")
    parser.add_argument("--stop", type=float, default=10.0,
                        help="last attenuation in dB, inclusive (default: 10)")
    parser.add_argument("--step", type=float, default=1.0,
                        help="attenuation step in dB (default: 1)")
    parser.add_argument("--project-dir", default=None,
                        help="project root (default: the script's grandparent)")
    parser.add_argument("--netlists", action="store_true",
                        help="write the per-dB netlists only, without running "
                             "ngspice or writing the CSV")
    parser.add_argument("--write", action="store_true",
                        help="run ngspice and write the netlists, logs, and "
                             "CSV (default: only print the table)")
    args = parser.parse_args(argv)
    project_dir = args.project_dir or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    rows, csv_path = generate(project_dir, args.start, args.stop, args.step,
                              write=args.write, netlists_only=args.netlists)
    if csv_path is not None:
        print("wrote %s (%d rows)" % (csv_path, len(rows)))


if __name__ == "__main__":
    main()
