"""Q1 灵敏度分析：聚合 scan/results/q1 现成扫描数据，输出 S 系列 CSV + 图 + 报告。

维度：
  S1. λ 权重灵敏度   —— 面积/长宽比随 λ 变化（n100/n200 11 点 + n300 6 点）
  S2. 轮次收敛灵敏度 —— best 面积随 repeats 变化（4/8/12/16/24）
  S3. 精修温度灵敏度 —— 面积随 t2-div 变化（10/15/20/30）

不重跑求解器（SA 昂贵）；数据来自参数扫描，按 (芯片, 维度值) 聚合取字典序最优。
用法: conda activate math && python q1/sensitivity/q1_sensitivity.py
"""
import csv
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Songti SC"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(ROOT, "scan", "results", "q1")
SENS = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.join(ROOT, "图表", "灵敏度", "Q1")
REPORT = FIGS
os.makedirs(SENS, exist_ok=True)
os.makedirs(FIGS, exist_ok=True)


def load_rows():
    """读全部 q1 结果 CSV，返回行字典列表（含文件名）。"""
    rows = []
    for f in glob.glob(os.path.join(RESULTS, "*.csv")):
        try:
            with open(f) as fh:
                for r in csv.DictReader(fh):
                    r["_file"] = os.path.basename(f)
                    rows.append(r)
        except (csv.Error, OSError, KeyError):
            continue
    return rows


def f(x):
    return float(x)


def lex_min(a, b):
    """(area, aspect) 字典序取优。"""
    return b if (f(a[0]), f(a[1])) > (f(b[0]), f(b[1])) else a


