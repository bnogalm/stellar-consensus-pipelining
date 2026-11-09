# k sweep: apply cost calibrated on mainnet (1,250 us per op), links with jitter, loss and
# 100 Mbit/s, load from 4 watchers, 200 ms target. 300 tx (3 runs) and 600 tx, 7 validators; 300 tx, 12.
. "$(dirname "$0")/common.sh"; links; export WAN_WATCHERS="1 2 3 4"; net7
for r in 1 2 3; do
  ( bigw 300 "8 9 10 11"; export KSWEEP_RATE=2000; KSWEEP_TAG=-cl-t300-r$r KSWEEP_BEFORE="$(mapply)" bash $S/ksweep.sh pay "1 2 3 4 5" 200 180 )
done
( bigw 600 "8 9 10 11"; export KSWEEP_RATE=2000; KSWEEP_TAG=-cl-t600 KSWEEP_BEFORE="$(mapply)" bash $S/ksweep.sh pay "1 2 3" 200 180 )
export WAN_WATCHERS="1 4 7 10"; net12
( bigw 300 "13 14 15 16"; export KSWEEP_RATE=2000; ORG_SIZE=3 KSWEEP_TAG=-cl-n12-t300 KSWEEP_BEFORE="$(mapply)" bash $S/ksweep.sh pay "1 2 3" 200 180 )
