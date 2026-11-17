# 180 again for the two largest sizes. The load generator refuses a rate that needs more than a
# third of its accounts in one ledger, so the offered rate is set from the size: 1.3 n / T.
. ~/src/lab-runs/night/common.sh; links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$HOME/src/bins/d7d21471c/stellar-core
for p in "6000 5000" "10000 8000"; do
    set -- $p
    echo "######## $(date +%H:%M) real apply, $1 per ledger, target $2 ms"
    ( bigw $1 "8 9 10 11"; export KSWEEP_RATE=$(( 13 * $1 * 100 / $2 ))
      KSWEEP_TAG=-ap-n$1 KSWEEP_K_UPGRADE=1 bash $S/ksweep.sh pay "1" $2 240 )
done
bash $S/wan-nodes.sh stop > /dev/null 2>&1
echo "######## $(date +%H:%M) done"
