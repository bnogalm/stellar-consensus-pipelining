#!/usr/bin/env python3
"""Where the latency of a run goes, per transaction, from n1/node.log: receipt to the trigger of
the slot it entered (the wait), trigger to externalize, externalize to applied.
Usage: tx-budget.py <run dir> [first ledger]"""
import re
import statistics
import sys

run = sys.argv[1]
first = int(sys.argv[2]) if len(sys.argv) > 2 else 40
trig, ext, end, lat = {}, {}, {}, {}
for line in open(run + "/n1/node.log", errors="replace"):
    m = re.search(r"PipelineLive event=(\w+) ledger=(\d+)(.*)", line)
    if m:
        kind, seq, rest = m.group(1), int(m.group(2)), m.group(3)
        if kind == "txlat":
            t = re.search(r"ms=([\d,]*)", rest)
            if t and t.group(1):
                lat[seq] = [int(x) for x in t.group(1).split(",")]
            continue
        t = re.search(r"t_ns=(\d+)", rest)
        if t and kind == "trigger":
            trig.setdefault(seq, int(t.group(1)) / 1e6)
        if t and kind == "externalize":
            ext.setdefault(seq, int(t.group(1)) / 1e6)
        continue
    m = re.search(r"PipelineApply ledger=(\d+) .*t_end_ns=(\d+)", line)
    if m:
        end[int(m.group(1))] = int(m.group(2)) / 1e6
seqs = sorted(s for s in lat if s >= first and s in trig and s in ext and s in end)
ts = [trig[s] for s in seqs]
gaps = [b - a for a, b in zip(ts, ts[1:])]
wait, cons, app = [], [], []
for s in seqs:
    for x in lat[s]:
        wait.append(x - (ext[s] - trig[s]))
        cons.append(ext[s] - trig[s])
        app.append(end[s] - ext[s])
wait.sort()
n = len(wait)
print("gap between two slots opened %.0f ms; transactions %d" % (statistics.mean(gaps), n))
print("receipt to the opening of its slot: mean %.0f  p10 %.0f  p50 %.0f  p90 %.0f ms" % (
    statistics.mean(wait), wait[n // 10], wait[n // 2], wait[n * 9 // 10]))
print("opening to externalize: mean %.0f ms; externalize to applied: mean %.0f ms; total %.0f ms" % (
    statistics.mean(cons), statistics.mean(app),
    statistics.mean(wait) + statistics.mean(cons) + statistics.mean(app)))
edges = [0, 100, 200, 300, 400, 500, 600, 700, 800, 1000, 1200, 1600, 1e9]
h = [0] * (len(edges) - 1)
for x in wait:
    for i in range(len(h)):
        if x < edges[i + 1]:
            h[i] += 1
            break
print("wait histogram: " + ", ".join("<%s: %.0f%%" % (
    "%d" % edges[i + 1] if edges[i + 1] < 1e9 else "inf", 100 * c / n) for i, c in enumerate(h)))
