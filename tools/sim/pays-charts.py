"""Build the chart data of results/when-pipelining-pays.md from the two simulations.

Usage: python pays-charts.py   (writes results/when-pipelining-pays.json; takes a few minutes)
"""
import importlib.util
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "results", "when-pipelining-pays.json")


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), os.path.join(HERE, name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ovp = load("overlap-vs-pipelining")
abl = load("apply-busy-limit")
CASES = [("overlap", 1, "Overlap", "--s1"), ("p", 2, "k = 2", "--s3"), ("p", 3, "k = 3", "--s4"),
         ("p", 4, "k = 4", "--s2")]
charts = {}

# 1. How busy apply can be, against apply per ledger / mean consensus (mainnet's consensus times).
ratios = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0]
series = [{"name": "Overlap, no variation", "color": "--s1", "dash": "dot", "x": ratios,
           "y": [min(a, 1.0) * 100 for a in ratios],
           "hover": [f"apply {a} × consensus: {min(a, 1.0):.0%}" for a in ratios]}]
for k, name, color in ((0, "Overlap", "--s1"), (2, "k = 2", "--s3"), (3, "k = 3", "--s4"), (4, "k = 4", "--s2")):
    y = [round(abl.util(k, a, abl.MV) * 100, 1) for a in ratios]
    series.append({"name": name, "color": color, "x": ratios, "y": y,
                   "hover": [f"apply {a} × consensus: {v:.0f}%" for a, v in zip(ratios, y)]})
charts["busy"] = {"title": "Time the apply thread is busy, with mainnet's consensus times",
                  "xTitle": "Apply per ledger / mean consensus", "xType": "linear",
                  "yTitle": "busy", "ySuffix": "%", "series": series}

# 2. Throughput against ledger size, for three apply speeds (G = 8 %).
sizes = [300, 600, 1000, 2000, 4000, 8000, 16000, 32000]
for e, key in ((1.25, "size-slow"), (0.35, "size-fast"), (0.15, "size-faster")):
    series = []
    for mode, k, name, color in CASES:
        pts = [ovp.sim(mode, k, n, e, 0.08) for n in sizes]
        series.append({"name": name, "color": color, "x": sizes, "y": [round(p[0]) for p in pts],
                       "hover": [f"{n:,} tx per ledger: {p[0]:,.0f} tx/s, a ledger every {p[1]:,.0f} ms, "
                                 f"latency {p[2] / 1000:.1f} s, apply busy {p[3]:.0%}"
                                 for n, p in zip(sizes, pts)]})
    charts[key] = {"title": f"Throughput against ledger size, apply {e} ms per transaction",
                   "xTitle": "Transactions per ledger (log scale)", "xType": "log",
                   "yTitle": "tx/s", "series": series,
                   "refLines": [{"y": round(1000 / e), "label": f"apply's ceiling, {1000 / e:,.0f} tx/s"}]}

# 3. Throughput against latency, apply 0.35 ms per transaction (G = 5 %): the class wait.
sizes = [100, 200, 300, 430, 600, 800, 1000, 1500, 2000, 3000, 4000]
series = []
for mode, k, name, color, dash, per_class in (("overlap", 1, "Overlap", "--s1", None, False),
                                              ("p", 4, "k = 4, one account", "--s2", None, False),
                                              ("p", 4, "k = 4, one account per class", "--s2", "dot", True)):
    pts = [ovp.sim(mode, k, n, 0.35, 0.05) for n in sizes]
    lat = [(p[2] - (k - 1) * p[1] / 2 if per_class else p[2]) / 1000 for p in pts]
    s = {"name": name, "color": color, "x": [round(v, 2) for v in lat], "y": [round(p[0]) for p in pts],
         "hover": [f"{n:,} tx per ledger: {p[0]:,.0f} tx/s, latency {v:.2f} s"
                   for n, p, v in zip(sizes, pts, lat)]}
    if dash:
        s["dash"] = dash
    series.append(s)
charts["latency"] = {"title": "Throughput against latency, apply 0.35 ms per transaction",
                     "xTitle": "Mean latency of a transaction (s)", "xType": "linear",
                     "yTitle": "tx/s", "series": series}

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    json.dump(charts, f, indent=1)
print("wrote", OUT)
