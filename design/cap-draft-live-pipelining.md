# CAP draft: Pipelined consensus (k ledgers in consensus at once)

```
CAP: (unassigned)
Title: Pipelined consensus: k ledgers in consensus at once
Working Group:
    Owner: Benjamín Nogal Muñoz
    Authors: Benjamín Nogal Muñoz
Status: Draft (not submitted)
Created: 2026-11-05
Discussion: https://github.com/orgs/stellar/discussions/2066
Protocol version: (next)
```

## Simple summary

Let validators start nominating ledger N before ledger N−1 has externalized, so that up to k
ledgers are in consensus at once. When consensus across continents takes longer than the target
close time, ledgers can then close at the target while the latency of each ledger stays about the
same.

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
- **Overlapping consensus with apply,** as SDF plans (voting on N+1 while applying N; its
  [roadmap](https://stellar.org/foundation/roadmap) calls it pipelining consensus and
  execution), lowers the floor to max(C, E). With validators on several continents that is still
  C. This proposal is meant to work on top of it.

Pipelining consensus removes that floor. With k ledgers in consensus, the interval becomes
max(L, (C + E + S) / k, E). Apply stays sequential and is the final limit, the same one the
overlap has.

**Against today's protocol.** Measured on the testbed with the mainnet apply cost and
300-transaction ledgers, against k = 1 at the same target
([testbed-results.md](../results/testbed-results.md); three runs per point for seven validators):

| Network | Target | k | Throughput | Median transaction latency |
|---|---|---|---|---|
| 7 validators | 200 ms | 2 | 1.90× | +8% |
| 7 validators | 200 ms | 3 | 2.55× | +18% |
| 12 validators in organizations | 200 ms | 2 | 1.92× | +5% |
| 12 validators in organizations | 200 ms | 3 | 2.66× | +12% |

The gain stops at k = 4 to 5, at about 790 tx/s (2.9×), where the interval reaches the apply
time; after that only latency grows. With Soroban calls of 4M instructions it goes on to 3.7× at
k = 7 ([throughput-current.md](../results/throughput-current.md)). Doubling the ledger size
without pipelining gave 1.47× for 17% more latency, because apply also doubles and adds to the
interval.

**Against the planned overlap** the gain is smaller and conditional
([when-pipelining-pays.md](../results/when-pipelining-pays.md)). Both have the same ceiling, one
transaction per apply time, and pipelining pays only when all three of these hold:

1. validators apply a ledger in clearly less time than its consensus;
2. ledger size is bounded, by the network cap, by latency, or by what big tx sets cost in
   consensus;
3. the network needs more than the overlap gives: ledgers closer than about 0.65 s apart, or,
   with today's cap, more than about 1,500 operations per second.

Then k = 3–4 gives 1.5 to 2× the overlap's throughput at the same ledger size. A client with one
payer account has more latency than with the overlap; a client with a payer account in every
class has less, at the same throughput. For mainnet in the medium term, with ledgers every 2.5
to 5 s, they do not hold and the overlap is enough. This draft is for a possible step after
it.

With ledgers several times larger the choice is open: the overlap catches up by growing ledgers
only while a transaction adds more to apply than to consensus, and the measured cases fall on
both sides ([apply-and-consensus-by-size.md](../results/apply-and-consensus-by-size.md)).

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
8. Every account has a fee reserve. In a ledger of another class, a transaction can't take an
   account's native balance below the lower of what it held and its fee reserve; in a ledger of
   its class, the account pays at most its fee reserve in fees.

## Specification

### Network setting

`ledgerPipelineDepth` (uint32, default 1): a new field of the ledger header, changed by a ledger
upgrade of its own type, like the base fee and the tx set size. It is in the header so that a
node that catches up, or a tool that verifies history, reads the rule of each ledger from the
headers. Raising or lowering it takes effect at a ledger boundary (see Protocol upgrade
transition). Values above a small bound are rejected: the prototype allows up to 12, and 2 to 4
is the useful range.

The depth should be set with the target close time, as the smallest k with
k × target ≥ consensus + apply. A larger k adds transaction latency and no throughput: on the
testbed, at a 500 ms target the gain stayed at about 2.1× from k = 3 while latency kept growing
([testbed-results.md](../results/testbed-results.md)). Whether the protocol should derive k from
the target and a measured consensus time, or leave both to the network vote, is open.

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
  Soroban footprints) are not restricted by class. A transaction that conflicts at apply with a
  transaction of another open slot fails as today (bad sequence number, underfunded, footprint
  conflict), and its payer is charged its fee. The fee reserve below keeps the payer's own fee
  payable.

### Fee reserve

- Every account has a fee reserve R: a new account field, settable by the account (a
  SetOptions field, for example), never below the network minimum `pipelineFeeReserveMin`, and
  `pipelineFeeReserveDefault` until set. Both are network settings.
