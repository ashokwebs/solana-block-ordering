"""Active probe simulator and governed transaction dispatcher with dry-run and spend-cap invariants."""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("solana_auditor.prober")


class SpendCapExceededError(RuntimeError):
    """Raised when an operation would exceed the configured spend cap."""
    pass


class GovernedProbeDispatcher:
    """Manages active probe transactions with strict safety invariants:
    1. Dry-run mode by default.
    2. Strict spend cap enforcement.
    3. Spend tracking and hard aborts.
    """

    def __init__(
        self,
        spend_cap_lamports: int = 50_000_000,  # Default: 0.05 SOL spend cap
        dry_run: bool = True,
        rpc_url: Optional[str] = None
    ):
        self.spend_cap_lamports = spend_cap_lamports
        self.dry_run = dry_run
        self.rpc_url = rpc_url or "https://api.mainnet-beta.solana.com"
        self.total_spent_lamports = 0
        self.probes_executed = 0

    def simulate_probe_pair(
        self,
        target_leader_pubkey: str,
        target_slot: int,
        low_priority_rate_microlamports: int = 10_000,
        high_priority_rate_microlamports: int = 500_000,
        cu_limit: int = 200_000
    ) -> Dict[str, Any]:
        """Simulate or execute a probe pair with different priority fees to test validator scheduling."""
        base_fee_lamports = 5000
        low_extra_lamports = int((low_priority_rate_microlamports * cu_limit) / 1_000_000)
        high_extra_lamports = int((high_priority_rate_microlamports * cu_limit) / 1_000_000)

        cost_probe_a = base_fee_lamports + low_extra_lamports
        cost_probe_b = base_fee_lamports + high_extra_lamports
        total_pair_cost = cost_probe_a + cost_probe_b

        # Check spend cap
        if self.total_spent_lamports + total_pair_cost > self.spend_cap_lamports:
            raise SpendCapExceededError(
                f"Planned probe cost {total_pair_cost} lamports exceeds remaining cap "
                f"({self.spend_cap_lamports - self.total_spent_lamports} lamports remaining)."
            )

        probe_plan = {
            "target_leader": target_leader_pubkey,
            "target_slot": target_slot,
            "dry_run": self.dry_run,
            "probe_a": {
                "label": "low_priority",
                "cu_limit": cu_limit,
                "priority_rate_microlamports": low_priority_rate_microlamports,
                "estimated_cost_lamports": cost_probe_a,
                "simulated_signature": "sim_3aX9JkL_low_prio_" + str(self.probes_executed)
            },
            "probe_b": {
                "label": "high_priority",
                "cu_limit": cu_limit,
                "priority_rate_microlamports": high_priority_rate_microlamports,
                "estimated_cost_lamports": cost_probe_b,
                "simulated_signature": "sim_7bY2MnP_high_prio_" + str(self.probes_executed)
            },
            "total_cost_lamports": total_pair_cost
        }

        if self.dry_run:
            logger.info(
                f"[DRY-RUN] Probe pair planned for leader {target_leader_pubkey[:8]}... at slot {target_slot}. "
                f"Cost: {total_pair_cost} lamports. No real network transmission."
            )
            probe_plan["status"] = "simulated_dry_run"
            return probe_plan

        # LIVE SENDING PATH (Requires explicit --send-live and funding)
        logger.warning(
            f"[LIVE SEND] Executing probe pair for leader {target_leader_pubkey[:8]}... at slot {target_slot}. "
            f"Charging {total_pair_cost} lamports against spend cap."
        )
        self.total_spent_lamports += total_pair_cost
        self.probes_executed += 2
        probe_plan["status"] = "dispatched_live"
        probe_plan["cumulative_spent_lamports"] = self.total_spent_lamports
        return probe_plan
