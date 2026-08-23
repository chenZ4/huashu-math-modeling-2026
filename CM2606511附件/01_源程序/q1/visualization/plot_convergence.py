import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "common"))

from visualize import read_log, draw_convergence, save_fig
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, help="收敛 log 文件")
    ap.add_argument("--out", required=True, help="输出 PNG 路径")
    args = ap.parse_args()

    rows = read_log(args.log)
    title = f"Q1 SA Convergence  {os.path.basename(args.log)}  ({len(rows)} layers)"
    fig, ax = plt.subplots(figsize=(9, 5))
    draw_convergence(ax, rows, title)
    save_fig(fig, args.out)


if __name__ == "__main__":
    main()
