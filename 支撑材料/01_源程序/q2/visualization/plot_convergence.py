import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "common"))

from visualize import read_log, save_fig
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = read_log(args.log)
    colors = {"run": "#0060ad", "run2": "#d62728"}
    fig, ax = plt.subplots(figsize=(9, 5))
    for phase in ("run", "run2"):
        pts = [(r[1], r[3]) for r in rows if r[0] == phase]
        if pts:
            xs, ys = zip(*pts)
            ax.plot(xs, ys, "-", color=colors.get(phase, "gray"),
                    linewidth=1.2, label=f"phase {phase}")
    ax.set_title(f"Q2 SA Convergence  {os.path.basename(args.log)}  ({len(rows)} layers)")
    ax.set_xlabel("temperature layer")
    ax.set_ylabel("best cost (normalized)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save_fig(fig, args.out)


if __name__ == "__main__":
    main()
