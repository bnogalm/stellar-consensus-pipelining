# One run with the SCP and Herder logs at debug level on every validator, to see what the slots
# that take about 1.37 s are (4 to 10 % of them at every k). k = 1, ledgers of 1,000, 650 tx/s
# mixed load, default flooding, as the first point of 227. The level is set once the load runs
# (a restart puts it back), and the whole node logs are kept, compressed.
. ~/src/lab-runs/night/common.sh; links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$HOME/src/bins/latency-client/stellar-core
K=${TRACE_K:-1}; N=${TRACE_N:-1000}; TARGET=${TRACE_TARGET:-100}
before="bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING [350] > /dev/null; bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING [1] > /dev/null;"
( for wait in 170 60; do
      sleep $wait
      for i in 1 2 3 4 5 6 7; do
          for part in SCP Herder; do
              bash $S/wan-nodes.sh http $i "ll?level=debug&partition=$part" > /dev/null 2>&1
          done
      done
      echo "$(date +%H:%M:%S) log level set"
  done ) &
( export KSWEEP_TXSET=$N KSWEEP_ACCOUNTS=80000 LOADGEN_ACCOUNTS=80000 LOADGEN_NODES="1 2 3 4" KSWEEP_RATE=650
  export LOADGEN_FIRST_RATE=65 LOADGEN_FIRST_EXTRA=""
  KSWEEP_TAG=-scptrace KSWEEP_K_UPGRADE=1 KSWEEP_BEFORE="$before" KSWEEP_PAY_EXTRA="&stepms=2" \
      bash $S/ksweep.sh pay "$K" "$TARGET" 240 ) 2>&1 | grep -E "crashes|rejected|did not apply|not in sync"
wait
d=~/src/lab-runs/wan/ksw-pay-k$K-scptrace/s1-c$TARGET
echo "RUN: $(grep -E "^ledgers|host cpu" $d/summary.txt | tr '\n' ' ' | cut -c1-200)"
mkdir -p $d/full
for i in 1 2 3 4 5 6 7; do gzip -c /ram/wan/n$i/node.log > $d/full/n$i.log.gz; done
ls -la $d/full | tail -7
bash $S/wan-nodes.sh stop > /dev/null 2>&1
echo "TRACE-DONE"
