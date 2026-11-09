# Target close time x k with the mainnet apply cost: 300 tx, links, watchers, 7 validators.
. "$(dirname "$0")/common.sh"; links; export WAN_WATCHERS="1 2 3 4"; net7
for L in 150 250 500; do
  ( bigw 300 "8 9 10 11"; export KSWEEP_RATE=2000; KSWEEP_TAG=-cl-grid-L$L KSWEEP_BEFORE="$(mapply)" bash $S/ksweep.sh pay "1 2 3 4 5 6" $L 180 )
done
