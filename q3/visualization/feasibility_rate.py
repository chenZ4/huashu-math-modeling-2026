#!/usr/bin/env python3
"""P1-2: Q3 最小可行死区比例 —— 逐种子可行率曲线。
数据源: q3/output/final/q3_metrics.csv（confirm_steps 列，逐 d 逐种子布尔数组）。
输出: 图表/Q3/图/q3_feasibility_rate.png + 图表/Q3/表/q3_feasibility_rate.csv
"""
import ast
import csv
import os
from collections import OrderedDict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Songti SC"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
METRICS = os.path.join(ROOT, "q3/output/final/q3_metrics.csv")
OUT_PNG = os.path.join(ROOT, "图表/Q3/图/q3_feasibility_rate.png")
OUT_CSV = os.path.join(ROOT, "图表/Q3/表/q3_feasibility_rate.csv")
SEEDS = {"n100": 15, "n200": 15, "n300": 10}

chip_data = {}
with open(METRICS) as f:
    reader = csv.DictReader(f)
    for row in reader:
        chip = row["chip"]
        d_star = float(row["d_star"])
        steps = ast.literal_eval(row["confirm_steps"])
        # 每个候选 d 的逐种子可行性（取最后一次记录，跳过 up-shift 重试的中间态）
        rate_at = OrderedDict()
        for e in steps:
            if "below" in e and "below_results" in e:
                d = float(e["below"])
                rs = e["below_results"]
                rate_at[d] = (sum(bool(v) for v in rs), len(rs))
        chip_data[chip] = {"d_star": d_star, "rate_at": rate_at}

os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)

colors = {"n100": "#2980b9", "n200": "#27ae60", "n300": "#c0392b"}
fig, ax = plt.subplots(figsize=(8, 5.5))
csv_rows = []
for chip, info in chip_data.items():
    ds, rates = [], []
    for d, (hit, n) in info["rate_at"].items():
        ds.append(d)
        rates.append(hit / n * 100)
        csv_rows.append({"chip": chip, "d": d, "seeds": n,
                         "feasible_hits": hit, "rate_pct": round(hit / n * 100, 1)})
    order = sorted(range(len(ds)), key=lambda i: ds[i])
    ds = [ds[i] for i in order]
    rates = [rates[i] for i in order]
    ax.plot(ds, rates, "o-", color=colors[chip], label=f"{chip}（{SEEDS[chip]} 种子/判定）")
    ax.axvline(info["d_star"], color=colors[chip], ls="--", lw=0.9, alpha=0.7)
    ax.text(info["d_star"], 2, f"$d^*$={info['d_star']:.4f}", rotation=90,
            va="bottom", ha="right", fontsize=8, color=colors[chip])
ax.axhline(0, color="gray", lw=0.6)
ax.set_xlabel("死区比例 $d$")
ax.set_ylabel("可行率（%，逐种子判定）")
ax.set_title("Q3 临界死区比例附近的多种子可行率（双向确认数据）")
ax.grid(True, alpha=0.3)
ax.legend(fontsize=9)
fig.tight_layout()
fig.savefig(OUT_PNG, dpi=160)
print("saved", OUT_PNG)

with open(OUT_CSV, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["chip", "d", "seeds", "feasible_hits", "rate_pct"])
    w.writeheader()
    w.writerows(csv_rows)
print("saved", OUT_CSV)
for r in csv_rows:
    print(r)
