"""Unit tests for governed probe dispatcher safety invariants."""

import pytest
from solana_auditor.prober import GovernedProbeDispatcher, SpendCapExceededError


def test_prober_dry_run_invariant():
    """Verify prober defaults to dry-run and generates simulated plans without spending."""
    prober = GovernedProbeDispatcher(spend_cap_lamports=1000000, dry_run=True)
    plan = prober.simulate_probe_pair(
        target_leader_pubkey="TestLeader1111111111111111111111111111111111",
        target_slot=500000
    )
    assert plan["dry_run"] is True
    assert plan["status"] == "simulated_dry_run"
    assert prober.total_spent_lamports == 0


def test_prober_spend_cap_enforcement():
    """Verify prober strictly rejects transactions that exceed the configured spend cap."""
    # Spend cap is 10,000 lamports (less than single pair cost of ~112,000 lamports)
    tiny_cap_prober = GovernedProbeDispatcher(spend_cap_lamports=10000, dry_run=True)
    with pytest.raises(SpendCapExceededError) as exc_info:
        tiny_cap_prober.simulate_probe_pair(
            target_leader_pubkey="TestLeader1111111111111111111111111111111111",
            target_slot=500000
        )
    assert "exceeds remaining cap" in str(exc_info.value)
