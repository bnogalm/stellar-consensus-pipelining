"""The overlap against pipelining with mainnet's ledger sizes, with no minimum close time.

Sizes: 2,000 consecutive mainnet ledgers (results/data/mainnet-sizes), or every ledger at the
classic cap (1,000 operations, about 600 transactions). Consensus: mainnet's watcher quantiles,
times 1 + G (k - 1); it does not grow with size here, since sizes stay near today's. Apply: n * e,
with a lognormal mix of CV 0.2. Latency: wait for the next ledger of the payer's class, then that
ledger's consensus, queue and apply; in brackets, a user with one payer account per class.
"Agreed after" stops at the externalize of the ledger, as the latency measured on the testbed
does; the queue is the time an agreed ledger waits for the ledgers before it to be applied.

Usage: mainnet-cap.py
"""
import json, random, bisect, math, os
sz = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "results", "data",
                                 "mainnet-sizes", "ledgers-65509300-65511299.json")))["txs"]
Q = [0, .10, .50, .90, .99, 1]; CONS = [300, 428, 541, 886, 1756, 3000]
random.seed(11)
def draw(v):
    u = random.random(); i = bisect.bisect(Q, u) - 1
    return v[i] + (v[i+1]-v[i]) * (u-Q[i]) / (Q[i+1]-Q[i])
N = len(sz) * 3
C0 = [draw(CONS) for _ in range(N)]
s = math.sqrt(math.log(1 + .2**2)); MIX = [random.lognormvariate(-s*s/2, s) for _ in range(N)]
def run(mode, k, sizes, e, G, L=50.0):
    kk = 1 if mode == "overlap" else k
    cs, ce, ae, ast = [0.0]*N, [0.0]*N, [0.0]*N, [0.0]*N
    for i in range(N):
        n = sizes[i % len(sizes)]
        if mode == "overlap": cs[i] = max(ce[i-1] if i else 0, ast[i-1] if i else 0)
        else: cs[i] = max(ae[i-k] if i >= k else 0, (cs[i-1] + L) if i else 0)
        ce[i] = cs[i] + C0[i] * (1 + G*(kk-1))
        ast[i] = max(ce[i], ae[i-1] if i else 0)
        ae[i] = ast[i] + n * e * MIX[i]
    w = N // 10; T = ae[-1] - ae[w]; I = T / (N-1-w)
    tot = sum(sizes[i % len(sizes)] for i in range(w+1, N))
    busy = sum(sizes[i % len(sizes)] * e * MIX[i] for i in range(w+1, N)) / T
    path = sum(ae[i]-cs[i] for i in range(w, N)) / (N-w)
    cons = sum(ce[i]-cs[i] for i in range(w, N)) / (N-w)
    queue = sum(ast[i]-ce[i] for i in range(w, N)) / (N-w)
    return (tot/T*1000, I, (kk*I/2 + path)/1000, (I/2 + path)/1000, busy,
            (kk*I/2 + cons)/1000, (I/2 + cons)/1000, queue)
cap = [600] * 10  # ledgers full at the classic cap: about 1,000 operations, 600 transactions
for name, sizes in (("mainnet sizes as observed (mean 438 tx)", sz), ("every ledger at the cap (600 tx)", cap)):
    for e, en in ((0.35, "fast node 0.35 ms/tx"), (1.25, "replay 1.25 ms/tx")):
        print(f"\n{name}, {en}")
        for G in (0.05, 0.08):
            for mode, k in (("overlap", 1), ("p", 2), ("p", 3), ("p", 4)):
                thr, I, lat, lat1, busy, agr, agr1, queue = run(mode, k, sizes, e, G)
                lab = "overlap" if mode == "overlap" else f"k={k}"
                print(f"  G {G:.0%} {lab:7s} {thr:6,.0f} tx/s  interval {I:4.0f} ms  latency {lat:.2f} s (one account per class {lat1:.2f} s)  agreed after {agr:.2f} s ({agr1:.2f} s), queue {queue:.0f} ms  apply busy {busy:.0%}")
