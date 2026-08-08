"""数据探索性分析（EDA）：三芯片原始数据统计 + 出图（给论文手选择）。
注：与题目领域 EDA（Electronic Design Automation）同名，论文可呼应。"""
import csv
import math
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "raw")
OUT = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.join(OUT, "figs")
CHIPS = ["n100", "n200", "n300"]


def load_blocks(chip):
    dims = {}
    for line in open(os.path.join(DATA, f"{chip}.blocks")):
        if "block 4" not in line:
            continue
        nums = [int(x) for x in re.findall(r"\d+", line)]
        name = line.split()[0]
        xs, ys = nums[2::2], nums[3::2]
        dims[name] = (max(xs) - min(xs), max(ys) - min(ys))
    return dims


def load_nets(chip):
    degs = []
    for line in open(os.path.join(DATA, f"{chip}.nets")):
        if line.startswith("NetDegree"):
            degs.append(int(line.split()[-1]))
    return degs


def load_terms(chip):
    pts = []
    for line in open(os.path.join(DATA, f"{chip}.pl")):
        p = line.split()
        if len(p) == 3:
            pts.append((int(p[1]), int(p[2])))
    return pts


def save(fig, name):
    os.makedirs(FIGS, exist_ok=True)
    fig.savefig(os.path.join(FIGS, name), dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    summary = []
    all_w, all_h, all_ar = [], [], []
    for chip in CHIPS:
        dims = load_blocks(chip)
        ws = [v[0] for v in dims.values()]
        hs = [v[1] for v in dims.values()]
        total = sum(w * h for w, h in dims.values())
        side15 = math.ceil(math.sqrt(total * 1.15))
        side00 = math.ceil(math.sqrt(total))
        nets = load_nets(chip)
        terms = load_terms(chip)
        all_w.extend(ws)
        all_h.extend(hs)
        all_ar.extend(max(w, h) / min(w, h) for w, h in dims.values())
        summary.append({
            "chip": chip, "blocks": len(dims), "terminals": len(terms),
            "nets": len(nets), "total_area": total,
            "avg_w": round(sum(ws) / len(ws), 1),
            "avg_h": round(sum(hs) / len(hs), 1),
            "max_w": max(ws), "max_h": max(hs),
            "side_d0": side00, "side_d15": side15,
            "packing_bound": round(total / (side15 * side15), 4),
            "avg_degree": round(sum(nets) / len(nets), 2),
            "max_degree": max(nets),
        })
    with open(os.path.join(OUT, "eda_summary.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader()
        w.writerows(summary)
    print(open(os.path.join(OUT, "eda_summary.csv")).read())

    # 1 三芯片规模概览
    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for ax, key, title in zip(axes, ("blocks", "terminals", "nets", "total_area"),
                              ("Blocks", "Terminals", "Nets", "Total Area")):
        ax.bar([s["chip"] for s in summary], [s[key] for s in summary],
               color="#1f77b4")
        ax.set_title(title)
        ax.set_ylabel("count" if key != "total_area" else "area")
    fig.suptitle("Chip Scale Overview (n100/n200/n300)")
    fig.tight_layout()
    save(fig, "eda_01_scale.png")

    # 2 模块尺寸分布（w-h 散点）
    fig, ax = plt.subplots(figsize=(7, 6))
    colors = {"n100": "#1f77b4", "n200": "#ff7f0e", "n300": "#2ca02c"}
    for chip in CHIPS:
        dims = load_blocks(chip)
        ws = [v[0] for v in dims.values()]
        hs = [v[1] for v in dims.values()]
        ax.scatter(ws, hs, s=12, alpha=0.6, label=chip, color=colors[chip])
    ax.set_xlabel("width")
    ax.set_ylabel("height")
    ax.set_title("Module Dimension Distribution")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save(fig, "eda_02_dims.png")

    # 3 模块长宽比分布
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.hist(all_ar, bins=30, color="#1f77b4", alpha=0.85)
    ax.set_xlabel("aspect ratio (max/min)")
    ax.set_ylabel("count")
    ax.set_title("Module Aspect Ratio Distribution (all chips)")
    save(fig, "eda_03_aspect.png")

    # 4 线网度数分布
    fig, ax = plt.subplots(figsize=(7, 5))
    for chip in CHIPS:
        ax.hist(load_nets(chip), bins=20, alpha=0.5, label=chip)
    ax.set_xlabel("net degree")
    ax.set_ylabel("count")
    ax.set_title("Net Degree Distribution")
    ax.legend()
    save(fig, "eda_04_nets.png")

    # 5 终端空间分布
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, chip in zip(axes, CHIPS):
        pts = load_terms(chip)
        ax.scatter([p[0] for p in pts], [p[1] for p in pts], s=3, alpha=0.7)
        ax.set_title(f"{chip} terminals")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.set_aspect("equal")
    fig.suptitle("Terminal Spatial Distribution")
    fig.tight_layout()
    save(fig, "eda_05_terminals.png")

    # 6 打包难度：利用率下界 vs 死区比例
    fig, ax = plt.subplots(figsize=(7, 5))
    for s in summary:
        ax.plot([0, 0.15], [s["total_area"] / (s["side_d0"] ** 2),
                            s["packing_bound"]],
                "o-", label=s["chip"])
    ax.set_xlabel("dead-space ratio d")
    ax.set_ylabel("area utilization upper bound")
    ax.set_title("Packing Difficulty Bound (d=0 vs d=0.15)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    save(fig, "eda_06_packing.png")

    # 7 大模块占比（Top 10）
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, chip in zip(axes, CHIPS):
        dims = load_blocks(chip)
        areas = sorted((w * h for w, h in dims.values()), reverse=True)
        total = sum(areas)
        top10 = sum(areas[:10]) / total
        ax.bar(range(1, len(areas) + 1), areas, color="#ff7f0e")
        ax.set_title(f"{chip}: Top-10 area share {top10*100:.1f}%")
        ax.set_xlabel("module rank")
        ax.set_ylabel("area")
    fig.suptitle("Module Area Distribution (packing difficulty)")
    fig.tight_layout()
    save(fig, "eda_07_top10.png")

    # 8 三芯片对比矩阵（归一化雷达/条形）
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    keys = ["blocks", "nets", "total_area", "avg_degree", "max_degree"]
    for ax, chip in zip(axes, CHIPS):
        s = next(x for x in summary if x["chip"] == chip)
        vals = [s[k] for k in keys]
        nvals = [v / max(vals) for v in vals]
        ax.bar(keys, nvals, color="#2ca02c")
        ax.set_title(chip)
        ax.set_xticks(range(len(keys)))
        ax.set_xticklabels(keys, rotation=20, fontsize=8)
        ax.set_ylim(0, 1.1)
    fig.suptitle("Normalized Feature Comparison")
    fig.tight_layout()
    save(fig, "eda_08_compare.png")

    print("EDA figures ->", FIGS)


if __name__ == "__main__":
    main()
