#!/usr/bin/env python3
"""For every transaction of a run (n1/node.log): the slot that node 1 triggered next after it
received the transaction, and the slot it entered. Prints the histogram of (entered - next), the
time left to that next trigger split by outcome, and the ledger sizes.
Usage: tx-slots.py <run dir> [first ledger]"""
import bisect
import re
import statistics
import sys

run = sys.argv[1]
first = int(sys.argv[2]) if len(sys.argv) > 2 else 40
trig, ext, lat = {}, {}, {}
for line in open(run + "/n1/node.log", errors="replace"):
    m = re.search(r"PipelineLive event=(\w+) ledger=(\d+)(.*)", line)
    if not m:
        continue
    kind, seq, rest = m.group(1), int(m.group(2)), m.group(3)
    if kind == "txlat":
        t = re.search(r"ms=([\d,]*)", rest)
        if t and t.group(1):
            try:
                lat[seq] = [int(x) for x in t.group(1).split(",")]
            except ValueError:  # a line cut short
                pass
        continue
    t = re.search(r"t_ns=(\d+)", rest)
    if t and kind == "trigger":
        trig.setdefault(seq, int(t.group(1)) / 1e6)
    if t and kind == "externalize":
        ext.setdefault(seq, int(t.group(1)) / 1e6)
seqs = sorted(s for s in trig if s >= first)
times = [trig[s] for s in seqs]
gaps = sorted(b - a for a, b in zip(times, times[1:]))
print("trigger to trigger, ms: mean %.0f p10 %.0f p50 %.0f p90 %.0f" % (
    statistics.mean(gaps), gaps[len(gaps) // 10], gaps[len(gaps) // 2], gaps[len(gaps) * 9 // 10]))
sizes = sorted(len(lat[s]) for s in lat if s >= first)
print("ledger sizes: mean %.0f p10 %d p50 %d p90 %d max %d" % (
    statistics.mean(sizes), sizes[len(sizes) // 10], sizes[len(sizes) // 2],
    sizes[len(sizes) * 9 // 10], sizes[-1]))
skip = {}
left = {}
for s in sorted(lat):
    if s < first or s not in ext:
        continue
    for x in lat[s]:
        r = ext[s] - x
        i = bisect.bisect_left(times, r)
        if i >= len(seqs) or i == 0:
            continue
        d = s - seqs[i]
        skip[d] = skip.get(d, 0) + 1
        left.setdefault(d, []).append(times[i] - r)
n = sum(skip.values())
print("entered slot minus the next slot triggered after receipt (share, mean ms left to that trigger):")
for d in sorted(skip):
    if skip[d] / n > 0.002:
        print("  %+d: %5.1f%%  %4.0f ms" % (d, 100 * skip[d] / n, statistics.mean(left[d])))
# by time left to the next trigger, in bins of 50 ms: share that entered that slot
bins = {}
for d, xs in left.items():
    for x in xs:
        b = int(x // 50) * 50
        e = bins.setdefault(b, [0, 0])
        e[0] += 1
        e[1] += d == 0
print("entered the next slot, by ms left to its trigger: " + ", ".join(
    "%d: %.0f%%" % (b, 100 * e[1] / e[0]) for b, e in sorted(bins.items()) if e[0] > n / 300))
