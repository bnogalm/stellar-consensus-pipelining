# Testbed

The scripts that produced the results in `results/`. They run every node of a network on one
Linux machine, each in its own network namespace, with `netem` delays between them.

## What you need

- Linux with `ip` and `tc` (iproute2), and `sudo` for those two commands only.
- A build of the prototype (branch `live-pipelining` of https://github.com/bnogalm/stellar-core),
  with tests enabled (the default; the load generator needs them). `BIN` points to it; the
  default is `$HOME/src/stellar-core-pipeline/src/stellar-core`.
- Node data goes to `/ram/wan` (`WAN_DIR`), a tmpfs, so the disk is not part of the
  measurement.

## Scripts

| Script | What it does |
|---|---|
| `wan-net.sh` | Creates one namespace per node and the delays between them from an RTT matrix (`rtt-7.tsv`, `rtt-12-orgs.tsv`), with optional jitter, loss and rate (`WAN_JITTER_PCT`, `WAN_LOSS_PCT`, `WAN_RATE`) |
| `wan-nodes.sh` | Creates the validators and watchers (configs, databases, quorum sets), starts and stops them, and sets config options on all of them |
| `wan-sweep.sh` | Runs the load for one point and keeps the timing lines of every node |
| `ksweep.sh` | One point per k: a fresh network, upgrades with 5 s ledgers, then the rules switched at a ledger boundary (restart with the target close time and `EXPERIMENTAL_LIVE_PIPELINE_DEPTH`), and the load |
| `wan-analyze.py` | Per-ledger timeline from the logs: wait, consensus, queue, apply, completion, interval, throughput and transaction latency |
| `cpu-threads.sh` | Host CPU use during a run |
| `runs/core.sh`, `runs/attack.sh`, `runs/grid.sh` | The runs in the reports (k sweep, leader DoS, target × k) |

## Why it is set up this way

- **One machine.** Runs are repeatable, and all nodes share one clock, so a ledger can be followed
  across nodes. The cost: all nodes share 8 physical cores (host CPU at most 71% in the published runs).
- **Load from non-validating nodes, above capacity** (2,000 tx/s offered). The numbers are the
  network's capacity, and the validators don't spend time generating load.
- **Apply cost from mainnet.** The disk is in RAM and payments are cheap, so apply would be almost
  free. stellar-core's testing options `OP_APPLY_SLEEP_TIME_DURATION_FOR_TESTING=[1250]` and
  `OP_APPLY_SLEEP_TIME_WEIGHT_FOR_TESTING=[1]` stretch each ledger's apply to 1.25 ms per
  operation, the average cost per transaction of a replay of 10,000 mainnet ledgers. It is a
  sleep, so it doesn't compete for CPU.
- **`EXPERIMENTAL_TRIGGER_NO_DRIFT_FALLBACK`.** With a target shorter than consensus, stellar-core
  would take the late externalize as clock drift and fall back to a different trigger time. The
  node clocks agree here (one machine), so the fallback is turned off in every run, with and
  without pipelining.
- **Switching rules at a ledger boundary.** Pipelining changes which values are valid, so it is
  switched on with all nodes stopped right after a ledger closes, when no ledger is in consensus.
