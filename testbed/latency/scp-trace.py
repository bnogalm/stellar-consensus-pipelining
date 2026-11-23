#!/usr/bin/env python3
"""What the slow slots of a run with SCP debug logs are (232-scp-trace.sh).
For every slot of a node's full log: trigger to externalize, the nomination and prepare times the
herder logs, the nomination rounds and their leaders. Prints the totals and the slow slots.
Usage: scp-trace.py <full dir with n<i>.log.gz> [node, default 1] [slow threshold ms, 1100]"""
import gzip
import re
import statistics
import sys

d = sys.argv[1]
node = sys.argv[2] if len(sys.argv) > 2 else "1"
slow_ms = int(sys.argv[3]) if len(sys.argv) > 3 else 1100
trig, ext, nom, prep, rounds, leaders, winner = {}, {}, {}, {}, {}, {}, {}
cur = None
for line in gzip.open("%s/n%s.log.gz" % (d, node), "rt", errors="replace"):
    m = re.search(r"PipelineLive event=(trigger|externalize) ledger=(\d+).*t_ns=(\d+)", line)
    if m:
        s = int(m.group(2))
        (trig if m.group(1) == "trigger" else ext).setdefault(s, int(m.group(3)) / 1e6)
        if m.group(1) == "trigger":
            cur = s
        continue
    m = re.search(r"(Nominate|Prepare) delta for slot (\d+) is (\d+) ms", line)
    if m:
        (nom if m.group(1) == "Nominate" else prep)[int(m.group(2))] = int(m.group(3))
        continue
    m = re.search(r"updateRoundLeaders: (\d+) -> (\d+)", line)
    if m and cur is not None:
        rounds[cur] = rounds.get(cur, 0) + 1
        continue
    m = re.search(r"SCP DEBUG\]\s+leader (\w+)", line)
    if m and cur is not None:
        leaders.setdefault(cur, []).append(m.group(1))
        continue
    m = re.search(r"Got consensus: \[seq=(\d+).*?\[ \w+@(\w+)", line)
    if m:
        winner.setdefault(int(m.group(1)), m.group(2))
slots = sorted(s for s in nom if s in trig and s in ext)
if not slots:
    sys.exit("no slots with debug lines")
total = {s: ext[s] - trig[s] for s in slots}
slow = [s for s in slots if total[s] >= slow_ms]
fast = [s for s in slots if total[s] < slow_ms]


def mean(xs):
    return statistics.mean(xs) if xs else float("nan")


print("slots with debug logs: %d; slow (>= %d ms): %d (%.1f %%)" % (
    len(slots), slow_ms, len(slow), 100 * len(slow) / len(slots)))
for name, group in (("fast", fast), ("slow", slow)):
    print("%s: trigger to externalize %.0f ms; nomination %.0f ms; prepare %.0f ms; rounds %.2f" % (
        name, mean([total[s] for s in group]), mean([nom[s] for s in group]),
        mean([prep.get(s, 0) for s in group]), mean([rounds.get(s, 0) for s in group])))
print("slots by number of nomination rounds:",
      {r: sum(1 for s in slots if rounds.get(s, 0) == r) for r in sorted(set(rounds.get(s, 0) for s in slots))})
print("slow slots: slot, total, nomination, prepare, rounds, leaders by round, winner")
for s in slow:
    print("  %d  %.0f  %d  %d  %d  %s  %s" % (s, total[s], nom[s], prep.get(s, -1), rounds.get(s, 0),
                                          ">".join(leaders.get(s, [])), winner.get(s, "?")))
# is the first leader special in the slow slots?
first = {}
for s in slots:
    l = (leaders.get(s) or ["?"])[0]
    e = first.setdefault(l, [0, 0])
    e[0] += 1
    e[1] += s in slow
print("first round leader: slots, slow:", {l: tuple(e) for l, e in sorted(first.items())})