def save_fig(fig, name):
    fig.savefig(os.path.join(FIGS, name), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("  图 ->", os.path.join(FIGS, name))


def write_csv(name, header, rows):
    path = os.path.join(SENS, name)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("  CSV ->", path)


def s1_lambda(rows):
    """S1: λ 权重灵敏度。按 (chip, lambda) 聚合取 (area, aspect) 字典序最优。
    排除 q1t2 配置（t2 干扰项）。"""
    print("[S1] λ 权重灵敏度")
    best = {}
    for r in rows:
        if "q1t2" in r["_file"]:
            continue
        key = (r["chip"], float(r["lambda"]))
        cand = (int(f(r["area"])), f(r["aspect"]))
        best[key] = lex_min(best.get(key, cand), cand)
    rows_out = []
    for (c, lam), (a, asp) in sorted(best.items()):
        rows_out.append([c, lam, a, round(asp, 4)])
    write_csv("S1_λ权重灵敏度.csv",
              ["chip", "lambda", "area", "aspect"], rows_out)

    fig, ax1 = plt.subplots(figsize=(8, 5))
    for chip in ["n100", "n200", "n300"]:
        pts = sorted([(lam, a) for (c, lam), (a, _) in best.items() if c == chip])
        if pts:
            ax1.plot([p[0] for p in pts], [p[1] for p in pts], "o-", label=chip)
    ax1.set_xlabel(r"权重 $\lambda$")
    ax1.set_ylabel("最小包围盒面积")
    ax1.set_title(r"Q1 灵敏度：$\lambda$ 对面积的影响")
    ax1.legend()
    save_fig(fig, "q1_lambda_sensitivity.png")

    fig, ax2 = plt.subplots(figsize=(8, 5))
    for chip in ["n100", "n200", "n300"]:
        pts = sorted([(lam, asp) for (c, lam), (_, asp) in best.items()
                      if c == chip])
        if pts:
            ax2.plot([p[0] for p in pts], [p[1] for p in pts], "o-", label=chip)
    ax2.set_xlabel(r"权重 $\lambda$")
    ax2.set_ylabel("长宽比 $R$")
    ax2.set_title(r"Q1 灵敏度：$\lambda$ 对长宽比的影响")
    ax2.legend()
    save_fig(fig, "q1_lambda_aspect_sensitivity.png")
    return rows_out


def s2_repeats(rows):
    """S2: 轮次收敛。λ=0.5、默认 t2 下按 (chip, repeats) 聚合。"""
    print("[S2] 轮次收敛灵敏度")
    best = {}
    for r in rows:
        if "q1t2" in r["_file"]:
            continue
        if abs(float(r["lambda"]) - 0.5) > 1e-9:
            continue
        key = (r["chip"], int(r["repeats"]))
        cand = (int(f(r["area"])), f(r["aspect"]))
        best[key] = lex_min(best.get(key, cand), cand)
    rows_out = []
    for (c, rep), (a, asp) in sorted(best.items()):
        rows_out.append([c, rep, a, round(asp, 4)])
    write_csv("S2_轮次收敛灵敏度.csv",
              ["chip", "repeats", "area", "aspect"], rows_out)

    fig, ax = plt.subplots(figsize=(8, 5))
    for chip in ["n100", "n200", "n300"]:
        pts = sorted([(rep, a) for (c, rep), (a, _) in best.items()
                      if c == chip])
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", label=chip)
    ax.set_xlabel("独立轮次 repeats")
    ax.set_ylabel("最小包围盒面积")
    ax.set_title(r"Q1 灵敏度：轮次收敛性（$\lambda=0.5$）")
    ax.legend()
    save_fig(fig, "q1_repeats_convergence.png")
    return rows_out


def s3_t2div(rows):
    """S3: 精修初始温度除数 t2-div（q1t2 系列配置）。"""
    print("[S3] 精修温度灵敏度")
    best = {}
    for r in rows:
        if "q1t2" not in r["_file"]:
            continue
        key = (r["chip"], int(float(r["t2_div"])))
        cand = (int(f(r["area"])), f(r["aspect"]))
        best[key] = lex_min(best.get(key, cand), cand)
    rows_out = []
    for (c, t2), (a, asp) in sorted(best.items()):
        rows_out.append([c, t2, a, round(asp, 4)])
    write_csv("S3_精修温度灵敏度.csv",
              ["chip", "t2_div", "area", "aspect"], rows_out)

    fig, ax = plt.subplots(figsize=(8, 5))
    for chip in ["n100", "n200", "n300"]:
        pts = sorted([(t2, a) for (c, t2), (a, _) in best.items() if c == chip])
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", label=chip)
    ax.set_xlabel("精修初始温度除数 t2-div")
    ax.set_ylabel("最小包围盒面积")
    ax.set_title(r"Q1 灵敏度：精修初始温度（$\lambda=0.5$）")
    ax.legend()
    save_fig(fig, "q1_t2div_sensitivity.png")
    return rows_out


def build_report(s1, s2, s3):
    """生成 q1_sensitivity_report.tex（表格来自数据，tex 输出至 图表/灵敏度/ 下编译）。"""
    def esc(x):
        return str(x).replace("_", r"\_")

    def table(head, rows, caption, label):
        lines = [r"  \begin{tabular}{" + "l" * len(head) + "}",
                 r"  \toprule",
                 "  " + " & ".join(esc(h) for h in head) + r" \\",
                 r"  \midrule"]
        for r in rows:
            lines.append("  " + " & ".join(esc(x) for x in r) + r" \\")
        lines += [r"  \bottomrule", r"  \end{tabular}"]
        return (r"  \begin{table}[H]" + "\n" + r"  \centering" + "\n"
                + r"  \caption{" + caption + r"}\label{" + label + "}\n"
                + "\n".join(lines) + "\n" + r"  \end{table}")

    tex = r"""\documentclass[12pt,a4paper]{article}
\usepackage[UTF8]{ctex}
\usepackage{amsmath, amssymb}
\usepackage{geometry}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage{float}
\geometry{left=2.5cm, right=2.5cm, top=2.5cm, bottom=2.5cm}
\title{\textbf{问题一 灵敏度分析报告}\\[4pt]
\large VLSI 布图规划设计 --- 参数灵敏度分析}
\author{2026 年第七届"华数杯"大学生数学建模竞赛 B 题}
\date{2026/08}
\begin{document}
\maketitle

\section{S1：权重 $\lambda$ 灵敏度}

目标函数 $f = \lambda\, A/\bar A + (1-\lambda)\, P(R)/\bar P$ 中，$\lambda$
刻画面积与长宽比的相对重要性。扫描 $\lambda \in [0.375, 0.625]$（11 点
$\times$ n100/n200，6 点 $\times$ n300），各 $\lambda$ 取
$(A, R)$ 字典序最优。

\begin{figure}[H]
\centering
\includegraphics[width=0.82\textwidth]{q1_lambda_sensitivity.png}
\caption{面积随 $\lambda$ 变化}
\end{figure}

\begin{figure}[H]
\centering
\includegraphics[width=0.82\textwidth]{q1_lambda_aspect_sensitivity.png}
\caption{长宽比随 $\lambda$ 变化}
\end{figure}

""" + table(["chip", "lambda", "area", "aspect"], s1,
             r"S1 数据（每 $\lambda$ 取字典序最优）", "tab:q1s1") + r"""

\textbf{结论}：n100 面积谷底清晰地位于 $\lambda = 0.5$（189198）；
n300 亦在 $\lambda = 0.5$ 取最小面积（285228）；n200 在
$\lambda \in [0.4, 0.625]$ 区间面积波动仅 0.4\%（183112$\sim$184230），
且 $\lambda$ 越大长宽比越差（$\lambda=0.625$ 时 $R=1.71$）。
综合三芯片，\textbf{$\lambda = 0.5$ 是面积与长宽比的均衡点}，结果对
$\lambda$ 在 $[0.45, 0.55]$ 内不敏感（面积变化 $<1\%$）。

\section{S2：轮次收敛灵敏度}

模拟退火为随机启发式，独立轮次越多越稳定。在 $\lambda=0.5$ 下扫描
repeats $= 4/8/12/16/24$。

\begin{figure}[H]
\centering
\includegraphics[width=0.82\textwidth]{q1_repeats_convergence.png}
\caption{最优面积随轮次收敛}
\end{figure}

""" + table(["chip", "repeats", "area", "aspect"], s2,
             "S2 数据", "tab:q1s2") + r"""

\textbf{结论}：n100 在 8 轮后不再改善（189198 平台）；n200/n300 在
16$\sim$24 轮仍有 $<0.1\%$ 级微小改善。\textbf{8 轮即可收敛}，
交付取多轮取优以保证稳定性。

\section{S3：精修初始温度灵敏度}

精修阶段初始温度 $T_0/\text{t2-div}$ 控制局部搜索强度。扫描
t2-div $= 10/15/20/30$（$\lambda=0.5$）。

\begin{figure}[H]
\centering
\includegraphics[width=0.82\textwidth]{q1_t2div_sensitivity.png}
\caption{最优面积随精修温度除数变化}
\end{figure}

""" + table(["chip", "t2_div", "area", "aspect"], s3,
             "S3 数据", "tab:q1s3") + r"""

\textbf{结论}：n100 在默认 t2-div$=20$ 处最优（189198）；n200 随
t2-div 增大单调改善（t2-div$=30$ 时 183112，低于默认 20 的
183742）——定稿对 n200 取 t2-div$=30$（较默认降面积 0.34\% 且
长宽比更优）；n300 保持默认 t2-div$=20$。t2-div 的加密扫描
（40/50/60）因赛程时间未执行，如实记录。

\end{document}
"""
    path = os.path.join(REPORT, "q1_sensitivity_report.tex")
    with open(path, "w") as f:
        f.write(tex)
    print("  报告 ->", path)


def main():
    rows = load_rows()
    print(f"读取 {len(rows)} 行 q1 结果")
    s1 = s1_lambda(rows)
    s2 = s2_repeats(rows)
    s3 = s3_t2div(rows)
    build_report(s1, s2, s3)
    print("完成。CSV -> q1/sensitivity/，图 -> 做图/")


if __name__ == "__main__":
    main()
