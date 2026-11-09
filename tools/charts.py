"""Charts and tables of the k sweeps with the mainnet apply cost (300 and 600 transactions, 7 and
12 validators), the target x k grid and the leader DoS runs.

Reads the run summaries copied from the lab, averages the repeats (-r<n>) and writes the chart
data. Prints a Markdown table of every configuration.

Usage: fx-charts.py <tag> <out.json> <summaries.txt>...
  tag: the run tag after k<k>- (fx for the v8 runs, cl for the published code)
"""
import collections
import json
import os
import re
import sys

TAG, OUT, FILES = sys.argv[1], sys.argv[2], sys.argv[3:]
STAGES = ["wait", "consensus", "queue", "apply", "execution", "post", "interval"]

runs = collections.defaultdict(list)
for name in FILES:
    for block in open(name, encoding="utf-8").read().split("== ")[1:]:
        run = block.split("\n", 1)[0].strip()
        m = re.search(r"txs per ledger (\d+), ledger interval (\d+) ms, throughput (\d+) tx/s", block)
        p = re.search(r"p50 (\d+) ms, p90 (\d+) ms, p99 (\d+) ms", block)
        a = re.search(r"^all +\d+ +(.*)$", block, re.M)
        if not (m and p and a):
            continue
        means = [float(x) for x in re.findall(r"(-?[\d.]+) \( *-?\d+/ *-?\d+\)", a.group(1))]
        r = dict(txs=int(m[1]), interval=int(m[2]), tps=int(m[3]), p50=int(p[1]), p99=int(p[3]))
        r.update(zip(STAGES, means))
        runs[re.sub(r"-r\d$", "", run)].append(r)


def mean(key, field):
    v = runs[key]
    return sum(r[field] for r in v) / len(v)


def k_of(key):
    return int(re.match(r"ksw-pay-k(\d+)", key)[1])


def series(fmt, ks, base_key, field, name, color, unit):
    xs, ys, hover = [], [], []
    for k in ks:
        key = fmt.format(k=k)
        if key not in runs:
            continue
        tps, base = mean(key, "tps"), mean(base_key, "tps")
        p50, base_p50 = mean(key, "p50"), mean(base_key, "p50")
        y = {"gain": tps / base, "tps": tps, "p50": p50}[field]
        xs.append(k), ys.append(round(y, 2 if field == "gain" else 0))
        hover.append(f"{name}, k = {k}: {tps:,.0f} tx/s ({tps / base:.2f}×), interval "
                     f"{mean(key, 'interval'):,.0f} ms, consensus {mean(key, 'consensus'):,.0f} ms, "
                     f"apply {mean(key, 'apply'):,.0f} ms, latency p50 {p50:,.0f} ms "
                     f"({p50 / base_p50 - 1:+.0%}), runs {len(runs[key])}")
    return dict(name=name, color=color, x=xs, y=ys, hover=hover)


P = "ksw-pay-k{k}-" + TAG
B = "ksw-pay-k1-" + TAG
core = [(P + "-t300", B + "-t300", "7 validators, 300 tx", "--s1"),
        (P + "-t600", B + "-t600", "7 validators, 600 tx", "--s2"),
        (P + "-n12-t300", B + "-n12-t300", "12 validators, 300 tx", "--s3")]
grid = [(P + "-grid-L%d" % t, B + "-grid-L%d" % t, "%d ms target" % t, c)
        for t, c in ((150, "--s1"), (250, "--s2"), (500, "--s3"))]
K = range(1, 7)
charts = {
    "k-gain": dict(title="Throughput, mainnet apply cost",
                   xTitle="Ledgers in consensus at once (k)", yTitle="tx/s", ySuffix="",
                   series=[series(f, K, b, "tps", n, c, "tx/s") for f, b, n, c in core],
                   refLines=[dict(y=800, label="apply ceiling, 800 tx/s (1.25 ms per tx)")]),
    "k-latency": dict(title="Median transaction latency, mainnet apply cost",
                      xTitle="Ledgers in consensus at once (k)", yTitle="ms", ySuffix=" ms",
                      series=[series(f, K, b, "p50", n, c, "ms") for f, b, n, c in core]),
    "grid-gain": dict(title="Throughput relative to k = 1 by target close time, 300 tx",
                      xTitle="Ledgers in consensus at once (k)", yTitle="times k = 1", ySuffix="×",
                      series=[series(f, K, b, "gain", n, c, "×") for f, b, n, c in grid]),
}
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(charts, f, ensure_ascii=False, indent=1)

print("| Runs | k | n | Tx per ledger | Interval | Consensus | Apply | Throughput | Median latency | p99 |")
print("|---|---|---|---|---|---|---|---|---|---|")
for key in sorted(runs, key=lambda s: (re.sub(r"ksw-pay-k\d+", "", s), k_of(s))):
    print(f"| {re.sub(r'ksw-pay-k[0-9]+-[a-z]+-', '', key)} | {k_of(key)} | {len(runs[key])} "
          f"| {mean(key, 'txs'):.0f} | {mean(key, 'interval'):,.0f} ms | {mean(key, 'consensus'):,.0f} ms "
          f"| {mean(key, 'apply'):,.0f} ms | {mean(key, 'tps'):,.0f} tx/s | {mean(key, 'p50'):,.0f} ms "
          f"| {mean(key, 'p99'):,.0f} ms |")
