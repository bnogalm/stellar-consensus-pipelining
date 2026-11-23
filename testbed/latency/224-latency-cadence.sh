# Latency with the slots opened at a regular cadence. In the runs of 223 the target close time was
# 100 ms, far below what k slots in consensus sustain, so every slot waited for its base ledger and
# the openings came in bursts (k = 4: 58 % of the gaps under 150 ms). Here the target is 1.1 times
# the mean gap measured there: 420 ms (k = 2), 280 ms (k = 3), 220 ms (k = 4).
# Fast transaction flooding (FLOOD_TX_PERIOD_MS 10, FLOOD_ADVERT_PERIOD_MS 10,
# FLOOD_DEMAND_PERIOD_MS 20), half load (406 tx/s), submissions every 2 ms from validator 1,
# 350 us per operation, 240 s, three repetitions. Clients: one account; an account in every class
# (classmargin 200 ms). The k = 1 reference is the fast flooding run of 223.
. ~/src/lab-runs/night/common.sh; links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$HOME/src/bins/latency-client/stellar-core
before() {
    echo "bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING [350] > /dev/null; bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING [1] > /dev/null;"
    echo "bash $S/wan-nodes.sh set FLOOD_TX_PERIOD_MS 10 > /dev/null; bash $S/wan-nodes.sh set FLOOD_ADVERT_PERIOD_MS 10 > /dev/null; bash $S/wan-nodes.sh set FLOOD_DEMAND_PERIOD_MS 20 > /dev/null;"
}
for rep in ${REPS:-1 2 3}; do
for p in ${LAT_POINTS:-2:400:420:one 2:400:420:k 3:270:280:one 3:270:280:k 4:210:220:one 4:210:220:k}; do
    IFS=: read -r k n target client <<< "$p"
    rate=406; margin=${MARGIN:-200}
    tag=-cad-n$n-$client-r$rep
    extra="&stepms=2"
    [ "$client" = k ] && extra="$extra&classmargin=$margin"
    echo; echo "######## $(date +%H:%M) rep $rep, k=$k, ledgers of $n, target $target ms, client $client"
    ( bigw $n "1"; export KSWEEP_RATE=$rate
      KSWEEP_TAG=$tag KSWEEP_K_UPGRADE=1 KSWEEP_BEFORE="$(before)" KSWEEP_PAY_EXTRA="$extra" \
          bash $S/ksweep.sh pay "$k" "$target" 240 ) 2>&1 | grep -E "crashes|rejected|did not apply|not in sync"
    d=~/src/lab-runs/wan/ksw-pay-k$k$tag/s1-c$target
    echo "RUN rep=$rep flood=cad k=$k client=$client: $(grep -E "^ledgers|host cpu" $d/summary.txt | tr '\n' ' ' | cut -c1-200)"
    echo "LAT rep=$rep flood=cad k=$k client=$client: $(python3 ~/src/lab-runs/latency-dist.py $d 10 2000000000 $d/latency.json 2>&1 | tr '\n' ' ' | cut -c1-400)"
    echo "BUD rep=$rep flood=cad k=$k client=$client: $(python3 ~/src/lab-runs/tx-budget.py $d | head -3 | tr '\n' ' ' | cut -c1-400)"
    echo "GAP rep=$rep flood=cad k=$k client=$client: $(python3 ~/src/lab-runs/tx-slots.py $d | head -2 | tr '\n' ' ' | cut -c1-300)"
done
done
bash $S/wan-nodes.sh stop > /dev/null 2>&1
echo; echo "######## $(date +%H:%M) CADENCE-DONE"
