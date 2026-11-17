#!/usr/bin/env bash
# Full workload round on the WAN testbed: every classic operation type and real contracts
# (the load generator's FullWorkload: SAC for XLM and two issued assets, the OpenZeppelin token,
# Soroswap), on a fresh network per k, and a check of everything the round must show.
# Needs the network with watchers (wan-net.sh up, WAN_WATCHERS="1 2 3 4").
#
# Usage: full-round.sh <tag> "<k list>" [seconds] [target_ms]
#   FULL_USERS (20000), FULL_RATE (offered tx/s over all load nodes, 600), FULL_TXSET (classic tx
#   set limit in operations, 1000), FULL_INVARIANTS=1 to run every invariant on every node,
#   LOADGEN_NODES (watchers that generate load, "8 9 10 11"; the first one also runs the setup).
# During the load: an upgrade at a third (tx set limit + 200, base fee 200) and a restart of one
# validator (FULL_RESTART, default n3, 20 s down) at two thirds.
#   FULL_RESTART=all stops every validator at two thirds and starts them again 20 s later;
#   FULL_STOP=kill (default) kills them with SIGKILL, FULL_STOP=clean sends SIGTERM and waits.
#   FULL_MID_UPGRADE=version makes the network start one protocol version below the binary's and
#   adds the version upgrade to the one at a third; FULL_MID_UPGRADE=k:<n> makes the upgrade at a
#   third a change of k to n instead.
# k is a network parameter (header flags, bits 16 to 19): it is set by an upgrade after genesis.
# Results: ~/src/lab-runs/wan/full-<tag>-k<k>/: summary.txt (timeline, wan-analyze.py),
#   checks.txt (crashes, invariants, ledger hashes), results.txt (full-analyze.py), the
#   transaction logs of the load nodes and the FullWorkload stats lines.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NODES="bash $HERE/wan-nodes.sh"
W="${WAN_DIR:-/ram/wan}"
tag="$1"
secs="${3:-600}"
target="${4:-200}"
users="${FULL_USERS:-20000}"
rate="${FULL_RATE:-600}"
gen=(${LOADGEN_NODES:-8 9 10 11})
BIN="${BIN:-$HOME/src/stellar-core-pipeline/src/stellar-core}"
export BIN

