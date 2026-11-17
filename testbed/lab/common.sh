S=~/src/stellar-pipelining-study/scripts/wan
RTT12=~/src/stellar-pipelining-study/testbed/rtt-12-orgs.tsv
net7() { bash $S/wan-nodes.sh stop > /dev/null 2>&1; bash $S/wan-net.sh down; bash $S/wan-net.sh up > /dev/null; unset WAN_N WAN_RTT ORG_SIZE; }
net12() { bash $S/wan-nodes.sh stop > /dev/null 2>&1; bash $S/wan-net.sh down; bash $S/wan-net.sh up $RTT12 12 > /dev/null; export WAN_N=12 WAN_RTT=$RTT12; }
setq() { echo "bash $S/wan-nodes.sh set TRANSACTION_QUEUE_SIZE_MULTIPLIER_FOR_TESTING $1 > /dev/null"; }
setf() { echo "bash $S/wan-nodes.sh set FLOOD_OP_RATE_PER_LEDGER $1 > /dev/null"; }
links() { export WAN_JITTER_PCT=10 WAN_LOSS_PCT=0.1 WAN_RATE=100mbit; }
big() { export KSWEEP_TXSET=$1 KSWEEP_ACCOUNTS=80000 LOADGEN_ACCOUNTS=80000 LOADGEN_NODES="1 2 3 4" KSWEEP_RATE=6000; }
bigw() { export KSWEEP_TXSET=$1 KSWEEP_ACCOUNTS=80000 LOADGEN_ACCOUNTS=80000 LOADGEN_NODES="$2" KSWEEP_RATE=6000; }
mapply() { echo "bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING [1250] > /dev/null; bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING [1] > /dev/null;"; }
