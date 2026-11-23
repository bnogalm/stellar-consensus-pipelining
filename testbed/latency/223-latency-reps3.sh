# Second version of 222, with the third flooding timer too. Latency by depth k with normal and fast transaction flooding, three repetitions of every point,
# at half the capacity (406 of 813 tx/s), submissions every 2 ms from validator 1.
#   normal: FLOOD_TX_PERIOD_MS 200, FLOOD_ADVERT_PERIOD_MS 100, FLOOD_DEMAND_PERIOD_MS 200 (the defaults)
#   fast:   10, 10 and 20
# Clients: one account; an account in every class (classmargin 300 ms normal, 200 ms fast).
# Testbed as in 211 (350 us per operation, target 100 ms, 240 s). The repetition is the outer
# loop, so that a partial night is balanced.
. ~/src/lab-runs/night/common.sh; links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$HOME/src/bins/latency-client/stellar-core
before() {
    echo "bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING [350] > /dev/null; bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING [1] > /dev/null;"
    [ "$1" = fast ] && echo "bash $S/wan-nodes.sh set FLOOD_TX_PERIOD_MS 10 > /dev/null; bash $S/wan-nodes.sh set FLOOD_ADVERT_PERIOD_MS 10 > /dev/null; bash $S/wan-nodes.sh set FLOOD_DEMAND_PERIOD_MS 20 > /dev/null;"
}
for rep in ${REPS:-1 2 3}; do
for flood in normal fast; do
for p in ${LAT_POINTS:-1:1000:one 2:400:one 2:400:k 3:270:one 3:270:k 4:210:one 4:210:k}; do
    IFS=: read -r k n client <<< "$p"
    rate=406; margin=300; [ "$flood" = fast ] && margin=200
    tag=-reps3-$flood-n$n-$client-r$rep
    extra="&stepms=2"
    [ "$client" = k ] && extra="$extra&classmargin=$margin"
    echo; echo "######## $(date +%H:%M) rep $rep, flooding $flood, k=$k, ledgers of $n, client $client"
    ( bigw $n "1"; export KSWEEP_RATE=$rate
      KSWEEP_TAG=$tag KSWEEP_K_UPGRADE=1 KSWEEP_BEFORE="$(before $flood)" KSWEEP_PAY_EXTRA="$extra" \
          bash $S/ksweep.sh pay "$k" 100 240 ) 2>&1 | grep -E "crashes|rejected|did not apply|not in sync"
    d=~/src/lab-runs/wan/ksw-pay-k$k$tag/s1-c100
    echo "RUN rep=$rep flood=$flood k=$k client=$client: $(grep -E "^ledgers|host cpu" $d/summary.txt | tr '\n' ' ' | cut -c1-200)"
    echo "LAT rep=$rep flood=$flood k=$k client=$client: $(python3 ~/src/lab-runs/latency-dist.py $d 10 2000000000 $d/latency.json 2>&1 | tr '\n' ' ' | cut -c1-400)"
    echo "BUD rep=$rep flood=$flood k=$k client=$client: $(python3 ~/src/lab-runs/tx-budget.py $d | head -3 | tr '\n' ' ' | cut -c1-400)"
done
done
done
bash $S/wan-nodes.sh stop > /dev/null 2>&1
echo; echo "######## $(date +%H:%M) REPS-DONE"
