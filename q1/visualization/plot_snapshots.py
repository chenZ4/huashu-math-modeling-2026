"""Q1 SA 过程快照可视化：解析 log 中的 9 个 checkpoint，逐张绘制布图。"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "common"))

from visualize import read_snapshots, draw_floorplan, save_fig
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True, help="收敛 log 文件（含 snap 段）")
    ap.add_argument("--outdir", required=True, help="输出目录")
    ap.add_argument("--total-layers", type=int, default=None,
                    help="总温度层数（用于进度标注），默认取最后收敛行 iter")
    args = ap.parse_args()

    snaps = read_snapshots(args.log)
    if not snaps:
        print(f"no snapshots in {args.log}", file=sys.stderr)
        sys.exit(1)
    snaps = snaps[-9:]
    os.makedirs(args.outdir, exist_ok=True)
    for k, iter_no, W, H, blocks in snaps:
        title = (f"Q1 SA snapshot {k}/9  layer={iter_no}  size={W}x{H}")
        fig, ax = plt.subplots(figsize=(7, 7))
        draw_floorplan(ax, blocks, W, H, title, annotate=False)
        save_fig(fig, os.path.join(args.outdir, f"snap_{k:02d}.png"))


if __name__ == "__main__":
    main()
