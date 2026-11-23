#!/usr/bin/env python3
"""Offline comparison of ways to choose the slot a transaction aims for, on the recorded times of
a run (n1/node.log: trigger, externalize and apply end of every slot).

A client with an account in every class sends at time t and aims for slot S. The transaction
enters S with the probability measured for the time left to its opening (the time it takes to
reach the leader); otherwise it enters S+k, S+2k... by the same rule. The wait is from t to the
opening of the slot it entered.

Choices: random class; "grid" (last opening + mean gap, the current code); "chain" (a slot opens
when its base S-k is applied: externalized base -> now; base in consensus -> its opening + the
usual consensus time); oracle (knows the real openings).
Usage: aim-sim.py <run dir> <k> [fast]"""
import bisect
import random
import re
import statistics
import sys

run, k = sys.argv[1], int(sys.argv[2])
fast = len(sys.argv) > 3
# probability of entering a slot by ms left to its opening when the tx is received, measured
# (k = 1, even submissions): normal flooding, and flooding with 10/20 ms timers
if fast:
    CURVE = [(0, .15), (50, .25), (100, .45), (150, .65), (200, .78), (250, .86), (300, .9),
             (350, .93), (400, .96), (500, .98), (10**9, .99)]
else:
    CURVE = [(0, .15), (50, .15), (100, .18), (150, .26), (200, .40), (250, .55), (300, .70),
             (350, .80), (400, .85), (450, .90), (500, .94), (550, .96), (600, .97), (10**9, .98)]


def p_enter(left):
    if left < 0:
        return 0.0
    i = bisect.bisect_right([c[0] for c in CURVE], left) - 1
    return CURVE[i][1]


trig, ext, end = {}, {}, {}
for line in open(run + "/n1/node.log", errors="replace"):
    m = re.search(r"PipelineLive event=(\w+) ledger=(\d+).*t_ns=(\d+)", line)
    if m and m.group(1) == "trigger":
        trig.setdefault(int(m.group(2)), int(m.group(3)) / 1e6)
    elif m and m.group(1) == "externalize":
        ext.setdefault(int(m.group(2)), int(m.group(3)) / 1e6)
    else:
        m = re.search(r"PipelineApply ledger=(\d+) .*t_end_ns=(\d+)", line)
        if m:
            end[int(m.group(1))] = int(m.group(2)) / 1e6
seqs = sorted(s for s in trig if s in ext and s in end)
# the loaded part: contiguous slots with short gaps
seqs = [s for s in seqs if s - 1 in trig and trig[s] - trig[s - 1] < 3000][60:-20]
lo, hi = seqs[0], seqs[-1]
gap = statistics.mean(trig[s] - trig[s - 1] for s in seqs)
cons = statistics.mean(end[s] - trig[s] for s in seqs)
print("slots %d, gap %.0f ms, opening to applied %.0f ms" % (len(seqs), gap, cons))
times = [trig[s] for s in range(lo, hi + 1)]
random.seed(1)
samples = [random.uniform(trig[lo + 3 * k + 20], trig[hi - 6 * k - 20]) for _ in range(40000)]


def next_slot(t):  # first slot not yet opened at t
    return lo + bisect.bisect_right(times, t)


def grid(t, margin):
    s = next_slot(t)
    # mean of the last 8 gaps, as the node's running mean
    g = (trig[s - 1] - trig[s - 9]) / 8
    opens = max(trig[s - 1] + g, t)
    while opens - t < margin:
        s += 1
        opens += g
    return s


def chain_est(t, s0, n, c_est):
    est = {}
    for s in range(s0, s0 + n):
        b = s - k
        if end.get(b, 1e18) <= t:
            e = t
        elif ext.get(b, 1e18) <= t:
            e = t + 30
        elif trig.get(b, 1e18) <= t:
            e = max(trig[b] + c_est, t + 60)
        else:
            e = est[b] + c_est
        if s - 1 in est:
            e = max(e, est[s - 1] + 100)
        elif trig.get(s - 1, 1e18) <= t:
            e = max(e, trig[s - 1] + 100)
        est[s] = e
    return est


def chain(t, margin, c_est=None):
    s0 = next_slot(t)
    est = chain_est(t, s0, 3 * k + 4, c_est or cons)
    for s in sorted(est):
        if est[s] - t >= margin:
            return s
    return max(est)


def oracle(t, margin):
    s = next_slot(t)
    while trig[s] - t < margin:
        s += 1
    return s


def rand(t, margin):
    return next_slot(t) + random.randrange(k)


def wait(t, s):
    # expected wait: enters s with p, else s+k...
    w, left_p = 0.0, 1.0
    for j in range(6):
        sj = s + j * k
        p = p_enter(trig[sj] - t) if j < 5 else 1.0
        w += left_p * p * (trig[sj] - t)
        left_p *= 1 - p
    return w, 1 - p_enter(trig[s] - t)


for name, f in (("random class", rand), ("grid (current)", grid), ("chain", chain),
                ("oracle", oracle)):
    best = None
    for margin in ([0] if f is rand else range(0, 801, 50)):
        ws, miss = zip(*(wait(t, f(t, margin)) for t in samples))
        r = (statistics.mean(ws), margin, statistics.mean(miss), sorted(ws)[len(ws) // 2])
        if best is None or r < best:
            best = r
    print("%-16s best margin %3d ms: mean wait %4.0f ms, median %4.0f ms, misses its slot %2.0f%%" % (
        name, best[1], best[0], best[3], 100 * best[2]))
# how wrong each estimate of the opening is, for the slots 1 to k ahead
for name in ("grid", "chain"):
    errs = {j: [] for j in range(k + 1)}
    for t in samples[:8000]:
        s0 = next_slot(t)
        if name == "grid":
            g = (trig[s0 - 1] - trig[s0 - 9]) / 8
            est = {s0 + j: max(trig[s0 - 1] + g, t) + j * g for j in range(k + 1)}
        else:
            est = chain_est(t, s0, k + 1, cons)
        for j in range(k + 1):
            errs[j].append(abs(est[s0 + j] - trig[s0 + j]))
    print("%s: mean error of the estimated opening, slots 0 to %d ahead: %s ms" % (
        name, k, ", ".join("%.0f" % statistics.mean(errs[j]) for j in range(k + 1))))
