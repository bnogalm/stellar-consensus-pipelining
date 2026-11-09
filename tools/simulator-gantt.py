"""Illustrative Gantt of the real-time simulator example in the discussion post: the same models
run one after another (one cycle every 100 ms, 10 Hz) or pipelined by a clock that starts a cycle
every 10 ms (100 Hz). In the pipelined case each model waits only for the data it reads, so the
electrics and the hydraulics, which do not read each other, run at the same time. The simulator had
many more models; these groups and durations are an illustrative example, not measurements."""
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
    return dict(type="gantt", title=title, rows=rows, series=series,
                xTitle="ms", yTitle="", xRange=[0, window]), t


seq_cycle = sum(d for st in STAGES for _, d, _ in (st if isinstance(st, list) else [st]))
seq, _ = chart(f"One model after another: a cycle every {seq_cycle} ms (10 Hz)", seq_cycle, 3, 300,
               False)
pipe, pipe_latency = chart("", 10, 20, 300, True)
pipe["title"] = f"Pipelined: a cycle starts every 10 ms (100 Hz) and takes {pipe_latency} ms"
out = {"sequential": seq, "pipelined": pipe}
path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "live-simulator.json")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("wrote", path, "sequential cycle", seq_cycle, "ms, pipelined latency", pipe_latency, "ms")
