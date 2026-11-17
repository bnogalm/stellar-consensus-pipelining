#!/usr/bin/env python3
"""Apply time per ledger against its size: fit apply = F + e * n on the PipelineStudy lines.

Usage:
  apply-fit.py replay <study.log[.gz]> <ledger,txs csv> [skip=32]
  apply-fit.py live <watch.log[.gz]> <replay study.log[.gz]> [skip_ledgers=300]

replay: the timing lines of a replay, with the transactions per ledger from a CSV.
live:   a live watcher's lines ("Got consensus" gives transactions and operations) against a
        replay of the same ledgers on the same machine. skip_ledgers drops the first ones the
        watcher applied, which include the catchup and the ledgers it buffered meanwhile.
The PipelineStudy lines come from upstream stellar-core with the per-ledger timing patch of
results/mainnet-steps.md. Data: results/data/size-apply.
"""
import csv
import gzip
import re
import statistics
import sys

STUDY = re.compile(r"PipelineStudy ledger=(\d+) (.*)")
CONS = re.compile(r"Got consensus: \[seq=(\d+), prev=\w+, txs=(\d+), ops=(\d+)")


def lines(path):
    return (gzip.open if path.endswith(".gz") else open)(path, "rt", errors="replace")


def study(path):
    out = {}
    for line in lines(path):
        m = STUDY.search(line)
        if m:
            out[int(m[1])] = {k: int(v) / 1e6 for k, v in (kv.split("=") for kv in m[2].split())}
    return out


def fit(xs, ys):
    mx, my = statistics.mean(xs), statistics.mean(ys)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
    a = my - b * mx
    st = sum((y - my) ** 2 for y in ys)
    return a, b, 1 - sum((y - a - b * x) ** 2 for x, y in zip(xs, ys)) / st


def p(v, q):
    v = sorted(v)
    return v[min(len(v) - 1, int(q * len(v)))]


EDGES = [0, 100, 200, 300, 400, 500, 600, 800, 1000, 5000]
KEYS = ("close_ns", "total_apply_ns", "seal_ns", "commit_ns", "meta_ns")

if sys.argv[1] == "replay":
    rows = study(sys.argv[2])
    txs = {int(r["ledger"]): int(r["txs"]) for r in csv.DictReader(lines(sys.argv[3]))}
    skip = int(sys.argv[4]) if len(sys.argv) > 4 else 32
    ledgers = [L for L in sorted(rows)[skip:] if L in txs]
    xs = [txs[L] for L in ledgers]
    print(f"{len(ledgers)} ledgers {ledgers[0]}..{ledgers[-1]}, txs mean {statistics.mean(xs):.0f}")
    for key in KEYS:
        ys = [rows[L].get(key, 0) for L in ledgers]
        a, b, r2 = fit(xs, ys)
        print(f"{key:15s} mean {statistics.mean(ys):6.1f} ms  fit {a:6.1f} + {b:.3f}/tx  R2 {r2:.2f}")
    print("\nclose by transactions per ledger (p50, ms):")
    for lo, hi in zip(EDGES, EDGES[1:]):
        sel = [L for L in ledgers if lo <= txs[L] < hi]
        if len(sel) >= 20:
            c = statistics.median(rows[L]["close_ns"] for L in sel)
            mt = statistics.mean(txs[L] for L in sel)
            print(f"  {lo:4d}-{hi:<4d} n={len(sel):5d} txs {mt:5.0f}  close {c:6.1f}  per tx {c / mt:.3f}")
else:
    live, rep = study(sys.argv[2]), study(sys.argv[3])
    skip = int(sys.argv[4]) if len(sys.argv) > 4 else 300
    size = {}
    for line in lines(sys.argv[2]):
        m = CONS.search(line)
        if m:
            size[int(m[1])] = (int(m[2]), int(m[3]))
    start = min(size) + skip
    common = sorted(L for L in live if L in rep and L in size and L >= start)
    tx = [size[L][0] for L in common]
    op = [size[L][1] for L in common]
    print(f"{len(common)} ledgers in both, {common[0]}..{common[-1]}; txs mean {statistics.mean(tx):.0f}"
          f" (p10 {p(tx, .1)}, p90 {p(tx, .9)}, max {max(tx)}), ops per tx {sum(op) / sum(tx):.2f}")
    for key in KEYS:
        for name, src in (("live", live), ("replay", rep)):
            ys = [src[L][key] for L in common]
            a, b, r2 = fit(tx, ys)
            ao, bo, r2o = fit(op, ys)
            print(f"{key:15s} {name:6s} mean {statistics.mean(ys):6.1f} p50 {statistics.median(ys):6.1f}"
                  f" | {a:6.1f} + {b:.3f}/tx R2 {r2:.2f} | {ao:6.1f} + {bo:.3f}/op R2 {r2o:.2f}")
    r = [live[L]["close_ns"] / rep[L]["close_ns"] for L in common if rep[L]["close_ns"] > 0]
    print(f"close live / replay, same ledger: p50 {statistics.median(r):.2f}")
    print("\nclose by transactions per ledger (p50, ms): live / replay")
    for lo, hi in zip(EDGES, EDGES[1:]):
        sel = [L for L in common if lo <= size[L][0] < hi]
        if len(sel) >= 15:
            lv = statistics.median(live[L]["close_ns"] for L in sel)
            rv = statistics.median(rep[L]["close_ns"] for L in sel)
            mt = statistics.mean(size[L][0] for L in sel)
            mo = statistics.mean(size[L][1] for L in sel)
            print(f"  {lo:4d}-{hi:<4d} n={len(sel):4d} txs {mt:5.0f} ops/tx {mo / mt:.2f}"
                  f"  {lv:6.1f} / {rv:6.1f}")
