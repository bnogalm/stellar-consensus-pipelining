#!/usr/bin/env bash
# Per-thread CPU of every stellar-core process over a window, to see whether one thread (such as
# the main thread) saturates while the host total looks low.
# Usage: cpu-threads.sh [seconds]   prints, per node, its total CPU and its three busiest threads
secs="${1:-10}"
hz=$(getconf CLK_TCK)
snap() {
    for p in $(pgrep -f "[s]tellar-core run --conf stellar.cfg"); do
        node=$(basename "$(readlink -f /proc/$p/cwd)")
        for t in /proc/$p/task/*; do
            read -r -a f < "$t/stat" 2>/dev/null || continue
            tid=${t##*/}; name=$([ "$tid" = "$p" ] && echo main || cat "$t/comm" 2>/dev/null | tr " " _)
            echo "$node $tid $name $((f[13] + f[14]))"
        done
    done
}
a=$(snap); sleep "$secs"; b=$(snap)
python3 - "$secs" "$hz" <<PY
import sys
secs, hz = float(sys.argv[1]), float(sys.argv[2])
a = {(l.split()[0], l.split()[1]): (l.split()[2], int(l.split()[3])) for l in """$a""".splitlines() if l}
b = {(l.split()[0], l.split()[1]): (l.split()[2], int(l.split()[3])) for l in """$b""".splitlines() if l}
nodes = {}
for key, (name, t1) in b.items():
    if key in a:
        pct = 100 * (t1 - a[key][1]) / hz / secs
        nodes.setdefault(key[0], []).append((pct, name))
for node in sorted(nodes, key=lambda n: int(n.lstrip("n"))):
    th = sorted(nodes[node], reverse=True)
    print(f"{node}: total {sum(p for p, _ in th):5.0f}%  busiest " +
          ", ".join(f"{n} {p:.0f}%" for p, n in th[:3]))
PY
