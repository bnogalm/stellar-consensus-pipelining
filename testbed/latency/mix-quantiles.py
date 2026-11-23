#!/usr/bin/env python3
"""Distribution of the latency of the transactions of one origin, pooled over runs, and the
share of transactions that entered the slot opened next by the time left to its opening.

Usage: mix-quantiles.py <origin node number> <label>=<run dir>[,<run dir>...] ...
Prints one JSON object: {label: {"n": count, "q": [latency at 0, 2.5, ... 100 %],
"enter": {ms left (bin of 50): share that entered the next slot},
"parts": {wait|consensus|apply|total: {mean, sd, p10, p50, p90, mode}}}}, the mode being the
start of the 100 ms band with most transactions.
Same parsing and origin rule as mix-lat.py."""
import bisect
import json
import statistics
import os
import re
import sys


def load(run):
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
    return nodes


def run_stats(run, origin, first=40):
    nodes = load(run)
    trig, ext, end, _ = nodes[origin]
    seqs = sorted(trig)
    times = [trig[s] for s in seqs]
    lats, bins, parts = [], {}, []
    for s in sorted(nodes[1][3]):
        if s < first:
            continue
        ok = [j for j in nodes if s in nodes[j][3] and s in nodes[j][1] and s in nodes[j][2]
              and s in nodes[j][0] and len(nodes[j][3][s]) == len(nodes[1][3][s])]
        if origin not in ok or len(ok) < 5:
            continue
        for i in range(len(nodes[1][3][s])):
            rec = {j: nodes[j][1][s] - nodes[j][3][s][i] for j in ok}
            if min(rec, key=rec.get) != origin:
                continue
            r = rec[origin]
            lats.append(end[s] - r)
            parts.append((trig[s] - r, ext[s] - trig[s], end[s] - ext[s]))
            k = bisect.bisect_left(times, r)
            if 0 < k < len(seqs):
                b = int((times[k] - r) // 50) * 50
                e = bins.setdefault(b, [0, 0])
                e[0] += 1
                e[1] += seqs[k] == s
    return lats, bins, parts


out = {}
origin = int(sys.argv[1])
for arg in sys.argv[2:]:
    label, runs = arg.split("=", 1)
    lats, bins, parts = [], {}, []
    for run in runs.split(","):
        l, b, p = run_stats(run, origin)
        lats += l
        parts += p
        for key, e in b.items():
            t = bins.setdefault(key, [0, 0])
            t[0] += e[0]
            t[1] += e[1]
    lats.sort()
    n = len(lats)
    stats = {}
    for i, name in enumerate(("wait", "consensus", "apply", "total")):
        xs = sorted(p[i] for p in parts) if i < 3 else lats
        bands = {}
        for x in xs:
            bands[int(x // 100)] = bands.get(int(x // 100), 0) + 1
        stats[name] = {"mean": round(statistics.mean(xs)), "sd": round(statistics.pstdev(xs)),
                       "p10": round(xs[len(xs) // 10]), "p50": round(xs[len(xs) // 2]),
                       "p90": round(xs[len(xs) * 9 // 10]),
                       "mode": 100 * max(bands, key=bands.get)}
    out[label] = {
        "n": n,
        "parts": stats,
        "q": [round(lats[min(n - 1, int(p / 40 * n))]) for p in range(41)],
        "enter": {str(b): round(100 * e[1] / e[0], 1) for b, e in sorted(bins.items())
                  if e[0] >= n / 400 and b <= 1000},
    }
print(json.dumps(out))
