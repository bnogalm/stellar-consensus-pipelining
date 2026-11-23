#!/usr/bin/env python3
"""Ledger-by-ledger simulation of the overlap of consensus and apply against pipelining.

Consensus of a ledger of n transactions with k ledgers in flight takes
    (A + B * n) * (1 + G * (k - 1)) * r
A and B fit the testbed at k = 1 (696 ms at 300 transactions, 880 at 1,000, 1,336 at 3,000).
G is the extra cost of each further ledger in flight (testbed: 5 to 8 %, up to 15 % on a busy host).
r follows the shape of mainnet consensus times (watcher quantiles, results/mainnet-steps.md).
Apply takes n * e * m, with m lognormal with a CV of 0.3 (the mix of each ledger).
Ledgers are full: the question is the ceiling, not a light load.

Overlap: one consensus at a time; consensus of N+1 starts when that of N has ended and apply has
taken N. Pipelining: slot N opens once N-k is applied (and at least 50 ms after N-1).

Latency of a transaction: the wait for the next ledger it can enter (half an interval for the
overlap; half of k intervals with pipelining, since a payer enters one ledger in k), then that
ledger's consensus, queue and apply. --no-class-wait drops the k.

Usage: overlap-vs-pipelining.py [--sizes] [--budgets] [--no-class-wait] [--check]
"""
import bisect, math, random, sys

A, B = 620.0, 0.24
Q = [0, .10, .50, .90, .99, 1]
CONS = [300, 428, 541, 886, 1756, 3000]
N = 6000
L = 50.0

random.seed(7)
def draw(v):
    u = random.random(); i = bisect.bisect(Q, u) - 1
    return v[i] + (v[i + 1] - v[i]) * (u - Q[i]) / (Q[i + 1] - Q[i])
MEAN = sum(draw(CONS) for _ in range(200000)) / 200000
R = [draw(CONS) / MEAN for _ in range(N)]
_s = math.sqrt(math.log(1 + 0.3 ** 2))
M = [random.lognormvariate(-_s * _s / 2, _s) for _ in range(N)]
CLASS_WAIT = "--no-class-wait" not in sys.argv


def sim(mode, k, n, e, G, parts=False):
    kk = 1 if mode == "overlap" else k
    cbase = (A + B * n) * (1 + G * (kk - 1))
    cs, ce, ae, ast = [0.0] * N, [0.0] * N, [0.0] * N, [0.0] * N
    for i in range(N):
        if mode == "overlap":
            cs[i] = max(ce[i - 1] if i else 0, ast[i - 1] if i else 0)
        else:
            cs[i] = max(ae[i - k] if i >= k else 0, (cs[i - 1] + L) if i else 0)
        ce[i] = cs[i] + cbase * R[i]
        ast[i] = max(ce[i], ae[i - 1] if i else 0)
        ae[i] = ast[i] + n * e * M[i]
    w = N // 10
    T = ae[-1] - ae[w]
    I = T / (N - 1 - w)
    thr = n * (N - 1 - w) / T * 1000
    busy = sum(n * e * M[i] for i in range(w + 1, N)) / T
    path = sum(ae[i] - cs[i] for i in range(w, N)) / (N - w)
    lat = (kk if CLASS_WAIT else 1) * I / 2 + path
    if parts:
        # mean consensus, queue and apply of a ledger, for the client charts
        mean = lambda a, b: sum(a[i] - b[i] for i in range(w, N)) / (N - w)
        return thr, I, lat, busy, mean(ce, cs), mean(ast, ce), mean(ae, ast)
    return thr, I, lat, busy


CASES = (("overlap", 1, "Overlap"), ("p", 2, "k = 2"), ("p", 3, "k = 3"), ("p", 4, "k = 4"), ("p", 6, "k = 6"))

