"""How busy the apply thread can be, with the overlap and with pipelining, under mainnet's variation.

Ledgers are as large as needed and there is no minimum close time, so only two ratios matter:
apply per ledger against mean consensus (a), and the shape of consensus times from ledger to
ledger. Consensus times are the 368 measured by the watcher node (results/mainnet-steps.md),
resampled as they are; apply varies with a lognormal CV of 0.3 (the mix of each ledger), or not.

Overlap: one consensus at a time, it starts once the previous one has ended and apply has taken it.
Pipelining: slot i starts once i-k is applied.

Usage: apply-busy-limit.py [data dir, default results/data/mainnet-watch]
"""
import gzip, math, os, random, re, statistics, sys

DATA = sys.argv[1] if __name__ == "__main__" and len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "results", "data", "mainnet-watch")
def ts(s):
    h, m, x = s[11:23].split(":")
    return ((int(s[8:10]) * 24 + int(h)) * 60 + int(m)) * 60 + float(x)
first, ext = {}, {}
for line in gzip.open(os.path.join(DATA, "envelopes.log.gz"), "rt"):
    t, _, kind, slot = line.split()
    first.setdefault((int(slot[2:]), kind[9:]), ts(t))
for line in gzip.open(os.path.join(DATA, "events.log.gz"), "rt", errors="replace"):
    if "PipelineLive event=externalize" in line:
        ext.setdefault(int(re.search(r"ledger=(\d+)", line)[1]), ts(line))
slots = sorted(n for n in ext if n - 1 in ext and (n, "NOMINATE") in first
               and (n, "PREPARE") in first and ext[n] > first[(n, "NOMINATE")])
C = [(ext[n] - first[(n, "NOMINATE")]) * 1000 for n in slots]
mu, sd = statistics.mean(C), statistics.pstdev(C)
Cs = sorted(C)
R = [c / mu for c in C]          # consensus relative to its mean
N = 60000
random.seed(5)
RV = [random.choice(R) for _ in range(N)]   # resample the real values
s = math.sqrt(math.log(1 + 0.3 ** 2))
MV = [random.lognormvariate(-s * s / 2, s) for _ in range(N)]
def util(k, a, M):
    cs, ce, ast, ae = [0.0] * N, [0.0] * N, [0.0] * N, [0.0] * N
    for i in range(N):
        cs[i] = (max(ce[i - 1], ast[i - 1]) if i else 0) if k == 0 else (ae[i - k] if i >= k else 0)
        ce[i] = cs[i] + RV[i]
        ast[i] = max(ce[i], ae[i - 1] if i else 0)
        ae[i] = ast[i] + a * M[i]
    w = N // 10
    return sum(a * M[i] for i in range(w + 1, N)) / (ae[-1] - ae[w])


if __name__ == "__main__":
    print(f"{len(C)} ledgers: mean {mu:.0f} ms, sd {sd:.0f}, CV {sd/mu:.2f}, min {Cs[0]:.0f}, "
          f"p50 {Cs[len(C)//2]:.0f}, p90 {Cs[int(.9*len(C))]:.0f}, p99 {Cs[int(.99*len(C))]:.0f}, max {Cs[-1]:.0f}")
    print("ledgers over 1, 2, 3 s:", sum(c > 1000 for c in C), sum(c > 2000 for c in C), sum(c > 3000 for c in C))
    print("max / mean:", round(Cs[-1] / mu, 2))

    # closed form for the overlap with apply fixed at a (relative to mean consensus), no queue:
    #   busy = a / mean(max(r, a))
    print("\nclosed form, overlap, apply constant = a x mean consensus: busy = a / mean(max(r, a))")
    for a in (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 5.2):
        print(f"  a {a}: {a / statistics.mean(max(r, a) for r in R):.0%}")

    ratios = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 5.2)
    for name, M in (("apply constant", [1.0] * N), ("apply mix CV 0.3", MV)):
        print(f"\nsimulation, real consensus values, {name}; columns = apply / mean consensus")
        print("        " + " ".join(f"{a:>5}" for a in ratios))
        for k, lab in ((0, "overlap"), (2, "k=2"), (3, "k=3"), (4, "k=4"), (6, "k=6")):
            print(f"{lab:8s}" + " ".join(f"{util(k, a, M):5.0%}" for a in ratios))
