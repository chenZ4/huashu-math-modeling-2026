"""Q4 最优摆放示意图：分解矩形绘制 + 模块/旋转角/尺寸标注。"""
import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
COLORS = {"b1": "#1f77b4", "b2": "#ff7f0e", "b3": "#2ca02c", "b4": "#d62728"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True, help="q4_result.csv")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = []
    with open(args.csv) as f:
        for r in csv.DictReader(f):
            if r.get("module") and r["module"] in COLORS:
                rows.append(r)

    fig, ax = plt.subplots(figsize=(9, 9))
    for r in rows:
        name = r["module"]
        rot = int(r["rotation_deg"])
        x0, y0 = int(r["x"]), int(r["y"])
        color = COLORS[name]
        rects = []
        for part in r["rects"].split(";"):
            rx, ry, rw, rh = map(int, part.split(","))
            rects.append((rx, ry, rw, rh))
            ax.add_patch(Rectangle((x0 + rx, y0 + ry), rw, rh,
                                   facecolor=color, edgecolor="black",
                                   linewidth=1.0, alpha=0.85, zorder=2))
        w = max(rx + rw for rx, ry, rw, rh in rects)
        h = max(ry + rh for rx, ry, rw, rh in rects)
        cx = x0 + w / 2.0
        cy = y0 + h / 2.0
        ax.text(cx, cy, f"{name}  {rot}\N{DEGREE SIGN}", fontsize=11,
                ha="center", va="center", fontweight="bold", zorder=3,
                bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="none",
                          alpha=0.8))

    maxx = max(int(r["x"]) + 4 for r in rows)
    maxy = 0
    for r in rows:
        for part in r["rects"].split(";"):
            rx, ry, rw, rh = map(int, part.split(","))
            maxy = max(maxy, int(r["y"]) + ry + rh)
    ax.add_patch(Rectangle((0, 0), maxx, maxy, fill=False,
                           edgecolor="red", linewidth=1.5, linestyle="--",
                           zorder=1))
    ax.set_xlim(-0.5, maxx + 0.5)
    ax.set_ylim(-0.5, maxy + 0.5)
    ax.set_aspect("equal")
    ax.set_title(f"Q4 Optimal Placement  area={maxx}x{maxy}={maxx*maxy} "
                 f"(= total area lower bound, provably optimal)",
                 fontsize=12)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(True, alpha=0.2)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    fig.savefig(args.out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print("figure ->", args.out)


if __name__ == "__main__":
    main()
