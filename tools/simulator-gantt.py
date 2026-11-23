"""Illustrative Gantt of the real-time simulator example in the discussion post: the same models
run one after another (one cycle every 100 ms, 10 Hz) or pipelined by a clock that starts a cycle
every 10 ms (100 Hz). In the pipelined case each model waits only for the data it reads, so the
electrics and the hydraulics, which do not read each other, run at the same time. The simulator had
many more models; these groups and durations are an illustrative example, not measurements.

The last row of each chart is something the user does (a lever, a button) halfway between two
cycle starts: it waits for the next cycle to read it, and that cycle has to end before the user
sees the result."""
import json
import os

# Stages in order; a list inside is a group of independent models that can run at the same time.
STAGES = [("cab controls", 5, "--s4"),
          ("train physics, per car", 20, "--s1"),
          [("electrics, catenary", 15, "--s3"), ("hydraulics, brakes", 10, "--s6")],
          ("ERTMS, DMI, DDU", 25, "--s2"),
          ("interlocking", 25, "--s5")]


def chart(title, period, cycles, window, parallel):
    rows = [f"cycle {c + 1}" for c in range(cycles)]
    series, t = [], 0
    for stage in STAGES:
        group = stage if isinstance(stage, list) else [stage]
        start = t
        for lane, (name, dur, color) in enumerate(group):
            offset = start if parallel else t
            s = dict(name=name, color=color, base=[c * period + offset for c in range(cycles)],
                     x=[dur] * cycles,
                     hover=[f"cycle {c + 1}, {name}: {dur} ms" for c in range(cycles)])
            if parallel and len(group) > 1:
                s["lane"] = lane
            series.append(s)
            t = t + dur if not parallel else t
        if parallel:
            t = start + max(d for _, d, _ in group)
    # The user acts halfway between two cycle starts; the second cycle is the first to read it
    rows.append("user action")
    for s in series:
        s["base"].append(None), s["x"].append(None), s["hover"].append("")
    wait = period / 2
    blank = [None] * cycles
    series.append(dict(name="waits for the next cycle", color="--muted", legend=False,
                       base=blank + [period - wait],
                       x=blank + [wait], hover=[""] * cycles + [f"user action: waits {wait:g} ms "
                                                                 "for the next cycle"]))
    series.append(dict(name="until the user sees the result", color="--ink-2", legend=False,
                       base=blank + [period],
                       x=blank + [t], hover=[""] * cycles + [f"user action: the cycle takes {t} ms; "
                                                             f"seen {wait + t:g} ms after it"]))
    return dict(type="gantt", title=title, rows=rows, series=series,
                xTitle="ms", yTitle="", xRange=[0, window]), t, wait + t


seq_cycle = sum(d for st in STAGES for _, d, _ in (st if isinstance(st, list) else [st]))
seq, _, seq_seen = chart("", seq_cycle, 3, 300, False)
seq["title"] = (f"One model after another: a cycle every {seq_cycle} ms (10 Hz); "
                f"an action is seen {seq_seen:g} ms later")
pipe, pipe_latency, pipe_seen = chart("", 10, 20, 300, True)
pipe["title"] = (f"Pipelined: a cycle starts every 10 ms (100 Hz) and takes {pipe_latency} ms; "
                 f"an action is seen {pipe_seen:g} ms later")
out = {"sequential": seq, "pipelined": pipe}
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "live-simulator.json")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("wrote", path, "sequential cycle", seq_cycle, "ms, pipelined latency", pipe_latency, "ms;",
      "action seen after", seq_seen, "and", pipe_seen, "ms")
