#!/usr/bin/env python3
"""Where the consensus time of a ledger goes, from the tx set logs of one testbed round.

Usage: txset-timings.py <round dir with n1..n7/node.log[.gz]> [min_fill=0.9]
The logs come from the prototype with the tx set timing lines of
results/data/size-apply/txsetlog.diff (measurement only).
For each ledger whose externalized tx set holds at least min_fill of the largest one, and for
each validator, on the steady clock shared by the nodes (one host):
  build     the leader builds the winning tx set (trigger to built, at the leader)
  to_fetch  built at the leader -> this node asks for it (a NOMINATE naming it has arrived)
  transfer  asks for it -> has it
  check     has it -> finished validating it (waiting plus the check itself)
  check_dur the validation alone
  rest      validated -> externalize (the rest of nomination and the ballot)
  total     earliest trigger of the ledger -> this node externalizes
Validators that built the tx set themselves have no fetch: they count in build and total only.
Then, per ledger, how many tx sets were nominated: the one that won plus every other one some
validator asked for. More than one means several leaders in a nomination round, or a round that
timed out before the first tx set reached a quorum, so that the next round added leaders.
"""
import glob
import gzip
import os
import re
import statistics
import sys

d = sys.argv[1]
min_fill = float(sys.argv[2]) if len(sys.argv) > 2 else 0.9
KV = re.compile(r"(\w+)=(\S+)")
nodes = {}
for f in sorted(glob.glob(os.path.join(d, "n[0-9]*", "node.log*"))):
    name = os.path.basename(os.path.dirname(f))
    opener = gzip.open if f.endswith(".gz") else open
    ev = {"trigger": {}, "externalize": {}, "fetch": {}, "recv": {}, "check": {}, "build": {},
          "won": {}, "txs": {}, "asked": {}}
    for line in opener(f, "rt", errors="replace"):
        if "Got consensus" in line:
            m = re.search(r"seq=(\d+).*txs=(\d+).*txH: (\w+)", line)
            if m:
                ev["won"][int(m[1])] = m[3]
                ev["txs"][int(m[1])] = int(m[2])
            continue
        if "PipelineLive event=" not in line:
            continue
        kv = dict(KV.findall(line.split("PipelineLive", 1)[1]))
        e = kv["event"]
        t = int(kv.get("t_ns", 0)) / 1e6
        if e == "trigger":
            ev["trigger"][int(kv["ledger"])] = t
        elif e == "externalize":
            ev["externalize"].setdefault(int(kv["ledger"]), t)
        elif e == "txset_fetch":
            ev["fetch"].setdefault(kv["hash"], t)
            ev["asked"].setdefault((int(kv["slot"]), kv["hash"]), t)
        elif e == "txset_recv":
            ev["recv"].setdefault(kv["hash"], (t, int(kv["bytes"])))
        elif e == "txset_check":
            ev["check"].setdefault((int(kv["ledger"]), kv["hash"]), (t, int(kv["dur_ns"]) / 1e6))
        elif e == "txset_build":
            ev["build"][kv["hash"]] = (int(kv["ledger"]), t, int(kv["dur_ns"]) / 1e6)
    nodes[name] = ev

any_node = next(iter(nodes.values()))
txs = any_node["txs"]
big = max(txs.values()) if txs else 0
ledgers = sorted(L for L, n in txs.items() if n >= min_fill * big and n > 0)
builds = {}
for ev in nodes.values():
    builds.update(ev["build"])

rows = {k: [] for k in ("build", "to_fetch", "transfer", "check", "check_dur", "rest", "total")}
sizes = []
nsets, one, more, second = [], [], [], []
for L in ledgers:
    h = any_node["won"][L]
    if h not in builds:
        continue
    _, tb0, bdur = builds[h]
    t0 = min(ev["trigger"][L] for ev in nodes.values() if L in ev["trigger"])
    built = tb0 + bdur
    rows["build"].append(built - t0)
    others = {}  # the other tx sets nominated for this ledger, with when each was first asked for
    for ev in nodes.values():
        for (slot, other), t in ev["asked"].items():
            if slot == L and other != h:
                others[other] = min(t, others.get(other, t))
    total = statistics.mean(ev["externalize"][L] - t0 for ev in nodes.values()
                            if L in ev["externalize"])
    nsets.append(1 + len(others))
    (more if others else one).append(total)
    if others:
        second.append(min(others.values()) - t0)
    for ev in nodes.values():
        if L not in ev["externalize"]:
            continue
        rows["total"].append(ev["externalize"][L] - t0)
        if h in ev["fetch"] and h in ev["recv"] and (L, h) in ev["check"]:
            tf, (tr, nbytes), (tc, cdur) = ev["fetch"][h], ev["recv"][h], ev["check"][(L, h)]
            sizes.append(nbytes)
            rows["to_fetch"].append(tf - built)
            rows["transfer"].append(tr - tf)
            rows["check"].append(tc + cdur - tr)
            rows["check_dur"].append(cdur)
            rows["rest"].append(ev["externalize"][L] - (tc + cdur))


def q(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(p * len(v)))]


print(f"{d}: {len(ledgers)} ledgers with >= {min_fill:.0%} of {big} txs;"
      f" tx set {statistics.mean(sizes) / 1e6:.2f} MB" if sizes else f"{d}: no fetches")
print(f"{'ms':10s} {'mean':>7s} {'p50':>7s} {'p90':>7s} {'n':>5s}")
for k, v in rows.items():
    if v:
        print(f"{k:10s} {statistics.mean(v):7.0f} {q(v, .5):7.0f} {q(v, .9):7.0f} {len(v):5d}")
if nsets:
    print(f"tx sets nominated per ledger: mean {statistics.mean(nsets):.2f};"
          f" one only in {len(one)} of {len(nsets)} ledgers")
if one and more:
    print(f"total with one tx set nominated: {statistics.mean(one):.0f} ms; with more:"
          f" {statistics.mean(more):.0f} ms; a second one first asked for"
          f" {q(second, .5):.0f} ms after the trigger (p50)")
