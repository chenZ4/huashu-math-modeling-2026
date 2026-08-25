#!/usr/bin/env python3
"""P1-3: 数据集统计表（模块数/总面积/线网/引脚/端子 + 轮廓边长依据）。
数据源: data/raw/n{100,200,300}.blocks/.nets/.pl
输出: 图表/公共/数据总览/dataset_stats.csv + dataset_stats.tex
"""
import csv
import math
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, "data/raw")
OUTDIR = os.path.join(ROOT, "图表/公共/数据总览")
os.makedirs(OUTDIR, exist_ok=True)

rows = []
for chip in ["n100", "n200", "n300"]:
    T, nb = 0, 0
    with open(os.path.join(RAW, f"{chip}.blocks")) as f:
        for line in f:
            m = re.match(r"(\S+)\s+block\s+\d+\s+\((\d+),\s*(\d+)\)\s*\((\d+),\s*(\d+)\)\s*\((\d+),\s*(\d+)\)",
                         line.strip())
            if m:
                x1, y1, _, _, x3, _ = (int(m.group(i)) for i in (2, 3, 4, 5, 6, 7))
                w, h = x3 - x1, int(m.group(5)) - y1
                T += w * h
                nb += 1
    nets = pins = 0
    with open(os.path.join(RAW, f"{chip}.nets")) as f:
        for line in f:
            mm = re.match(r"NumNets\s*:\s*(\d+)", line)
            mp = re.match(r"NumPins\s*:\s*(\d+)", line)
            if mm:
                nets = int(mm.group(1))
            if mp:
                pins = int(mp.group(1))
    terms = 0
    with open(os.path.join(RAW, f"{chip}.pl")) as f:
        terms = sum(1 for l in f if l.strip() and not l.startswith("#"))
    side15 = math.ceil(math.sqrt(T * 1.15))
    rows.append({
        "实例": chip, "模块数": nb, "模块总面积 T": T,
        "线网数": nets, "引脚数": pins, "端子数": terms,
        "side(d=0.15)": side15,
    })

csv_path = os.path.join(OUTDIR, "dataset_stats.csv")
with open(csv_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
print("saved", csv_path)

tex_path = os.path.join(OUTDIR, "dataset_stats.tex")
with open(tex_path, "w") as f:
    f.write("% 数据集统计（P1 生成，数据源 data/raw/）\n")
    f.write("\\begin{table}[H]\n\\centering\n\\scriptsize\n")
    f.write("\\caption{三组实例数据集统计}\n\\label{tab:dataset}\n")
    f.write("\\begin{tabular}{lrrrrrr}\n\\toprule\n")
    f.write("实例 & 模块数 & 模块总面积 $T$ & 线网数 & 引脚数 & 端子数 & $\\lceil\\sqrt{1.15T}\\rceil$ \\\\\n\\midrule\n")
    for r in rows:
        f.write(f"{r['实例']} & {r['模块数']} & {r['模块总面积 T']:,} & {r['线网数']} & "
                f"{r['引脚数']} & {r['端子数']} & {r['side(d=0.15)']} \\\\\n")
    f.write("\\bottomrule\n\\end{tabular}\n")
    f.write("\\end{table}\n")
print("saved", tex_path)
for r in rows:
    print(r)
