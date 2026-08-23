import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "common"))

from visualize import read_rpt, draw_floorplan, save_fig
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--side", type=int, default=None, help="轮廓边长（默认取 rpt 的 W）")
    args = ap.parse_args()

    r = read_rpt(args.rpt)
    side = args.side or r["W"]
    util = None
    title = f"Q2 Floorplan  {os.path.basename(args.rpt)}  "
    title += f"outline={side}x{side}  bbox={r['W']}x{r['H']}  HPWL={r['hpwl']:.0f}"
    fig, ax = plt.subplots(figsize=(9, 9))
    draw_floorplan(ax, r["blocks"], r["W"], r["H"], title, outline=(side, side))
    save_fig(fig, args.out)


if __name__ == "__main__":
    main()
