"""Q3 二分轨迹可视化：d 区间收缩过程 + 可行/不可行标记 + d* 标注。"""
import argparse
import csv
import os
import sys

import matplotlib.pyplot as plt

from matplotlib.patches import Rectangle


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", required=True, help="二分轨迹 CSV")
    ap.add_argument("--dstar", type=float, required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = []
    with open(args.trace) as f:
        for r in csv.DictReader(f):
            rows.append(r)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    iters = [int(r["iter"]) for r in rows]
    for r in rows:
        i = int(r["iter"])
        feasible = int(r["feasible"])
        color = "#2ca02c" if feasible else "#d62728"
        ax.add_patch(Rectangle((i - 0.35, float(r["lo"])), 0.7,
                               float(r["hi"]) - float(r["lo"]),
                               facecolor=color, alpha=0.15, edgecolor="none"))
        ax.plot([i], [float(r["mid"])], "o", color=color, markersize=4)
    ax.axhline(args.dstar, color="#0060ad", linestyle="--", linewidth=1.5,
               label=f"d* = {args.dstar:.6f}")
    ax.set_title(f"Q3 Bisection on dead-space ratio  {os.path.basename(args.trace)}")
    ax.set_xlabel("iteration")
    ax.set_ylabel("dead-space ratio d")
    ax.set_xlim(0.5, max(iters) + 0.5)
    ax.legend()
    ax.grid(True, alpha=0.3)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
