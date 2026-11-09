# CAP draft: Pipelined consensus (k ledgers in consensus at once)

```
CAP: (unassigned)
Title: Pipelined consensus: k ledgers in consensus at once
Working Group:
    Owner: Benjamín Nogal Muñoz
    Authors: Benjamín Nogal Muñoz
Status: Draft (not submitted)
Created: 2026-11-05
Discussion: (none yet)
Protocol version: (next)
```

## Simple summary

Let validators start nominating ledger N before ledger N−1 has externalized, so that up to k
ledgers are in consensus at once. When consensus across continents takes longer than the target
close time, ledgers can then close at the target while the latency of each ledger stays the same.

## Working group

To be formed. This draft summarizes tests on a WAN testbed of seven and twelve validators with a
prototype of stellar-core; it is meant to start that discussion.

## Motivation

A ledger's cycle is: nomination and ballot protocol (consensus, C), then apply (E), then
completion (S). Today a validator nominates N only after it has applied N−1, because the tx set
of N names N−1's hash and is validated against N−1's state. The time between ledgers therefore
cannot be less than C + E + S, whatever the target close time is.

With validators on several continents, C is likely to dominate:

- **Consensus time.** On the seven-validator testbed (round trips of 12–325 ms), C is about
  0.7 s, and about 1.05 s with twelve validators in organizations spread over three continents.
  Apply and commit of mainnet ledgers take about 1.25 ms per transaction (394 ms p50 for about
  314 transactions in a replay; [mainnet-steps.md](../results/mainnet-steps.md)).
