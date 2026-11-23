#!/usr/bin/env python3
"""Latency by origin in a run with load from several validators (n1..n7/node.log).
The origin of a transaction is the validator that received it first (txlat lists are in tx set
order, the same on every node; receipt = that node's externalize - ms). For the transactions of
each origin: latency from the receipt at the origin to the end of apply on the origin, and its
split in wait (to the origin's trigger of the slot), consensus and apply.
Usage: mix-lat.py <run dir> [first ledger]   -> one line per origin with transactions"""
import os
import re
import statistics
import sys

run = sys.argv[1]
first = int(sys.argv[2]) if len(sys.argv) > 2 else 40
nodes = {}
for j in range(1, 8):
    path = os.path.join(run, "n%d" % j, "node.log")
    if not os.path.exists(path):
        continue
    trig, ext, end, lat = {}, {}, {}, {}
    for line in open(path, errors="replace"):
        m = re.search(r"PipelineLive event=(\w+) ledger=(\d+)(.*)", line)
        if m:
            kind, seq, rest = m.group(1), int(m.group(2)), m.group(3)
            if kind == "txlat":
                t = re.search(r"ms=([\d,]*)\s*$", rest)
                if t and t.group(1):
                    try:
                        lat[seq] = [int(x) for x in t.group(1).split(",")]
                    except ValueError:
                        pass
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
    nodes[j] = (trig, ext, end, lat)
out = {}
for s in sorted(nodes[1][3]):
    if s < first:
        continue
    ok = [j for j in nodes if s in nodes[j][3] and s in nodes[j][1] and s in nodes[j][2]
          and s in nodes[j][0] and len(nodes[j][3][s]) == len(nodes[1][3][s])]
    if 1 not in ok or len(ok) < 5:
        continue
    for i in range(len(nodes[1][3][s])):
        rec = {j: nodes[j][1][s] - nodes[j][3][s][i] for j in ok}
        o = min(rec, key=rec.get)
        trig, ext, end, _ = nodes[o]
        out.setdefault(o, []).append((end[s] - rec[o], trig[s] - rec[o], ext[s] - trig[s],
                                      end[s] - ext[s]))
for o in sorted(out):
    v = out[o]
    if len(v) < 500:
        continue
    tot = sorted(x[0] for x in v)
    wait = sorted(x[1] for x in v)
    n = len(v)
    print("origin n%d: txs %d, latency mean %.0f p50 %.0f p90 %.0f p99 %.0f; wait mean %.0f p50 %.0f; "
          "consensus %.0f; apply %.0f" % (
              o, n, statistics.mean(tot), tot[n // 2], tot[n * 9 // 10], tot[n * 99 // 100],
              statistics.mean(wait), wait[n // 2], statistics.mean(x[2] for x in v),
              statistics.mean(x[3] for x in v)))
