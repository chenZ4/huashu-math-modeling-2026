"""论文补图：全问提升总览 / Q2 轮次分布 / 四问耗时对比（纯数据绘图，不跑求解器）。"""
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Songti SC"]
plt.rcParams["axes.unicode_minus"] = False

FIGS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "做图")


def save(fig, name):
    fig.savefig(os.path.join(FIGS, name), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("图 ->", os.path.join(FIGS, name))


def fig1():
    improvements = {
        "Q1 面积": [0.0, -0.40, -0.77],
        "Q2 HPWL": [-4.16, -5.71, -7.55],
        "Q3 d*": [-35.2, -22.8, -10.5],
    }
    chips = ["n100", "n200", "n300"]
    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(3)
    width = 0.25
    colors = ["#2980b9", "#27ae60", "#c0392b"]
    for i, (q, vals) in enumerate(improvements.items()):
        ax.bar(x + i * width, vals, width, label=q, color=colors[i])
        for xi, v in zip(x + i * width, vals):
            ax.text(xi, v - 1.2, f"{v:.1f}%", ha="center", fontsize=9,
                    color="white")
    ax.set_xticks(x + width)
    ax.set_xticklabels(chips)
    ax.set_ylabel("较冻结交付的变化（%）")
    ax.set_title("定稿 vs 冻结：三问提升总览（负值 = 更优）")
    ax.axhline(0, color="gray", lw=0.8)
    ax.legend()
    save(fig, "overall_improvement.png")


def fig2():
    fig, ax = plt.subplots(figsize=(8, 5))
    data, labels = [], []
    for c in ["n100", "n200", "n300"]:
        vals = []
        for f in glob.glob(f"q2/output/baseline/q2_{c}_r*.rpt"):
            try:
                vals.append(float(open(f).read().splitlines()[1]))
            except Exception:
                pass
        data.append(vals)
        labels.append(c)
    ax.boxplot(data)
    ax.set_xticklabels(labels)
    ax.set_ylabel("HPWL")
    ax.set_title("Q2 冻结版 8 轮 HPWL 分布（轮间方差 → 多起点取优的必要性）")
    save(fig, "q2_rounds_distribution.png")


def fig3():
    times = {"Q1": 31.5, "Q2": 601.4, "Q3": 3802.1, "Q4": 1.0}
    fig, ax = plt.subplots(figsize=(7, 5))
    qs = list(times.keys())
    vals = list(times.values())
    bars = ax.bar(qs, vals, color=["#2980b9", "#27ae60", "#c0392b", "#f39c12"])
    for b, v in zip(bars, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 40, f"{v:.0f}s",
                ha="center")
    ax.set_ylabel("总求解耗时（s，三芯片合计）")
    ax.set_title("四问定稿求解耗时对比")
    save(fig, "overall_runtime.png")


if __name__ == "__main__":
    os.makedirs(FIGS, exist_ok=True)
    fig1()
    fig2()
    fig3()
    print("完成")
