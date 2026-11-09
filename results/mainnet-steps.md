# Step times on mainnet: apply and consensus

The testbed results are only useful if each step of the ledger cycle has a realistic size. This
report gives the two that come from mainnet: how long a validator takes to apply and commit a
ledger, and how long consensus takes.

## Apply and commit: replay of 10,000 ledgers

Catchup of mainnet ledgers 65244992 to 65255039 (10,048 ledgers, 3,154,626 transactions, about
14 hours of network time) with stellar-core v30.0.0 plus timing logs, on a desktop (WSL2, 16
vCPUs, 8 GB of RAM, SSD). The first 32 ledgers are left out as warm-up.

| Per ledger (ms) | Mean | p50 | p99 | Max |
|---|---|---|---|---|
| Apply and commit (whole `applyLedger`) | 402 | 394 | 839 | 1,673 |
| of which transaction execution (fees and operations) | 268 | 262 | 595 | 1,085 |
| of which seal (bucket list, Soroban state) | 44 | 24 | 155 | 1,066 |
| of which meta | 26 | 26 | 53 | 178 |
| of which commit (SQL, checkpoint files) | 43 | 22 | 173 | 271 |

With 314 transactions per ledger on average, apply and commit cost about **1.25 ms per
transaction**. That is an average over mainnet's mix of payments, DEX and Soroban transactions,
not a cost model: a Soroban-heavy ledger costs more, a payments-only ledger less. A single thread
was busy during apply.

The testbed uses this number: with stellar-core's testing options
`OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING=[1250]` and `OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING=[1]`,
each ledger's apply is stretched with a sleep to 1.25 ms per operation. Its load is one-operation
payments, so per operation and per transaction are the same there.

## Consensus: a watcher node

2026-11-08, 22:30 to 23:01 CET, ledgers 65377485 to 65377847 (363 ledgers). A non-validating node
(the prototype with pipelining off) synced to mainnet on a Ryzen 7 5800X with its database and
buckets in RAM, at the lowest CPU and IO priority, with Herder logging at TRACE for 30 minutes.
Its quorum set is SDF's three validators, so "externalize" is when this node sees them
externalize. Script: `tools/mainnet-consensus.py`; data: [data/mainnet-watch](data/mainnet-watch).

| Per ledger | Mean | p10 | p50 | p90 | p99 |
|---|---|---|---|---|---|
| Interval, externalize to externalize (ms) | 4,998 | 4,598 | 4,901 | 5,691 | 6,372 |
| Previous externalize to first nomination seen (ms) | 4,377 | 3,965 | 4,364 | 5,064 | 5,442 |
| Consensus: first nomination seen to externalize (ms) | 621 | 428 | 541 | 886 | 1,756 |
| of which nomination: first NOMINATE to first PREPARE (ms) | 344 | 198 | 308 | 467 | 1,225 |
| of which ballot: first PREPARE to externalize (ms) | 277 | 196 | 221 | 440 | 1,093 |
| Apply and commit on the watcher (ms) | 149 | 100 | 149 | 192 | 263 |
| Transactions per ledger | 430 | 197 | 357 | 732 | 844 |
| Operations per ledger | 850 | 564 | 851 | 1,074 | 1,297 |

- Consensus takes about 0.5–0.6 s, and over 1.7 s for 1% of ledgers.
- About 4.4 s of each 5 s interval is the wait for the next ledger's timer.
- Apply and commit took 149 ms (p50) on this machine, with everything in RAM, against 394 ms in
  the replay above. Validators' hardware and disks vary, so E on mainnet is somewhere around
  150–400 ms for today's ledgers.

Limits:

- Times are as seen from one node in Spain. "First nomination seen" is later than the first
  nomination by the network delay from it, and externalize is seen late by a similar amount, so
  the consensus time is roughly right, but not exact.
- The node trusts only SDF's validators.
- One half-hour on a Sunday evening.

## What it means for pipelining

With C ≈ 541 ms, S ≈ 5 ms and E between 149 and 394 ms, the rule
`interval ≈ max((C + E + S) / k, E)` gives these estimates, against SDF's planned overlap of
consensus and apply, whose interval would be about max(C, E) ≈ 541 ms. They come from the formula,
not from runs on mainnet:

| | E = 149 ms (fast machine, RAM) | E = 394 ms (desktop, SSD) |
|---|---|---|
| Today (C + E + S) | 695 ms | 940 ms |
| Overlap of consensus and apply, max(C, E) | 541 ms | 541 ms |
| k = 2 | 348 ms (1.55× the overlap) | 470 ms (1.15×) |
| k = 3 | 232 ms (2.3×) | 394 ms, apply-bound (1.37×) |

The gain over the overlap depends mostly on how fast validators apply: with apply at a quarter of
consensus, k = 2 and 3 would give 1.5–2.3×; with apply close to consensus, little. On the testbed,
C/E is about 1.9 at 300 transactions; on mainnet it is about 1.4–3.6.
