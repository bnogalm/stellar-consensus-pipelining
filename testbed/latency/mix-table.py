#!/usr/bin/env python3
"""Table of a mixed-load log (MIX lines of 225-latency-mix.sh): per k and operators' client, the
mean over the repetitions for the operators (origin n1) and the users (origins n2 to n4).
Usage: mix-table.py <log>"""
import re
import statistics
import sys

rows = {}
for line in open(sys.argv[1], errors="replace"):
    m = re.match(r"MIX rep=(\d+) k=(\d+) client=(\w+) origin n(\d): txs (\d+), latency mean (\d+) "
                 r"p50 (\d+) p90 (\d+) p99 (\d+); wait mean (\d+) p50 (\d+); consensus (\d+); "
                 r"apply (\d+)", line)
    if not m:
        continue
    rep, k, client, o = int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4))
    vals = [int(x) for x in m.groups()[5:]]
    who = "oper" if o == 1 else "user"
    rows.setdefault((k, client, who), {}).setdefault(rep, []).append(vals)
names = ["mean", "p50", "p90", "p99", "wait", "wait50", "cons", "apply"]
print("k client who  reps " + " ".join("%14s" % n for n in names))
order = {"one": 0, "k200": 1, "k350": 2}
for key in sorted(rows, key=lambda x: (x[0], order.get(x[1], 9), x[2])):
    per_rep = [[statistics.mean(v[i] for v in vs) for i in range(len(names))]
               for vs in rows[key].values()]
    out = []
    for i in range(len(names)):
        c = [r[i] for r in per_rep]
        out.append("%5.0f %4.0f-%-4.0f" % (statistics.mean(c), min(c), max(c)))
    print("%d %-5s %-4s  %d   " % (key[0], key[1], key[2], len(per_rep)) + " ".join(out))