- **Lowering the target close time** (CAP-0070's `ledgerTargetCloseTimeMilliseconds`) cannot
  help once it is below C + E + S.
- **Pipelining consensus with apply,** as SDF has described (voting on N+1 while applying N),
  lowers the floor to max(C, E). With validators on several continents that is still C. This
  proposal is meant to work on top of it.

Pipelining consensus removes that floor. With k ledgers in consensus, the interval becomes
max(L, (C + E + S) / k, E): apply stays sequential and is the final limit. Measured on the
testbed with the mainnet apply cost, 300-transaction ledgers, against k = 1 at the same target
([testbed-results.md](../results/testbed-results.md); three runs per point for seven validators):

| Network | Target | k | Throughput | Median transaction latency |
|---|---|---|---|---|
| 7 validators | 200 ms | 2 | 1.90× | +8% |
| 7 validators | 200 ms | 3 | 2.55× | +18% |
| 12 validators in organizations | 200 ms | 2 | 1.92× | +5% |
| 12 validators in organizations | 200 ms | 3 | 2.66× | +12% |

From k = 4 the interval stays near the apply time and only latency grows. Doubling the ledger
size without pipelining gave 1.47× for 17% more latency, because apply also doubles and adds to
the interval. With consensus and apply overlapped (not measured), the estimate at 300
transactions is about 420 tx/s against 520 with k = 2, and a bigger ledger would get close to the
same
ceiling, so pipelining is of most interest where consensus is much longer than apply. On mainnet,
consensus took about 541 ms (median) from a watcher node
([mainnet-steps.md](../results/mainnet-steps.md)); with apply
between 149 and 394 ms, the formula gives k = 2 about 1.15–1.55× the overlap and k = 3 about
1.37–2.3×.

### Goals alignment

Higher throughput and shorter time between ledgers, without changing the trust model of SCP or
the ledger format seen by downstream systems (history, meta, Horizon): ledgers are still applied
one at a time, in order, with the usual header chain.

## Abstract

A new network setting gives the pipeline depth k (k = 1 is today's protocol). From the protocol
version that introduces it:

1. Nomination of N starts one target close time after nomination of N−1, as soon as N−k has
   applied, even if N−1 and older slots are still in consensus.
2. The tx set of N names the hash of ledger N−k as its previous ledger, and is validated against
   the state of N−k.
3. Every transaction belongs to the class of the account that pays its fee (a hash of the
   account key, modulo k). Ledger N only contains transactions of class N mod k.
4. Leader election for N uses the value of N−k.
5. The effective close time of N is the later of its value's close time and N−1's plus one step.
6. Ledgers are applied in order; a ledger that externalizes before its predecessor waits for it.
7. Only ledgers that are a multiple of k may carry upgrades; the k − 1 ledgers after one apply
   empty, and values of slots in consensus across a protocol upgrade are checked under the
   protocol they were nominated with.

## Specification

### Network setting

`ledgerPipelineDepth` (uint32, default 1), in the SCP timing config setting alongside
`ledgerTargetCloseTimeMilliseconds`. Raising or lowering it takes effect at a ledger boundary
(see Protocol upgrade transition). Values above a small bound (for example 4) are rejected.

The depth should be set with the target close time, as the smallest k with
k × target ≥ consensus + apply. A larger k adds transaction latency and no throughput: on the
testbed, k = 2 at a 1 s target added 36% median latency for no gain, and at a 500 ms target the
gain stopped at about 2.2× from k = 3 while latency kept growing. Whether the protocol should
derive k from the target and a measured consensus time, or leave both to the network config
vote, is open.

### Tx set base

- For ledger N with depth k ≥ 2, `GeneralizedTransactionSet.v1TxSet.previousLedgerHash` is the
  hash of ledger N−k.
- A validator considers a value for N only once it has applied N−k, and rejects a tx set with any
  other base.
- Validity of the tx set, including each transaction's validity, is evaluated against the
  ledger state at N−k and the ledger header of N−k, whatever ledger the validator has applied
  since.
- At apply, ledger N is built on N−1 as today: its header's `previousLedgerHash` is N−1's hash,
  and the tx set's base is checked to be N−k.

### Transaction class

- The class of a transaction is c(payer) = H(payer key ‖ salt) mod k:
  - the payer is the fee source (the outer source of a fee-bump, otherwise the transaction
    source);
  - the salt is constant (see Design rationale for why it must not change from ledger to
    ledger).
- A tx set for ledger N is invalid if it contains a transaction whose class is not N mod k.
- Accounts other than the payer (the inner source of a fee-bump, operation sources, destinations,
  Soroban footprints) are not restricted. A transaction that conflicts at apply with a
  transaction of another open slot fails as today (bad sequence number, underfunded, footprint
  conflict), and its payer is charged its fee.

### Nomination

- Leader priorities for slot N are computed with the value of N−k, as applied (with its
  effective close time), as the previous value.
- A validator nominates N when both hold:
  - one target close time has passed since it nominated N−1;
  - it has applied N−k.
- The close time a validator proposes for N must be later than N−k's close time, and within the
  usual bounds into the future.
- Validators process SCP messages for slots up to their LCL + k, and run nomination and ballot
  timers for all open slots.
- Nomination of N is not stopped when an older slot externalizes.
- Recommended with k ≥ 2 (see Security concerns):
  - several leaders per nomination round (the m highest priorities);
  - in a later version, secret leader priority with a VRF.

### Apply and close time

- Externalized ledgers are applied in ledger order.
- The effective close time of N is max(closeTime(value of N), effectiveCloseTime(N−1) + 1 ms).
  Everything that reads the ledger close time uses the effective one: time bounds, Soroban
  timestamps, upgrade scheduling.
- The value, and its signature, are stored unchanged.
- A transaction's time bounds are checked at nomination against the proposed close time, and at
  apply against the effective close time. A transaction near its `maxTime` can therefore fail at
  apply, and its payer is charged, as today when a ledger closes later than expected.

### Upgrades

Measured on the testbed: a network config upgrade during a k = 3 run works with rules 1 and 2. A
protocol upgrade (29 → 30) with rules 1 and 2 applied, but the network stalled right after,
which rule 3 addresses.

1. **Upgrade slots.** Only a ledger whose number is a multiple of k may carry ledger upgrades
   (protocol version, base fee, base reserve, tx set size, flags, network config). Validators
   reject values with upgrades in other slots. Otherwise the slots already in consensus all
   carry the same armed upgrade and it is applied more than once, which is invalid for a protocol
   version change.
2. **Drain.** The k − 1 ledgers after a ledger that applied an upgrade apply with an empty tx
   set. Their tx sets were validated under the rules before the upgrade; their transactions stay
   queued for later ledgers. Every node knows the upgrade ledger when it applies them, so this
   is deterministic.
3. **Value format across a protocol upgrade** (not prototyped). The SCP value of the slots
   already in consensus when a protocol upgrade applies was built under the old protocol, and
   protocols can change the value format (protocol 30 adds millisecond close times). Values for
   ledgers N+1 … N+k−1 after a protocol upgrade in N must be checked, and applied, under the
   protocol version of their base ledger, not the LCL's.

### History and catchup

Archived tx sets name ledger N−k as their previous ledger from the activation ledger on, while
headers still chain one by one. Catchup, archive verification and any tool that checks a tx set
against the previous header must accept the N−k base after activation.

### Transaction queue

Nodes keep queued transactions for about k times as many ledgers, and size their queues k times
larger. These are node policy, not protocol.

## Design rationale

**Why a fixed base (N−k), not "any recent ledger".** With a flexible base, a leader can build on a
ledger some validators have not applied yet. They cannot check the value, and SCP leaves them
silent in that slot. On the testbed this caused intermittent stalls at start-up with k = 4. A
fixed base is one that every validator allowed to vote has applied.

**Why validate against N−k, not each node's LCL.** A node's LCL may be anything from N−k to N−1.
Transactions whose validity depends on the ledgers in between (for example the inner source of a
fee-bump used in another slot) would get different answers on different validators. An attacker
could then submit them on purpose to split honest validators.

**Why the fee payer decides the class.** The abuse to prevent is a payer charged in two open
slots against the same stale balance: apply charges min(balance, fee), so inclusion beyond the
balance would be free.
Restricting every account a transaction touches would leave transactions that span classes
unable to enter any ledger. Conflicts on non-payer accounts fail at apply and are paid for.

**Why the class does not rotate per ledger.** Account keys are free to generate, so with a
constant salt anyone can choose their class and concentrate demand on one slot in k. Rotating the
class every ledger (for example a salt of hash(N−k)) would prevent that, but it breaks the rule it
exists for: a payer's classes for N and N+1 would be independent, so the same payer could be
valid in two open slots, each validated against a state that does not see the other charge.
A safe
rotation would have to keep every payer's ledgers at least k apart, for example by changing the
salt only at an epoch boundary and excluding, for k ledgers after it, payers whose class changed.
That is left open. Concentrating demand on one class only raises the fees of that class's slots,
since surge pricing applies per slot.

**Why the effective close time is derived, not rewritten.** N's close time is fixed before N−1
externalizes, so it may not follow N−1's: on the testbed this happened in about 5% of ledgers at
k = 5. Rewriting the value would invalidate the nominator's signature, so the effective time is
derived.

**Choosing k.** k = ⌈(C + E + S) / L⌉ sets the cadence, and the testbed confirms it; put the
other way, the target close time should be about the consensus time divided by k. Each extra
ledger in flight adds less throughput and about 10–30% more median latency
([testbed-results.md](../results/testbed-results.md)), and widens the liveness attack surface. k = 2 or
3 is the practical range. Since consensus time varies with load, ledger size and topology, a
fixed k is only right for some of the time; how much that costs is an open question.

## Protocol upgrade transition

- Enabling the pipeline, changing k, and changing the class rule all change which tx sets are
  valid. They take effect at a ledger boundary:
  - the slots in consensus when the upgrade ledger applies finish under the old rules;
  - the new rules apply from the first slot nominated afterwards.
- The first k−1 slots after the boundary are built on the boundary ledger itself, not on N−k:
  no validator can be expected to keep the states of the ledgers before it. Validators keep the
  hashes of the last k ledgers and the boundary ledger across restarts. A validator that restarts
  alone, without the states of the last k ledgers, doesn't propose or vote on the slots built on
  them until it has applied their bases again.
- On the testbed, switching rules with slots in consensus split the network. Switching at a
  boundary works.

### Backwards incompatibilities

- Tx sets name an older ledger.
- Close times of consecutive ledgers' values are not ordered; their effective close times are.
- Ledgers carry only one class of payer each.
- Clients that submit many transactions from one account see them included at most once every k
  ledgers.
- Transaction latency (receipt by a validator to externalize) rises: on the testbed +5% to +8% at the median
  with k = 2 and +12% to +18% with k = 3, and more when k is larger than needed
  ([testbed-results.md](../results/testbed-results.md)).
- Fee sponsors and relayers that pay fees for many users from one account only get into one
  ledger in k, and would need k paying accounts to keep their rate.
- Surge pricing applies per slot, so there are k separate fee markets.

### Resource utilization

- **Memory:** validators keep k ledger states (shared buckets) and k-times larger queues.
- **Nomination traffic:** grows with the number of open slots and leaders per round.
- **Apply:** unchanged per ledger. It becomes the bound once (C + E + S) / k approaches E + S,
  which parallel apply relaxes.

## Security concerns

See [live-pipelining-threats.md](live-pipelining-threats.md) for the full review:

- **Safety:** unchanged. Apply is deterministic and in order, and validity is a function of
  (tx set, ledger N−k).
- **Liveness:**
  - **Predictable leaders.** With k ≥ 2 the leaders of N are known about one consensus round
    in advance, which makes a DoS aimed at them practical.
  - **Timeouts compound.** A lost round holds back the slots built on it.

  On the testbed, a DoS that takes the top leader of every slot down for its first nomination
  round costs 48% of the throughput without pipelining and 46% at k = 2. Two mitigations together
  reduce it to 4% and 9% ([testbed-results.md](../results/testbed-results.md)), and cost 0–3%
  without an attack:
  - two leaders per round;
  - nomination timeouts tuned to the measured round time (300 ms instead of 1 s).

  Secret leader priority with a VRF removes the predictability; it is proposed as a follow-up.
- **Abuse:**
  - the fee payer pays in at most one open slot;
  - other conflicts fail at apply and are paid for;
  - concentrating demand on one class raises fees only in that class's slots (per-slot surge
    pricing); a safe class rotation is an open question.

## Test cases

- Upgrade transitions:
  - k: 1 → 2 → 3 → 1 at ledger boundaries;
  - restarts with k slots in consensus;
  - catchup across the upgrade.
- Partition rules:
  - tx sets with a transaction of another class are rejected;
  - fee-bumps with payer and inner source in different classes are included in the payer's
    slots.
- Base:
  - tx sets built on anything other than N−k are rejected;
  - a validator one ledger behind can check every value it may vote on.
- Close time: values out of order between consecutive ledgers, and effective close times strictly
  increasing.
- Liveness: an unavailable leader, and a targeted DoS on predicted leaders, with one and several
  leaders per round.

## Implementation

Prototype: branch `live-pipelining` of https://github.com/bnogalm/stellar-core, one commit on
stellar-core v30. It is behind a configuration option (`EXPERIMENTAL_LIVE_PIPELINE_DEPTH`)
instead of a network setting, and differs from this specification in the class hash (the
prototype uses the key modulo k) and in the close time (rewritten in the header). The
measurements are in [testbed-results.md](../results/testbed-results.md).
