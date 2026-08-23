#!/usr/bin/env python3
"""M5: 解析臂 vs 随机臂汇总（对比表 CSV + 箱线图 PNG）。
只读既有数据（final rpt + analytic_init rpt），不重跑。
"""
import csv
import glob
import json
import os
import re
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
N_RAND = {"n100": 16, "n200": 24, "n300": 24}
OUT = os.path.join(ROOT, "q2", "output", "analytic_init")
BEST_KEYS = {"n100": "xy", "n200": "xy", "n300": "y"}


def load(chip, kind):
    legal = []
    if kind == "rand":
        files = glob.glob(os.path.join(
            ROOT, "q2/output/final", f"q2_{chip}_r*.rpt"))
    else:
        files = glob.glob(os.path.join(
            OUT, f"q2_{chip}_{kind}_r*.rpt"))
    for fp in files:
        lines = open(fp, encoding="utf-8").read().splitlines()
        hpwl = float(lines[1])
        W, H = (int(x) for x in lines[3].split())
        if W <= SIDE[chip] and H <= SIDE[chip]:
            legal.append(hpwl)
    legal.sort()
    return legal


def main():
    rows = []
    for chip in ["n100", "n200", "n300"]:
        rand = load(chip, "rand")
        rows.append([chip, "rand(定稿)", len(rand), rand[0],
                     statistics.median(rand), rand[-1],
                     round((rand[-1] - rand[0]) / rand[0] * 100, 1)])
        for key in ["x", "y", "xy"]:
            a = load(chip, key)
            if not a:
                continue
            rows.append([chip, f"analytic({key})", len(a), a[0],
                         statistics.median(a), a[-1],
                         round((a[-1] - a[0]) / a[0] * 100, 1)])
    csv_path = os.path.join(OUT, "summary_q2.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chip", "arm", "n_legal", "min", "median", "max",
                    "spread_pct"])
        w.writerows(rows)
    print("saved", csv_path)
    for r in rows:
        print(r)

    # 箱线图：随机 vs 最优解析键
    fig, ax = plt.subplots(figsize=(9, 5))
    data, labels = [], []
    for chip in ["n100", "n200", "n300"]:
        data.append(load(chip, "rand"))
        labels.append(f"{chip}\n随机")
        data.append(load(chip, BEST_KEYS[chip]))
        labels.append(f"{chip}\n解析({BEST_KEYS[chip]})")
    ax.boxplot(data, tick_labels=labels, widths=0.5)
    ax.set_ylabel("HPWL（合法轮）")
    ax.set_title("Q2 解析初始臂 vs 随机臂（定稿协议）")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    png = os.path.join(OUT, "summary_q2_boxplot.png")
    fig.savefig(png, dpi=150)
    print("saved", png)


if __name__ == "__main__":
    main()
