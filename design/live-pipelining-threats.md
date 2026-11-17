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
3. **Each transaction belongs to one class,** that of the account that pays its fee: the first
   byte of its key modulo k in the prototype, a salted hash of the key in the draft CAP.
   Ledger N only takes transactions of class N mod k, and validators reject a tx set with a
   transaction of another class.
4. Leader election for N uses the value of N−k as applied (its header), which every node that can
   nominate N has.
5. The close time of N must follow that of N−k as applied. At apply, a close time that does not
   follow N−1 is raised to N−1's plus one step, the same on every node.
6. Ledgers are applied in order. A ledger that externalizes before its predecessor is held until
   the predecessor externalizes.
7. Upgrades only go in ledgers that are a multiple of k; the next k − 1 ledgers apply empty.
8. **Fee reserve.** In a ledger of another class, an account can't end a transaction holding less
   native balance (net of what its offers sell) than the lower of what it held before and its
   fee reserve, nor lower its fee reserve. In a ledger of its own class, the fees it pays are at
   most the lower of its fee reserve and its available balance at N−k. The fee reserve is per
   account, with a network default and minimum.

## Safety: can honest validators diverge?

### S1. Apply is deterministic

All validators apply the same externalized values in the same order, from the same state.
Pipelining changes what a value commits to (an older base) but not how it is applied. The header
chain is the usual one: N's header hashes N−1's, whatever base the tx set names.

**Status:** holds in the prototype. Every run checks that all nodes end on the same ledger, and
the test `live pipelining keeps the network in agreement` checks the ledger hashes of every node.

### S2. Transactions validated against an older state

A tx set for N is validated against the state of N−k (rule 2), so every validator that may vote
on N gets the same answer, whatever its last closed ledger. A payer is only charged fees in the
ledgers of its own class, and the previous one of those is N−k; its fee reserve keeps the fee it
bid payable whatever the ledgers in between do (A1). Everything else can change in those
ledgers:

- the payer's own sequence number, when it is the inner source of a fee-bump paid from another
  class, and the rest of its balance;
- the other accounts a transaction touches: operation source accounts, payment destinations,
  offers, Soroban footprints.

Those transactions are included and can fail at apply (A2).

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

**Risk:** if validators switch rules at different ledgers, they disagree on which tx sets are valid
for the slots in between.

**Prototype:** k is in the ledger header and changed by a network upgrade, so every validator
switches at the same ledger. After a change at U from k_o to k_n, the slots up to U + k_o − 1 keep
the old rule and later ones are built on max(N − k_n, U); k changes again only once no slot follows
an older rule. Catchup reads the rule of each ledger from the headers. Tested by unit tests for the
four transitions and under load on the testbed (2 → 3, 3 → 1, 1 → 3).

**Protocol design:** k needs a header field and an upgrade of its own; the prototype keeps it in the
header flags, where an upgrade of another flag replaces it, and no protocol version gates it.

## Liveness: can an attacker stall or slow the network?

### L1. Contentious tx sets

A Byzantine leader, or ordinary users, can include transactions whose result depends on another
class's ledgers. Validity only looks at N−k (S2), so honest validators agree on the value; the
transactions fail at apply and pay (A2).

### L2. Predictable leaders

The leaders of a ledger are known before its nomination starts, with and without pipelining, so
an attacker who can DoS specific validators has time to target the leader of each ledger:

- **Today** the leaders of N follow from the value of N−1, known when N−1 externalizes, and
  nomination of N waits for the timer: about 4.4 s on mainnet
  ([mainnet-steps.md](../results/mainnet-steps.md)).
- **With pipelining** they follow from the value of N−k, and nomination of N starts once N−k has
  applied. The time in between is the queue plus the apply of N−k: about 0.4 s at k = 2 and 0.7 s
  at k = 4 on the testbed. With ledgers back to back and no pipelining it is one apply, also
  about 0.4 s there.

Pipelining does not give the attacker more time. What changes with ledgers shorter than a
nomination timeout, pipelined or not, is what each hit costs:

- **The cost.** Each hit costs that ledger a nomination timeout, 1 s, which on the testbed is as
  long as a whole ledger interval without pipelining and longer with it. It also shows in the
  ledgers built on it (L3).
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
without an attack. The testbed measures the cost of a successful attack, not how hard it is to
mount.

### L3. Timeouts compound

A slow ledger delays its successors' bases: N+k cannot be nominated until N applies. A nomination
timeout on one ledger therefore shows in up to k later ledgers (the p99 interval in the runs).

**Design:** report p99, and bound how far a single ledger can hold back the others. If N−k is not
applied in time, N could be nominated as an empty ledger.

### L4. Restarts and catchup with open slots

**Risk:** a validator that restarts without the states of the k − 1 ledgers before its LCL cannot
vote on the open slots; if a quorum restarts at once, the network stops. A validator that catches
up may be too far behind to hear the current slots.

**Prototype:**
- **States:** each ledger stores its header and bucket list hashes. The states of the k − 1
  ledgers before the LCL are rebuilt at start from buckets kept on disk.
- **SCP state:** every open slot persists its SCP state.
- **Pending slots:** slots externalized and not applied before a stop are delivered again.

On the testbed, killing or stopping every validator at once under load resumes without catchup
([correctness-rounds.md](../results/correctness-rounds.md)). For catchup:
- **Replay:** a catchup replays at least the k − 1 ledgers before its target.
- **Trusted hash:** an online catchup accepts the previous ledger hash of any of the first twelve
  buffered tx sets, so a node that does not know the network's k can join.
