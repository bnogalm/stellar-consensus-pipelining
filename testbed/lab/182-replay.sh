# Mainnet replay of ledgers 65245040..65255039 (the same 10,000 as the desktop replay in
# results/mainnet-steps.md) with upstream v30 plus the per-ledger timing log, everything in RAM:
# apply time per ledger against its size, on a fast machine with mainnet's real mix.
set -uo pipefail
BIN=$HOME/src/bins/timing-v30/stellar-core
RUN=/ram/replay
KEEP=$HOME/src/lab-runs/replay
mkdir -p $RUN && cd $RUN
cp $KEEP/stellar.cfg stellar.cfg
rm -rf stellar.db buckets
$BIN --conf stellar.cfg new-db > catchup.log 2>&1
start=$(date +%s.%N); rc=0
( while sleep 10; do [ $(df --output=avail -k /ram | tail -1) -lt 2000000 ] && { echo RAM-FULL-STOP; pkill -u "$USER" -f "^$BIN --conf stellar.cfg catchup"; break; }; done ) & G=$!
$BIN --conf stellar.cfg catchup 65255039/10000 --metadata-output-stream /dev/null >> catchup.log 2>&1 || rc=$?
kill $G 2>/dev/null; end=$(date +%s.%N)
printf 'binary=%s\nrange=65255039/10000\nwall_seconds=%s\nrc=%s\n' "$($BIN version | head -n 1)" \
    "$(awk -v a=$start -v b=$end 'BEGIN{printf "%.3f", b-a}')" $rc > time.txt
cp time.txt catchup.log stellar.cfg $KEEP/
ls stellar-core*.log 2>/dev/null | head -1 | xargs -r -I{} cp {} $KEEP/node.log
du -sh $RUN > $KEEP/ram-used.txt
rm -rf $RUN/buckets $RUN/stellar.db
echo REPLAY-DONE rc=$rc