- Let held(A) be A's native balance minus its native selling liabilities. In a ledger N whose
  class is not A's, a transaction fails with `txINSUFFICIENT_BALANCE` if, at its end:
  - held(A) is below min(held(A) at its start, R(A)), counting a deleted account as 0; or
  - R(A) is lower than at its start.
  This is checked on the transaction's final state, so intermediate debits within it are allowed.
- A tx set for ledger N is invalid if, for some fee payer A, the sum of the fees of A's
  transactions exceeds min(R(A), available balance of A), both read from the state of N−k.
- With k = 1 there is no ledger of another class, and both rules have no effect.
- Since R also caps the fees of a payer in its own ledgers, a transaction whose total fee
  (resource fee included) is above R is refused until the account raises R, and the new R
  counts from k ledgers later. In practice this is a contract wasm upload, rare next to
  invocations, which stay well under the default. Deployment tools should raise R, deploy, and
  lower it again, and the refusal should say that the fee is above the account's fee reserve.
  The default is a network setting so that it can follow fee levels.

### Nomination

- Leader priorities for slot N are computed with the value of N−k, as applied (with its
  effective close time), as the previous value.
- A validator nominates N when both hold:
  - one target close time has passed since it nominated N−1;
  - it has applied N−k.
- The close time a validator proposes for N must be later than N−k's close time, and within the
  usual bounds into the future. A validator that does not have N−k (it is catching up) checks
  the upper bound only: the values of consecutive slots are not ordered.
- A slot N is open for a validator when N−k is at or below its LCL. The validator processes the
  SCP messages of its open slots, treats them as current for validation, and runs their timers.
  A validator that is catching up handles the next slot only, as today: it cannot check later
  slots, and a ballot timer there would make it emit a statement for a value it cannot
  validate.
- The empty-tx-set form of a value (CAP-0083) names N−k, its hash and protocol, as the tx sets of
  N do, so a value has one such form whatever ledger the builder has applied.
- A value for the slot of a validator's LCL is valid if its close time is at or before the
  ledger's effective close time (see Apply and close time).
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

Measured on the testbed with all three rules, under load
([correctness-rounds.md](../results/correctness-rounds.md)):

- base fee and tx set size upgrades, at k = 2 to 5;
- a protocol upgrade (29 → 30, which changes the value format), at k = 2 to 5;
- three changes of k: 2 → 3, 3 → 1 and 1 → 3.

A network config upgrade was only run before k moved into the ledger, at k = 3.

1. **Upgrade slots.** Only a ledger whose number is a multiple of k may carry ledger upgrades
   (protocol version, base fee, base reserve, tx set size, flags, network config). Validators
   reject values with upgrades in other slots. Otherwise the slots already in consensus all
   carry the same armed upgrade and it is applied more than once, which is invalid for a protocol
   version change.
2. **Drain.** The k − 1 ledgers after a ledger that applied an upgrade apply with an empty tx
   set. Their tx sets were validated under the rules before the upgrade; their transactions stay
   queued for later ledgers. Every node knows the upgrade ledger when it applies them, so this
   is deterministic.
3. **Value format across a protocol upgrade.** The SCP value of the slots
   already in consensus when a protocol upgrade applies was built under the old protocol, and
   protocols can change the value format (protocol 30 adds millisecond close times). Values for
   ledgers N+1 … N+k−1 after a protocol upgrade in N must be checked, and applied, under the
   protocol version of their base ledger, not the LCL's.

### History and catchup

Archived tx sets name ledger N−k as their previous ledger from the activation ledger on, while
headers still chain one by one. Catchup, archive verification and any tool that checks a tx set
against the previous header must accept the N−k base after activation.

- The rule of each ledger (k, base, drain) follows from the headers, so a replay applies every
  ledger as the network did, across changes of k.
- A catchup that applies buckets replays at least the k−1 ledgers before its target, so that the
  node has the states the next slots are validated against.
- An online catchup takes its trusted hash from the buffered ledgers: the tx set of the ledger
  k−1 after the first buffered one names the ledger before it. A node does not know the
  network's k before it has caught up, so it accepts the previous ledger hash of any of the
  first few buffered tx sets. A header hashes its own sequence number, so the hash of another
  ledger cannot match.
- A drained ledger keeps the tx set it externalized in history and in the meta, with the
  transactions it did not apply.

### Transaction queue

Nodes keep queued transactions for about k times as many ledgers, and size their queues k times
larger, following the network's k. These are node policy, not protocol.

### Limits counted in ledgers

Several limits of stellar-core are counted in ledgers and sized for 5 s ledgers. With pipelining
a ledger closes about every target close time, so they shrink in time by the same factor:

