#!/usr/bin/env bash
# Throughput and cadence against pipeline depth k, on a fresh WAN testbed network per point.
# k = 1 is the network without pipelining. Every point removes the trigger drift fallback.
#
# Usage: ksweep.sh pay|soroban "<k list>" [target_ms] [seconds]
#   pay:     payments, 200-operation tx set limit, 2,000 tx/s offered
#   soroban: contract calls (4M instructions, 2 entries, 2 kB IO), 100 Soroban txs per ledger,
#            700 tx/s offered
# Results: ~/src/lab-runs/wan/ksw-<load>-k<k><KSWEEP_TAG>/s1-c<target>/summary.txt
# WAN_N and WAN_RTT select the network size and RTT matrix (default 7, rtt-7.tsv); ORG_SIZE groups
# validators into organizations for the quorum (see wan-nodes.sh).
# KSWEEP_TXSET sets the tx set size limit (operations), KSWEEP_ACCOUNTS the genesis accounts;
# LOADGEN_NODES (wan-sweep.sh) spreads the load over several nodes.
# KSWEEP_RATE overrides the offered tx/s, KSWEEP_INSTANCES the Soroban contract instances.
# KSWEEP_PAY_EXTRA and KSWEEP_PAY_SETUP add load parameters and setup steps to the payment load.
# KSWEEP_BEFORE and KSWEEP_AFTER are shell commands run around the measured load (after the
# rules switch), e.g. to isolate a validator.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
NODES="bash $HERE/wan-nodes.sh"
load="$1"
target="${3:-150}"
secs="${4:-180}"

ledger_num() {
    $NODES http 1 info | python3 -c 'import json, sys
print(json.load(sys.stdin)["info"]["ledger"]["num"])' 2>/dev/null || echo 0
}
node_lcls() { # LCL of each node, from its log, to check they all stopped on the same one
    for n in /ram/wan/n*; do
        grep "Ledger close complete" "$n/node.log" | tail -n 1 | grep -o "[0-9]*$"
    done | sort | uniq -c | tr "\n" " "
}

for k in $2; do
    $NODES stop
    pkill -u "$(id -u)" -f "[s]tellar-core run --conf stellar.cfg"
    $NODES init "${WAN_N:-7}" "$target" "${KSWEEP_ACCOUNTS:-20000}"
    $NODES set EXPERIMENTAL_TRIGGER_NO_DRIFT_FALLBACK true
    $NODES set EXPERIMENTAL_TEST_TX_LATENCY true
    if [ "$load" = soroban ]; then
        $NODES set TESTING_SOROBAN_HIGH_LIMIT_OVERRIDE true
        $NODES set UPDATE_SOROBAN_COSTS_DURING_PROTOCOL_UPGRADE_FOR_TESTING true
        $NODES set LOADGEN_NUM_DATA_ENTRIES_FOR_TESTING "[2]"
        $NODES set LOADGEN_NUM_DATA_ENTRIES_DISTRIBUTION_FOR_TESTING "[1]"
        $NODES set LOADGEN_IO_KILOBYTES_FOR_TESTING "[2]"
        $NODES set LOADGEN_IO_KILOBYTES_DISTRIBUTION_FOR_TESTING "[1]"
        $NODES set LOADGEN_TX_SIZE_BYTES_FOR_TESTING "[1000]"
        $NODES set LOADGEN_TX_SIZE_BYTES_DISTRIBUTION_FOR_TESTING "[1]"
        $NODES set LOADGEN_INSTRUCTIONS_FOR_TESTING "[4000000]"
        $NODES set LOADGEN_INSTRUCTIONS_DISTRIBUTION_FOR_TESTING "[1]"
    fi
    # Genesis and upgrades with 5 s ledgers, so the network can be stopped between ledgers.
    $NODES set ARTIFICIALLY_SET_CLOSE_TIME_FOR_TESTING 5000 > /dev/null
    $NODES start > /dev/null
    sleep 30
    $NODES upgrade "${KSWEEP_TXSET:-$([ "$load" = pay ] && echo 200 || echo 1000)}" > /dev/null
    sleep 20
    $NODES http 1 info | grep -E "maxTxSetSize|\"version\""
    # Switch the rules like an upgrade would, at a ledger boundary: stop all nodes shortly after
    # a ledger closes, when every node has applied it and no slot is in consensus yet.
    l0=$(ledger_num)
    while [ "$(ledger_num)" = "$l0" ]; do sleep 0.1; done
    sleep 1.5
    $NODES stop
    echo "rules switched after ledger $(node_lcls)"
    $NODES set ARTIFICIALLY_SET_CLOSE_TIME_FOR_TESTING "$target" > /dev/null
    if [ "$k" -gt 1 ]; then
        $NODES set EXPERIMENTAL_LIVE_PIPELINE_DEPTH "$k"
    fi
    eval "${KSWEEP_BEFORE:-true}"
    if [ "$load" = soroban ]; then
        LOADGEN_MODE=soroban_invoke \
            LOADGEN_EXTRA="&instances=${KSWEEP_INSTANCES:-5}&maxfeerate=10000000&skiplowfeetxs=true" \
            LOADGEN_SETUP="mode=soroban_invoke_setup&instances=${KSWEEP_INSTANCES:-5}&wasms=1" LOADGEN_SETUP_WAIT=40 \
            bash "$HERE/wan-sweep.sh" "ksw-$load-k$k${KSWEEP_TAG:-}" "${KSWEEP_RATE:-700}" "$secs" "1" "$target"
    else
        LOADGEN_EXTRA="&maxfeerate=10000&skiplowfeetxs=true${KSWEEP_PAY_EXTRA:-}" \
            LOADGEN_SETUP="${KSWEEP_PAY_SETUP:-}" LOADGEN_SETUP_WAIT="${KSWEEP_PAY_SETUP_WAIT:-20}" \
            bash "$HERE/wan-sweep.sh" "ksw-$load-k$k${KSWEEP_TAG:-}" "${KSWEEP_RATE:-2000}" "$secs" "1" "$target"
    fi
    eval "${KSWEEP_AFTER:-true}"
    echo "k=$k crashes: $(grep -l printAssertFailure /ram/wan/n*/stdout.log | wc -l)" \
        "partition violations: $(cat /ram/wan/n*/node.log | grep -c partition_violation)" \
        "close times raised (n1): $(grep -c closetime_raised /ram/wan/n1/node.log)"
    $NODES http 1 metrics | python3 -c 'import json, sys
m = json.load(sys.stdin)["metrics"]
print({k: v.get("count") for k, v in m.items()
       if k in ("soroban.host-fn-op.failure", "soroban.host-fn-op.success",
                "ledger.apply.success", "ledger.apply.failure")})'
    # What the load generator achieved, and how many submissions the queue turned away
    grep LoadGen /ram/wan/n1/node.log | grep -i "actual" | tail -n 1 | cut -c1-160
    echo "rejected: $(grep -c "tx rejected" /ram/wan/n1/node.log)" \
        "skipped low fee: $(grep -c "skipped low fee" /ram/wan/n1/node.log)"
    $NODES status | sort | uniq -c | head -3
done
