#!/usr/bin/env python3
"""Q2 箱线图 v2：定稿协议 vs 定稿+局部下降（含 α 调优）双臂对比，标注新纪录。
数据只读：final rpt / alpha_scan rpt / elite boost rpt。越界轮不计入。
输出：figures/q2_hpwl_boxplot.png + 图表/Q2/图/ 同名。
"""
import glob
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "common"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Songti SC"]
plt.rcParams["axes.unicode_minus"] = False

SIDE = {"n100": 455, "n200": 450, "n300": 561}
FINAL = os.path.join(ROOT, "q2/output/final")
ALPHA = os.path.join(ROOT, "q2/output/alpha_scan")
ELITE = os.path.join(ROOT, "q2/output/elite")


def legal_hpwls(files, side):
    out = []
    for f in files:
        lines = open(f, encoding="utf-8").read().splitlines()
        W, H = (int(x) for x in lines[3].split())
        if W <= side and H <= side:
            out.append(float(lines[1]))
    out.sort()
    return out


def main():
    arms = {}
    arms["n100_定稿"] = legal_hpwls(glob.glob(os.path.join(FINAL, "q2_n100_r*.rpt")), 455)
    arms["n100_定稿+下降"] = legal_hpwls(
        glob.glob(os.path.join(ALPHA, "q2_n100_a0.1_t270_r*.rpt")), 455)
    arms["n200_定稿"] = legal_hpwls(glob.glob(os.path.join(FINAL, "q2_n200_r*.rpt")), 450)
    arms["n200_定稿+下降"] = legal_hpwls(
        glob.glob(os.path.join(ELITE, "q2_n200_boost2_r*.rpt")), 450)
    arms["n300_定稿"] = legal_hpwls(glob.glob(os.path.join(FINAL, "q2_n300_r*.rpt")), 561)
    arms["n300_定稿+下降"] = legal_hpwls(
        glob.glob(os.path.join(ELITE, "q2_n300_boost3_r*.rpt")), 561)
    order = ["n100_定稿", "n100_定稿+下降", "n200_定稿", "n200_定稿+下降",
             "n300_定稿", "n300_定稿+下降"]
    data = [arms[k] for k in order]
    labels = [k.replace("_", " ") for k in order]
    colors = ["#8fa7c3", "#2980b9", "#8fa7c3", "#2980b9", "#8fa7c3", "#2980b9"]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_yscale("log")
    bp = ax.boxplot(data, tick_labels=labels, widths=0.45, patch_artist=True,
                    showmeans=True,
                    meanprops=dict(marker="D", mfc="white", mec="k", ms=5))
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c)
        patch.set_alpha(0.45)
    bests = {"n100_定稿+下降": 207061.5, "n300_定稿+下降": 519010.5,
             "n200_定稿": 380261.0}
    for i, k in enumerate(order, start=1):
        if k in bests and arms[k]:
            b = bests[k]
            ax.plot([i - 0.22, i + 0.22], [b, b], color="k", lw=1.6)
            ax.text(i, b * 1.1, f"best {b:,.0f}", ha="center", fontsize=9)
    ax.set_ylabel("HPWL（对数坐标，合法轮）")
    ax.set_title("Q2 多种子 HPWL 分布：定稿协议 vs 定稿+局部下降（越界轮不计入）")
    ax.grid(True, which="both", alpha=0.25)
    fig.tight_layout()
    for out in ("figures/q2_hpwl_boxplot.png", "图表/Q2/图/q2_hpwl_boxplot.png"):
        fig.savefig(os.path.join(ROOT, out), dpi=160)
        print("saved", out)
    for k in order:
        a = arms[k]
        print(k, "n=", len(a), "min=", min(a) if a else None,
              "median=", round(statistics.median(a), 1) if a else None)


if __name__ == "__main__":
    main()