- **Envelopes kept:** the validity bracket scales with the ledger rate (120 s of ledgers), so a
  node that catches up keeps the envelopes of the current slots meanwhile. With it, a restarted
  validator rejoined in 16 of 16 rounds, against 11 of 16 with upstream's 100 slots.

**Limit:** other limits counted in ledgers (the slots a peer sends on request, the apply drift, the
checkpoint an online catchup waits for) and the SCP timeouts are sized for 5 s ledgers.

### L5. Values a validator cannot check yet

**Risk:** with k slots open, the values of a slot depend on ledgers some validators have not
applied, and a faulty proposer can send values built to land in that gap. A statement a validator
cannot judge marks the slot as not validated for it, and it stops voting there. A statement of its
own that it later judges invalid makes it exit.

**Prototype:**
- **Wrong base:** a tx set not built on N−k is invalid for the slot, as it is for the next ledger
  today. It is not "maybe valid", which would let one faulty validator silence the others.
- **Empty-tx-set forms** name N−k, so an honest validator's form stays valid across a protocol
  upgrade, and every validator handed the slot can check it.
- **Close times:** the close time of a value is checked against N−k; a validator without N−k
  checks the upper bound only. A value for the slot of the LCL may be at or before the header's
  raised close time.
- **Open slots:** a validator handles, validates as current, and runs timers for the slots whose
  base it has applied, and only the next slot while it catches up.

Each case has a unit test. The WAN rounds have no faulty validator.

## Abuse: can someone get service without paying for it?

### A1. Fee payer in several open ledgers

**Risk: a payer in several open ledgers.** If the class were the transaction source's instead of
the fee payer's, a fee-bump's fee source, or a transaction whose fee comes from another account,
could pay in several open ledgers. Each would be validated against the same old balance, and
apply charges min(balance, fee), so inclusion beyond the balance would be free. With the class of
the fee payer (rule 3), a payer is in at most one open ledger.

**Risk: the payer's balance moves in a ledger of another class.** The class rule is not enough on
its own, as vendrell46 pointed out in the discussion
([comment](https://github.com/orgs/stellar/discussions/2066#discussioncomment-19515575)). The
payer can be the source of an operation, or sign a Soroban authorization, in a transaction
someone else pays for. Then:

- **It pays less than it bid.** Its own transaction in N was validated against N−k and apply
  charges min(balance, fee), so it keeps its place. Under surge pricing that holds inclusion
  slots for less than other bidders pay.
- **A merge stops every validator.** When N applies the payer no longer exists, fee processing
  finds no account, and the node aborts ("Unexpected database state"). This was reproduced with
  the prototype before rule 8.

**Prototype: rule 8,** following Monad's reserve balance rules
([Monad docs](https://docs.monad.xyz/developer-essentials/reserve-balance)):

- **Outside its class** an account keeps at least the lower of what it held and its fee reserve,
  net of what its offers sell. A merge leaves it nothing, so it fails.
- **In its own ledgers** it pays at most the lower of its fee reserve and its available balance
  at N−k, so what it bid is there when N applies.
- **One ledger at a time:** a payer is in one open ledger at a time, so unlike Monad there is no
  sum over ledgers in flight.
- **Where it is checked:** on each transaction's final state, in the classic and the parallel
  Soroban apply, so payments, offers, merges, operation sources and SAC transfers are covered
  alike.

**The reserve is per account** (a data entry in the prototype), with a network default (1 XLM in
the prototype) and minimum (0.01 XLM). A single network value would also cap fee bids, since a
transaction has one payer: an account that bids high raises its reserve, and one that never pays
fees, like the main account behind channel accounts, lowers it to the minimum.

**Cost:**

- **Outside its class,** an account below its reserve can't send native balance, and a merge only
  happens in a ledger of its class. A sponsor or channel provider avoids that by paying from an
  account of the user's class.
- **In its own ledgers,** a transaction whose total fee is above the reserve is refused until the
  account raises it. In practice that is a contract wasm upload
  ([decisions.md](decisions.md), decision 4).

### A2. Conflicts that fail at apply

Apart from the payer's balance and existence (A1), everything a transaction depends on that
another open ledger can change is checked again at apply, as it is today within a single ledger:
the source account, its sequence number and signers, preconditions, operation accounts and
balances, and Soroban entries.
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
costs. What makes that harder is the capacity itself, where pipelining adds to it
([when-pipelining-pays.md](../results/when-pipelining-pays.md)). What the classes
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
wallets that sponsor fees, fee-bump services) only gets into one ledger in k: about as often as
a ledger closes without pipelining, and it needs k paying accounts to use the capacity that
pipelining adds. Surge pricing becomes per ledger, so a burst in one class raises fees
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
and tx sets, also in history and in the meta, so catchup, which applies the same rule, gets the
same result. A protocol upgrade also changes the format of the values already in consensus: their
format follows the protocol of N−k, on both sides and in catchup, and apply raises a close time by
the smallest step of the value's format. Tested under load: base fee and tx set size upgrades, and
the protocol upgrade 29 → 30, at k = 2 to 5.

## What the prototype does not cover

1. Effective close time without rewriting the signed value (S3).
2. k in a header field of its own, gated by a protocol version (S4).
3. Limits counted in ledgers other than the validity bracket, and SCP timeouts, defined in time
   (L4).
4. A safe class rotation (A3), and the A2 measurements.
5. Overlay flood limits with k open ledgers (A4).
6. The fee reserve as an account field instead of a data entry, its default as a network setting
   chosen from mainnet fees, and a clear refusal for a fee above it (A1).
7. WAN rounds with a faulty validator (L5); runs of days; networks larger than twelve validators.

This review is by the author of the prototype; an external review is needed.
