# Checks of the latency table (results/latency-by-depth.md).
#   B: capacity of each k with the slot cadence and the flooding of the table: load over the
#      capacity (6,000 tx/s from the four watchers), default and fast flooding. To know which
#      share of its capacity each k faced at 406 and 650 tx/s.
#   C: the client with one account at an apply cost of 100 us per transaction instead of 350,
#      k = 1 and k = 3, half load, default and fast flooding, two runs. To split what a client
#      that does not aim gains into the smaller ledgers' apply and the rest.
#   A: k = 1 and k = 3 at 650 tx/s, default and fast flooding interleaved in one session, four
#      runs each (repetitions 3 to 6 of 226, which keeps its own 1 and 2).
# Testbed as in 225/226: slots every 420, 280, 220 ms for k = 2, 3, 4, k = 1 back to back;
# mixed load (10 % at validator 1, the rest at validators 2 to 4), submissions every 2 ms.
. ~/src/lab-runs/night/common.sh; links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$HOME/src/bins/latency-client/stellar-core
before() { # flooding, apply us
    echo "bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING [$2] > /dev/null; bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING [1] > /dev/null;"
    [ "$1" = fast ] && echo "bash $S/wan-nodes.sh set FLOOD_TX_PERIOD_MS 10 > /dev/null; bash $S/wan-nodes.sh set FLOOD_ADVERT_PERIOD_MS 10 > /dev/null; bash $S/wan-nodes.sh set FLOOD_DEMAND_PERIOD_MS 20 > /dev/null;"
}
if [ "${SKIP_B:-0}" = 0 ]; then
for flood in normal fast; do
for p in 1:1000:100 2:400:420 3:270:280 4:210:220; do
    IFS=: read -r k n target <<< "$p"
    tag=-cap-$flood-n$n
    echo; echo "######## $(date +%H:%M) capacity, flooding $flood, k=$k, ledgers of $n, target $target ms"
    ( bigw $n "8 9 10 11"
      KSWEEP_TAG=$tag KSWEEP_K_UPGRADE=1 KSWEEP_BEFORE="$(before $flood 350)" \
          bash $S/ksweep.sh pay "$k" "$target" 240 ) 2>&1 | grep -E "crashes|rejected|did not apply|not in sync"
    d=~/src/lab-runs/wan/ksw-pay-k$k$tag/s1-c$target
    echo "CAP flood=$flood k=$k n=$n target=$target: $(grep -E "^ledgers|host cpu" $d/summary.txt | tr '\n' ' ' | cut -c1-200)"
    echo "GAP flood=$flood k=$k: $(python3 ~/src/lab-runs/tx-slots.py $d | head -2 | tr '\n' ' ' | cut -c1-300)"
done
done
fi
if [ "${SKIP_C:-0}" = 0 ]; then
for rep in 1 2; do
for flood in normal fast; do
for p in 1:1000:100 3:270:280; do
    IFS=: read -r k n target <<< "$p"
    tag=-apply100-$flood-n$n-one-r$rep
    echo; echo "######## $(date +%H:%M) apply 100 us, rep $rep, flooding $flood, k=$k, ledgers of $n, target $target ms"
    ( export KSWEEP_TXSET=$n KSWEEP_ACCOUNTS=80000 LOADGEN_ACCOUNTS=80000 LOADGEN_NODES="1 2 3 4" KSWEEP_RATE=406
      export LOADGEN_FIRST_RATE=40 LOADGEN_FIRST_EXTRA=""
      KSWEEP_TAG=$tag KSWEEP_K_UPGRADE=1 KSWEEP_BEFORE="$(before $flood 100)" KSWEEP_PAY_EXTRA="&stepms=2" \
          bash $S/ksweep.sh pay "$k" "$target" 240 ) 2>&1 | grep -E "crashes|rejected|did not apply|not in sync"
    d=~/src/lab-runs/wan/ksw-pay-k$k$tag/s1-c$target
    id="rep=$rep flood=$flood rate=406 k=$k client=one"
    echo "RUN $id: $(grep -E "^ledgers|host cpu" $d/summary.txt | tr '\n' ' ' | cut -c1-200)"
    python3 ~/src/lab-runs/mix-lat.py $d | sed "s/^/MIX $id /"
done
done
done
fi
bash $S/wan-nodes.sh stop > /dev/null 2>&1
echo; echo "######## $(date +%H:%M) part A"
P=""
for flood in normal fast; do
    m=300; [ "$flood" = fast ] && m=200
    P="$P $flood:650:65:1:1000:100:one:0:0 $flood:650:65:3:270:280:one:0:0 $flood:650:65:3:270:280:k:$m:0"
done
REPS="3 4 5 6" LAT_POINTS="$P" bash ~/src/lab-runs/226-latency-mix2.sh
echo; echo "######## $(date +%H:%M) CHECKS-DONE"
