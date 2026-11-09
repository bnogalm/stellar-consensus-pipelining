# Helpers for the run scripts (core.sh, attack.sh, grid.sh). Source it, don't run it.
# The stellar-core binary is $BIN (see wan-nodes.sh); results go to ~/src/lab-runs/wan/<run>.
S="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RTT12="$S/rtt-12-orgs.tsv"
# Seven validators on the default RTT matrix, or twelve in four organizations
net7() { bash $S/wan-nodes.sh stop > /dev/null 2>&1; bash $S/wan-net.sh down; bash $S/wan-net.sh up > /dev/null; unset WAN_N WAN_RTT ORG_SIZE; }
net12() { bash $S/wan-nodes.sh stop > /dev/null 2>&1; bash $S/wan-net.sh down; bash $S/wan-net.sh up $RTT12 12 > /dev/null; export WAN_N=12 WAN_RTT=$RTT12; }
# Links with 10% jitter, 0.1% loss and 100 Mbit/s
links() { export WAN_JITTER_PCT=10 WAN_LOSS_PCT=0.1 WAN_RATE=100mbit; }
# Tx set size limit, 80,000 accounts, load submitted by the given (non-validating) nodes
bigw() { export KSWEEP_TXSET=$1 KSWEEP_ACCOUNTS=80000 LOADGEN_ACCOUNTS=80000 LOADGEN_NODES="$2" KSWEEP_RATE=6000; }
# Apply cost calibrated on mainnet: each ledger's apply is stretched to 1.25 ms per operation
mapply() { echo "bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING [1250] > /dev/null; bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING [1] > /dev/null;"; }
