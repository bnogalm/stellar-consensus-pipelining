#!/usr/bin/env python3
"""Latency of every transaction of a testbed run, from node 1's first receipt of it to the end
of the apply of its ledger on node 1, and its distribution.

Usage: latency-dist.py <run dir with n1/node.log> [first ledger] [last ledger] [json out]

From the log lines of node 1: PipelineLive event=txlat (receipt to externalize, one value per
transaction of the ledger), event=externalize and PipelineApply (apply end), all on the host's
monotonic clock. A transaction is counted when its ledger is in the range.
"""
import json
import os
import re
import statistics
import sys

LIVE = re.compile(r"PipelineLive event=externalize ledger=(\d+).*? t_ns=(\d+)")
APPLY = re.compile(r"PipelineApply ledger=(\d+) .*t_end_ns=(\d+)")
TXLAT = re.compile(r"PipelineLive event=txlat ledger=(\d+) n=(\d+) ms=([\d,]*)")


def pct(xs, p):
    return xs[min(len(xs) - 1, int(p / 100 * len(xs)))]


def main():
    run = sys.argv[1]
    first = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    last = int(sys.argv[3]) if len(sys.argv) > 3 else 1 << 31
    ext, end, lat = {}, {}, {}
    with open(os.path.join(run, "n1", "node.log"), errors="replace") as f:
        for line in f:
            m = TXLAT.search(line)
            if m:
                if m.group(3):
                    lat[int(m.group(1))] = [int(x) for x in m.group(3).split(",")]
                continue
            m = LIVE.search(line)
            if m:
                ext.setdefault(int(m.group(1)), int(m.group(2)))
                continue
            m = APPLY.search(line)
            if m:
                end[int(m.group(1))] = int(m.group(2))
    to_ext, to_applied, after, sizes = [], [], [], []
    for seq in sorted(lat):
        if seq < first or seq > last or seq not in ext or seq not in end:
            continue
        rest = (end[seq] - ext[seq]) / 1e6
        after.append(rest)
        sizes.append(len(lat[seq]))
        to_ext += lat[seq]
        to_applied += [x + rest for x in lat[seq]]
    if not to_applied:
        sys.exit("no transactions in the range")
    to_applied.sort()
    to_ext.sort()
    seqs = [s for s in sorted(ext) if first <= s <= last]
    span = (ext[seqs[-1]] - ext[seqs[0]]) / 1e9
    out = {
        "ledgers": len(sizes),
        "txs": len(to_applied),
        "tx_per_ledger": statistics.mean(sizes),
        "interval_ms": 1000 * span / max(len(seqs) - 1, 1),
        "throughput": len(to_applied) / span if span else 0,
        "to_externalize_mean": statistics.mean(to_ext),
        "externalize_to_applied_mean": statistics.mean(after),
        "min": to_applied[0],
        "mean": statistics.mean(to_applied),
        "max": to_applied[-1],
    }
    for p in (10, 50, 90, 99):
        out["p%d" % p] = pct(to_applied, p)
    print("ledgers %d, %.0f tx per ledger, a ledger every %.0f ms, %.0f tx/s"
          % (out["ledgers"], out["tx_per_ledger"], out["interval_ms"], out["throughput"]))
    print("latency to applied, ms: min %.0f, mean %.0f, max %.0f; p10 %.0f, p50 %.0f, p90 %.0f, "
          "p99 %.0f (n %d)" % (out["min"], out["mean"], out["max"], out["p10"], out["p50"],
                               out["p90"], out["p99"], out["txs"]))
    print("  of the mean: receipt to externalize %.0f ms, externalize to applied %.0f ms"
          % (out["to_externalize_mean"], out["externalize_to_applied_mean"]))
    if len(sys.argv) > 4:
        # the distribution, as the latency at every half percent
        out["quantiles"] = [round(pct(to_applied, q / 2), 1) for q in range(0, 200)]
        out["quantiles"].append(round(to_applied[-1], 1))
        with open(sys.argv[4], "w") as f:
            json.dump(out, f)


if __name__ == "__main__":
    main()
