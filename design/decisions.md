# Decisions: why the prototype works the way it does

Each decision below says what problem it answers, what was chosen, what was left out and why, what it changes for users and operators, and what it does not solve.

Related documents:
- **When pipelining is worth this complexity at all:** [when-pipelining-pays.md](../results/when-pipelining-pays.md).
- **The specification:** the [draft CAP](cap-draft-live-pipelining.md).
- **The risks:** the [threat review](live-pipelining-threats.md).
- **The measurements:** [throughput-current.md](../results/throughput-current.md) and [correctness-rounds.md](../results/correctness-rounds.md).

## 1. Ledger N is built on N−k, and transactions are split into classes by fee payer

**Problem.** To nominate N before N−1 has applied, the value of N must be built and checked on a ledger every validator that may vote on it already has.

**Chosen.** The tx set of N names N−k and is validated against the state and header of N−k. Each transaction belongs to the class of its fee payer, and ledger N only takes class N mod k. In the prototype the class is the first byte of the payer's public key mod k; the [draft CAP](cap-draft-live-pipelining.md) specifies a salted hash of the key instead.

**Left out:**
- **"Any recent ledger" as the base:** a leader could build on a ledger some validators have not applied yet. They cannot check the value and stay silent in that slot. On the testbed this stalled k = 4 at start-up.
- **Restricting every account a transaction touches to the payer's class:** transactions that span classes, channel accounts and sponsored payments could not enter any ledger.

**Effects:**
- A payer is charged in at most one open slot.
- A client that sends many transactions from one account gets them included in one ledger in k. Ledgers come k times as often, so its next ledger is about as far away as without pipelining: it does not wait longer, and it does not gain in latency either ([when-pipelining-pays.md](../results/when-pipelining-pays.md)). Clients with a payer account in every class (channel accounts, a fee-bump sponsor per class) use the one whose ledger comes next and wait k times less.
- Conflicts on accounts other than the payer fail at apply and are paid for, as today.

**Limits:**
- **Fee markets:** surge pricing becomes per slot, so there are k of them.
- **Choosing a class:** anyone can pick their class by generating keys. A safe rotation of the classes is left open.
- **Clients:** neither k nor the next open slot is exposed to them today (k is in the ledger header flags only). A client that knows k and the last closed ledger L can expect ledger L+k to be nominating already, and aim at L+k+1, class (L+1) mod k.

## 2. Everything about slot N is checked against N−k

**Problem.** A validator's last closed ledger (LCL) can be anywhere from N−k to N−1, and it moves while N is open. Every check that reads the LCL can give different answers on different validators, or on the same one at different times. A transaction designed to be valid on some and invalid on others could split honest validators, or silence a slot.

**Chosen.** These are all checked against N−k, never against the LCL:
- ledger bounds and the minimum sequence ledger gap;
- the cache of tx set validity;
- the format of the value;
- the lower bound of the close time;
- the base of the tx set;
- the ledger the empty-tx-set form of a value names.

A tx set of an open slot that is not built on N−k is invalid, as it is for the next ledger today.

**Effects.** Whether a value is valid is a function of the value and N−k only: the same on every node, at any time.

**Limits:**
- **Close times of consecutive values are not ordered:** N is proposed before N−1 externalizes. Apply raises a close time that does not follow the ledger before it, so the headers stay ordered. A header can then carry a close time later than the one its proposer signed, which a consumer checking that signature has to know.
- **A validator that is catching up does not have N−k.** It checks the upper bound of a close time only, and treats such values as "maybe valid", without voting on them.

## 3. k is a network parameter in the ledger, changed by an upgrade

**Problem.** Every validator must apply the same rule to the same slot. A depth read from each node's configuration can differ between nodes, and changing it needs every validator restarted at the same ledger.

**Chosen.** k is in the ledger header and changed by a network upgrade. After a change at U from k_o to k_n:
- the slots up to U + k_o − 1 keep the old rule, because they were in flight;
- later slots are built on max(N − k_n, U), because no node keeps the states before U for the new rule;
- k changes again only once no slot follows an older rule.

Upgrades only go in ledgers that are a multiple of k, and the k − 1 ledgers after one apply empty. Their values were checked under the old rules.

**Left out.** k as a configuration option of each validator.

**Effects:**
- Changing k is a vote, like any network setting.
- A node that catches up reads the rule of every ledger from the headers.
- Each upgrade costs k − 1 ledgers without transactions.

**Limits.** The prototype keeps k in bits 16 to 19 of the header flags, to avoid an XDR change. A flags upgrade replaces the whole word, so an operator who changes another flag without the k bits votes k back to 1, and no protocol version gates the bits. The CAP needs a field and an upgrade type of its own.

## 4. A fee reserve per account

**Problem.** Raised in the discussion by vendrell46. The class of the fee payer keeps it out of the other open slots, but not its balance: it can be the source of an operation, or sign a Soroban authorization, in a transaction another account pays for in another class's ledger. Its own transaction, validated against N−k, would then pay less than it bid. If that operation merges the account, fee processing finds no account and every validator stops.

**Chosen.** Following Monad's reserve balance rules, each account has a reserve R. R is a data entry the account sets (`pipeline.fee_reserve`), with a default and a minimum that are network settings in the CAP.
- **In a ledger of another class:** a transaction cannot leave the account with less native balance than min(what it held at the start, R), nor lower R. A merge holds nothing.
- **In a ledger of its class:** the account pays at most min(R, its available balance at N−k) in fees.

**Left out:**
- **A single network value:** it would cap every fee bid.
- **Locking the payer's account in other classes:** see decision 1.
- **A reserve that adapts on its own:** more complex, and not needed for the case.
- **A cap on the inclusion fee only, leaving resource fees out:** it reopens the case, because resource fees are charged up front.

