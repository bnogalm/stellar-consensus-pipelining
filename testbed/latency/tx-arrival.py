#!/usr/bin/env python3
"""When node 1 received each transaction of a run and how long it took to reach the other nodes.
From event=txlat (receipt to externalize, per transaction, in tx set order, the same on every
node) and event=externalize of each node, all on the host's monotonic clock.
Usage: tx-arrival.py <run dir> [first ledger]"""
import os
import re
import statistics
import sys

run = sys.argv[1]
first = int(sys.argv[2]) if len(sys.argv) > 2 else 40


def load(node):
    ext, lat = {}, {}
    path = os.path.join(run, node, "node.log")
    if not os.path.exists(path):
        return None
    for line in open(path, errors="replace"):
        m = re.search(r"PipelineLive event=(\w+) ledger=(\d+)(.*)", line)
        if not m:
            continue
        seq = int(m.group(2))
        if m.group(1) == "txlat":
            t = re.search(r"ms=([\d,]*)", m.group(3))
            if t and t.group(1):
                lat[seq] = [int(x) for x in t.group(1).split(",")]
        elif m.group(1) == "externalize":
            t = re.search(r"t_ns=(\d+)", m.group(3))
            if t:
                ext.setdefault(seq, int(t.group(1)) / 1e6)
    return {s: [ext[s] - x for x in lat[s]] for s in lat if s in ext and s >= first}


n1 = load("n1")
rec = sorted(x for s in n1 for x in n1[s])
print("transactions %d over %.0f s" % (len(rec), (rec[-1] - rec[0]) / 1000))
# arrivals per 10 ms bin of the 100 ms cycle, and per 100 ms window
phase = [0] * 10
for x in rec:
    phase[int(x % 100) // 10] += 1
print("share of the receipts in each 10 ms of a 100 ms cycle: " +
      " ".join("%.0f%%" % (100 * c / len(rec)) for c in phase))
gaps = sorted(b - a for a, b in zip(rec, rec[1:]))
print("gap between two receipts, ms: mean %.1f p50 %.1f p90 %.1f p99 %.1f max %.0f" % (
    statistics.mean(gaps), gaps[len(gaps) // 2], gaps[len(gaps) * 9 // 10],
    gaps[len(gaps) * 99 // 100], gaps[-1]))
win = {}
for x in rec:
    win[int(x // 100)] = win.get(int(x // 100), 0) + 1
w = sorted(win.get(i, 0) for i in range(min(win), max(win) + 1))
print("receipts per 100 ms window: mean %.1f p10 %d p50 %d p90 %d max %d, empty %.0f%%" % (
    statistics.mean(w), w[len(w) // 10], w[len(w) // 2], w[len(w) * 9 // 10], w[-1],
    100 * w.count(0) / len(w)))
for j in range(2, 8):
    nj = load("n%d" % j)
    if not nj:
        continue
    d = sorted(b - a for s in n1 if s in nj and len(nj[s]) == len(n1[s])
               for a, b in zip(n1[s], nj[s]))
    if d:
        print("receipt at n%d after n1, ms: mean %.0f p10 %.0f p50 %.0f p90 %.0f p99 %.0f" % (
            j, statistics.mean(d), d[len(d) // 10], d[len(d) // 2], d[len(d) * 9 // 10],
            d[len(d) * 99 // 100]))
