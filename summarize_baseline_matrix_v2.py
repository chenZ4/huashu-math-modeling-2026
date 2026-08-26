#!/usr/bin/env python3
"""IEEE TCAD 格式对比矩阵生成器（条件统计 + Wilcoxon 显著性检验）。

读 baseline_metrics.csv → 输出：
  1. 每算例×方法：合法率（含 Clopper-Pearson 95%CI）、条件 HPWL mean±std、CPU mean±std
  2. 方法对 Wilcoxon rank-sum p-value（仅合法种子）
  3. IEEE 双栏 LaTeX 表体（每算例一张表）

用法：
  conda run -n math python3 summarize_baseline_matrix_v2.py \
      q2/output/baseline_matrix/baseline_metrics.csv
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

METHODS_ORDER = ["blf", "sp_random", "sp_sa", "otree_sa", "bstar_mem"]
METHOD_ZH = {
    "blf": "BLF 贪心",
    "sp_random": "SP 随机游走",
    "sp_sa": "SP+SA",
    "otree_sa": "O-tree+SA",
    "bstar_mem": "B$^*$+SA",
}
PAIRS = [("sp_sa", "otree_sa"), ("sp_sa", "bstar_mem"), ("otree_sa", "bstar_mem")]
PAIR_ZH = {
    ("sp_sa", "otree_sa"): "SP vs O-tree",
    ("sp_sa", "bstar_mem"): "SP vs B$^*$",
    ("otree_sa", "bstar_mem"): "O-tree vs B$^*$",
}
CHIPS = ["n100", "n200", "n300"]


def load(path):
    rows = defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            rows[(r["method"], r["chip"])].append(r)
    return rows


def legal_stats(rs):
    legal = [r for r in rs if r["legal"] == "True"]
    n_legal = len(legal)
    n_total = len([r for r in rs if r.get("note") != "timeout"])
    hpwl_legal = [float(r["hpwl"]) for r in legal if r.get("hpwl") not in (None, "")]
    cpus = [float(r["cpu_time_s"]) for r in rs
            if r.get("cpu_time_s") not in (None, "", "--")
            and r.get("note") != "timeout"]
    timeouts = sum(1 for r in rs if r.get("note") == "timeout")
    return n_legal, n_total, hpwl_legal, cpus, timeouts


def fmt_mean_std(vals, nd=0):
    if not vals:
        return "---"
    if len(vals) == 1:
        return f"{vals[0]:.{nd}f}"
    if len(vals) == 2:
        return f"{np.mean(vals):.{nd}f}$\\pm${abs(vals[1]-vals[0])/2:.{nd}f}"
    return f"{np.mean(vals):.{nd}f}$\\pm${np.std(vals, ddof=1):.{nd}f}"


def clopper_ci(n_succ, n_total, alpha=0.05):
    """Clopper-Pearson 精确置信区间。"""
    if n_total == 0:
        return (0.0, 0.0)
    lo = stats.beta.ppf(alpha / 2, n_succ, n_total - n_succ + 1) if n_succ > 0 else 0.0
    hi = stats.beta.ppf(1 - alpha / 2, n_succ + 1, n_total - n_succ) if n_succ < n_total else 1.0
    return (lo, hi)


def wilcoxon_pair(rows, chip, m1, m2):
    """两方法合法种子 HPWL 的 Wilcoxon rank-sum 检验。"""
    hpwl1 = [float(r["hpwl"]) for r in rows.get((m1, chip), [])
             if r["legal"] == "True" and r.get("hpwl") not in (None, "")]
    hpwl2 = [float(r["hpwl"]) for r in rows.get((m2, chip), [])
             if r["legal"] == "True" and r.get("hpwl") not in (None, "")]
    if len(hpwl1) < 2 or len(hpwl2) < 2:
        return None, None
    stat, p = stats.ranksums(hpwl1, hpwl2)
    return stat, p


def generate_ieee_table(rows, chip):
    """生成单个算例的 IEEE 双栏 LaTeX 表体。"""
    lines = []
    for m in METHODS_ORDER:
        rs = rows.get((m, chip), [])
        if not rs:
            continue
        n_legal, n_total, hpwl_legal, cpus, timeouts = legal_stats(rs)
        if n_total == 0:
            hpwl_s = "timeout"
            rate_s = f"0/{n_total}$^\\dagger$"
            cpu_s = ">900"
        elif n_legal == 0:
            hpwl_s = "---"
            rate_s = f"0/{n_total}"
            cpu_s = fmt_mean_std(cpus, 1)
        else:
            hpwl_s = fmt_mean_std(hpwl_legal, 0)
            lo, hi = clopper_ci(n_legal, n_total)
            rate_s = f"{n_legal}/{n_total} [{lo:.0%},{hi:.0%}]"
            cpu_s = fmt_mean_std(cpus, 1)
        zh = METHOD_ZH.get(m, m)
        lines.append(f"{zh} & {hpwl_s} & {rate_s} & {cpu_s} \\\\")
    return "\n".join(lines)


def generate_wilcoxon(rows, chip):
    """生成 Wilcoxon 检验结果。"""
    results = []
    for m1, m2 in PAIRS:
        stat, p = wilcoxon_pair(rows, chip, m1, m2)
        if p is None:
            results.append(f"{PAIR_ZH[(m1, m2)]}: N/A")
        else:
            star = "**" if p < 0.01 else ("*" if p < 0.05 else "n.s.")
            results.append(f"{PAIR_ZH[(m1, m2)]}: p={p:.4f} ({star})")
    return results


def main(path):
    rows = load(path)
    print("% ==== IEEE TCAD 对比矩阵（条件统计 + Wilcoxon）====")
    print(f"% 数据源: {path}")
    print()
    for chip in CHIPS:
        print(f"% ===== {chip} =====")
        print(f"% 合法率格式: 成功/总数 [Clopper-Pearson 95%CI]")
        print(f"% HPWL: 仅合法种子 mean$\\pm$std")
        print()
        print(generate_ieee_table(rows, chip))
        print()
        print(f"% Wilcoxon rank-sum (HPWL, legal seeds only):")
        for line in generate_wilcoxon(rows, chip):
            print(f"%   {line}")
        print()
    # 汇总
    print("% ===== 横向汇总 =====")
    for m in METHODS_ORDER:
        for chip in CHIPS:
            rs = rows.get((m, chip), [])
            if not rs:
                continue
            n_legal, n_total, _, _, _ = legal_stats(rs)
            hpwl = [float(r["hpwl"]) for r in rs if r["legal"] == "True" and r.get("hpwl")]
            if hpwl:
                print(f"% {m}/{chip}: {n_legal}/{n_total} legal, "
                      f"HPWL={np.mean(hpwl):.0f}±{np.std(hpwl, ddof=1):.0f}")
            else:
                print(f"% {m}/{chip}: {n_legal}/{n_total} legal, HPWL=N/A")


if __name__ == "__main__":
    main(sys.argv[1])
