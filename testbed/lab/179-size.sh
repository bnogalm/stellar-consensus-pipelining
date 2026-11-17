# When does pipelining beat the overlap of consensus with apply? Consensus time against ledger
# size (k = 1), and pipelining (k = 2, 4), for three apply speeds: 1,250 us per operation (the
# mainnet replay), 350 us (a fast mainnet node: 149 ms for 430 transactions) and none.
. ~/src/lab-runs/night/common.sh; links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$HOME/src/bins/d7d21471c/stellar-core
applyset() { # $1 us per operation, 0 for none
    if [ "$1" = 0 ]; then
        echo "true"
    else
        echo "bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING [$1] > /dev/null; bash $S/wan-nodes.sh set OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING [1] > /dev/null;"
    fi
}
for a in 1250 350 0; do
    for n in 300 1000 3000; do
        echo "######## $(date +%H:%M) apply $a us, $n per ledger"
        ( bigw $n "8 9 10 11"; export KSWEEP_RATE=6000
          KSWEEP_TAG=-sz-a$a-n$n KSWEEP_K_UPGRADE=1 KSWEEP_BEFORE="$(applyset $a)" \
              bash $S/ksweep.sh pay "1 2 4" 100 180 )
    done
done
echo "######## $(date +%H:%M) done"