info() { $NODES http "$1" info | python3 -c 'import json, sys
i = json.load(sys.stdin)["info"]
print(i["ledger"]["num"] if i["state"] == "Synced!" else 0)' 2>/dev/null || echo 0; }
completed() { $NODES http "$1" metrics | python3 -c 'import json, sys
m = json.load(sys.stdin)["metrics"]
print(m.get("loadgen.run.complete", {}).get("count", 0), m.get("loadgen.run.failed", {}).get("count", 0))' 2>/dev/null || echo "0 0"; }
# Stops the round when n1 closes no ledger for 3 target times; $1: what is about to happen.
alive() {
    local a b
    a=$(info 1); sleep $((target * 3 / 1000 + 2)); b=$(info 1)
    if [ "$a" = 0 ] || [ "$b" = 0 ] || [ "$b" -le "$a" ]; then
        echo "== k=$k: no ledgers closing before $1 (n1 at $a, then $b)"
        grep -c -E "Invalid close time selected|Lost track of consensus" "$W"/n[1-7]/node.log
        tail -n 5 "$W/n1/stdout.log"
        $NODES stop
        exit 1
    fi
}

for k in $2; do
    OUT="$HOME/src/lab-runs/wan/full-$tag-k$k"
    mkdir -p "$OUT"
    $NODES stop
    pkill -u "$(id -u)" -f "[s]tellar-core run --conf stellar.cfg"
    $NODES init "${WAN_N:-7}" "$target" "$((users + 1000))" > /dev/null
    $NODES set EXPERIMENTAL_TRIGGER_NO_DRIFT_FALLBACK true > /dev/null
    $NODES set EXPERIMENTAL_TEST_TX_LATENCY true > /dev/null
    $NODES set TESTING_SOROBAN_HIGH_LIMIT_OVERRIDE true > /dev/null
    $NODES set UPDATE_SOROBAN_COSTS_DURING_PROTOCOL_UPGRADE_FOR_TESTING true > /dev/null
    $NODES set TRANSACTION_QUEUE_SIZE_MULTIPLIER_FOR_TESTING 4 > /dev/null
    $NODES set SOROBAN_TRANSACTION_QUEUE_SIZE_MULTIPLIER_FOR_TESTING 4 > /dev/null
    if [ "${FULL_INVARIANTS:-0}" = 1 ]; then
        # All but the events invariant, which needs the metadata stream and the classic events.
        $NODES set INVARIANT_CHECKS '["(?!EventsAreConsistentWithEntryDiffs).*"]' > /dev/null
    fi
    # Genesis and upgrades with 5 s ledgers, then the rules switch at a ledger boundary (as in
    # ksweep.sh).
    $NODES set ARTIFICIALLY_SET_CLOSE_TIME_FOR_TESTING 5000 > /dev/null
    $NODES start > /dev/null
    sleep 30
    if [ "$(info 1)" = 0 ]; then
        echo "== k=$k: n1 not synced 30 s after the start, stopping"
        tail -n 5 "$W/n1/stdout.log"
        $NODES stop
        exit 1
    fi
    proto=$("$BIN" version 2>/dev/null | awk '!p && /ledger protocol version/ { print $NF; p = 1 }')
    mid="${FULL_MID_UPGRADE:-fee}"
    first=$proto
    [ "$mid" = version ] && first=$((proto - 1))
    export UPGRADE_PROTOCOL=$first
    $NODES upgrade "${FULL_TXSET:-1000}" > /dev/null
    sleep 20
    if [ "$k" -gt 1 ]; then
        UPGRADE_EXTRA="&flags=$((k << 16))" $NODES upgrade "${FULL_TXSET:-1000}" > /dev/null
        for _ in $(seq 1 60); do
            grep -q "k changes from 1 to $k" "$W/n1/node.log" && break
            sleep 1
        done
        if ! grep -q "k changes from 1 to $k" "$W/n1/node.log"; then
            echo "== k=$k: the upgrade of k did not apply"
            $NODES stop
            exit 1
        fi
        # The change settles k ledgers later.
        sleep $((5 * k + 5))
    fi
    l0=$(info 1)
    while [ "$(info 1)" = "$l0" ]; do sleep 0.1; done
    sleep 1.5
    $NODES stop
    $NODES set ARTIFICIALLY_SET_CLOSE_TIME_FOR_TESTING "$target" > /dev/null
    [ "$k" -gt 1 ] && $NODES set EXPERIMENTAL_LIVE_PIPELINE_DEPTH "$k" > /dev/null
    $NODES start > /dev/null
    for _ in $(seq 1 60); do [ "$(info 1)" -gt 0 ] && [ "$(info "${gen[0]}")" -gt 0 ] && break; sleep 2; done
    sleep 10
    echo "== k=$k: network up at ledger $(info 1)"
    alive "the setup"

    # Setup, one step at a time from the first load node: each step waits for the load generator
    # to finish submitting and then for 4k ledgers more.
    # As FullWorkload::setupSteps: 4 + the most of the user payment rounds, the token mint
    # batches and 2.
    per_l2=$(((users + 199) / 200)); rounds=$(((per_l2 * 2 + 99) / 100))
    batches=$(((((users + 99) / 100) + 19) / 20))
    steps=$((4 + (rounds > batches ? (rounds > 2 ? rounds : 2) : (batches > 2 ? batches : 2))))
    for s in $(seq 1 "$steps"); do
        read -r c0 f0 <<< "$(completed "${gen[0]}")"
        echo "setup step $s: $(HTTP_TIMEOUT=300 $NODES http "${gen[0]}" "generateload?mode=full_setup&step=$s&users=$users&accounts=$users&offset=1000&txrate=${FULL_SETUP_RATE:-300}&skiplowfeetxs=true" | tr -d '\n' | cut -c1-200)"
        for _ in $(seq 1 300); do
            read -r c1 f1 <<< "$(completed "${gen[0]}")"
            [ "$c1" -gt "$c0" ] || [ "$f1" -gt "$f0" ] && break
            sleep 1
        done
        sleep $((2 + k * 2))
    done
    # The last setup transactions apply before the load starts.
    sleep $((10 + k * 5))
    grep -h "FullWorkload setup" "$W/n${gen[0]}/node.log" | tail -n 3 | cut -c1-200

    alive "the load"
    start=$(($(info 1) + 3))
    per=$((rate / ${#gen[@]}))
    cpu0=$(head -n 1 /proc/stat)
    for i in "${!gen[@]}"; do
        $NODES http "${gen[$i]}" "generateload?mode=full&node=$i&users=$users&accounts=$((users / ${#gen[@]}))&offset=$((1000 + i * users / ${#gen[@]}))&txs=$((per * secs * 2))&txrate=$per&maxfeerate=10000&skiplowfeetxs=true&spikeinterval=120&spikesize=$((per * 5))" > /dev/null
    done
    # Under load: an upgrade at a third (tx set limit and base fee, so the k - 1 ledgers after
    # it apply drained), and a validator restarted at two thirds (it catches up while the
    # others go on).
    sleep $((secs / 3))
    alive "the upgrade vote"
    case "$mid" in
    k:*)
        UPGRADE_EXTRA="&flags=$((${mid#k:} << 16))" $NODES upgrade "${FULL_TXSET:-1000}" > /dev/null
        ;;
    *)
        UPGRADE_PROTOCOL=$proto UPGRADE_EXTRA="&basefee=200" \
            $NODES upgrade "$(( ${FULL_TXSET:-1000} + 200 ))" > /dev/null
        ;;
    esac
    echo "upgrade ($mid) voted at ledger $(info 1)"
    sleep $((secs / 3))
    alive "the stop"
    restart="${FULL_RESTART:-3}"
    if [ "$restart" = all ]; then
        restarted=$(seq 1 "${WAN_N:-7}")
        sig=$([ "${FULL_STOP:-kill}" = clean ] && echo TERM || echo KILL)
        echo "stopping every validator (SIG$sig) at ledger $(info 1)"
        for i in $restarted; do
            [ -f "$W/n$i/pid" ] && kill -"$sig" "$(cat "$W/n$i/pid")" 2>/dev/null
        done
        t0=$(date +%s)
        for i in $restarted; do
            f="$W/n$i/pid"
            [ -f "$f" ] || continue
            for _ in $(seq 1 300); do kill -0 "$(cat "$f")" 2>/dev/null || break; sleep 0.1; done
            kill -0 "$(cat "$f")" 2>/dev/null && echo "n$i still running after 30 s, killed" &&
                kill -9 "$(cat "$f")"
            rm -f "$f"
        done
        echo "all stopped after $(($(date +%s) - t0)) s"
    else
        restarted=$restart
        echo "restarting n$restart at ledger $(info 1)"
        $NODES stop "$restart"
    fi
    sleep 20
    $NODES start $restarted > /dev/null
    sleep $((secs - 2 * (secs / 3) - 20))
    cpu1=$(head -n 1 /proc/stat)
    end=$(info 1)
    upgraded=$($NODES http 1 info | python3 -c 'import json, sys
l = json.load(sys.stdin)["info"]["ledger"]
print("protocol", l["version"], "base fee", l["baseFee"], "max tx set size", l["maxTxSetSize"])' 2>/dev/null)
    restarted_state=$(for i in $restarted; do echo "n$i $($NODES http "$i" info | python3 -c 'import json, sys
i = json.load(sys.stdin)["info"]
print(i["state"], "at ledger", i["ledger"]["num"])' 2>/dev/null)"; done | tr '\n' ';')
    for n in "${gen[@]}"; do $NODES http "$n" "generateload?mode=stop" > /dev/null; done
    # Let the queued transactions apply and the checkpoints publish.
    sleep 30

    d="$OUT/s1-c$target"
    mkdir -p "$d"
    for n in "$W"/n*; do
        i="${n##*/n}"
        mkdir -p "$d/n$i"
        if [ "$i" -le "${WAN_N:-7}" ]; then
            grep -E "PipelineLive|PipelineApply|PipelineStudy|Got consensus" "$n/node.log" > "$d/n$i/node.log"
        else
            grep -E "FullWorkload|LoadGen.*(rejected|failed|complete)" "$n/node.log" | tail -n 2000 > "$d/n$i/loadgen.log"
            [ -f "$n/fullworkload-txs.log" ] && gzip -c "$n/fullworkload-txs.log" > "$d/n$i/fullworkload-txs.log.gz"
        fi
    done
    # The whole log of the restarted validators, for their catch-up.
    for i in $restarted; do gzip -c "$W/n$i/node.log" > "$d/n$i/node-full.log.gz"; done
    grep -H -E "considers invalid|locally-invalid|Inconsistent txSet validity|buckets of ledger|Starting catchup|k changes from|invalid value from self|moved to a bad state|future message" \
        "$W"/n*/node.log > "$d/flagged.log" 2>/dev/null
    python3 "$HERE/wan-analyze.py" "$d" "$start" "$end" > "$d/summary.txt"
    python3 - "$cpu0" "$cpu1" >> "$d/summary.txt" <<'PY'
import sys
a, b = ([int(x) for x in s.split()[1:]] for s in sys.argv[1:3])
d = [y - x for x, y in zip(a, b)]
print(f"host cpu busy {100 * (sum(d) - d[3] - d[4]) / sum(d):.0f}%")
PY
    # A node can end without a core dump or a signal (an exception): its process is gone.
    dead=$(for n in "$W"/n*; do
        i="${n##*/n}"; f="$n/pid"
        [ -f "$f" ] && kill -0 "$(cat "$f")" 2>/dev/null || echo "n$i"
    done | sort -V | tr '
' ' ')
    # Keep the evidence of a node that died or asserted: its stdout and whole log.
    for n in "$W"/n*; do
        i="${n##*/n}"
        if grep -q printAssertFailure "$n/stdout.log" 2>/dev/null || [[ " $dead " == *" n$i "* ]]; then
            mkdir -p "$d/n$i"
            cp "$n/stdout.log" "$d/n$i/stdout.log" 2>/dev/null
            gzip -c "$n/node.log" > "$d/n$i/node-full.log.gz"
        fi
    done
    $NODES stop
    {
        echo "k=$k ledgers $start-$end"
        echo "nodes not running at the end: ${dead:-none}"
        echo "crashes: $(grep -l printAssertFailure "$W"/n*/stdout.log 2>/dev/null | wc -l)"
        echo "invariant failures: $(cat "$W"/n*/node.log | grep -c -i "invariant.*does not hold")"
        echo "partition violations: $(cat "$W"/n*/node.log | grep -c partition_violation)"
        echo "after the upgrade: $upgraded"
        echo "drained ledgers (n1): $(grep -c "event=drained" "$W/n1/node.log")"
        echo "restarted: last ledgers $(for i in $restarted; do grep "Ledger close complete" "$W/n$i/node.log" | tail -n 1 | grep -o "[0-9]*$"; done | tr '\n' ' ')," \
            "n1 last ledger $(grep "Ledger close complete" "$W/n1/node.log" | tail -n 1 | grep -o "[0-9]*$")," \
            "state at the end: $restarted_state"
        echo "catchups started per validator: $(for i in $(seq 1 "${WAN_N:-7}"); do grep -c "Starting catchup" "$W/n$i/node.log"; done | tr '\n' ' ')"
        echo "k changes (n1): $(grep -o "k changes from .*" "$W/n1/node.log" | tr '\n' ';')"
        for s in "considers invalid" "locally-invalid" "Inconsistent txSet validity" "buckets of ledger"; do
            echo "\"$s\": $(cat "$W"/n*/node.log | grep -c "$s")"
        done
        for s in "Got an exception" "moved to a bad state" "Invalid close time selected"             "Lost track of consensus" "processing a future message while tracking"; do
            echo "\"$s\": $(cat "$W"/n[1-7]/node.log "$W"/n[1-7]/stdout.log 2>/dev/null | grep -c "$s")"
        done
        echo "setup: $(grep -h "FullWorkload setup \(complete\|incomplete\)" "$W"/n*/node.log | sort | uniq -c | tr -s ' ' | tr '\n' ';')"
        python3 "$HERE/full-hashes.py" "$W" "${WAN_N:-7}"
    } > "$d/checks.txt" 2>&1
    python3 "$HERE/full-analyze.py" "$BIN" "$W/n1/history" "$d" "$start" "$end" "$k" > "$d/results.txt" 2>&1
    echo "== k=$k"
    cat "$d/checks.txt"
    tail -n 6 "$d/summary.txt"
    cat "$d/results.txt"
done
