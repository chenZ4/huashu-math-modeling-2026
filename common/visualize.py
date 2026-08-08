"""共享绘图基础：.rpt 解析与布图绘制。"""
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch


def read_rpt(path):
    """解析 .rpt: cost / hpwl / area / W H / time / name x1 y1 x2 y2 ..."""
    with open(path) as f:
        lines = f.readlines()
    cost = float(lines[0])
    hpwl = float(lines[1])
    area = int(lines[2])
    W, H = map(int, lines[3].split())
    time_s = float(lines[4])
    blocks = []
    for line in lines[5:]:
        parts = line.split()
        if len(parts) == 5:
            name, x1, y1, x2, y2 = parts[0], *map(int, parts[1:])
            blocks.append((name, x1, y1, x2 - x1, y2 - y1))
    return {"cost": cost, "hpwl": hpwl, "area": area, "W": W, "H": H,
            "time": time_s, "blocks": blocks}


def draw_floorplan(ax, blocks, W, H, title, outline=None, annotate=True,
                   cmap="tab20"):
    """在给定 axes 上绘制布图。outline: 轮廓 (ow, oh) 或 None。"""
    cm = plt.get_cmap(cmap)
    for i, (name, x, y, w, h) in enumerate(blocks):
        color = cm(i % cm.N)
        ax.add_patch(Rectangle((x, y), w, h, facecolor=color,
                               edgecolor="black", linewidth=0.5, zorder=2))
        if annotate and w * h > max(1, W * H / 600):
            ax.text(x + w / 2, y + h / 2, name, ha="center", va="center",
                    fontsize=4, zorder=3)
    if outline is not None:
        ow, oh = outline
        ax.add_patch(Rectangle((0, 0), ow, oh, fill=False, edgecolor="red",
                               linewidth=1.2, linestyle="--", zorder=1))
    ax.set_xlim(0, max(W, 1) * 1.02)
    ax.set_ylim(0, max(H, 1) * 1.02)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("x")
    ax.set_ylabel("y")


def read_log(path):
    """解析收敛 log: phase iter T best_cost alpha feas"""
    rows = []
    with open(path) as f:
        for line in f:
            parts = line.split()
            if len(parts) == 6:
                rows.append((parts[0], int(parts[1]), float(parts[2]),
                             float(parts[3]), float(parts[4]), int(parts[5])))
    return rows


def draw_convergence(ax, rows, title):
    """绘制收敛曲线（best cost vs 温度层序号）。"""
    iters = [r[1] for r in rows]
    best = [r[3] for r in rows]
    ax.plot(iters, best, "-", color="#0060ad", linewidth=1.2)
    ax.set_title(title, fontsize=11)
    ax.set_xlabel("temperature layer")
    ax.set_ylabel("best cost (normalized)")
    ax.grid(True, alpha=0.3)


def save_fig(fig, out_path, dpi=150):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fig.savefig(out_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
