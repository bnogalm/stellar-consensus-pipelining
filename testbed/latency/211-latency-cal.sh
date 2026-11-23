# Calibration for the latency table: the capacity of the testbed for a depth k and a ledger size n,
# as in 193-emulate.sh (350 us per operation, 6,000 tx/s offered from the four watchers, target
# 100 ms, links as in the published sweeps, 240 s). The points are "k:n" in CAL_POINTS. The sizes
# are first guesses, from the runs of 193, of the ledger that gives 813 tx/s (k = 1 with 1,000 per
# ledger) and 1,220 tx/s (half more) at each k. Waits for the build of 210.
until grep -q "BUILD-LATENCY-DONE" ~/src/lab-runs/210-build-latency.log 2>/dev/null; do sleep 20; done
[ -x ~/src/bins/latency-client/stellar-core ] || { echo "no binary"; exit 1; }
. ~/src/lab-runs/night/common.sh; links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$HOME/src/bins/latency-client/stellar-core
sleepus() { echo "bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING [$1] > /dev/null; bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING [1] > /dev/null;"; }
for p in ${CAL_POINTS:-2:366 2:756 3:230 3:450 3:1000 4:138 4:310 1:2700}; do
    k=${p%%:*}; n=${p##*:}
    echo; echo "######## $(date +%H:%M) k=$k, ledgers of $n"
    ( bigw $n "8 9 10 11"
      KSWEEP_TAG=-cal-n$n KSWEEP_K_UPGRADE=1 KSWEEP_BEFORE="$(sleepus 350)" \
          bash $S/ksweep.sh pay "$k" 100 240 ) 2>&1 | grep -E "crashes|rejected|did not apply|not in sync"
    echo "k=$k n=$n: $(grep -E "^ledgers|host cpu" ~/src/lab-runs/wan/ksw-pay-k$k-cal-n$n/s1-c100/summary.txt | tr '\n' ' ' | cut -c1-200)"
done
bash $S/wan-nodes.sh stop > /dev/null 2>&1
echo; echo "######## $(date +%H:%M) LATENCY-CAL-DONE"