- **The validity bracket**, how far ahead of the next slot a node keeps envelopes (100 ledgers,
  500 s at 5 s). At 200 ms it is 20 s, less than a catchup takes: a restarted validator ended its
  catchup too far behind, dropped the envelopes of the current slots, and fell behind again. The
  prototype scales it with the ledger rate: the ledgers of 120 s at the target close time,
  between 100 and 1,200 slots. It stays a count of slots, so it does not grow while
  the network is stalled. With it, a restarted validator rejoined in 16 of 16 test rounds,
  against 11 of 16 before.
- **Not changed yet:** the slots a peer sends a node that asks for SCP state
  (`MAX_SLOTS_TO_REMEMBER`, 12), the apply drift (12 ledgers), and the checkpoint an online
  catchup waits for (64 ledgers).
- **SCP timeouts** are counted in time, but sized for 5 s ledgers: the first nomination and
  ballot timeouts are 1 s, several ledger intervals at 200 ms. Their lower bounds as network
  settings (750 ms) would have to be lowered to tune them.

These should be defined in time, or scaled with the ledger rate, in the CAP.

## Design rationale

**Why a fee reserve.** The class of the fee payer keeps it out of the other open slots, but not
its balance: it can be the source of an operation, or sign a Soroban authorization, in a
transaction another account pays for in N−1. Its own transaction in N was validated against N−k,
so it would pay less than it bid, and if the operation merges the account, fee processing finds
no account at all (on the prototype, every validator aborts). This was pointed out by vendrell46
in the discussion ([comment](https://github.com/orgs/stellar/discussions/2066#discussioncomment-19515575)). The fee reserve follows Monad's reserve balance rules
([Monad docs](https://docs.monad.xyz/developer-essentials/reserve-balance)); since a payer is in one open slot at a time, the sum over in-flight
transactions that Monad needs reduces to one ledger. The reserve is per account, not a single
network value, because a single value would also cap every fee bid (a transaction has one
payer); Monad also plans per-account reserves. Restricting every account a transaction touches to
the payer's class would close the same hole, but would leave transactions that span classes,
channel accounts and sponsored payments unable to enter any ledger.

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
externalizes, so it may not follow N−1's: on the testbed
apply raised it in 1 of 633 ledgers at k = 3, 1% at k = 4, 8–9% at k = 5 and 20% at k = 6. Rewriting the value would invalidate the nominator's signature, so the effective time is
derived.

**Choosing k.** k = ⌈(C + E + S) / L⌉ sets the cadence, and the testbed confirms it; put the
other way, the target close time should be about the consensus time divided by k. Each extra
ledger in flight adds less throughput and, for a client with one payer account, 5 to 16% of the
k = 1 median latency, at 300 transactions per ledger ([testbed-results.md](../results/testbed-results.md)), and widens the
liveness attack surface.
On the testbed the gain stops at k = 4 to 5 with the mainnet apply cost, where the interval
reaches the apply time ([throughput-current.md](../results/throughput-current.md)). Against
today's protocol, k = 2 gives 1.9× for 8% more median latency, and k = 4 gives 2.8× for 32% more.
Against the planned overlap, pipelining pays at k = 3–4 and only under the conditions in
Motivation; otherwise k = 1 is the right value. Since consensus time varies with load, ledger
size and topology, a fixed k is only right for some of the time; how much that costs is an open
question.

**Why k is in the ledger.** Every validator has to apply the same rule to the same slot. A
setting that each node reads from its configuration can differ between nodes, and changing it
needs every validator to restart at the same ledger. A network setting changed by an upgrade
reaches all of them at the same ledger, and a node that catches up reads it from the headers.

**Why the empty-tx-set form names N−k.** It names the ledger its tx set builds on. If it named
the builder's LCL, nodes at different LCLs would build different forms of one value, and a form
built before a protocol upgrade applied would become invalid for its own builder after it, which
on the prototype made that validator exit.

## Protocol upgrade transition

- Enabling the pipeline, changing k, and changing the class rule all change which tx sets are
  valid. They take effect at a ledger boundary:
  - the slots in consensus when the upgrade ledger applies finish under the old rules;
  - the new rules apply from the first slot nominated afterwards.
- After a change of k at ledger U from k_o to k_n, the slots up to U + k_o − 1 keep the old rule
  (they were in flight), and slot N from U + k_o on is built on max(N − k_n, U): no validator can
  be expected to keep the states of the ledgers before U for the new rule. k changes again only
  once no slot follows an older rule.
- Validators store the state of each of the last k−1 ledgers with that ledger (its header and
  bucket list hashes), and the SCP state of every open slot, and rebuild them at a restart. On
  the testbed, killing every validator at once under load and starting them again resumes
  without catchup. A validator that does not have the states (a new node) does not vote on the
  slots built on them until it has.
- On the testbed, switching rules with slots in consensus split the network. Switching at a
  boundary works.

### Backwards incompatibilities

- Tx sets name an older ledger.
- Close times of consecutive ledgers' values are not ordered; their effective close times are. A
  consumer that takes a ledger's close time from the value in its header must derive the
  effective one (see Apply and close time).
- Ledgers carry only one class of payer each.
- Clients that submit many transactions from one account see them included at most once every k
  ledgers. Ledgers come k times as often, so that is about as often as a ledger closes without
  pipelining; a client with a payer account in every class gets every ledger.
- Transaction latency (receipt by a validator to externalize) rises for a client that pays from
  one account: on the testbed +5% to +8% at the median with k = 2 and +12% to +18% with k = 3,
  and more when k is larger than needed ([testbed-results.md](../results/testbed-results.md)).
  A client with a payer account in every class waits k times less for its next ledger.
- Fee sponsors and relayers that pay fees for many users from one account only get into one
  ledger in k, about as often as a ledger closes without pipelining. To use the capacity that
  pipelining adds they need k paying accounts.
- A transaction with a fee above the payer's fee reserve, such as a wasm upload, needs the
  reserve raised first (see Fee reserve).
- The k − 1 ledgers after each upgrade apply no transactions.
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
  - **Predictable leaders.** The leaders of N are known before its nomination starts, as they
    are today. On mainnet that is the 4.4 s nomination waits for the timer
    ([mainnet-steps.md](../results/mainnet-steps.md)); with pipelining it is the queue plus the
    apply of N−k, about 0.4 s at k = 2 and 0.7 s at k = 4 on the testbed. Pipelining does not
    make them known earlier. What changes with ledgers shorter than a nomination timeout,
    pipelined or not, is the cost of a DoS aimed at them: each lost round takes a large share
    of the throughput.
  - **Timeouts compound.** A lost round holds back the slots built on it.

  On the testbed, a DoS that takes the top leader of every slot down for its first nomination
  round costs 48% of the throughput without pipelining and 46% at k = 2. Two mitigations together
  reduce it to 4% and 9% ([testbed-results.md](../results/testbed-results.md)), and cost 0–3%
  without an attack:
  - two leaders per round;
  - nomination timeouts tuned to the measured round time (300 ms instead of 1 s).

  Secret leader priority with a VRF removes the predictability; it is proposed as a follow-up.
- **Abuse:**
  - the fee payer pays in at most one open slot, and its fee reserve keeps what it bid payable
    whatever the other slots do;
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
- Fee reserve:
  - outside its class, a merge of an account fails, and payments, offers and SAC transfers can't
    take it below min(held, R); it can raise R but not lower it;
  - in its class, a payer's fees above min(R, available) make the tx set invalid; R can be raised
    to bid higher, and is never below the network minimum.
- Base:
  - tx sets built on anything other than N−k are rejected;
  - a validator one ledger behind can check every value it may vote on.
- Close time: values out of order between consecutive ledgers, and effective close times strictly
  increasing.
- Liveness: an unavailable leader, and a targeted DoS on predicted leaders, with one and several
  leaders per round.
- Restarts: one validator and every validator at once under load, killed and stopped cleanly;
  a validator away across a change of k joining online.
- Empty-tx-set values: a form built before a protocol upgrade stays valid after it.

The prototype has unit tests for each rule, and
[correctness-rounds.md](../results/correctness-rounds.md) has the rounds that combine them under
load on the WAN testbed.

## Implementation

Prototype: branch `live-pipelining` of https://github.com/bnogalm/stellar-core, on stellar-core
v30, with everything this draft describes. With k = 1 it behaves as upstream. It differs from this specification in:

- **k:** kept in bits 16 to 19 of the ledger header flags and changed with a
  `LEDGER_UPGRADE_FLAGS` upgrade, to avoid an XDR change. A flags upgrade replaces the whole
  word, and no protocol version gates the new bits; the CAP needs a field and an upgrade of its
  own. `EXPERIMENTAL_LIVE_PIPELINE_DEPTH` sets the genesis k and the k a validator votes for.
- **The class hash:** the first byte of the payer's ed25519 key, modulo k.
- **The close time:** rewritten in the header. There the header's close time can be later than
  the one its proposer signed, and a consumer that checks that signature must use the value's
  close time.
- **The fee reserve:** a data entry, `pipeline.fee_reserve`, instead of an account field, and
  configuration options instead of network settings.

Related documents:

- **Measurements:** [testbed-results.md](../results/testbed-results.md),
  [throughput-current.md](../results/throughput-current.md) and, against the planned overlap,
  [when-pipelining-pays.md](../results/when-pipelining-pays.md).
- **Correctness rounds:** [correctness-rounds.md](../results/correctness-rounds.md).
- **The reasons for each decision:** [decisions.md](decisions.md).
