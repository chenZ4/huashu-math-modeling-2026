#!/usr/bin/env python3
"""P1-1: 定稿协议 Q2 多种子 HPWL 箱线图 + 统计表。
数据源: q2/output/final/q2_<chip>_r*.rpt（16/24/24 轮，越界轮单列）。
输出: 图表/Q2/图/q2_hpwl_boxplot.png + 图表/Q2/表/q2_hpwl_stats.csv
"""
import csv
import glob
import os
import statistics as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Songti SC"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
FINAL = os.path.join(ROOT, "q2/output/final")
OUT_PNG = os.path.join(ROOT, "图表/Q2/图/q2_hpwl_boxplot.png")
OUT_CSV = os.path.join(ROOT, "图表/Q2/表/q2_hpwl_stats.csv")
SIDE = {"n100": 455, "n200": 450, "n300": 561}
N_RUNS = {"n100": 16, "n200": 24, "n300": 24}

rows = []
for chip, side in SIDE.items():
    legal, illegal = [], []
    for r in range(N_RUNS[chip]):
        fp = os.path.join(FINAL, f"q2_{chip}_r{r}.rpt")
        if not os.path.exists(fp):
            continue
        with open(fp) as f:
            lines = f.read().splitlines()
        hpwl = float(lines[1])
        W, H = (int(x) for x in lines[3].split())
        (legal if (W <= side and H <= side) else illegal).append(hpwl)
    legal.sort()
    spread = (legal[-1] - legal[0]) / legal[0] * 100
    rows.append({
        "chip": chip, "n_runs": len(legal) + len(illegal),
        "n_legal": len(legal), "n_illegal": len(illegal),
        "min": legal[0], "median": st.median(legal), "mean": round(st.mean(legal), 1),
        "max": legal[-1], "std": round(st.pstdev(legal), 1),
        "spread_pct": round(spread, 1),
        "med_min_ratio": round(st.median(legal) / legal[0], 2),
    })

os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

fig, ax = plt.subplots(figsize=(8, 5.5))
labels = []
legal_data, illegal_data = [], []
for chip, side in SIDE.items():
    leg, ill = [], []
    for r in range(N_RUNS[chip]):
        fp = os.path.join(FINAL, f"q2_{chip}_r{r}.rpt")
        if not os.path.exists(fp):
            continue
        with open(fp) as f:
            lines = f.read().splitlines()
        hpwl = float(lines[1])
        W, H = (int(x) for x in lines[3].split())
        (leg if (W <= side and H <= side) else ill).append(hpwl)
    labels.append(chip)
    legal_data.append(leg)
    illegal_data.append(ill)

ax.set_yscale("log")
bp = ax.boxplot(legal_data, tick_labels=labels, widths=0.5, patch_artist=True,
                showmeans=True, meanprops=dict(marker="D", mfc="white", mec="k", ms=5))
colors = ["#2980b9", "#27ae60", "#c0392b"]
for patch, c in zip(bp["boxes"], colors):
    patch.set_facecolor(c)
    patch.set_alpha(0.45)
for i, ill in enumerate(illegal_data, start=1):
    if ill:
        ax.scatter([i] * len(ill), ill, marker="x", color="k", s=55, zorder=5,
                   label="越界轮（未收敛进轮廓）" if i == 2 else None)
best = [min(d) for d in legal_data]
for i, b in enumerate(best, start=1):
    ax.plot([i - 0.25, i + 0.25], [b, b], color="k", lw=1.6)
    ax.text(i, b * 1.13, f"best {b:.0f}", ha="center", fontsize=9)
ax.set_xlabel("实例")
ax.set_ylabel("HPWL（对数坐标）")
ax.set_title("Q2 定稿协议多种子 HPWL 分布（t2-div 35/60/70；越界轮不计入统计）")
ax.legend(loc="lower left", fontsize=9)
ax.grid(True, which="both", alpha=0.25)
fig.tight_layout()
fig.savefig(OUT_PNG, dpi=160)
print("saved", OUT_PNG)

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print("saved", OUT_CSV)
for r in rows:
    print(r)
