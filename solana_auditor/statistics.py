"""Statistical ordering metrics, rank correlations, and partition analysis."""

import numpy as np
from scipy import stats
from typing import Dict, Any, List
from collections import defaultdict
from .block_analyzer import ParsedBlock, ParsedTransaction


def compute_gini_coefficient(values: List[float]) -> float:
    """Calculate Gini coefficient of a distribution."""
    if not values or len(values) < 2:
        return 0.0
    arr = np.array(values, dtype=np.float64)
    if np.all(arr == 0):
        return 0.0
    arr = np.sort(arr)
    n = len(arr)
    index = np.arange(1, n + 1)
    return float((np.sum((2 * index - n - 1) * arr)) / (n * np.sum(arr)))


class BlockOrderingMetrics:
    """Computes empirical ordering metrics on a parsed block."""

    def __init__(self, block: ParsedBlock, filter_votes: bool = True):
        self.block = block
        self.filter_votes = filter_votes

        # Filter transactions
        if filter_votes:
            self.txs = [tx for tx in block.transactions if not tx.is_vote]
        else:
            self.txs = list(block.transactions)

    def calculate_global_fee_correlation(self) -> Dict[str, Any]:
        """Compute Spearman and Kendall Tau correlation between position and fee-per-CU."""
        if len(self.txs) < 5:
            return {
                "spearman_rho": 0.0,
                "spearman_pvalue": 1.0,
                "kendall_tau": 0.0,
                "kendall_pvalue": 1.0,
                "sample_size": len(self.txs)
            }

        positions = np.array([tx.index for tx in self.txs])
        fees = np.array([tx.effective_fee_per_cu for tx in self.txs])

        # If all fees are identical, correlation is zero
        if np.all(fees == fees[0]):
            return {
                "spearman_rho": 0.0,
                "spearman_pvalue": 1.0,
                "kendall_tau": 0.0,
                "kendall_pvalue": 1.0,
                "sample_size": len(self.txs)
            }

        # Negative rho means higher fees appear at earlier indices (lower index)
        rho, pval = stats.spearmanr(positions, fees)
        tau, tau_pval = stats.kendalltau(positions, fees)

        return {
            "spearman_rho": float(rho) if not np.isnan(rho) else 0.0,
            "spearman_pvalue": float(pval) if not np.isnan(pval) else 1.0,
            "kendall_tau": float(tau) if not np.isnan(tau) else 0.0,
            "kendall_pvalue": float(tau_pval) if not np.isnan(tau_pval) else 1.0,
            "sample_size": len(self.txs)
        }

    def calculate_intra_lock_correlation(self) -> Dict[str, Any]:
        """Analyze ordering within conflicting write-lock groups."""
        lock_to_txs = defaultdict(list)
        for tx in self.txs:
            for lock in tx.write_locks:
                lock_to_txs[lock].append(tx)

        # Groups with at least 3 transactions
        conflicting_groups = [txs for txs in lock_to_txs.values() if len(txs) >= 3]

        if not conflicting_groups:
            return {
                "average_intra_group_rho": 0.0,
                "conflicting_groups_analyzed": 0,
                "inversion_ratio": 0.0
            }

        rhos = []
        inversions = 0
        total_pairs = 0

        for group in conflicting_groups:
            pos = [tx.index for tx in group]
            fees = [tx.effective_fee_per_cu for tx in group]
            if len(set(fees)) > 1:
                r, _ = stats.spearmanr(pos, fees)
                if not np.isnan(r):
                    rhos.append(r)

            # Pairwise inversion count (higher fee should have lower index)
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    total_pairs += 1
                    # Inversion: earlier tx has lower fee than later tx
                    if group[i].effective_fee_per_cu < group[j].effective_fee_per_cu:
                        inversions += 1

        avg_rho = float(np.mean(rhos)) if rhos else 0.0
        inversion_ratio = (inversions / total_pairs) if total_pairs > 0 else 0.0

        return {
            "average_intra_group_rho": avg_rho,
            "conflicting_groups_analyzed": len(conflicting_groups),
            "inversion_ratio": inversion_ratio,
            "total_pairs_compared": total_pairs
        }

    def analyze_jito_bundles(self) -> Dict[str, Any]:
        """Detect Jito MEV bundles and calculate front-placement bias."""
        tip_txs = [tx for tx in self.txs if tx.is_jito_tip]
        total_non_vote = len(self.txs)

        if not tip_txs or total_non_vote == 0:
            return {
                "jito_tip_count": 0,
                "front_quartile_ratio": 0.0,
                "mean_relative_position": 0.5
            }

        rel_positions = [tx.index / total_non_vote for tx in tip_txs]
        front_quartile = sum(1 for p in rel_positions if p <= 0.25)

        return {
            "jito_tip_count": len(tip_txs),
            "front_quartile_ratio": float(front_quartile / len(tip_txs)),
            "mean_relative_position": float(np.mean(rel_positions))
        }

    def summarize(self) -> Dict[str, Any]:
        """Produce full metrics summary for block."""
        fees = [tx.effective_fee_per_cu for tx in self.txs]
        global_corr = self.calculate_global_fee_correlation()
        lock_corr = self.calculate_intra_lock_correlation()
        jito_stats = self.analyze_jito_bundles()

        return {
            "slot": self.block.slot,
            "leader_pubkey": self.block.leader_pubkey,
            "total_transactions": self.block.total_transactions,
            "vote_transactions": self.block.vote_transactions,
            "non_vote_transactions": len(self.txs),
            "fee_gini_coefficient": compute_gini_coefficient(fees),
            "mean_fee_per_cu": float(np.mean(fees)) if fees else 0.0,
            "median_fee_per_cu": float(np.median(fees)) if fees else 0.0,
            "max_fee_per_cu": float(np.max(fees)) if fees else 0.0,
            "global_correlation": global_corr,
            "intra_lock_correlation": lock_corr,
            "jito_bundle_analysis": jito_stats
        }
