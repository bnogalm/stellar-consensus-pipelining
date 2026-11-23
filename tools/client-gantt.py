"""Gantt of what a client sees: a payment from the moment it arrives at a payment processor to
the moment it is applied, over the ledgers of the network, in three cases of the simulation
behind results/when-pipelining-pays.md (apply 0.35 ms per transaction, G = 8 %):

- the overlap with ledgers of 1,000 transactions,
- pipelining with k = 3 and the ledger size that gives the throughput of the first: the same
  capacity in smaller ledgers, for latency alone,
- the overlap with ledgers of 4,000, which is how it doubles its throughput,
- pipelining with k = 4 and ledgers of 1,000, about the same throughput as the third.

Every bar is the mean of the simulation: the interval between ledgers, and the consensus, queue
and apply of a ledger. A payment waits the mean for its case: half an interval when its payer
can enter the next ledger, half of k intervals when it has one payer account and enters one ledger
in k. Not a measurement.

Usage: client-gantt.py   (writes results/client-gantt.json and prints the table of the same
capacity in smaller ledgers, against the overlap and against today's protocol back to back)
"""
import importlib.util
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = sys.argv[:1]
spec = importlib.util.spec_from_file_location(
    "ovp", os.path.join(HERE, "sim", "overlap-vs-pipelining.py"))
ovp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ovp)

E, G, WINDOW = 0.35, 0.08, 5600
STAGES = [("consensus", "--s1"), ("queue", "--s3"), ("apply", "--s2")]
WAIT = ("waits for a ledger it can enter", "--s4")


def chart(mode, k, n, ledgers):
    thr, I, _, _, cons, queue, apply_ = ovp.sim(mode, k, n, E, G, parts=True)
    kk = 1 if mode == "overlap" else k
    dur = dict(consensus=cons, queue=queue, apply=apply_)
    rows = [f"N+{i}" if i else "N" for i in range(ledgers)]
    if kk > 1:
        rows = [f"{r}, class {i % kk}" for i, r in enumerate(rows)]
    # (row label, the ledger it enters, how long it waits for it)
    if kk > 1:
        clients = [("one account", kk - 1, kk * I / 2), ("every class", 1, I / 2)]
    else:
        clients = [("payment", 1, I / 2)]
    rows += [c[0] for c in clients]
    starts = [i * I for i in range(ledgers)] + [c[1] * I for c in clients]
    series, latency = [], []
    for name, color in STAGES:
        base, x, hover, offset = [], [], [], 0.0
        for prev, _ in STAGES:
            if prev == name:
                break
            offset += dur[prev]
        for row, start in zip(rows, starts):
            base.append(round(start + offset))
            x.append(round(dur[name]))
            hover.append(f"{row}: {name} {dur[name]:,.0f} ms")
        series.append(dict(name=name, color=color, base=base, x=x, hover=hover))
    base, x, hover = [None] * ledgers, [None] * ledgers, [""] * ledgers
    for label, entered, wait in clients:
        total = wait + cons + queue + apply_
        latency.append(total)
        base.append(round(entered * I - wait))
        x.append(round(wait))
        hover.append(f"{label}: waits {wait:,.0f} ms for ledger N+{entered}, "
                     f"applied {total / 1000:.1f} s after it arrives")
    series.insert(0, dict(name=WAIT[0], color=WAIT[1], base=base, x=x, hover=hover))
    what = "Overlap" if kk == 1 else f"k = {k}"
    if kk > 1:
        lat = (f"applied {latency[0] / 1000:.1f} s after it arrives with one payer account, "
               f"{latency[1] / 1000:.1f} s with one in every class")
    else:
        lat = f"applied {latency[0] / 1000:.1f} s after it arrives"
    title = (f"{what}, ledgers of {n:,}: a ledger every {I:,.0f} ms, {thr:,.0f} tx/s;<br>"
             f"a payment is {lat}")
    print(f"{what} n={n}: interval {I:.0f} ms, {thr:.0f} tx/s, consensus {cons:.0f}, queue "
          f"{queue:.0f}, apply {apply_:.0f}, latency " + ", ".join(f"{l:.0f}" for l in latency))
    return dict(type="gantt", title=title, rows=rows, series=series,
                xTitle="ms", yTitle="", xRange=[0, WINDOW])


def same_capacity(name, mode, n):
    """The ledger sizes at which k ledgers in consensus give the throughput of `mode` at n."""
    thr, I, _, _, cons, queue, apply_ = ovp.sim(mode, 1, n, E, G, parts=True)
    print(f"{name}, ledgers of {n}: {thr:,.0f} tx/s, a ledger every {I:,.0f} ms, "
          f"latency {(I / 2 + cons + queue + apply_) / 1000:.2f} s")
    sizes = {}
    for k in (2, 3, 4):
        size = min(range(40, n + 1, 5), key=lambda m: abs(ovp.sim("p", k, m, E, G)[0] - thr))
        t, i, _, _, cons, queue, apply_ = ovp.sim("p", k, size, E, G, parts=True)
        path = cons + queue + apply_
        print(f"  k = {k}, ledgers of {size}: {t:,.0f} tx/s, a ledger every {i:,.0f} ms, one account "
              f"{(k * i / 2 + path) / 1000:.2f} s, every class {(i / 2 + path) / 1000:.2f} s "
              f"(queue {queue:,.0f} ms)")
        sizes[k] = size
    return sizes


same = same_capacity("overlap", "overlap", 1000)
same_capacity("today back to back", "p", 1000)
out = {"overlap-1000": chart("overlap", 1, 1000, 4),
       "k3-same": chart("p", 3, same[3], 9),
       "overlap-4000": chart("overlap", 1, 4000, 3),
       "k4-1000": chart("p", 4, 1000, 8)}
path = os.path.join(HERE, "..", "results", "client-gantt.json")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("wrote", path)
