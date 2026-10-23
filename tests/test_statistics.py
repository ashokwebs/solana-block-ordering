"""Unit tests for statistical ordering metrics."""

import pytest
from solana_auditor.block_analyzer import ParsedBlock, ParsedTransaction
from solana_auditor.statistics import BlockOrderingMetrics, compute_gini_coefficient


def test_gini_coefficient():
    """Verify Gini coefficient on equal vs unequal distributions."""
    # Equal distribution has Gini 0.0
    assert compute_gini_coefficient([100.0, 100.0, 100.0, 100.0]) == 0.0
    # Unequal distribution has positive Gini
    gini = compute_gini_coefficient([0.0, 0.0, 0.0, 1000.0])
    assert gini > 0.5


def test_block_metrics_correlation():
    """Verify Spearman correlation correctly flags priority ordering."""
    # Create block with strictly descending priority fees (index 0 highest fee)
    txs = [
        ParsedTransaction(
            index=i,
            signature=f"sig_{i}",
            fee_lamports=5000 + (100 - i) * 1000,
            compute_units_consumed=10000,
            compute_unit_limit=200000,
            priority_fee_micro_lamports=(100 - i) * 1000,
            effective_fee_per_cu=float((100 - i) * 100),
            write_locks={"shared_lock"}
        )
        for i in range(10)
    ]

    block = ParsedBlock(
        slot=100,
        block_time=1792745000,
        leader_pubkey="leader_pubkey",
        total_transactions=10,
        vote_transactions=0,
        non_vote_transactions=10,
        transactions=txs
    )

    metrics = BlockOrderingMetrics(block)
    summary = metrics.summarize()

    # Index 0..9 and Fee 10000..1000 -> Spearman rho should be -1.0
    assert summary["global_correlation"]["spearman_rho"] == pytest.approx(-1.0)
    assert summary["global_correlation"]["kendall_tau"] == pytest.approx(-1.0)

    # Inversion ratio should be 0.0 (no inversions)
    assert summary["intra_lock_correlation"]["inversion_ratio"] == 0.0
