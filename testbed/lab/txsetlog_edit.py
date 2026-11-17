"""Measurement-only logging of tx set fetch, arrival, validation and build (pipelining study).

Run from the root of a stellar-core-fix copy. Adds PipelineLive lines on the Herder partition,
INFO level, with steady-clock times (comparable across the testbed nodes, which share one host).
"""
import sys


def edit(path, old, new, count=1):
    s = open(path).read()
    if s.count(old) != count:
        sys.exit(f"{path}: expected {count} match(es), found {s.count(old)}:\n{old}")
    open(path, "w").write(s.replace(old, new))


CLOCK = """
// Pipelining study: steady-clock time for the tx set log lines.
static int64_t
txSetLogNs()
{
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}
"""

# 1. PendingEnvelopes: a tx set hash first requested, and a tx set arriving.
p = "src/herder/PendingEnvelopes.cpp"
edit(p, '#include <xdrpp/marshal.h>\n', '#include <xdrpp/marshal.h>\n#include <chrono>\n')
edit(p, "\nbool\nPendingEnvelopes::recvTxSet(", CLOCK + "\nbool\nPendingEnvelopes::recvTxSet(")
edit(p, """    addTxSet(hash, lastSeenSlotIndex, txset);

    // Update any ValueWrappers""", """    CLOG_INFO(Herder,
              "PipelineLive event=txset_recv slot={} hash={} txs={} bytes={} "
              "t_ns={}",
              lastSeenSlotIndex, hexAbbrev(hash), txset->sizeTxTotal(),
              txset->encodedSize(), txSetLogNs());
    addTxSet(hash, lastSeenSlotIndex, txset);

    // Update any ValueWrappers""")
edit(p, """        if (!hasTxSet(h2))
        {
            mTxSetFetcher.fetch(h2, envelope);""", """        if (!hasTxSet(h2))
        {
            if (mTxSetFetcher.getLastSeenSlotIndex(h2) == 0)
            {
                CLOG_INFO(Herder,
                          "PipelineLive event=txset_fetch slot={} hash={} "
                          "t_ns={}",
                          envelope.statement.slotIndex, hexAbbrev(h2),
                          txSetLogNs());
            }
            mTxSetFetcher.fetch(h2, envelope);""")

# 2. HerderSCPDriver: each tx set validation that is not a cache hit.
p = "src/herder/HerderSCPDriver.cpp"
edit(p, '#include "xdr/Stellar-ledger-entries.h"\n',
     '#include "xdr/Stellar-ledger-entries.h"\n#include <chrono>\n')
edit(p, "\nbool\nHerderSCPDriver::checkAndCacheTxSetValid(",
     CLOCK + "\nbool\nHerderSCPDriver::checkAndCacheTxSetValid(")
edit(p, """        ZoneNamedN(txSetValidityMissZone, "txset validity cache miss", true);
        auto validationTime = mSCPMetrics.mTxSetValidation.TimeScope();
""", """        ZoneNamedN(txSetValidityMissZone, "txset validity cache miss", true);
        auto validationTime = mSCPMetrics.mTxSetValidation.TimeScope();
        auto const studyStart = txSetLogNs();
""")
edit(p, """        if (buildsOn || mLedgerManager.pipelineDepth(ledgerSeq) < 2)
        {
            mTxSetValidCache.put(key, res);
        }
        return res;""", """        if (buildsOn || mLedgerManager.pipelineDepth(ledgerSeq) < 2)
        {
            mTxSetValidCache.put(key, res);
        }
        auto const studyEnd = txSetLogNs();
        CLOG_INFO(Herder,
                  "PipelineLive event=txset_check ledger={} hash={} txs={} "
                  "valid={} t_ns={} dur_ns={}",
                  ledgerSeq, hexAbbrev(txSet.getContentsHash()),
                  txSet.sizeTxTotal(), res, studyStart, studyEnd - studyStart);
        return res;""")

# 3. HerderImpl: the leader building its tx set.
p = "src/herder/HerderImpl.cpp"
edit(p, """    auto [proposedSet, applicableProposedSet] = makeTxSetFromTransactions(
        txPhases, mApp, closeTimeOffset, invalidTxPhases);
""", """    auto const studyBuildStart = pipelineLogNs();
    auto [proposedSet, applicableProposedSet] = makeTxSetFromTransactions(
        txPhases, mApp, closeTimeOffset, invalidTxPhases);
    CLOG_INFO(Herder,
              "PipelineLive event=txset_build ledger={} hash={} txs={} bytes={} "
              "t_ns={} dur_ns={}",
              ledgerSeqToTrigger, hexAbbrev(proposedSet->getContentsHash()),
              proposedSet->sizeTxTotal(), proposedSet->encodedSize(),
              studyBuildStart, pipelineLogNs() - studyBuildStart);
""")
print("edits applied")
