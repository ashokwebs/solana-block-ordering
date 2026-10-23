"""Generates empirical visual charts for the benchmark report."""

import os
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def generate_charts():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    summary_path = os.path.join(base_dir, "data", "raw_blocks", "benchmark_summary.json")
    assets_dir = os.path.join(base_dir, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    if not os.path.exists(summary_path):
        print(f"Summary file not found: {summary_path}")
        return

    with open(summary_path) as f:
        data = json.load(f)

    # Style configuration
    plt.style.use("dark_background")
    plt.rcParams["font.family"] = "sans-serif"

    # Chart 1: Gini Coefficient Comparison across Client Families
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    
    slots = [f"Slot {b['slot']}\n({b['client_family'].split('/')[0].strip()})" for b in data]
    ginis = [b["fee_gini_coefficient"] for b in data]
    colors = []
    for b in data:
        fam = b["client_family"]
        if "Firedancer" in fam:
            colors.append("#ec4899")  # Pink
        elif "Agave" in fam:
            colors.append("#10b981")  # Emerald
        else:
            colors.append("#3b82f6")  # Blue

    bars = ax.bar(range(len(slots)), ginis, color=colors, width=0.6, edgecolor="#374151")
    ax.set_ylim(0.8, 1.02)
    ax.set_ylabel("Gini Coefficient (Priority Fee Inequality)", fontsize=11, color="#e5e7eb")
    ax.set_title("Priority Fee Concentration Across Solana Mainnet Blocks (Gini > 0.88)", fontsize=13, color="#f9fafb", pad=12)
    ax.set_xticks(range(len(slots)))
    ax.set_xticklabels(slots, rotation=45, ha="right", fontsize=8, color="#9ca3af")
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    for bar, val in zip(bars, ginis):
        ax.text(bar.get_x() + bar.get_width()/2, val + 0.005, f"{val:.3f}", ha="center", va="bottom", fontsize=7.5, color="#f3f4f6")

    plt.tight_layout()
    chart1_path = os.path.join(assets_dir, "gini_distribution.png")
    plt.savefig(chart1_path)
    plt.close()
    print(f"Saved: {chart1_path}")

    # Chart 2: Spearman Rank Correlation Comparison
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    rhos = [b["global_correlation"]["spearman_rho"] for b in data]
    
    ax.axhline(0, color="#6b7280", linestyle="-", linewidth=1)
    bars2 = ax.bar(range(len(slots)), rhos, color=colors, width=0.6, edgecolor="#374151")
    ax.set_ylim(-0.25, 0.25)
    ax.set_ylabel("Spearman Rank Correlation (ρ)", fontsize=11, color="#e5e7eb")
    ax.set_title("Global Block Position vs Priority Fee Rate Correlation (Near Zero: ρ ≈ 0)", fontsize=13, color="#f9fafb", pad=12)
    ax.set_xticks(range(len(slots)))
    ax.set_xticklabels(slots, rotation=45, ha="right", fontsize=8, color="#9ca3af")
    ax.grid(axis="y", linestyle="--", alpha=0.3)

    for bar, val in zip(bars2, rhos):
        y_pos = val + 0.01 if val >= 0 else val - 0.02
        ax.text(bar.get_x() + bar.get_width()/2, y_pos, f"{val:+.3f}", ha="center", va="bottom", fontsize=7.5, color="#f3f4f6")

    plt.tight_layout()
    chart2_path = os.path.join(assets_dir, "fee_vs_position_correlation.png")
    plt.savefig(chart2_path)
    plt.close()
    print(f"Saved: {chart2_path}")

if __name__ == "__main__":
    generate_charts()
