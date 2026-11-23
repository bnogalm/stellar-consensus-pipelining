#!/usr/bin/env python3
"""Chart specs of results/latency-by-depth.md, written to results/latency-by-depth.json.
From results/data/latency/mix-quantiles-650.json: mix-quantiles.py on the runs of the 80 % load
in one session, four runs a client (228-latency-checks.sh). Run from the repository root."""
import json

quant = json.load(open("results/data/latency/mix-quantiles-650.json"))

CLIENTS = [(1, "o", "k = 1"), (3, "o", "k = 3, one account"),
           (3, "k", "k = 3, an account in every class")]
FLOODS = [("normal", "default flooding"), ("fast", "fast flooding")]

# 1: where the latency goes, one bar per client and flooding; the hover has the spread of the
# stage over the payments of the four runs
names, stats = [], []
for flood, fname in FLOODS:
    for k, c, cname in CLIENTS:
        key = "k%d%s-%s" % (k, {"o": "one" if k > 1 else "", "k": "aim"}[c], flood)
        names.append("%s,<br>%s" % (cname, fname))
        stats.append(quant[key])
num = "{:,}".format
series, base = [], [0] * len(names)
for part, name, color in (("wait", "waits for its ledger to open", "--s4"),
                          ("consensus", "consensus", "--s1"), ("apply", "apply", "--s2")):
    x = [st["parts"][part]["mean"] for st in stats]
    hover = []
    for n, st in zip(names, stats):
        q, t = st["parts"][part], st["parts"]["total"]
        hover.append(
            "<b>%s</b><br>%s: mean %s ms, median %s ms<br>"
            "most often %s to %s ms; 10th to 90th percentile %s to %s ms<br>"
            "standard deviation %s ms<br>"
            "whole latency: mean %s ms, median %s ms, 10th to 90th percentile %s to %s ms<br>"
            "%s payments, four runs" % (
                n.replace("<br>", " "), name, num(q["mean"]), num(q["p50"]), num(q["mode"]),
                num(q["mode"] + 100), num(q["p10"]), num(q["p90"]), num(q["sd"]),
                num(t["mean"]), num(t["p50"]), num(t["p10"]), num(t["p90"]), num(st["n"])))
    series.append({"name": name, "color": color, "base": list(base), "x": x, "hover": hover})
    base = [b + a for b, a in zip(base, x)]
parts = [[st["parts"][p]["mean"] for p in ("wait", "consensus", "apply")] for st in stats]
split = {"type": "gantt", "leftMargin": 230, "rows": names, "series": series, "xTitle": "ms",
         "xRange": [0, 2350],
         "title": "Where the latency of a payment goes: 80 % load, means of four runs"}


def line(title, xtitle, ytitle, floodkey, fname):
    out = []
    for (k, c, cname), color in zip(CLIENTS, ("--s1", "--s2", "--s3")):
        q = quant["k%d%s-%s" % (k, {"o": "one" if k > 1 else "", "k": "aim"}[c], floodkey)]["q"]
        pct = [2.5 * i for i in range(41)]
        keep = range(1, 40)  # without the minimum and the maximum
        out.append({"name": cname, "color": color, "x": [q[i] for i in keep],
                    "y": [pct[i] for i in keep],
                    "hover": ["%s: %g %% applied within %s ms" % (cname, pct[i], "{:,}".format(q[i]))
                              for i in keep]})
    return {"title": title % fname, "xTitle": xtitle, "xType": "linear", "yTitle": ytitle,
            "ySuffix": " %", "series": out}


dist = {key: line("Latency of a payment, share applied within a time: 80 %% load, %s",
                  "ms from receipt to applied", "Payments applied", key, fname)
        for key, fname in FLOODS}

# 3: share that entered the slot opened next, by the time left to its opening, k = 1
enter = {"title": "A payment enters the ledger that opens next only if it arrives early: k = 1, 80 % load",
         "xTitle": "ms left to the opening of the next ledger when the payment arrives",
         "xType": "linear", "yTitle": "Entered that ledger", "ySuffix": " %", "series": []}
for (key, fname), color in zip(FLOODS, ("--s1", "--s2")):
    e = quant["k1-%s" % key]["enter"]
    xs = sorted(int(b) for b in e if int(b) <= 800)
    enter["series"].append({
        "name": fname, "color": color, "x": [b + 25 for b in xs], "y": [e[str(b)] for b in xs],
        "hover": ["%s, %d to %d ms left: %g %% entered" % (fname, b, b + 50, e[str(b)])
                  for b in xs]})

json.dump({"split": split, "dist-default": dist["normal"], "dist-fast": dist["fast"],
           "enter": enter}, open("results/latency-by-depth.json", "w"), indent=1)
for n, p in zip(names, parts):
    print(n.replace("<br>", " "), p, sum(p))
