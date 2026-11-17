# Apply and consensus time against ledger size, beyond what the size sweep (179) could fill:
# k = 1, real apply (no sleep), payments, with a target close time long enough for the load
# generators to fill each ledger. Answers: is apply proportional to ledger size, or a fixed part
# per ledger plus a smaller cost per transaction; and how consensus grows with the tx set.
. ~/src/lab-runs/night/common.sh; links; export WAN_WATCHERS="1 2 3 4"; net7
export BIN=$HOME/src/bins/d7d21471c/stellar-core
for p in "1000 2000" "3000 3000" "6000 5000" "10000 8000"; do
    set -- $p
    echo "######## $(date +%H:%M) real apply, $1 per ledger, target $2 ms"
    ( bigw $1 "8 9 10 11"
      KSWEEP_TAG=-ap-n$1 KSWEEP_K_UPGRADE=1 bash $S/ksweep.sh pay "1" $2 240 )
done
bash $S/wan-nodes.sh stop > /dev/null 2>&1
echo "######## $(date +%H:%M) done"
