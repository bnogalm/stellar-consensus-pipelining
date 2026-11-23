#!/usr/bin/env python3
"""Table of a repetitions log (LAT, BUD and RUN lines of 223-latency-reps3.sh): per flooding,
k and client, the mean over the repetitions and the range. Usage: reps-table.py <log>"""
import re
import statistics
import sys

rows = {}
for line in open(sys.argv[1], errors="replace"):
    m = re.match(r"(LAT|BUD|RUN) rep=(\d+) flood=(\w+) k=(\d+) client=(\w+): (.*)", line)
    if not m:
        continue
    kind, rep, flood, k, client, rest = m.groups()
    r = rows.setdefault((flood, int(k), client), {}).setdefault(int(rep), {})
    if kind == "LAT":
        x = re.search(r"mean (\d+), max \d+; p10 \d+, p50 (\d+), p90 (\d+)", rest)
        if x:
            r["mean"], r["p50"], r["p90"] = map(int, x.groups())
    elif kind == "BUD":
        x = re.search(r"opened (\d+) ms.*slot: mean (\d+) .*p50 (\d+) .*externalize: mean (\d+) ms; "
                      r"externalize to applied: mean (\d+)", rest)
        if x:
            r["gap"], r["wait"], r["wait50"], r["cons"], r["apply"] = map(int, x.groups())
    else:
        x = re.search(r"throughput (\d+) tx/s host cpu busy (\d+)%", rest)
        if x:
            r["tps"], r["cpu"] = map(int, x.groups())
cols = ["gap", "mean", "p50", "p90", "wait", "wait50", "cons", "apply", "tps", "cpu"]
print("flood  k client reps " + " ".join("%13s" % c for c in cols))
for key in sorted(rows, key=lambda x: (x[0] != "normal", x[1], x[2] != "one")):
    reps = [r for r in rows[key].values() if "mean" in r and "wait" in r and "tps" in r]
    if not reps:
        continue
    out = []
    for c in cols:
        v = [r[c] for r in reps]
        out.append("%5.0f %3d-%-4d" % (statistics.mean(v), min(v), max(v)))
    print("%-6s %d %-3s    %d   " % (key[0], key[1], key[2], len(reps)) + " ".join(out))
