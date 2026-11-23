#!/usr/bin/env python3
"""For a run dir with n1/node.log: when each slot is armed, fires, externalizes and is applied,
relative to its own fire time, and the histogram of the transaction latency to externalize in
units of the ledger interval. Usage: slot-timing.py <run dir> [first ledger]"""
import re
import statistics
import sys

run = sys.argv[1]
first = int(sys.argv[2]) if len(sys.argv) > 2 else 0
ev = {}
lat = {}
kinds = {}
for line in open(run + "/n1/node.log", errors="replace"):
    m = re.search(r"PipelineLive event=(\w+) ledger=(\d+)(.*)", line)
    if m:
        kind, seq, rest = m.group(1), int(m.group(2)), m.group(3)
        kinds[kind] = kinds.get(kind, 0) + 1
        if kind == "txlat":
            t = re.search(r"ms=([\d,]*)", rest)
            if t and t.group(1):
                lat[seq] = [int(x) for x in t.group(1).split(",")]
            continue
        t = re.search(r"t_ns=(\d+)", rest)
        if t:
            ev.setdefault(seq, {}).setdefault(kind, int(t.group(1)))
        d = re.search(r"delay_ms=(-?\d+)", rest)
        if d and kind == "armed":
            ev[seq].setdefault("delay", int(d.group(1)))
        continue
    m = re.search(r"PipelineApply ledger=(\d+) .*t_end_ns=(\d+)", line)
    if m:
        ev.setdefault(int(m.group(1)), {})["applied"] = int(m.group(2))
print("event kinds:", kinds)
seqs = [s for s in sorted(lat) if s >= first and s in ev and "externalize" in ev[s]]
if not seqs:
    sys.exit("no ledgers")
ext = [ev[s]["externalize"] for s in seqs]
interval = (ext[-1] - ext[0]) / 1e6 / max(len(ext) - 1, 1)
print("ledgers %d, interval %.0f ms" % (len(seqs), interval))


def stat(name, xs):
    if xs:
        xs = sorted(xs)
        print("%-34s mean %7.0f  p10 %7.0f  p50 %7.0f  p90 %7.0f  (n %d)" % (
            name, statistics.mean(xs), xs[len(xs) // 10], xs[len(xs) // 2],
            xs[len(xs) * 9 // 10], len(xs)))


for a, b in (("armed", "externalize"), ("armed", "applied"), ("externalize", "applied")):
    stat("%s to %s, ms" % (a, b),
         [(ev[s][b] - ev[s][a]) / 1e6 for s in seqs if a in ev[s] and b in ev[s]])
stat("armed delay_ms", [ev[s]["delay"] for s in seqs if "delay" in ev[s]])
for other in sorted(k for k in kinds if k not in ("txlat", "armed", "externalize")):
    stat("%s to externalize, ms" % other,
         [(ev[s]["externalize"] - ev[s][other]) / 1e6 for s in seqs if other in ev[s]])
# the ledger applied last when slot s is armed: offset of s from it
applied = sorted((ev[s]["applied"], s) for s in ev if "applied" in ev[s])
offs = {}
j = 0
for s in seqs:
    if "armed" not in ev[s]:
        continue
    while j < len(applied) and applied[j][0] <= ev[s]["armed"]:
        j += 1
    if j:
        o = s - applied[j - 1][1]
        offs[o] = offs.get(o, 0) + 1
print("slot armed minus last applied ledger at that time:", dict(sorted(offs.items())))
allx = [x for s in seqs for x in lat[s]]
stat("tx receipt to externalize, ms", allx)
h = {}
for x in allx:
    b = int(x / interval * 2) / 2
    h[b] = h.get(b, 0) + 1
print("receipt to externalize, in intervals (bin 0.5): " + ", ".join(
    "%.1f: %.1f%%" % (b, 100 * c / len(allx)) for b, c in sorted(h.items()) if c / len(allx) > 0.003))
