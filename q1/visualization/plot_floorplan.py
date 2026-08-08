"""Q1 布图可视化：读取 output/*.rpt 绘制摆放结果图。"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "common"))

from visualize import read_rpt, draw_floorplan, save_fig
import matplotlib.pyplot as plt


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rpt", required=True, help=".rpt 文件")
    ap.add_argument("--out", required=True, help="输出 PNG 路径")
    ap.add_argument("--outline", type=int, nargs=2, default=None,
                    help="可选：轮廓 (W H) 用虚线框标注")
    args = ap.parse_args()

    r = read_rpt(args.rpt)
    aspect = max(r["W"], r["H"]) / min(r["W"], r["H"])
    util = None
    title = f"Q1 Floorplan  {os.path.basename(args.rpt)}  "
    title += f"size={r['W']}x{r['H']}  area={r['area']}  aspect={aspect:.3f}"
    fig, ax = plt.subplots(figsize=(9, 9))
    draw_floorplan(ax, r["blocks"], r["W"], r["H"], title,
                   outline=tuple(args.outline) if args.outline else None)
    save_fig(fig, args.out)


if __name__ == "__main__":
    main()
