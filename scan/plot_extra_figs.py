"""论文补图：全问提升总览 / Q2 轮次分布 / 四问耗时对比（纯数据绘图，不跑求解器）。"""
import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Songti SC"]
plt.rcParams["axes.unicode_minus"] = False

FIG_OVERALL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "图表", "公共", "总体结论")
FIG_Q2 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "图表", "Q2", "图")


def save(fig, name, d=None):
    out = d or (FIG_OVERALL if name.startswith("overall") else FIG_Q2)
    fig.savefig(os.path.join(out, name), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("图 ->", os.path.join(out, name))


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


def fig4():
    """Q2 多种子求解总 HPWL：final 定稿协议各轮 HPWL（可行/越界区分，标注 best）。"""
    side = {"n100": 455, "n200": 450, "n300": 561}
    colors = {"n100": "#2980b9", "n200": "#27ae60", "n300": "#c0392b"}
    fig, ax = plt.subplots(figsize=(8, 5.5))
    for chip in ["n100", "n200", "n300"]:
        n = 16 if chip == "n100" else 24
        xs, ys, bad_x, bad_y = [], [], [], []
        for r in range(n):
            path = f"q2/output/final/q2_{chip}_r{r}.rpt"
            try:
                lines = open(path).read().splitlines()
                hpwl = float(lines[1])
                W, H = map(int, lines[3].split())
            except Exception:
                continue
            if W <= side[chip] and H <= side[chip]:
                xs.append(r)
                ys.append(hpwl)
            else:
                bad_x.append(r)
                bad_y.append(hpwl)
        ax.plot(xs, ys, "o-", color=colors[chip], label=f"{chip}（可行轮）")
        if bad_x:
            ax.plot(bad_x, bad_y, "o", mfc="none", mec=colors[chip],
                    ms=7, label=f"{chip}（越界轮）")
        if ys:
            b = min(zip(ys, xs))
            ax.annotate(f"best {b[0]:.0f}（轮 {b[1]}）", xy=(b[1], b[0]),
                        xytext=(b[1], b[0] * 0.45),
                        arrowprops=dict(arrowstyle="->", color="black", lw=0.8),
                        fontsize=9)
    ax.set_xlabel("独立随机种子（轮次）")
    ax.set_ylabel("HPWL")
    ax.set_title("Q2 多种子快速模拟退火求解结果（定稿协议各轮 HPWL）")
    ax.legend(fontsize=9)
    fig.tight_layout()
    save(fig, "q2_multiseed_hpwl.png", FIG_Q2)


if __name__ == "__main__":
    os.makedirs(FIG_OVERALL, exist_ok=True)
    os.makedirs(FIG_Q2, exist_ok=True)
    fig1()
    fig2()
    fig3()
    fig4()
    print("完成")
