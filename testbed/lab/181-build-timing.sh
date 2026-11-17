# Build upstream v30 (b8c4f12d6) with the per-ledger timing log of the mainnet replay, from a copy
# of the built upstream tree so the build is incremental.
set -e
cd ~/src
rm -rf stellar-core-timing
cp -a stellar-core-upstream stellar-core-timing
cd stellar-core-timing
git -c user.name=lab -c user.email=lab@localhost am ~/src/lab-runs/timing.patch
nice make -j14 > make-timing.out 2>&1
mkdir -p ~/src/bins/timing-v30
cp src/stellar-core ~/src/bins/timing-v30/stellar-core
grep -c PipelineStudy ~/src/bins/timing-v30/stellar-core
echo BUILD-DONE
