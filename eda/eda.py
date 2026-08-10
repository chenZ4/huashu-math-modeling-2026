"""数据探索性分析（EDA）：三芯片原始数据统计 + 出图（给论文手选择）。
注：与题目领域 EDA（Electronic Design Automation）同名，论文可呼应。"""
import collections
import csv
import math
import os
import re
import statistics

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy import stats as sp_stats

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

    # ============ 数据分析三维度（论证式 EDA）============
    # ---- 统计表 1：几何异质性 ----
    rows_hetero = [["chip", "n_blocks", "area_cv", "area_ratio_max_min",
                    "aspect_gt3", "aspect_gt3_pct"]]
    for chip in CHIPS:
        dims = load_blocks(chip)
        areas = [w * h for w, h in dims.values()]
        ratios = [max(w, h) / min(w, h) for w, h in dims.values()]
        cv = statistics.pstdev(areas) / statistics.mean(areas)
        ext = sum(1 for r in ratios if r > 3)
        rows_hetero.append([chip, len(areas), f"{cv:.4f}",
                            f"{max(areas)/min(areas):.1f}x", ext,
                            f"{ext/len(areas)*100:.1f}%"])
    with open(os.path.join(OUT, "eda_heterogeneity.csv"), "w", newline="") as f:
        csv.writer(f).writerows(rows_hetero)

    # ---- 统计表 2：Top5% 枢纽节点 ----
    with open(os.path.join(OUT, "eda_hubs.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["chip", "hub_module", "degree"])
        for chip in CHIPS:
            deg = collections.Counter()
            cur = None
            for line in open(os.path.join(DATA, f"{chip}.nets")):
                parts = line.split()
                if len(parts) >= 2 and parts[0] == "NetDegree":
                    cur = []
                elif cur is not None and parts and parts[0].startswith("b"):
                    deg[parts[0]] += 1
            k = max(1, round(len(deg) * 0.05))
            for m, d in sorted(deg.items(), key=lambda x: -x[1])[:k]:
                w.writerow([chip, m, d])

    # ---- 图 A：模块面积 KDE（log10 横轴）----
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, chip in zip(axes, CHIPS):
        dims = load_blocks(chip)
        areas = [math.log10(w * h) for w, h in dims.values()]
        xs = np.linspace(min(areas) - 0.3, max(areas) + 0.3, 400)
        kde = sp_stats.gaussian_kde(areas)
        ax.plot(xs, kde(xs), color="#1f77b4", lw=2)
        ax.fill_between(xs, kde(xs), alpha=0.3, color="#1f77b4")
        ax.set_xlabel(r"$\log_{10}$(area)")
        ax.set_ylabel("density")
        ax.set_title(f"{chip} (CV={statistics.pstdev(areas)/statistics.mean(areas):.3f})")
    fig.suptitle("Module Area KDE (log-scale): long-tail heterogeneity")
    fig.tight_layout()
    save(fig, "eda_09_area_kde.png")

    # ---- 图 B：W vs H 散点 + 对角线 + 长条模块红圈 ----
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, chip in zip(axes, CHIPS):
        dims = load_blocks(chip)
        ws = [w for w, h in dims.values()]
        hs = [h for w, h in dims.values()]
        m = max(max(ws), max(hs)) * 1.1
        ax.scatter(ws, hs, s=12, color="#2980b9", alpha=0.7, zorder=2)
        ax.plot([0, m], [0, m], ls="--", color="gray", lw=1, zorder=1)
        for name, (w, h) in dims.items():
            if max(w, h) / min(w, h) > 3:
                ax.scatter([w], [h], s=70, facecolor="none",
                           edgecolor="red", lw=1.6, zorder=3)
        ax.set_xlim(0, m)
        ax.set_ylim(0, m)
        ax.set_xlabel("width W")
        ax.set_ylabel("height H")
        ax.set_title(f"{chip}")
    fig.suptitle("Module W vs H: extreme-aspect-ratio blocks (red circles)")
    fig.tight_layout()
    save(fig, "eda_10_wvsh_scatter.png")

    # ---- 图 C：节点度数双对数直方图 ----
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, chip in zip(axes, CHIPS):
        deg = collections.Counter()
        cur = None
        for line in open(os.path.join(DATA, f"{chip}.nets")):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "NetDegree":
                cur = []
            elif cur is not None and parts and parts[0].startswith("b"):
                deg[parts[0]] += 1
        vals = sorted(deg.values())
        cnt = collections.Counter(vals)
        ks = sorted(cnt)
        pks = [v / len(vals) for v in ks]
        ax.loglog(ks, pks, "o-", color="#8e44ad", ms=4)
        ax.set_xlabel("degree (log)")
        ax.set_ylabel("P(degree) (log)")
        ax.set_title(f"{chip}")
    fig.suptitle("Module Degree Distribution (log-log)")
    fig.tight_layout()
    save(fig, "eda_11_degree_loglog.png")

    # ---- 图 D：Top5% 枢纽连接度 ----
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    for ax, chip in zip(axes, CHIPS):
        deg = collections.Counter()
        cur = None
        for line in open(os.path.join(DATA, f"{chip}.nets")):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "NetDegree":
                cur = []
            elif cur is not None and parts and parts[0].startswith("b"):
                deg[parts[0]] += 1
        k = max(1, round(len(deg) * 0.05))
        hubs = sorted(deg.items(), key=lambda x: -x[1])[:k]
        names = [m for m, _ in hubs]
        ds = [d for _, d in hubs]
        ax.bar(range(len(ds)), ds, color="#c0392b")
        ax.set_xticks(range(len(ds)))
        ax.set_xticklabels(names, rotation=45, fontsize=6)
        ax.set_ylabel("degree")
        ax.set_title(f"{chip}: Top5% hubs")
    fig.suptitle("Hub Nodes (top 5% degree)")
    fig.tight_layout()
    save(fig, "eda_12_hubs.png")

    print("EDA figures ->", FIGS)
    print("统计表 -> eda_heterogeneity.csv / eda_hubs.csv")


if __name__ == "__main__":
    main()
