# Build the prototype (fix branch, same core as bins/d7d21471c) with tx set fetch/arrival/validation/build logs.
set -euo pipefail
cd ~/src
[ -d stellar-core-txsetlog ] || cp -a stellar-core-fix stellar-core-txsetlog
cd stellar-core-txsetlog
git status --short | grep -v '^??' && { echo DIRTY; exit 1; } || true
python3 ~/src/lab-runs/txsetlog_edit.py
git diff --stat
git diff > ~/src/lab-runs/txsetlog.diff
nice make -j14 > make.out 2>&1 || { tail -30 make.out; exit 1; }
mkdir -p ~/src/bins/txsetlog-$(git rev-parse --short=9 HEAD)
cp src/stellar-core ~/src/bins/txsetlog-$(git rev-parse --short=9 HEAD)/
echo BUILD-DONE
