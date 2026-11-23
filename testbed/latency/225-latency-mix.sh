# Latency of a few operators that aim, among ordinary users that do not. 406 tx/s in all (half
# the capacity): 40 tx/s from validator 1, the operators, and 122 tx/s from each of validators
# 2, 3 and 4, ordinary users with one account (any class). The operators either pay from any
# account ("one", the reference) or from the class of the slot they aim for (classmargin).
# Fast transaction flooding (10, 10, 20 ms); slots opened at a regular cadence for k > 1 (target
# 420, 280, 220 ms); k = 1 back to back (target 100 ms). 350 us per operation, 240 s, submissions
# every 2 ms. Points "k:n:target:client[:margin]". mix-lat.py splits the latency by origin.
. ~/src/lab-runs/night/common.sh; links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$HOME/src/bins/latency-client/stellar-core
before() {
    echo "bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING [350] > /dev/null; bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING [1] > /dev/null;"
    echo "bash $S/wan-nodes.sh set FLOOD_TX_PERIOD_MS 10 > /dev/null; bash $S/wan-nodes.sh set FLOOD_ADVERT_PERIOD_MS 10 > /dev/null; bash $S/wan-nodes.sh set FLOOD_DEMAND_PERIOD_MS 20 > /dev/null;"
}
P="1:1000:100:one 2:400:420:one 2:400:420:k:200 2:400:420:k:350 3:270:280:one 3:270:280:k:200 3:270:280:k:350 4:210:220:one 4:210:220:k:200 4:210:220:k:350"
for rep in ${REPS:-1 2}; do
for p in ${LAT_POINTS:-$P}; do
    IFS=: read -r k n target client margin <<< "$p"
    tag=-mix-n$n-$client${margin:-}-r$rep
    first=""; [ "$client" = k ] && first="&classmargin=$margin"
    echo; echo "######## $(date +%H:%M) rep $rep, k=$k, ledgers of $n, target $target ms, operators $client ${margin:-}"
    ( export KSWEEP_TXSET=$n KSWEEP_ACCOUNTS=80000 LOADGEN_ACCOUNTS=80000 LOADGEN_NODES="1 2 3 4" KSWEEP_RATE=406
      export LOADGEN_FIRST_RATE=40 LOADGEN_FIRST_EXTRA="$first"
      KSWEEP_TAG=$tag KSWEEP_K_UPGRADE=1 KSWEEP_BEFORE="$(before)" KSWEEP_PAY_EXTRA="&stepms=2" \
          bash $S/ksweep.sh pay "$k" "$target" 240 ) 2>&1 | grep -E "crashes|rejected|did not apply|not in sync"
    d=~/src/lab-runs/wan/ksw-pay-k$k$tag/s1-c$target
    echo "RUN rep=$rep k=$k client=$client${margin:-}: $(grep -E "^ledgers|host cpu" $d/summary.txt | tr '\n' ' ' | cut -c1-200)"
    python3 ~/src/lab-runs/mix-lat.py $d | sed "s/^/MIX rep=$rep k=$k client=$client${margin:-} /"
    echo "GAP rep=$rep k=$k client=$client${margin:-}: $(python3 ~/src/lab-runs/tx-slots.py $d | head -2 | tr '\n' ' ' | cut -c1-300)"
done
done
bash $S/wan-nodes.sh stop > /dev/null 2>&1
echo; echo "######## $(date +%H:%M) MIX-DONE"
