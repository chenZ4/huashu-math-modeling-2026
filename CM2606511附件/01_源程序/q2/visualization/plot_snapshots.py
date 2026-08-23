import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "common"))

from visualize import read_snapshots, draw_floorplan, save_fig
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--outdir", required=True)
    args = ap.parse_args()

    snaps = read_snapshots(args.log)
    if not snaps:
        print(f"no snapshots in {args.log}", file=sys.stderr)
        sys.exit(1)
    snaps = snaps[-9:]
    os.makedirs(args.outdir, exist_ok=True)
    for k, iter_no, W, H, blocks in snaps:
        title = f"Q2 SA snapshot {k}/9  layer={iter_no}  size={W}x{H}"
        fig, ax = plt.subplots(figsize=(7, 7))
        draw_floorplan(ax, blocks, W, H, title, annotate=False)
        save_fig(fig, os.path.join(args.outdir, f"snap_{k:02d}.png"))


if __name__ == "__main__":
    main()
