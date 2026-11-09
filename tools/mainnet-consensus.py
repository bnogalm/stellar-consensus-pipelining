"""Consensus time on mainnet, seen from a watcher node (not a validator).

Reads the compact logs in results/data/mainnet-watch: envelopes.log.gz (one SCP envelope received
per line: time, sender, statement type, slot) and events.log.gz (local externalize, apply time and
ledger contents). For each slot: first NOMINATE seen -> first PREPARE seen -> local externalize,
the time since the previous externalize, and the apply and commit time on the watcher.

Usage: mainnet-consensus.py [first_slot]
"""
import gzip
import os
import re
import statistics
import sys

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "data", "mainnet-watch")


def ts(s):
    h, m, x = s[11:23].split(":")
    return ((int(s[8:10]) * 24 + int(h)) * 60 + int(m)) * 60 + float(x)


first, ext, close, txs, ops = {}, {}, {}, {}, {}
for line in gzip.open(os.path.join(DATA, "envelopes.log.gz"), "rt"):
    t, _, kind, slot = line.split()
    first.setdefault((int(slot[2:]), kind[9:]), ts(t))
for line in gzip.open(os.path.join(DATA, "events.log.gz"), "rt", errors="replace"):
    if "PipelineLive event=externalize" in line:
        ext.setdefault(int(re.search(r"ledger=(\d+)", line)[1]), ts(line))
    elif "PipelineStudy ledger=" in line or "PipelineApply ledger=" in line:
        close[int(re.search(r"ledger=(\d+)", line)[1])] = int(re.search(r"close_ns=(\d+)", line)[1]) / 1e6
    elif m := re.search(r"seq=(\d+).*txs=(\d+), ops=(\d+)", line):
        txs[int(m[1])], ops[int(m[1])] = int(m[2]), int(m[3])

start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
slots = sorted(n for n in ext if n >= start and n - 1 in ext and (n, "NOMINATE") in first
               and (n, "PREPARE") in first and ext[n] > first[(n, "NOMINATE")])


def show(name, v, unit="ms"):
    v = sorted(v)
    p = lambda q: v[min(len(v) - 1, int(q * len(v)))]
    print(f"| {name} | {statistics.mean(v):,.0f} | {p(.1):,.0f} | {p(.5):,.0f} | {p(.9):,.0f} | {p(.99):,.0f} |")


print(f"{len(slots)} ledgers, {slots[0]} to {slots[-1]}\n")
print("| Per ledger | Mean | p10 | p50 | p90 | p99 |\n|---|---|---|---|---|---|")
show("Interval, externalize to externalize (ms)", [(ext[n] - ext[n - 1]) * 1000 for n in slots])
show("Previous externalize to first nomination seen (ms)", [(first[(n, "NOMINATE")] - ext[n - 1]) * 1000 for n in slots])
show("Consensus: first nomination seen to externalize (ms)", [(ext[n] - first[(n, "NOMINATE")]) * 1000 for n in slots])
show("  nomination: first NOMINATE to first PREPARE (ms)", [(first[(n, "PREPARE")] - first[(n, "NOMINATE")]) * 1000 for n in slots])
show("  ballot: first PREPARE to externalize (ms)", [(ext[n] - first[(n, "PREPARE")]) * 1000 for n in slots])
show("Apply and commit on the watcher (ms)", [close[n] for n in slots if n in close])
show("Transactions", [txs[n] for n in slots if n in txs])
show("Operations", [ops[n] for n in slots if n in ops])
