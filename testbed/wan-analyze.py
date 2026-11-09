#!/usr/bin/env python3
"""Per-ledger timeline of a live testbed run, from the PipelineLive and PipelineApply log lines
(PipelineStudy in logs of the earlier prototype).

Usage: wan-analyze.py <run dir with n*/node.log> [first ledger] [last ledger]

For each validator and ledger N (all times on the host's monotonic clock, shared by the nodes):
  wait       armed(N) -> trigger(N)       timer slack before nominating N
  consensus  trigger(N) -> externalize(N)  nomination and ballot protocol
  queue      externalize(N) -> apply begin
  apply      apply begin -> apply end      applyLedger of N (execution, seal, commit)
  post       apply end -> armed(N+1)        completion on the main thread, then rearm
  interval   externalize(N-1) -> externalize(N)
"""
import glob
import os
import re
import statistics
import sys

LIVE = re.compile(r"PipelineLive event=(\w+) ledger=(\d+).*? t_ns=(\d+)")
STUDY = re.compile(r"Pipeline(?:Apply|Study) ledger=(\d+) close_ns=(\d+) total_apply_ns=(\d+) .*"
                   r"t_begin_ns=(\d+) t_end_ns=(\d+)")
TXLAT = re.compile(r"PipelineLive event=txlat ledger=(\d+) n=(\d+) ms=([\d,]*)")
CONSENSUS = re.compile(r"Got consensus: \[seq=(\d+), prev=\w+, txs=(\d+)")


def load(path):
    ev = {"trigger": {}, "externalize": {}, "armed": {}, "begin": {}, "end": {}, "exec": {},
          "txs": {}}
    with open(path, errors="replace") as f:
        for line in f:
            m = LIVE.search(line)
            if m:
                kind, seq, t = m.group(1), int(m.group(2)), int(m.group(3))
                ev[kind].setdefault(seq, t)
                continue
            m = STUDY.search(line)
            if m:
                seq = int(m.group(1))
                ev["exec"][seq] = int(m.group(3))
                ev["begin"][seq] = int(m.group(4))
                ev["end"][seq] = int(m.group(5))
                continue
            m = CONSENSUS.search(line)
            if m:
                ev["txs"][int(m.group(1))] = int(m.group(2))
    return ev


def segments(ev, first, last):
    out = {k: [] for k in ("wait", "consensus", "queue", "apply", "execution", "post", "interval")}
    for n in sorted(ev["externalize"]):
        if n < first or n > last:
            continue
        g = lambda k, s=n: ev[k].get(s)
        pairs = {
            "wait": (g("armed"), g("trigger")),
            "consensus": (g("trigger"), g("externalize")),
            "queue": (g("externalize"), g("begin")),
            "apply": (g("begin"), g("end")),
            "post": (g("end"), ev["armed"].get(n + 1)),
            "interval": (ev["externalize"].get(n - 1), g("externalize")),
        }
        for k, (a, b) in pairs.items():
            if a is not None and b is not None:
                out[k].append((b - a) / 1e6)
        if n in ev["exec"]:
            out["execution"].append(ev["exec"][n] / 1e6)
    return out


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


def main():
    run = sys.argv[1]
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    last = int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 31
    logs = sorted(glob.glob(os.path.join(run, "n*", "node.log")),
                  key=lambda p: int(re.search(r"n(\d+)", os.path.basename(os.path.dirname(p))).group(1)))
    keys = ("wait", "consensus", "queue", "apply", "execution", "post", "interval")
    allseg = {k: [] for k in keys}
    print(f"run {run}, ledgers {first} to {min(last, 1 << 31)}; mean ms (p50 / p99)")
    print(f"{'node':<6}{'ledgers':>8}" + "".join(f"{k:>22}" for k in keys))
    for path in logs:
        node = os.path.basename(os.path.dirname(path))
        ev = load(path)
        seg = segments(ev, first, last)
        for k in keys:
            allseg[k] += seg[k]
        row = f"{node:<6}{len(seg['consensus']):>8}"
        for k in keys:
            xs = seg[k]
            row += f"{statistics.mean(xs):>9.1f} ({pct(xs, 50):>5.0f}/{pct(xs, 99):>5.0f})" if xs else f"{'-':>22}"
        print(row)
    row = f"{'all':<6}{len(allseg['consensus']):>8}"
    for k in keys:
        xs = allseg[k]
        row += f"{statistics.mean(xs):>9.1f} ({pct(xs, 50):>5.0f}/{pct(xs, 99):>5.0f})" if xs else f"{'-':>22}"
    print(row)
    # Throughput, from the last node's view of the same ledgers.
    seqs = [n for n in sorted(ev["externalize"]) if first <= n <= last and n in ev["txs"]]
    if len(seqs) > 1:
        span = (ev["externalize"][seqs[-1]] - ev["externalize"][seqs[0]]) / 1e9
        txs = sum(ev["txs"][n] for n in seqs[1:])
        print(f"ledgers {len(seqs)}, txs per ledger {txs / (len(seqs) - 1):.0f}, "
              f"ledger interval {1000 * span / (len(seqs) - 1):.0f} ms, throughput {txs / span:.0f} tx/s")
    # Transaction latency at node 1, from its first receipt of a transaction to externalize (the
    # load may be submitted at node 1 or flooded to it from the nodes that submit it).
    lat = []
    with open(logs[0], errors="replace") as f:
        for line in f:
            m = TXLAT.search(line)
            if m and first <= int(m.group(1)) <= last and m.group(3):
                lat += [int(x) for x in m.group(3).split(",")]
    if lat:
        print(f"tx latency (submit at node 1 to externalize): mean {statistics.mean(lat):.0f} ms, "
              f"p50 {pct(lat, 50)} ms, p90 {pct(lat, 90)} ms, p99 {pct(lat, 99)} ms, n {len(lat)}")


if __name__ == "__main__":
    main()
