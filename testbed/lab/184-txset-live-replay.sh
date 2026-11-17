# Two measurements, one after the other so they do not disturb each other:
# 1. Testbed, k = 1, real apply, 1,000 to 10,000 payments per ledger, with the tx set logs
#    (bins/txsetlog-*): when each validator asks for a tx set, receives it, and finishes
#    validating it, and how long the leader takes to build it. Where the consensus time per
#    transaction goes.
# 2. A mainnet watcher node (upstream v30 + per-ledger timing) live for WATCH_SECS, then a replay
#    of the same ledgers on the same machine: apply live (signatures already checked when the
#    transactions arrived) against apply in replay, with the same mix.
set -uo pipefail
. ~/src/lab-runs/night/common.sh
KEEP=$HOME/src/lab-runs/live-replay
mkdir -p $KEEP

if [ "${SKIP_TESTBED:-0}" != 1 ]; then
echo "######## $(date +%H:%M) part 1: testbed tx set timings"
links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$(ls -d $HOME/src/bins/txsetlog-*/stellar-core | head -n 1)
echo "BIN=$BIN"
for p in "1000 2000" "3000 3000" "6000 5000" "10000 8000"; do
    set -- $p
    echo "######## $(date +%H:%M) tx set timings, $1 per ledger, target $2 ms"
    ( bigw $1 "8 9 10 11"; [ $1 -ge 6000 ] && export KSWEEP_RATE=$(( 13 * $1 * 100 / $2 ))
      KSWEEP_TAG=-tx-n$1 KSWEEP_K_UPGRADE=1 bash $S/ksweep.sh pay "1" $2 240 )
done
bash $S/wan-nodes.sh stop > /dev/null 2>&1
bash $S/wan-net.sh down > /dev/null 2>&1
rm -rf /ram/wan
fi

echo "######## $(date +%H:%M) part 2: mainnet watcher, live"
TBIN=$HOME/src/bins/timing-v30/stellar-core
RUN=/ram/watch
WATCH_SECS=${WATCH_SECS:-14400}
rm -rf $RUN; mkdir -p $RUN && cd $RUN
# Top-level keys first: after the [[VALIDATORS]] tables they would belong to the last one.
{ echo 'PEER_PORT=11725'
  echo 'LOG_FILE_PATH="watch.log"'
  cat $HOME/src/lab-runs/replay/stellar.cfg; } > stellar.cfg
$TBIN --conf stellar.cfg new-db > new-db.log 2>&1 || { echo "FAILED new-db"; tail -3 new-db.log; exit 1; }
guard() { # stop $1 (a PID) if /ram has less than 2 GB left
    while sleep 10; do
        [ $(df --output=avail -k /ram | tail -1) -lt 2000000 ] && { echo RAM-FULL-STOP; kill $1; break; }
    done
}
$TBIN --conf stellar.cfg run > stdout.log 2>&1 & W=$!
guard $W & G=$!
sleep 60
kill -0 $W 2>/dev/null || { echo "FAILED watcher did not start"; tail -3 stdout.log; kill $G; exit 1; }
sleep $((WATCH_SECS - 60))
kill $W; wait $W; kill $G 2>/dev/null
grep -E "PipelineStudy|Got consensus" watch.log > $KEEP/watch.log
cp stellar.cfg $KEEP/watch.cfg
first=$(grep -o "Got consensus: \[seq=[0-9]*" watch.log | head -n 1 | grep -o "[0-9]*$")
last=$(grep -o "PipelineStudy ledger=[0-9]*" watch.log | tail -n 1 | grep -o "[0-9]*$")
echo "watched ledgers $first..$last"
rm -rf $RUN

echo "######## $(date +%H:%M) part 3: replay of the same ledgers"
from=$((first + 300))  # past the catchup and the buffered ledgers it applies
target=$(( (last + 1) / 64 * 64 - 1 ))
count=$((target - from + 1))
echo "replay $target/$count (ledgers $from..$target)"
for _ in $(seq 1 120); do
    cur=$(curl -sf http://history.stellar.org/prd/core-live/core_live_001/.well-known/stellar-history.json |
          python3 -c 'import json, sys; print(json.load(sys.stdin)["currentLedger"])' 2>/dev/null || echo 0)
    [ "$cur" -ge "$target" ] && break
    sleep 30
done
echo "archive at $cur"
RUN=/ram/replay2
rm -rf $RUN; mkdir -p $RUN && cd $RUN
{ echo 'LOG_FILE_PATH="replay.log"'; cat $HOME/src/lab-runs/replay/stellar.cfg; } > stellar.cfg
$TBIN --conf stellar.cfg new-db > new-db.log 2>&1 || { echo "FAILED new-db"; tail -3 new-db.log; exit 1; }
start=$(date +%s.%N)
$TBIN --conf stellar.cfg catchup $target/$count --metadata-output-stream /dev/null > catchup.log 2>&1 & R=$!
guard $R & G=$!
wait $R; rc=$?; kill $G 2>/dev/null
end=$(date +%s.%N)
printf 'binary=%s\nrange=%s/%s\nwall_seconds=%s\nrc=%s\n' "$($TBIN version | head -n 1)" $target $count \
    "$(awk -v a=$start -v b=$end 'BEGIN{printf "%.3f", b-a}')" $rc > $KEEP/replay-time.txt
grep PipelineStudy replay.log > $KEEP/replay.log
cp stellar.cfg $KEEP/replay.cfg
tail -n 5 catchup.log > $KEEP/replay-catchup-tail.txt
rm -rf $RUN
echo "######## $(date +%H:%M) done, replay rc=$rc"