**Effects:**
- **High-fee transactions:** a transaction whose total fee is above R is refused until the account raises R, and the new R counts k ledgers later. In practice this is a contract wasm upload. The default stays at 1 XLM, which covers invocations, and a deployer raises its reserve first. Deployment tools should do it, and the refusal should say why (today it is a plain `txINSUFFICIENT_BALANCE`).
- **Spending in other classes:** in a ledger of another class, an account cannot spend its last R.

**Limits.** The right default should come from the distribution of fees on mainnet, which was not measured here.

## 5. Which slots a validator handles

**Problem.** With k slots open, a validator must not vote on, or emit statements for, a slot it cannot check. During a change of k, the depth is not the number of slots a validator can check. And a validator that is catching up does not have N−k for any slot but the next.

In an early round, a catching-up validator's ballot timer fired for a later slot. It emitted a statement it then judged invalid, and the process exited.

**Chosen.** A slot is open when its base is at or below the validator's LCL. That rule alone decides which slots SCP is handed, which are current for validation, and whose timers run. A validator that is catching up handles the next slot only, as upstream does.

**Effects.** No statement of a validator's own can be invalid for it.

**Limits.** A catching-up validator does not take part in the later slots until it has caught up.

## 6. Limits counted in ledgers are scaled with the ledger rate

**Problem.** stellar-core keeps envelopes for up to 100 slots ahead of the next one: 500 s at 5 s ledgers, 20 s at 200 ms. A catchup takes longer than that at four ledgers per second. A restarted validator then followed an old slot, dropped on arrival the envelopes of the current ones, lost track again, and in 5 of 16 test rounds had not rejoined three minutes after its restart.

**Chosen.** With pipelining, or while catching up, the bracket covers the ledgers of 120 s at the target close time, between 100 and 1,200 slots. With pipelining off and the node synced it is 100, as upstream.

**Left out:**
- **A bracket in wall-clock time:** it would grow while the network is stalled.
- **Upstream's 500 s:** 2,500 slots at 200 ms, five times the envelopes per sender for no gain. The rounds rejoined the same with 120 s.

**Effects.** The restarted validator rejoined in 16 of 16 rounds.

**Limits.** Other limits are still counted in ledgers:
- the slots a peer sends on request (12);
- the apply drift (12);
- the checkpoint an online catchup waits for (64 ledgers);
- the SCP timeouts (1 s), sized for 5 s ledgers.

The CAP should define them in time.

## 7. Restarts keep the states the next slots are checked against

**Problem.** After a restart a validator needs the states of the k − 1 ledgers before its LCL to check and propose the open slots. Without them a restart of every validator halts the network.

**Chosen:**
- **States:** each ledger stores its header and bucket list hashes, and they are rebuilt at start from buckets kept on disk.
- **SCP state:** every open slot persists its SCP state, in rows sized for the largest k.
- **Pending slots:** slots externalized and not applied before a stop are delivered again after the start.

**Effects.** On the testbed, killing every validator at once under load, or stopping them cleanly, resumed without catchup at k = 2 to 5.

**Limits.** One more row is written with each ledger. Its cost on a real disk, one SSD per validator, was not measured: the shared disk of the testbed is not representative.

## 8. Catchup without knowing k

**Problem:**
- A node that catches up cannot know the network's k before it has the headers, and k may have changed while it was away. The trusted hash of an online catchup comes from a buffered tx set k − 1 ledgers after the first buffered one.
- A catchup that applies buckets has none of the k − 1 states before its target.

**Chosen:**
- **Trusted hash:** the verification accepts the previous ledger hash of any of the first twelve buffered tx sets. A header hashes its own sequence number, so the hash of another ledger cannot match. An attempt that starts before the right tx set is buffered is retried quietly.
- **States:** a catchup replays at least k − 1 ledgers before its target.
- **Replay:** it reads the rule and the protocol of each ledger from the headers.

**Effects.** A new node, or one away across a change of k, joins online.

## 9. Which k, and when

**Choice.** k = ⌈(C + E + S) / L⌉ for a target close time L, where C, E and S are the times of consensus, execution and completion. Beyond that k only adds latency.

**Why.** Against today's protocol the gain stops where the interval reaches the apply time, at k = 4 to 5 on the testbed ([testbed-results.md](../results/testbed-results.md), [throughput-current.md](../results/throughput-current.md)). Against the planned overlap of consensus and apply the choice is narrower, and for mainnet in the medium term k = 1 with the overlap is the better one ([when-pipelining-pays.md](../results/when-pipelining-pays.md)).

k is a network vote, not an automatic setting, so it cannot follow the load from minute to minute.

## What is not solved

- **Apply is still sequential.** It sets the ceiling, whatever k is, and the planned overlap has the same one ([when-pipelining-pays.md](../results/when-pipelining-pays.md)). Pipelining moves the bottleneck to apply; parallel apply is a separate piece of work that would add to it.
- **Leaders are predictable,** as they are today: pipelining does not make them known earlier ([threat review](live-pipelining-threats.md), L2). With ledgers shorter than a nomination timeout, a DoS on them costs more per hit. Several leaders per round and shorter nomination timeouts reduce that cost; a VRF for leader priority is the follow-up.
- **Latency grows somewhat with k** for a client that pays from a single account, and more when k is deeper than apply allows ([testbed-results.md](../results/testbed-results.md), decision 1).
- **Not tested here:**
  - real disks;
  - networks larger than twelve validators;
  - runs of days;
  - a malicious validator in the WAN rounds (only in unit tests);
  - a full mainnet history replay with pipelining on.
