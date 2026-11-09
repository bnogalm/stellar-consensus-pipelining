# Pipelining Stellar consensus: k ledgers in consensus at once

Validators could run consensus on several ledgers at the same time, k of them, each one built on
ledger N−k, so that the time spent waiting for messages between continents is used for the next
ledgers. This repository has the measurements, a draft CAP and the testbed. The prototype is the
branch `live-pipelining` of https://github.com/bnogalm/stellar-core (one commit on stellar-core
v30, behind the option `EXPERIMENTAL_LIVE_PIPELINE_DEPTH`).

## Where the idea comes from

I have worked on real-time simulators, and among other things I redesigned the core that runs the
models distributed: physics, inputs and outputs run on several machines and have to stay in sync
and refresh with the right data. Some models took 20–30 ms and we needed to run at 100–200 Hz. We
did it with pipelining: start the next cycle before the previous one has finished, and make each
model wait only for the data it reads, so models that don't read each other, like the electrics
and the hydraulics of a train, also run at the same time. An example from a train simulator (the
numbers are only an example, and there were many more models):

![Train simulator, one cycle after another](results/figures/simulator-sequential.png)

![Train simulator with pipelining: the next cycle starts before the previous one ends, and the electrics and the hydraulics run at the same time](results/figures/simulator-pipelined.png)

Each result took about as long as before, still below what a person can react to, but there were
many more of them per second, so the simulator reacted sooner and ran more smoothly.

A Stellar validator works like the simulator before that change: it starts nominating ledger N
only after applying N−1, and most of the ledger interval is spent waiting for messages between
continents. Running consensus on the next ledgers during that wait is the same idea.

## Main results

On a WAN testbed of seven validators on four continents, with an apply cost taken from mainnet
(1.25 ms per transaction), 300 transactions per ledger, against the same network without
pipelining:

| k | Ledger interval | Throughput | Median latency |
|---|---|---|---|
| 1 (today) | 1,093 ms | 273 tx/s | 1.30 s |
| 2 | 572 ms | 520 tx/s (1.90×) | 1.41 s (+8%) |
| 3 | 427 ms | 697 tx/s (2.55×) | 1.54 s (+18%) |
| 4 | 390 ms | 762 tx/s (2.79×) | 1.73 s (+32%) |

With twelve validators in four organizations: 1.92× at k = 2 and 2.66× at k = 3.

![Throughput against k, with the 800 tx/s ceiling set by apply](results/figures/testbed-gain.png)

The ledger cycle on one validator, the same 5 s of each run
([ledger-gantt.md](results/ledger-gantt.md)):

![Today, k = 1](results/figures/gantt-k1.png)

*Today: each ledger starts when the previous one has been applied, a ledger about every 1.1 s.*

![k = 2](results/figures/gantt-k2.png)

*k = 2: two ledgers in consensus at once, and apply overlaps the next one's consensus. A ledger
about every 570 ms.*

![k = 3](results/figures/gantt-k3.png)

*k = 3: ledgers come about as fast as one apply, so some wait to be applied (queue).*

Apply is sequential and sets the ceiling: at 1.25 ms per transaction, about 800 tx/s, whatever k
is. On mainnet, consensus takes about 0.54 s (median, from a watcher node), so against SDF's
planned overlap of consensus and apply, k = 2 would add between 1.15× and 1.55×, and k = 3 between 1.37× and 2.3×, depending on how
fast validators apply.

## What's here

The measurements are in [testbed-results.md](results/testbed-results.md): the k sweep, the target
close time, bigger ledgers and a DoS on the predictable leaders.
[ledger-gantt.md](results/ledger-gantt.md) shows the ledger cycle stage by stage, and
[mainnet-steps.md](results/mainnet-steps.md) has the apply and consensus times measured on
mainnet, which the comparison above is based on.

How it would work as a protocol change is in the
[draft CAP](design/cap-draft-live-pipelining.md), and what it means for safety, liveness and
abuse in the [threat review](design/live-pipelining-threats.md). [testbed/](testbed/) has the
scripts that produced the results, and why the testbed is set up this way.

## Data

`results/data/testbed/` has the summary of every run (per-ledger stage times, throughput,
latency) and the node logs used for the Gantt charts; `results/data/mainnet-watch/` has the
watcher node's logs. `tools/` has the scripts that turn them into the tables and charts.

## License

The text, data and figures are under CC BY 4.0 (see [LICENSE](LICENSE)). The prototype code is
under Apache-2.0, like stellar-core.
