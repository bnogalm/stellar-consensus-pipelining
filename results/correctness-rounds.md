# Correctness rounds: the prototype under load, restarts and upgrades

Date: 2026-11-15 and 16. Does the network stay in agreement and alive when the rules are exercised together? The prototype (the branch `live-pipelining`) ran 31 rounds of ten minutes on the WAN testbed: a mix of every transaction type, restarts of one or every validator, protocol and network upgrades, and changes of k, all under load.

**Result.** In the 31 rounds:
- no node stopped;
- every validator published the same checkpoints;
- no invariant failed, and no transaction entered a ledger of the wrong class;
- none of the log lines listed below appeared;
- every restarted validator ended on the last ledger of the network.

Throughput is in [throughput-current.md](throughput-current.md).

## Testbed and load

- **Network:** the WAN testbed of [testbed-results.md](testbed-results.md): seven validators with inter-region delays, 10 % jitter and 0.1 % loss on the links, and four watcher nodes that generate the load. Protocol 30.
- **Timing:** a target close time of 200 ms, or 1,000 ms in the protocol upgrade rounds (see below). k is set by a network upgrade during the genesis phase.
- **Load:** 600 tx/s offered for 600 s, from the four watchers, with transactions of every kind:
  - all classic operations, including offers, path payments, claimable balances, liquidity pools, sponsorship, clawback and trustline flags;
  - fee bumps, and operations whose source is not the payer;
  - Soroban: SAC transfers of XLM and of an issued asset, an OpenZeppelin token, and Soroswap swaps.

  The setup creates 20,000 users first.
- **Per round:** k = 2, 3, 4 and 5 (the k-change rounds start at the k given).

## Checks in every round

- **Nodes:** every node process, validators and watchers, is alive at the end.
- **Logs:** none of these anywhere:
  - an assertion failure, an exception, or `moved to a bad state`;
  - an invariant failure;
  - a transaction of the wrong class in a ledger;
  - `processing a future message while tracking`;
  - a tx set or ledger state judged invalid by one validator and valid by others (`considers invalid`, `locally-invalid`, `Inconsistent txSet validity`);
  - a stored state that does not match its buckets.
- **History:** every validator publishes the same ledger, transaction and result files for every checkpoint of the run.
- **Restarted validators:** they end on the last ledger of the network.

## Rounds

What was exercised in each series, and how it ended. The last column is the name of its rounds in [data/correctness/](data/correctness/):

| Series | k | Ledgers | Checkpoints identical | Restarted validators | Data |
| --- | --- | --- | --- | --- | --- |
| Every validator killed (SIGKILL) under load, restarted 20 s later | 2, 3, 4, 5 | 1,138 to 2,318 per round | 30, 43, 53, 60 | all seven, without catchup | `kill-` |
| Every validator stopped cleanly (SIGTERM) under load, restarted 20 s later | 2, 3, 4, 5 | 1,131 to 2,325 | 30, 43, 54, 61 | all seven, without catchup | `stop-` |
| Protocol upgrade 29 → 30 under load (1 s ledgers), one validator restarted | 2, 3, 4, 5 | about 590 | 14, 14, 15, 15 | rejoined, one or two catchups | `ver-` |
| Change of k under load, one validator restarted | 2 → 3, 3 → 1, 1 → 3 | 1,437, 918, 1,215 | 35, 31, 27 | rejoined | `k2to3-`, `k3to1-`, `k1to3-` |
| Base fee and tx set size upgrade under load, one validator restarted (three times) | 2, 3, 4, 5 | 1,115 to 2,320 | all | rejoined in 12 of 12 | `g1-`, `g2-`, `g3-` |
| The same with every invariant checked | 2, 3, 4, 5 | 1,150 to 2,196 | 31, 42, 52, 59 | rejoined in 4 of 4 | `inv-` |

Two notes on the rounds:

- **The protocol upgrade rounds use 1 s ledgers** because protocol 29 close times are whole seconds. With 200 ms ledgers each ledger moves the close time 1 s forward, it is 60 s ahead of the clock after about 75 ledgers, and every node stops nominating, as upstream would. Protocol 30 has millisecond close times.
- **One other line is counted:** `Lost track of consensus`. The restarted validator logs it while it is behind, in 22 of the 23 rounds that restart a single validator.

## Unit tests

The suites `[pipelining]`, `[herder]`, `[history]`, `[catchup]`, `[config]` and `[scp]` pass: 214 test cases. The pipelining tests cover each rule on its own:
- the base and the class of a tx set;
- the fee reserve;
- close times;
- a change of k, with its catchup;
- restarts with slots in consensus;
- an online catchup across a change of k;
- empty-tx-set values across a protocol upgrade.

## Data

[data/correctness/](data/correctness/) has, for each round:
- `checks.txt`: the checks above and the restarted validators;
- `results.txt`: the transactions by kind, queued, rejected, applied and successful;
- `summary.txt`: the stage times per validator.

The round script is [testbed/full-round.sh](../testbed/full-round.sh).

## Limits

- **Size and duration:** seven validators, and rounds of ten minutes. No run of days.
- **Disk:** the validators do not have a disk each, and the testbed keeps node data in RAM by default (`testbed/README.md`). The cost of what is persisted with each ledger was not measured on real disks, and killing every validator tests the restart logic, not what survives a power cut.
- **Adversaries:** every validator is honest. The rules against a faulty proposer (a tx set built on the wrong ledger, an empty-tx-set value built before a protocol upgrade, out-of-order close times) are covered by unit tests, not by WAN rounds.
