#!/usr/bin/env bash
# Sweeps network delay and target close time on the WAN testbed under payment load.
# Needs a network (wan-net.sh up) and initialized, upgraded validators (wan-nodes.sh init/upgrade).
#
# Usage: wan-sweep.sh <name> <txrate> <seconds> "<delay scales>" "<close ms list>"
#   e.g. wan-sweep.sh baseline 500 180 "1 0" "5000 2000 1000 500"
# LOADGEN_EXTRA is appended to the generateload query, e.g. "&maxfeerate=10000&skiplowfeetxs=true"
# to keep generating when the tx queue is full. LOADGEN_MODE picks the load (default pay).
# MIDWAY_CMD, if set, is a shell command run half way through the load (e.g. an upgrade).
# LOADGEN_SETUP, if set, is a generateload query run after each restart (e.g. Soroban setup);
# several are separated by ";". LOADGEN_ACCOUNTS sets the accounts used (default 20000).
# Keeps the timing lines of every node, per point, in ~/src/lab-runs/wan/<name>/s<scale>-c<close>.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NODES="bash $HERE/wan-nodes.sh"
W="${WAN_DIR:-/ram/wan}"
OUT="$HOME/src/lab-runs/wan/$1"
rate="$2"
secs="$3"
mkdir -p "$OUT"

ledger() {
    $NODES http 1 info | python3 -c 'import json, sys
i = json.load(sys.stdin)["info"]
print(i["ledger"]["num"] if i["state"] == "Synced!" else 0)' 2>/dev/null || echo 0
}

for scale in $4; do
    bash "$HERE/wan-net.sh" delay "${WAN_RTT:-}" "${WAN_N:-7}" "$scale" 2>/dev/null
    for close in $5; do
        $NODES stop
        sed -i "s/^ARTIFICIALLY_SET_CLOSE_TIME_FOR_TESTING=.*/ARTIFICIALLY_SET_CLOSE_TIME_FOR_TESTING=$close/" \
            "$W"/n*/stellar.cfg
        $NODES start > /dev/null
        for _ in $(seq 1 60); do
            [ "$(ledger)" -gt 0 ] && break
            sleep 2
        done
        sleep 10
        if [ "$(ledger)" -eq 0 ]; then
            echo "node 1 is not in sync, stopping the sweep"
            bash "$HERE/wan-nodes.sh" status
            exit 1
        fi
        if [ -n "${LOADGEN_SETUP:-}" ]; then
            # Load generator state (e.g. Soroban contract instances) does not survive a restart.
            # Several setup steps are separated by ";", each followed by the wait.
            IFS=";" read -ra steps <<< "$LOADGEN_SETUP"
            for step in "${steps[@]}"; do
                $NODES http 1 "generateload?$step" > /dev/null
                sleep "${LOADGEN_SETUP_WAIT:-60}"
            done
        fi
        start=$(($(ledger) + 3))
        cpu0=$(head -n 1 /proc/stat)
        # Per-thread CPU of every node over 10 s, a third of the way into the load
        ( sleep $((secs / 3)); bash "$HERE/cpu-threads.sh" 10 > "$OUT/threads.tmp" 2>&1 ) &
        # LOADGEN_NODES spreads the load over several nodes, each with its own share of accounts
        gen=(${LOADGEN_NODES:-1})
        accounts=$((${LOADGEN_ACCOUNTS:-20000} / ${#gen[@]})); share=$((rate / ${#gen[@]}))
        for i in "${!gen[@]}"; do
            $NODES http "${gen[$i]}" "generateload?mode=${LOADGEN_MODE:-pay}&accounts=$accounts&offset=$((i * accounts))&txs=$((share * secs))&txrate=$share${LOADGEN_EXTRA:-}" > /dev/null
        done
        if [ -n "${MIDWAY_CMD:-}" ]; then
            sleep $((secs / 2))
            eval "$MIDWAY_CMD"
            sleep $((secs - secs / 2))
        else
            sleep "$secs"
        fi
        cpu1=$(head -n 1 /proc/stat)
        end=$(ledger)
        for n in ${LOADGEN_NODES:-1}; do $NODES http "$n" "generateload?mode=stop" > /dev/null; done
        d="$OUT/s$scale-c$close"
        for n in "$W"/n*; do
            [ "${n##*/n}" -gt "${WAN_N:-7}" ] && continue  # watchers are not analyzed
            mkdir -p "$d/$(basename "$n")"
            grep -E "PipelineLive|PipelineApply|PipelineStudy|Got consensus" "$n/node.log" > "$d/$(basename "$n")/node.log"
        done
        python3 "$HERE/wan-analyze.py" "$d" "$start" "$end" > "$d/summary.txt"
        # Host CPU busy share during the load (all cores), from /proc/stat
        python3 - "$cpu0" "$cpu1" >> "$d/summary.txt" <<'PY'
import sys
a, b = ([int(x) for x in s.split()[1:]] for s in sys.argv[1:3])
d = [y - x for x, y in zip(a, b)]
idle = d[3] + d[4]
print(f"host cpu busy {100 * (sum(d) - idle) / sum(d):.0f}%")
PY
        wait
        cat "$OUT/threads.tmp" >> "$d/summary.txt" 2>/dev/null
        echo "== delay scale $scale, target close $close ms, ledgers $start-$end"
        tail -n 4 "$d/summary.txt"
    done
done
