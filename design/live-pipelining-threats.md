# Live pipelining: attack surface and abuse review

The question is what an attacker gains when up to k ledgers are in consensus at once: a
validator, a set of validators below the safety threshold, or anyone who can submit
transactions. Each item states the risk, what the prototype does, and what a protocol design
would have to do.

## The rules under review

1. Nomination of ledger N starts one target close time after nomination of N−1, while up to k
   ledgers are in consensus. A validator nominates N only once N−k has applied.
2. **The value of N is built on exactly N−k** (on the ledger where pipelining started, for the
   first k − 1 ledgers after it). Its tx set carries the hash of that ledger as its previous
   ledger hash, and it is validated against its state. Validators reject any other base.
3. **Each transaction belongs to one class:** the key of the account that pays its fee, modulo k.
   Ledger N only takes transactions of class N mod k, and validators reject a tx set with a
   transaction of another class.
4. Leader election for N uses the value of N−k as applied (its header), which every node that can
   nominate N has.
5. The close time of N must follow that of N−k as applied. At apply, a close time that does not
   follow N−1 is raised to N−1's plus one step, the same on every node.
6. Ledgers are applied in order. A ledger that externalizes before its predecessor is held until
   the predecessor externalizes.
7. Upgrades only go in ledgers that are a multiple of k; the next k − 1 ledgers apply empty.

## Safety: can honest validators diverge?

### S1. Apply is deterministic

All validators apply the same externalized values in the same order, from the same state.
Pipelining changes what a value commits to (an older base) but not how it is applied. The header
chain is the usual one: N's header hashes N−1's, whatever base the tx set names.

**Status:** holds in the prototype. Every run checks that all nodes end on the same ledger, and
the test `live pipelining keeps the network in agreement` checks the ledger hashes of every node.

### S2. Transactions validated against an older state

A tx set for N is validated against the state of N−k (rule 2), so every validator that may vote
on N gets the same answer, whatever its last closed ledger. The fee payer's balance and sequence
number only change in its own class's ledgers, and the previous one of those is N−k. Other
accounts a transaction touches (a fee-bump's inner source, operation source accounts, payment
destinations, offers, Soroban footprints) may change in the ledgers in between; those
transactions are included and can fail at apply (A2).

**Why exactly N−k.** With a base that could be any recent ledger, a leader could build a value on
a ledger other validators have not applied yet. They could not check it, and SCP would leave them
silent in that slot ("maybe valid"); with enough of them silent the slot could not complete. A
fixed base is one that every validator allowed to vote has applied (rule 1).

**Cost:** each validator keeps the last k ledger states for validation.

### S3. Close time order

The close time of N is fixed before N−1 externalizes, so it may not follow N−1's. Apply raises it
to N−1's plus one step. This is deterministic.

**Risk:** in the prototype the raised close time overwrites the value stored in the header, so
the header's value no longer matches the nominator's signature.

**Design:** keep the signed value unchanged and define the effective close time as
max(value close time, previous close time + step), derived and not stored. Anything that reads
the close time (time bounds, Soroban timestamps, upgrade times) must use the effective one.

### S4. Switching pipelining on, or changing k

The depth and the class rule decide which tx sets are valid, so changing them while ledgers are in
consensus would make validators disagree on those ledgers.

**Prototype:** k is a configuration option, changed on all validators at a restart at the same
ledger, right after it closes, when no ledger is in consensus. That ledger is where pipelining
starts: the first k − 1 ledgers after it are built on it, since no node keeps the states of the
ledgers before it. Each node keeps the hashes of the last few ledgers, the last upgrade and the
start ledger in a small file next to the buckets, written on every apply. The test
`live pipelining switched on at a restart of all validators` covers it.

**Design:** activate pipelining, and any change of k or of the class rule, by a network upgrade at a
ledger boundary. Ledgers in consensus at the boundary close under the old rules.

## Liveness: can an attacker stall or slow the network?

### L1. Contentious tx sets

A Byzantine leader, or ordinary users, can include transactions whose result depends on another
class's ledgers. Validity only looks at N−k (S2), so honest validators agree on the value; the
transactions fail at apply and pay (A2).

### L2. Predictable leaders

Leader election for N uses the value of N−k, which is known about one consensus round before
nomination of N starts. Today the leaders of N are known when N−1 externalizes, which is when
nomination of N starts. An attacker who can DoS specific validators gets time to target the
predicted leader of each ledger.

- **The cost.** Each hit costs that ledger a nomination timeout, and it shows in the ledgers built
  on it (L3).
- **What it does not do.** It is a liveness attack, much cheaper than attacking every validator;
  it does not threaten safety.

SCP already rotates leaders on nomination timeouts, so a DoSed leader costs a timeout, not a
stall. Two remedies:

**Remedy 1: several leaders from the first round** (`EXPERIMENTAL_NOMINATION_LEADERS`).
- Each round takes the m nodes with the highest priority as leaders, instead of only the top one.
  Every node still computes the same priorities, so every node agrees on the leaders.
- A round only stalls if all m leaders are unavailable.
- The cost is more nomination traffic and more candidate values to combine.
- It is a local change to `NominationProtocol::updateRoundLeaders`, with no new data in SCP
  messages.