if "--sizes" in sys.argv:
    for e in (1.25, 0.35, 0.15):
        for G in (0.0, 0.08, 0.15):
            print(f"\napply {e} ms/tx, G {G:.0%}: throughput, interval, latency, apply busy")
            for n in (300, 430, 600, 1000, 2000, 4000, 8000, 32000):
                cells = [f"{t:,.0f} tx/s {i:,.0f} ms {l/1000:.1f} s {b:.0%}"
                         for t, i, l, b in (sim(m, k, n, e, G) for m, k, _ in CASES)]
                print(f"  {n:>5}: " + " | ".join(cells))

if "--budgets" in sys.argv:
    sizes = [50, 75, 100, 150, 200, 250, 300, 350, 430, 500, 600, 700, 800, 1000, 1200, 1500,
             2000, 2500, 3000, 4000, 5000, 6000, 8000]
    for e in (1.25, 0.35, 0.15):
        for G in (0.05, 0.08, 0.15):
            print(f"\napply {e} ms/tx, G {G:.0%}: best throughput within a latency budget")
            for m, k, name in CASES:
                pts = [(n,) + sim(m, k, n, e, G) for n in sizes]
                row = []
                for b in (1.5, 2.0, 3.0):
                    ok = [p for p in pts if p[3] / 1000 <= b]
                    row.append(f"{max(ok, key=lambda p: p[1])[1]:,.0f} ({max(ok, key=lambda p: p[1])[0]:,} tx)" if ok else "-")
                print(f"  {name:8s} " + " | ".join(f"<= {b} s: {r}" for b, r in zip((1.5, 2.0, 3.0), row)))

if "--apply-models" in sys.argv:
    # Apply as F + e * n (ms), measured (results/apply-and-consensus-by-size.md), against consensus
    # growing B ms per transaction. n* is the size at which a ledger's apply takes as long as its
    # mean consensus, where the overlap would reach apply's ceiling if consensus never varied.
    # Above 1,100 transactions per ledger every row is an extrapolation: mainnet has none larger.
    MODELS = [
        ("desktop SSD, replay (1 November)", 228, 0.553),
        ("lab RAM, replay (1 November), mean ledger", 0, 0.48),
        ("lab RAM, replay (17 November)", 70, 0.367),
        ("lab RAM, live (17 November)", 72, 0.306),
        ("lab RAM, replay (1 November)", 76, 0.238),
        ("testbed payments, live", 0, 0.09),
    ]
    SIZES = (600, 1000, 2000, 4000, 16000)
    for b in (0.24, 0.21):
        B = b
        print(f"\nconsensus {A:.0f} + {B} ms/tx, G 8 %: k = 4 over the overlap (throughput)")
        print(f"  {'apply (F + e n)':48s} {'n*':>7s} " + " ".join(f"{n:>7,}" for n in SIZES))
        for name, F, e in MODELS:
            nstar = f"{(A - F) / (e - B):7,.0f}" if e > B else "  never"
            cells = []
            for n in SIZES:
                ee = (F + e * n) / n
                cells.append(sim("p", 4, n, ee, 0.08)[0] / sim("overlap", 1, n, ee, 0.08)[0])
            print(f"  {name + f' ({F:.0f} + {e} n)':48s} {nstar} " + " ".join(f"{c:7.2f}" for c in cells))
    B = 0.24

if "--check" in sys.argv:
    # measured on the testbed (results/when-pipelining-pays.md); apply "none" is about 0.06 ms/tx
    for e, n, k, m in [(1.25, 300, 2, 513), (1.25, 300, 4, 759), (1.25, 1000, 2, 791), (1.25, 1000, 4, 809),
                       (0.35, 300, 2, 662), (0.35, 300, 4, 1073), (0.35, 1000, 2, 1321),
                       (0.06, 300, 2, 717), (0.06, 300, 4, 1101)]:
        print(f"apply {e} n {n} k {k}: simulated {sim('p', k, n, e, 0.05)[0]:,.0f} (G 5%), "
              f"{sim('p', k, n, e, 0.08)[0]:,.0f} (G 8%), measured {m}")
