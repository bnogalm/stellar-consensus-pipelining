#!/usr/bin/env python3
"""Chart data of results/apply-and-consensus-by-size.md: consensus and apply against ledger size.

Usage: size-apply-charts.py <txset-timings.py> <data dir> <out.json>
  e.g. size-apply-charts.py testbed/txset-timings.py results/data/size-apply \\
           results/apply-and-consensus-by-size.json
Reads the rounds ksw-pay-k1-tx-n* of the data directory: consensus from the tx set timings (all
ledgers, and those with one tx set nominated), apply from the summary of each round.
"""
import json
import os
import re
import subprocess
import sys

timings, data, out = sys.argv[1], sys.argv[2], sys.argv[3]
rounds = sorted((int(d.rsplit("-n", 1)[1]), os.path.join(data, d)) for d in os.listdir(data)
                if d.startswith("ksw-pay-k1-tx-n"))
sizes, total, one, apply = [], [], [], []
for n, path in rounds:
    text = subprocess.run([sys.executable, timings, path], capture_output=True, text=True,
                          check=True).stdout
    sizes.append(n)
    total.append(int(re.search(r"^total\s+(\d+)", text, re.M).group(1)))
    one.append(int(re.search(r"total with one tx set nominated: (\d+) ms", text).group(1)))
    row = next(l for l in open(os.path.join(path, "summary.txt")) if l.startswith("all "))
    means = re.findall(r"(\d+\.\d) \(", row)  # wait, consensus, queue, apply, execution, post, interval
    apply.append(round(float(means[3])))


def series(name, color, ys, dash=None):
    s = {"name": name, "color": color, "x": sizes, "y": ys,
         "hover": [f"{n:,} tx per ledger: {y:,} ms" for n, y in zip(sizes, ys)]}
    if dash:
        s["dash"] = dash
    return s


charts = {"size": {
    "title": "Consensus and apply against ledger size: the testbed, payments, k = 1",
    "xTitle": "Transactions per ledger", "xType": "linear", "yTitle": "ms per ledger",
    "series": [series("Consensus", "--s1", total),
               series("Consensus, ledgers with one tx set nominated", "--s1", one, "dot"),
               series("Apply", "--s2", apply)]}}
with open(out, "w", encoding="utf-8", newline="\n") as f:
    json.dump(charts, f, indent=1)
    f.write("\n")
print(sizes, total, one, apply)
