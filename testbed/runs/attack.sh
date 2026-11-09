# Targeted DoS on predicted leaders (each validator silent in round 1 of the slots
# where it has the top priority), same setup as core.sh (300 tx, 200 ms, mainnet apply cost), k = 1 and 2,
# with 1 leader per round, and with 2 leaders plus a 300 ms nomination timeout.
. "$(dirname "$0")/common.sh"; links; export WAN_WATCHERS="1 2 3 4"; net7
set_() { echo "bash $S/wan-nodes.sh set $1 $2 > /dev/null;"; }
ATK=$(set_ EXPERIMENTAL_TEST_DOS_TOP_LEADER true)
MIT="$(set_ EXPERIMENTAL_NOMINATION_LEADERS 2) $(set_ EXPERIMENTAL_NOMINATION_TIMEOUT_MS 300)"
run() { ( bigw 300 "8 9 10 11"; export KSWEEP_RATE=2000; KSWEEP_TAG=$1 KSWEEP_BEFORE="$(mapply) $2" bash $S/ksweep.sh pay "1 2" 200 180 ); }
run -cl-atk "$ATK"
run -cl-atk-mit "$ATK $MIT"
run -cl-mit "$MIT"
