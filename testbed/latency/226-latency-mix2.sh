# Mixed load, continued (see 225): a few operators at validator 1 among ordinary users with one
# account at validators 2, 3 and 4. Builds the head of latency-client first (option minfeerate).
#   A: default transaction flooding (200, 100, 200 ms), half load (406 tx/s, 40 from operators),
#      operators not aiming or aiming with a margin of 300 ms.
#   B: fast flooding (10, 10, 20 ms), 80 % of the capacity (650 tx/s, 65 from operators),
#      operators not aiming, aiming (margin 200 ms), and each of the two paying the top fee
#      rate of the users (minfeerate equal to the users' maxfeerate, 10,000).
# Slots at a regular cadence for k > 1 (target 420, 280, 220 ms), k = 1 back to back.
# Points "flood:rate:first:k:n:target:client:margin:fee" (margin 0 = not aiming, fee 0 = as users).
set -uo pipefail
cd ~/src/stellar-core-fix || exit 1
git checkout -q -B latency-client latency-client-in && git log --oneline -1
make -j14 > make-latency.out 2>&1; echo "make exit $?"
grep -q "error:" make-latency.out && { grep "error:" make-latency.out | head; exit 1; }
cp src/stellar-core ~/src/bins/latency-client/stellar-core
cd ~
. ~/src/lab-runs/night/common.sh; links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$HOME/src/bins/latency-client/stellar-core
before() {
    echo "bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING [350] > /dev/null; bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING [1] > /dev/null;"
    [ "$1" = fast ] && echo "bash $S/wan-nodes.sh set FLOOD_TX_PERIOD_MS 10 > /dev/null; bash $S/wan-nodes.sh set FLOOD_ADVERT_PERIOD_MS 10 > /dev/null; bash $S/wan-nodes.sh set FLOOD_DEMAND_PERIOD_MS 20 > /dev/null;"
}
A=""; B=""
for kk in "2:400:420" "3:270:280" "4:210:220"; do
    A="$A normal:406:40:$kk:one:0:0 normal:406:40:$kk:k:300:0"
    B="$B fast:650:65:$kk:one:0:0 fast:650:65:$kk:one:0:10000 fast:650:65:$kk:k:200:0 fast:650:65:$kk:k:200:10000"
done
A="normal:406:40:1:1000:100:one:0:0 $A"
B="fast:650:65:1:1000:100:one:0:0 fast:650:65:1:1000:100:one:0:10000 $B"
for rep in ${REPS:-1 2}; do
for p in ${LAT_POINTS:-$A $B}; do
    IFS=: read -r flood rate frate k n target client margin fee <<< "$p"
    name=$client; [ "$margin" != 0 ] && name=$name$margin; [ "$fee" != 0 ] && name=${name}fee
    tag=-mix2-$flood-r$rate-n$n-$name-r$rep
    first=""
    [ "$client" = k ] && first="$first&classmargin=$margin"
    [ "$fee" != 0 ] && first="$first&minfeerate=$fee"
    echo; echo "######## $(date +%H:%M) rep $rep, flooding $flood, $rate tx/s, k=$k, ledgers of $n, target $target ms, operators $name"
    ( export KSWEEP_TXSET=$n KSWEEP_ACCOUNTS=80000 LOADGEN_ACCOUNTS=80000 LOADGEN_NODES="1 2 3 4" KSWEEP_RATE=$rate
      export LOADGEN_FIRST_RATE=$frate LOADGEN_FIRST_EXTRA="$first"
      KSWEEP_TAG=$tag KSWEEP_K_UPGRADE=1 KSWEEP_BEFORE="$(before $flood)" KSWEEP_PAY_EXTRA="&stepms=2" \
          bash $S/ksweep.sh pay "$k" "$target" 240 ) 2>&1 | grep -E "crashes|rejected|did not apply|not in sync"
    d=~/src/lab-runs/wan/ksw-pay-k$k$tag/s1-c$target
    id="rep=$rep flood=$flood rate=$rate k=$k client=$name"
    echo "RUN $id: $(grep -E "^ledgers|host cpu" $d/summary.txt | tr '\n' ' ' | cut -c1-200)"
    python3 ~/src/lab-runs/mix-lat.py $d | sed "s/^/MIX $id /"
    echo "GAP $id: $(python3 ~/src/lab-runs/tx-slots.py $d | head -2 | tr '\n' ' ' | cut -c1-300)"
done
done
bash $S/wan-nodes.sh stop > /dev/null 2>&1
echo; echo "######## $(date +%H:%M) MIX2-DONE"
