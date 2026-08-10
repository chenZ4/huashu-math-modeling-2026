"""Q3 灵敏度分析：聚合 scan/results/q3 现成扫描数据，输出 S 系列 CSV + 图 + 报告。

维度：
  S1. 判定种子数灵敏度 —— d* 随判定/确认种子数变化（n100/n200 6 点，n300 2 点）
  S2. 二分精度灵敏度  —— d* 随二分终止精度 eps 变化（n100，seeds=3）
  S3. 判定/确认种子分离 —— 判定种子与确认种子解耦的影响（sep 系列）

不重跑求解器（判定昂贵）；数据来自参数扫描，按 (芯片, 种子数) 聚合取最小 d*。
用法: conda activate math && python q3/sensitivity/q3_sensitivity.py
"""
import csv
import glob
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["PingFang SC", "Heiti SC", "Songti SC"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(ROOT, "scan", "results", "q3")
SENS = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.join(ROOT, "做图")
os.makedirs(SENS, exist_ok=True)
os.makedirs(FIGS, exist_ok=True)


def load_rows():
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


def save_fig(fig, name):
    fig.savefig(os.path.join(FIGS, name), dpi=300, bbox_inches="tight")
    plt.close(fig)
    print("  图 ->", os.path.join(FIGS, name))


def write_csv(name, header, rows):
    path = os.path.join(SENS, name)
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print("  CSV ->", path)


def s1_seeds(rows):
    """S1: 判定种子数灵敏度（eps=1e-4，按 (chip, seeds) 取最小 d*）。"""
    print("[S1] 判定种子数灵敏度")
    best = {}
    conf = {}
    for r in rows:
        if r["_file"].startswith("sens_s3_e"):   # eps 系列，seeds=3 固定
            continue
        if "_sep_" in r["_file"]:                # 判定/确认分离配置，协议不同
            continue
        if abs(f(r.get("eps", 1e-4)) - 1e-4) > 1e-12:
            continue
        try:
            seeds = int(f(r["seeds"]))
        except (KeyError, ValueError):
            continue
        key = (r["chip"], seeds)
        cand = f(r["d_star"])
        if key not in best or cand < best[key]:
            best[key] = cand
            conf[key] = r["confirmed"]
    rows_out = []
    for (c, s), d in sorted(best.items()):
        rows_out.append([c, s, round(d, 6), conf[(c, s)]])
    write_csv("S1_判定种子数灵敏度.csv",
              ["chip", "seeds", "d_star", "confirmed"], rows_out)

    fig, ax = plt.subplots(figsize=(8, 5))
    for chip in ["n100", "n200", "n300"]:
        pts = sorted([(s, d) for (c, s), d in best.items() if c == chip])
        if pts:
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", label=chip)
    ax.set_xlabel("判定/确认种子数")
    ax.set_ylabel(r"最小可行死区比例 $d^*$")
    ax.set_title("Q3 灵敏度：判定种子数对 $d^*$ 的影响")
    ax.legend()
    save_fig(fig, "q3_seed_sensitivity.png")
    return rows_out


def s2_eps(rows):
    """S2: 二分精度灵敏度（n100，seeds=3 的 sens_s3_e 系列）。"""
    print("[S2] 二分精度灵敏度")
    best = {}
    for r in rows:
        if "sens_s3_e" not in r["_file"]:
            continue
        key = (r["chip"], f(r["eps"]))
        cand = f(r["d_star"])
        if key not in best or cand < best[key]:
            best[key] = cand
    rows_out = [[c, e, round(d, 6)] for (c, e), d in sorted(best.items())]
    write_csv("S2_二分精度灵敏度.csv", ["chip", "eps", "d_star"], rows_out)

    fig, ax = plt.subplots(figsize=(8, 5))
    pts = sorted([(e, d) for (c, e), d in best.items()])
    if pts:
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", label="n100")
    ax.set_xlabel("二分终止精度 eps")
    ax.set_ylabel(r"$d^*$")
    ax.set_title("Q3 灵敏度：二分精度对 $d^*$ 的影响（seeds=3）")
    ax.legend()
    save_fig(fig, "q3_eps_sensitivity.png")
    return rows_out


def s3_sep(rows):
    """S3: 判定/确认种子分离（w2_sep_s{J}_c{C} 系列，从文件名解析）。"""
    print("[S3] 判定/确认种子分离")
    best = {}
    for r in rows:
        m = re.search(r"sep_s(\d+)_c(\d+)_(\w+)\.csv$", r["_file"])
        if not m:
            continue
        j, c, chip = int(m.group(1)), int(m.group(2)), m.group(3)
        key = (chip, j, c)
        cand = f(r["d_star"])
        if key not in best or cand < best[key]:
            best[key] = (cand, r["confirmed"])
    rows_out = []
    for (chip, j, c), (d, ok) in sorted(best.items()):
        rows_out.append([chip, j, c, round(d, 6), ok])
    write_csv("S3_判定确认种子分离.csv",
              ["chip", "judge_seeds", "confirm_seeds", "d_star", "confirmed"],
              rows_out)

    fig, ax = plt.subplots(figsize=(8, 5))
    styles = {7: ("o-", "#2980b9", "确认种子 7"),
              10: ("s--", "#c0392b", "确认种子 10")}
    for chip in ["n100", "n200", "n300"]:
        for k, (marker, color, label) in styles.items():
            pts = sorted([(j, d) for (c, j, ck), (d, _) in best.items()
                          if c == chip and ck == k])
            if pts:
                ax.plot([p[0] for p in pts], [p[1] for p in pts], marker,
                        color=color, label=f"{chip}（{label}）")
    ax.set_xlabel("判定种子数")
    ax.set_ylabel(r"$d^*$")
    ax.set_title("Q3 灵敏度：判定/确认种子解耦")
    ax.legend(fontsize=9)
    save_fig(fig, "q3_sep_judge_confirm.png")
    return rows_out


def build_report(s1, s2, s3):
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
                + r"  \caption{" + caption + "}\label{" + label + "}\n"
                + "\n".join(lines) + "\n" + r"  \end{table}")

    tex = r"""\documentclass[12pt,a4paper]{article}
\usepackage[UTF8]{ctex}
\usepackage{amsmath, amssymb}
\usepackage{geometry}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage{float}
\geometry{left=2.5cm, right=2.5cm, top=2.5cm, bottom=2.5cm}
\title{\textbf{问题三 灵敏度分析报告}\\[4pt]
\large VLSI 布图规划设计 --- 判定强度参数灵敏度分析}
\author{2026 年第七届"华数杯"大学生数学建模竞赛 B 题}
\date{2026/08}
\begin{document}
\maketitle

\section{S1：判定种子数灵敏度}

可行性判定是启发式的，存在假阴性（搜索不足被判不可行）。判定种子数
$K$ 直接决定假阴性概率（$P \approx \prod P_s$）。扫描
$K = 1/3/5/7/10/15$（n100/n200），n300 扫描至 5/7/10
（seed15/20 因赛程时间未加密）。

\begin{figure}[H]
\centering
\includegraphics[width=0.82\textwidth]{../../做图/q3_seed_sensitivity.png}
\caption{$d^*$ 随判定种子数变化}
\end{figure}

""" + table(["chip", "seeds", "d_star", "confirmed"], s1,
             "S1 数据（eps=1e-4）", "tab:q3s1") + r"""

\textbf{结论}：$d^*$ 随种子数\textbf{单调下降}——n100 从 1 种子的
0.137183 降至 15 种子的 0.076072（改善 45\%），n200 从 3 种子的
0.108977 降至 15 种子的 0.084141（改善 23\%），n300 从 5 种子的
0.121921 降至 10 种子的 0.111773（改善 8\%）。种子数 3 时 n100
判定不可靠（未确认），5 及以上稳定。\emph{论文表述必须注明
"搜索强度相关"}：$d^*$ 是在当前判定强度下验证过的最小可行死区比例；
定稿协议为 n100/n200 判定 15、n300 判定 10（n300 的 15/20 因赛程
未扫描，可按需加密）。

\section{S2：二分终止精度灵敏度}

二分终止条件 $hi - lo < \varepsilon$，扫描
$\varepsilon = 10^{-3}/10^{-4}/10^{-5}$（n100，seeds=3）。

\begin{figure}[H]
\centering
\includegraphics[width=0.82\textwidth]{../../做图/q3_eps_sensitivity.png}
\caption{$d^*$ 随二分精度变化}
\end{figure}

""" + table(["chip", "eps", "d_star"], s2,
             "S2 数据", "tab:q3s2") + r"""

\textbf{结论}：$\varepsilon$ 从 $10^{-3}$ 收紧到 $10^{-5}$，
$d^*$ 仅变化 0.4\%（0.135323 $\to$ 0.134747）——二分精度对结果
\textbf{不敏感}，$10^{-4}$ 是成本与精度的合理平衡点（约 11 次判定）。

\section{S3：判定/确认种子解耦}

二分判定（judge）与最终双向确认（confirm）使用不同的种子数，
扫描判定 3/5 $\times$ 确认 7/10。

\begin{figure}[H]
\centering
\includegraphics[width=0.82\textwidth]{../../做图/q3_sep_judge_confirm.png}
\caption{判定/确认种子解耦对 $d^*$ 的影响}
\end{figure}

""" + table(["chip", "judge_seeds", "confirm_seeds", "d_star", "confirmed"],
             s3, "S3 数据", "tab:q3s3") + r"""

\textbf{结论}：\textbf{判定种子决定 $d^*$ 位置}（3 $\to$ 5 时
$d^*$ 从 0.134811 降至 0.116061），确认种子决定"确认"成败
（判定 5 + 确认 7 未通过，需更小的 $d^*$ 才能通过）——两者解耦验证了
"判定强度 $\rightarrow$ 假阴性率 $\rightarrow$ $d^*$ 精度"的因果链，
支持交付采用高判定/确认种子协议。

\end{document}
"""
    path = os.path.join(SENS, "q3_sensitivity_report.tex")
    with open(path, "w") as fh:
        fh.write(tex)
    print("  报告 ->", path)


def main():
    rows = load_rows()
    print(f"读取 {len(rows)} 行 q3 结果")
    s1 = s1_seeds(rows)
    s2 = s2_eps(rows)
    s3 = s3_sep(rows)
    build_report(s1, s2, s3)
    print("完成。CSV -> q3/sensitivity/，图 -> 做图/")


if __name__ == "__main__":
    main()