**Remedy 2: secret leader priority with a VRF** (as in Algorand's sortition).
- Each validator computes its priority for (slot, round) with a verifiable random function over
  its private key and the previous value, and publishes it with a proof.
- Nobody can compute another validator's priority in advance, so there is no one to target ahead
  of time, whatever k is. It also helps without pipelining.
- It changes the SCP nomination messages and how nodes pick whose votes to echo, so it is a larger
  protocol change. The priority must still reflect each node's weight in the quorum.

**Measured** ([testbed-results.md](../results/testbed-results.md#predictable-leaders)): each
validator stays silent in the first nomination round of every ledger where it is the top leader,
as a successful attack would make it. That costs 48% of the throughput at k = 1 and 46% at k = 2;
two leaders per round plus a 300 ms nomination timeout bring it to 4% and 9%, and cost 0–3%
without an attack. The testbed measures the cost of a successful attack, not how much easier
predictability makes it.

### L3. Timeouts compound

A slow ledger delays its successors' bases: N+k cannot be nominated until N applies. A nomination
timeout on one ledger therefore shows in up to k later ledgers (the p99 interval in the runs).

**Design:** report p99, and bound how far a single ledger can hold back the others. If N−k is not
applied in time, N could be nominated as an empty ledger.

### L4. Restarts and catchup with open slots

A restarted validator keeps the hashes of the last few ledgers, the last upgrade and the start
ledger (in a file next to the buckets), but not their states. Until it has applied N−k again it
doesn't propose or vote on N, and only applies what the others externalize. The test
`live pipelining across an upgrade and a restart` restarts a validator with k = 2 and 3.

**Limit:** if a quorum of validators restarts at once with pipelining on, none of them has the
states of the ledgers before its LCL, so none can vote on the next k − 1 ledgers and the network
stops. A protocol design would need either to keep those states across restarts or a rule for
restarting the pipeline at a ledger boundary (as when switching it on). Catchup from history
archives is untested.

## Abuse: can someone get service without paying for it?

### A1. Fee payer in several open ledgers

If the class were the transaction source's instead of the fee payer's, a fee-bump's fee source, or
a transaction whose fee comes from another account, could pay in several open ledgers. Each would
be validated against the same old balance, and apply charges min(balance, fee), so inclusion
beyond the balance would be free. With the class of the fee payer (rule 3), a payer is in at most
one open ledger.

### A2. Conflicts that fail at apply

A transaction can touch accounts of other classes: the inner source of a fee-bump, operation
source accounts, payment destinations, offers in the order book, Soroban footprint entries. When
two open ledgers touch the same account, the later one may fail at apply (bad sequence number,
underfunded, conflicting write). The failing transaction's payer still pays its fee, so the cost
is capacity, paid for at the fee rate.

**To check:** every failure path in apply charges the fee, including a fee-bump whose inner
transaction is invalid at apply; and what fraction of a ledger an attacker can fill with
conflicting transactions for a given fee budget.

### A3. Choosing a class

Account keys are free to generate, so anyone can pick the class of their accounts and concentrate
demand on one ledger in k. Surge pricing is per ledger, so that only raises fees in that class's
ledgers.

The classes don't make the network harder to saturate as a whole: an attacker can make paying
accounts in all k classes for free, so filling every ledger costs what filling the total capacity
costs. What makes that harder is the capacity itself (about 1.9× at k = 2). What the classes
change is where an attack lands: filling one class costs about 1/k of the capacity and only hurts
the payers of that class. That contains it, but makes it cheaper to aim at one user who pays every
fee from one account. A large operator that spreads its paying accounts over the k classes (which
it needs anyway to keep its rate, A5) only loses 1/k of its capacity to such an attack.

A class that rotates would spread demand, but **not per ledger**: if a payer's classes for N and
N+1 were independent (for example the key hashed with the value of N−k), the same payer could be
valid in two open ledgers against the same old balance, which is what the class exists to
prevent. A safe rotation must keep each payer's ledgers at least k apart (for example, change the
salt only at an epoch boundary, and exclude for k ledgers the payers whose class changed). Open.

### A4. Queue and flooding

Each ledger can only take 1/k of the queued transactions, so the queues are k times larger, and a
transaction can wait about 2k ledgers for its turn (the k ledgers already in consensus, then up to
k − 1 until its class comes round). The queue timeout (4 ledgers today, then a 10-ledger ban) is
therefore k times longer, about the same wall time as today.

**To check:** the overlay flood rate limits are per expected ledger close time. Check that they
stay right when ledgers close every L ms with k in consensus, and that a sender cannot use the
larger queue or the longer timeout to hold more pending transactions per account than today.

### A5. Fee sponsors and per-ledger fee markets

Not an attack, but a cost of the class rule. An account that pays fees for many users (relayers,
wallets that sponsor fees, fee-bump services) only gets into one ledger in k, and needs k paying
accounts to keep its rate. Surge pricing becomes per ledger, so a burst in one class raises fees
only in that class's ledgers.

### A6. Close time manipulation

The close time of N only has to follow N−k at nomination. A nominator can propose a close time
earlier than N−1's, which apply then raises.

**To check:** the bounds on how far a close time may be in the future (MAX_TIME_SLIP) and in the
past (after N−k), and whether time-bound transactions or Soroban timestamps can be steered by a
leader more than today.

## Upgrades in flight

An upgrade externalized in N changes the rules for N+1 … N+k−1, which were validated under the
old rules. The prototype only allows upgrades in ledgers that are a multiple of k and applies the
next k − 1 ledgers empty (rule 7); their transactions stay queued. The ledgers keep their values
and tx sets, also in history, so catchup, which applies the same rule, gets the same result; the
ledger close meta of a drained ledger shows no transactions. That covers config upgrades (tested
under load in `live pipelining across an upgrade and a restart`). A
protocol upgrade also changes the format of the values already in consensus, which would need
them to be checked with the protocol they were nominated under; that is not built.

## What the prototype does not cover

1. Effective close time without rewriting the signed value (S3).
2. Activation and change of k by upgrade (S4), and protocol upgrades in flight.
3. Catchup from history archives (L4).
4. A safe class rotation (A3), and the A2 measurements.
5. Overlay flood limits with k open ledgers (A4).

This review is by the author of the prototype; an external review is needed.
