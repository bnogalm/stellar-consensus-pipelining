# Round launchers on the lab machine

The scripts that ran the size and apply measurements of 2026-11-16 and 17, as they ran on the lab
machine (Ryzen 7 5800X, 78 GB RAM, a 48 GB ramdisk at `/ram`). They expect this repository at
`~/src/stellar-pipelining-study`, `common.sh` at `~/src/lab-runs/night/common.sh`, and the
binaries under `~/src/bins/`.

| Script | What it ran | Results |
|---|---|---|
| `179-size.sh` | Ledger size 300, 1,000, 3,000 at k = 1, 2, 4, three apply speeds | [when-pipelining-pays.md](../../results/when-pipelining-pays.md), [data/size-sweep](../../results/data/size-sweep) |
| `180-apply-size.sh`, `180c-apply-size.sh` | k = 1, real apply, 1,000 to 10,000 transactions per ledger (180c: the two largest, with the offered rate sized to the generators' accounts) | [apply-and-consensus-by-size.md](../../results/apply-and-consensus-by-size.md), `ksw-pay-k1-ap-n*` |
| `181-build-timing.sh` | Upstream v30 with the per-ledger timing lines | `timing.diff` (the script applies it as `timing.patch`) |
| `182-replay.sh` | Replay of 10,000 mainnet ledgers in RAM | the same report, `lab-replay-study.log.gz` |
| `183-build.sh`, `txsetlog_edit.py` | The prototype with the tx set timing lines | `txsetlog.diff` |
| `184-txset-live-replay.sh` | The 180 sizes with the tx set timings; then a mainnet watcher live and a replay of the same ledgers | `ksw-pay-k1-tx-n*`, `live-replay/` |
