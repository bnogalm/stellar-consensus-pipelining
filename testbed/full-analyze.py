#!/usr/bin/env python3
"""Results of a full workload run by kind of transaction, from the history one validator
published and the transaction logs of the load nodes (FullWorkload writes, for every submission,
its hash, kind, the first key byte of the fee payer and of the other account it touches, and
whether the queue took it).

Usage: full-analyze.py <stellar-core> <history dir> <run dir> <first ledger> <last ledger> <k>

A transaction is cross-class when the other account it touches is in another class than its fee
payer (first key byte mod k), so its balance can move in another open ledger: with k = 1 there is
no such case.
"""
import collections
import glob
import gzip
import json
import os
import subprocess
import sys
import tempfile

core, hist, run = sys.argv[1:4]
first, last, k = (int(x) for x in sys.argv[4:7])

kinds = {}
queue = collections.defaultdict(collections.Counter)
for f in glob.glob(f"{run}/n*/fullworkload-txs.log.gz"):
    with gzip.open(f, "rt") as g:
        for line in g:
            parts = line.split()
            if len(parts) != 6:
                continue
            h, kind, payer, other, accepted, code = parts
            if accepted == "1":
                kinds[h] = (kind, int(payer), int(other))
                queue[kind]["accepted"] += 1
            else:
                queue[kind][code] += 1


def entries():
    with tempfile.TemporaryDirectory() as t:
        for f in sorted(glob.glob(f"{hist}/results/**/results-*.xdr.gz", recursive=True)):
            p = os.path.join(t, os.path.basename(f)[:-3])
            with gzip.open(f) as g, open(p, "wb") as o:
                o.write(g.read())
            out = subprocess.run([core, "dump-xdr", "--compact", p], capture_output=True,
                                 text=True).stdout
            os.remove(p)
            if "[" in out:
                yield from json.loads(out[out.index("["):])


def outcome(res):
    """Result code of the transaction, with the first failing operation's code if it failed."""
    code = res["code"]
    if code in ("txFEE_BUMP_INNER_SUCCESS", "txFEE_BUMP_INNER_FAILED"):
        res = res["innerResultPair"]["result"]["result"]
        code = res["code"]
    if code == "txSUCCESS":
        return "success"
    for op in res.get("results") or []:
        if op.get("code") != "opINNER":
            return f"{code} {op.get('code')}"
        tr = op["tr"]
        for key, val in tr.items():
            if key != "type" and isinstance(val, dict) and "code" in val:
                if not val["code"].endswith("_SUCCESS"):
                    return f"{code} {val['code']}"
    return code


applied = collections.defaultdict(collections.Counter)
cross = collections.defaultdict(collections.Counter)
ledgers = set()
for e in entries():
    seq = e["ledgerSeq"]
    if seq < first or seq > last:
        continue
    ledgers.add(seq)
    for r in e["txResultSet"]["results"]:
        info = kinds.get(r["transactionHash"])
        kind = info[0] if info else "(not from the load: setup)"
        out = outcome(r["result"]["result"])
        applied[kind][out] += 1
        if info and k > 1 and info[1] % k != info[2] % k:
            cross[kind][out] += 1

total = sum(sum(c.values()) for c in applied.values())
ok = sum(c["success"] for c in applied.values())
print(f"k={k}, ledgers {first}-{last} with published results: {len(ledgers)}, transactions applied "
      f"{total}, successful {ok} ({100 * ok / max(total, 1):.1f}%)")
print()
print(f"{'kind':<22}{'queued':>8}{'rejected':>9}{'applied':>9}{'ok %':>7}  failures (top 3)"
      f"   | cross-class: applied, ok %, failures")
for kind in sorted(set(applied) | set(queue)):
    q = queue[kind]
    a = applied[kind]
    n = sum(a.values())
    fails = ", ".join(f"{c} {v}" for c, v in a.most_common() if c != "success")[:90]
    x = cross[kind]
    xn = sum(x.values())
    xs = (f" | {xn}, {100 * x['success'] / xn:.0f}%, "
          + ", ".join(f"{c} {v}" for c, v in x.most_common(3) if c != "success")) if xn else ""
    rejected = sum(v for c, v in q.items() if c != "accepted")
    print(f"{kind:<22}{q['accepted']:>8}{rejected:>9}{n:>9}{100 * a['success'] / max(n, 1):>7.1f}  "
          f"{fails}{xs}")
print()
print("Queue rejections by code:")
codes = collections.Counter()
for kind, q in queue.items():
    for c, v in q.items():
        if c != "accepted":
            codes[c] += v
for c, v in codes.most_common():
    print(f"  {c}: {v}")
