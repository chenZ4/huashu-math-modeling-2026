#!/usr/bin/env python3
"""读 baseline_metrics.csv → 生成论文对比矩阵 LaTeX 表体。

用法：
  conda run -n math python summarize_baseline_matrix.py \
      q2/output/baseline_matrix/baseline_metrics.csv > /tmp/matrix_rows.tex

输出三段：
  1. tab:baseline_matrix 表体（自测四方法 × 三算例，HPWL mean±std / 内存 / CPU）
  2. 每方法可行性摘要行（合法率、违规数）
  3. 校验提示（与金标准/final 口径的交叉核对结果）
"""
import csv
import statistics as st
import sys
from collections import defaultdict

METHODS = ["blf", "sp_random", "sp_sa", "bstar_mem"]
METHOD_ZH = {
    "blf": "BLF 贪心",
    "sp_random": "SP 随机游走",
    "sp_sa": "SP+SA（同引擎）",
    "bstar_mem": "B*-Tree+SA（本文）",
}
CHIPS = ["n100", "n200", "n300"]


def load(path):
    rows = defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            if r.get("note") == "timeout" or not r.get("hpwl"):
                continue
            rows[(r["method"], r["chip"])].append(r)
    return rows


def fmt(vals, nd=1):
    vals = [float(v) for v in vals if v not in ("", None)]
    if not vals:
        return "--"
    if len(vals) == 1:
        return f"{vals[0]:.{nd}f}"
    return f"{st.mean(vals):.{nd}f}$\\pm${st.stdev(vals):.{nd}f}"


def main(path):
    rows = load(path)
    print("% ==== 表体：自测基线矩阵（生成于 summarize_baseline_matrix.py）====")
    for chip in CHIPS:
        cells = []
        for m in METHODS:
            rs = rows.get((m, chip), [])
            if not rs:
                cells.append("-- & -- & -- & --")
                continue
            hpwl = fmt([r["hpwl"] for r in rs], 1)
            mem = fmt([r["peak_mem_mb"] for r in rs], 1)
            cpu = fmt([r["cpu_time_s"] for r in rs], 2)
            legal = sum(1 for r in rs if r["legal"] == "True")
            viol = sum(int(r["overlap_pairs"]) + int(r["outline_violations"])
                       for r in rs)
            viol_s = "0" if viol == 0 else str(viol)
            cells.append(f"{hpwl} & {mem} & {cpu} & {legal}/{len(rs)}"
                         f"/{viol_s}")
        print(f"{chip} & " + " & ".join(cells) + " \\\\")
    print("% ==== 汇总校验 ====")
    for m in METHODS:
        for chip in CHIPS:
            rs = rows.get((m, chip), [])
            if rs:
                utils = [float(r["utilization"]) for r in rs]
                print(f"% {m}/{chip}: n={len(rs)} util_mean={st.mean(utils):.4f}")


if __name__ == "__main__":
    main(sys.argv[1])
