"""Gantt charts of the ledger cycle: one row per ledger, one bar per stage, from a node log.

Stages, as in wan-analyze.py: consensus (trigger -> externalize), queue (externalize -> apply
begin), apply (begin -> end, including commit) and post (end -> next ledger armed). All charts
use the same time window, so the number of ledgers that fit in it can be compared.

Usage: gantt-charts.py <out.json> <window_s> <name>::<node.log> [<name>::<node.log> ...]
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("wan_analyze", os.path.join(HERE, "wan", "wan-analyze.py"))
wa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wa)

STAGES = [("consensus", "trigger", "externalize", "--s1"),
          ("queue", "externalize", "begin", "--s3"),
          ("apply and commit", "begin", "end", "--s2"),
          ("post", "end", None, "--s4")]

out, window = sys.argv[1], float(sys.argv[2]) * 1000
charts = {}
for arg in sys.argv[3:]:
    name, path = arg.split("::", 1)
    ev = wa.load(path)
    # Start in the middle of the run, where the load is steady
    ledgers = sorted(n for n in ev["trigger"] if n in ev["end"] and ev["txs"].get(n, 0) > 0)
    first = ledgers[len(ledgers) // 2]
    t0 = ev["trigger"][first]
    rows = [n for n in ledgers if n >= first and (ev["trigger"][n] - t0) / 1e6 <= window]
    series = []
    for label, a, b, color in STAGES:
        base, length, hover = [], [], []
        for n in rows:
            start = ev[a].get(n)
            stop = ev["armed"].get(n + 1) if b is None else ev[b].get(n)
            # "post" has no meaning once the next ledger is armed before this one ends (k > 1)
            if start is None or stop is None or stop <= start:
                base.append(None), length.append(None), hover.append("")
                continue
            base.append(round((start - t0) / 1e6, 1))
            length.append(round((stop - start) / 1e6, 1))
            hover.append(f"ledger {n}, {label}: {length[-1]:.0f} ms")
        series.append(dict(name=label, color=color, base=base, x=length, hover=hover))
    span = (max(ev["end"][n] for n in rows) - t0) / 1e6
    charts[name] = dict(type="gantt", title=name, rows=[str(n) for n in rows], series=series,
                        xTitle="ms from the first ledger shown", yTitle="Ledger",
                        xRange=[0, window + 1500])
    print(f"{name}: {len(rows)} ledgers started in {window / 1000:.0f} s, last applied at {span:.0f} ms")
with open(out, "w", encoding="utf-8", newline="\n") as f:
    json.dump(charts, f, ensure_ascii=False, indent=1)
