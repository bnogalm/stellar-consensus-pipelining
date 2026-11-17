#!/usr/bin/env python3
"""Whether every validator published the same ledgers and results: the checkpoint files of the
history archive of each one, decompressed, compared by hash.

Usage: full-hashes.py <testbed dir with n*/history> <number of validators>
"""
import glob
import gzip
import hashlib
import os
import sys

W, n = sys.argv[1], int(sys.argv[2])
for kind in ("ledger", "results", "transactions"):
    per = {}
    for i in range(1, n + 1):
        for f in glob.glob(f"{W}/n{i}/history/{kind}/**/{kind}-*.xdr.gz", recursive=True):
            with gzip.open(f) as g:
                per.setdefault(os.path.basename(f), {})[i] = hashlib.sha256(g.read()).hexdigest()
    common = sorted(c for c, d in per.items() if len(d) == n)
    differ = [c for c in common if len(set(per[c].values())) != 1]
    print(f"{kind} checkpoints on all {n} validators: {len(common)}, identical {len(common) - len(differ)}, "
          f"different {len(differ)}{' ' + ', '.join(differ[:5]) if differ else ''}")
