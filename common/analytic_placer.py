#!/usr/bin/env python3
"""解析式全局布局（T2 hybrid 组件）。

LSE(log-sum-exp) 可微 HPWL + 分 bin 密度惩罚 + Nesterov 加速梯度下降，
用于：(a) 生成 SA 初始序列 (--mode order)；(b) Q3 死区比例可行性佐证
(--mode oracle)。纯 numpy，固定种子完全确定。

坐标系约定（与 C++ 求解器逐位一致）：
  块引脚 = (2x+w, 2y+h)   （x,y 为左下角，w,h 为尺寸）
  端子引脚 = (2px, 2py)   （px,py 为 .pl 固定坐标）
  HPWL = Σ_net (Δx + Δy) / 2
"""
import argparse
import json
import os
import re
import subprocess

import numpy as np


# ---------------- 数据解析 ----------------
def parse_blocks(path):
    dims = {}
    for line in open(path, encoding="utf-8"):
        if " block " not in line:
            continue
        name = line.split()[0]
        nums = [int(x) for x in re.findall(r"-?\d+", line)]
        xs, ys = nums[2::2], nums[3::2]
        dims[name] = (max(xs) - min(xs), max(ys) - min(ys))
    return dims


def parse_terminals(path):
    terms = {}
    for line in open(path, encoding="utf-8"):
        p = line.split()
        if len(p) == 3:
            terms[p[0]] = (int(p[1]), int(p[2]))
    return terms


def parse_nets(path):
    lines = [l.strip() for l in open(path, encoding="utf-8")]
    nets = []
    i = 0
    while i < len(lines):
        m = re.match(r"NetDegree\s*:\s*(\d+)", lines[i])
        if m:
            k = int(m.group(1))
            nets.append(lines[i + 1:i + 1 + k])
            i += 1 + k
        else:
            i += 1
    return nets


def parse_instance(root, chip):
    b = parse_blocks(os.path.join(root, "data/raw", f"{chip}.blocks"))
    t = parse_terminals(os.path.join(root, "data/raw", f"{chip}.pl"))
    n = parse_nets(os.path.join(root, "data/raw", f"{chip}.nets"))
    return b, t, n


# ---------------- HPWL（精确 + 金标准） ----------------
def hpwl_exact(centers, block_dim, blocks, terminals, nets):
    """centers: {block_name: (x, y)} 左下角；返回报告口径 HPWL=raw/2。"""
    total = 0.0
    for net in nets:
        xs, ys = [], []
        for pin in net:
            if pin in blocks:
                x, y = centers[pin]
                w, h = block_dim[pin]
                xs.append(2 * x + w)
                ys.append(2 * y + h)
            elif pin in terminals:
                px, py = terminals[pin]
                xs.append(2 * px)
                ys.append(2 * py)
            else:
                raise KeyError(f"unknown pin {pin}")
        total += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return total / 2.0


def hpwl_of_rpt(rpt_path, blocks, terminals, nets):
    """从 rpt 独立重算 HPWL（金标准校验用）。rpt 第 2 行为报告 HPWL。
    块引脚按放置后（可能旋转）尺寸：(2x+w', 2y+h') = (x1+x2, y1+y2)。"""
    lines = open(rpt_path, encoding="utf-8").read().splitlines()
    pins = {}
    for line in lines[5:]:
        p = line.split()
        if len(p) == 5:
            name = p[0]
            x1, y1, x2, y2 = (int(v) for v in p[1:])
            pins[name] = (x1 + x2, y1 + y2)
    total = 0.0
    for net in nets:
        xs, ys = [], []
        for pin in net:
            if pin in pins:
                xs.append(pins[pin][0])
                ys.append(pins[pin][1])
            elif pin in terminals:
                px, py = terminals[pin]
                xs.append(2 * px)
                ys.append(2 * py)
            else:
                raise KeyError(f"unknown pin {pin}")
        total += (max(xs) - min(xs)) + (max(ys) - min(ys))
    return total / 2.0


# ---------------- 梯度项 ----------------
def _lse_wl_grad(pin_xy, gamma):
    """pin_xy: (M,2)（含固定端子）。返回 (wl, gx(M,), gy(M,))。max 平移+指数截断防溢出。"""
    ax = np.asarray(pin_xy, dtype=np.float64)
    g = max(gamma, 1e-6)
    x, y = ax[:, 0], ax[:, 1]
    mx, my = x.max(), y.max()
    t = np.minimum((x - mx) / g, 40.0)
    ex = np.exp(t)
    exn = np.exp(np.minimum((mx - x) / g, 40.0))
    ey = np.exp(np.minimum((y - my) / g, 40.0))
    eyn = np.exp(np.minimum((my - y) / g, 40.0))
    wx = (mx + g * np.log(ex.sum())) - (mx - g * np.log(exn.sum()))
    wy = (my + g * np.log(ey.sum())) - (my - g * np.log(eyn.sum()))
    gx = ex / ex.sum() - exn / exn.sum()
    gy = ey / ey.sum() - eyn / eyn.sum()
    return wx + wy, gx, gy


def _density_grad(pos, half, side, nbins, d_tar):
    """两遍法：pass1 得 D；pass2 得加权梯度 Σ_b 2(D_b-tar)·∂D_b/∂x_i。
    pos/变量为块中心。返回 (D, grad(N,2), excess)。"""
    N = pos.shape[0]
    bw = side / nbins
    D = np.zeros((nbins, nbins))
    # pass 1
    for i in range(N):
        x, y = pos[i]
        w, h = half[i]
        xl, xr, yl, yr = x - w, x + w, y - h, y + h
        bx0, bx1 = max(0, int(np.floor(xl / bw))), min(nbins - 1, int(np.floor(xr / bw)))
        by0, by1 = max(0, int(np.floor(yl / bw))), min(nbins - 1, int(np.floor(yr / bw)))
        for bi in range(bx0, bx1 + 1):
            ox = min(xr, (bi + 1) * bw) - max(xl, bi * bw)
            if ox <= 0:
                continue
            for bj in range(by0, by1 + 1):
                oy = min(yr, (bj + 1) * bw) - max(yl, bj * bw)
                if oy <= 0:
                    continue
                D[bi, bj] += ox * oy
    D /= (bw * bw)
    # pass 2（加权梯度）
    grad = np.zeros_like(pos)
    for i in range(N):
        x, y = pos[i]
        w, h = half[i]
        xl, xr, yl, yr = x - w, x + w, y - h, y + h
        bx0, bx1 = max(0, int(np.floor(xl / bw))), min(nbins - 1, int(np.floor(xr / bw)))
        by0, by1 = max(0, int(np.floor(yl / bw))), min(nbins - 1, int(np.floor(yr / bw)))
        gx_i = gy_i = 0.0
        for bi in range(bx0, bx1 + 1):
            ox = min(xr, (bi + 1) * bw) - max(xl, bi * bw)
            if ox <= 0:
                continue
            for bj in range(by0, by1 + 1):
                oy = min(yr, (bj + 1) * bw) - max(yl, bj * bw)
                if oy <= 0:
                    continue
                wgt = 2.0 * (D[bi, bj] - d_tar) / (bw * bw)
                gx = (1.0 if (bi * bw < xr < (bi + 1) * bw) else 0.0) \
                     - (1.0 if (bi * bw < xl < (bi + 1) * bw) else 0.0)
                gy = (1.0 if (bj * bw < yr < (bj + 1) * bw) else 0.0) \
                     - (1.0 if (bj * bw < yl < (bj + 1) * bw) else 0.0)
                gx_i += wgt * gx * oy
                gy_i += wgt * gy * ox
        grad[i, 0], grad[i, 1] = gx_i, gy_i
    excess = float(np.maximum(D - d_tar, 0.0).sum())
    return D, grad, excess


def _outline_grad(pos, half, side):
    N = pos.shape[0]
    grad = np.zeros_like(pos)
    pen = 0.0
    for i in range(N):
        x, y = pos[i]
        w, h = half[i]
        hi_x, hi_y = x + w - side, y + h - side
        if hi_x > 0:
            pen += hi_x * hi_x
            grad[i, 0] += 2.0 * hi_x
        if hi_y > 0:
            pen += hi_y * hi_y
            grad[i, 1] += 2.0 * hi_y
        lo_x, lo_y = w - x, h - y
        if lo_x > 0:
            pen += lo_x * lo_x
            grad[i, 0] -= 2.0 * lo_x
        if lo_y > 0:
            pen += lo_y * lo_y
            grad[i, 1] -= 2.0 * lo_y
    return grad, pen


def _rms_norm(g):
    r = float(np.sqrt(np.mean(g * g)))
    return g / r if r > 1e-12 else g


# ---------------- 主流程 ----------------
def analytic_place(blocks, terminals, nets, side, iters=1200, gamma0=40.0,
                   gamma_end=4.0, lam0=2.0, lam_ratio=1.008, lam_max=100.0,
                   lam_c0=0.5, lr=0.02, mom=0.6, seed=42, nbins=12):
    rng = np.random.default_rng(seed)
    names = sorted(blocks.keys())
    N = len(names)
    dims = np.array([blocks[k] for k in names], dtype=np.float64)
    half = dims / 2.0
    tc = np.mean(np.array(list(terminals.values()), dtype=np.float64), axis=0) \
        if terminals else np.array([side / 2.0, side / 2.0])
    pos = rng.uniform(tc[0] - side / 4, tc[0] + side / 4, size=(N, 2))
    pos = np.clip(pos, half, side - half)
    idx = {k: i for i, k in enumerate(names)}
    net_var, net_fix = [], []
    for net in nets:
        v, f = [], []
        for pin in net:
            if pin in idx:
                v.append(idx[pin])
            else:
                f.append((float(terminals[pin][0]), float(terminals[pin][1])))
        net_var.append(v)
        net_fix.append(f)
    deg = np.ones(N, dtype=np.float64)
    for vv in net_var:
        for ii in vv:
            deg[ii] += 1.0
    T = float((dims[:, 0] * dims[:, 1]).sum())
    d_tar = T / (side * side)
    v = np.zeros_like(pos)
    lam, lam_c, gamma = lam0, lam_c0, gamma0
    wl_total = 0.0
    excess = 1.0
    for _ in range(iters):
        look = np.clip(pos + mom * v, -side, 2.0 * side)   # Nesterov 前瞻点（防溢出）
        g_wl = np.zeros_like(pos)
        wl_total = 0.0
        for vv, ff in zip(net_var, net_fix):
            if vv and ff:
                pts = np.vstack([look[vv], np.array(ff, dtype=np.float64)])
            elif vv:
                pts = look[vv]
            elif ff:
                pts = np.array(ff, dtype=np.float64).reshape(-1, 2)
            else:
                continue
            if pts.shape[0] < 2:
                continue
            w, gx, gy = _lse_wl_grad(pts, gamma)
            wl_total += w
            for j, ii in enumerate(vv):
                g_wl[ii, 0] += gx[j]
                g_wl[ii, 1] += gy[j]
        g_wl /= deg[:, None]
        _, g_dens, excess = _density_grad(look, half, side, nbins, d_tar)
        g_c = (look - np.array(tc)) / side
        g = g_wl + lam * g_dens + lam_c * g_c
        v = np.clip(mom * v - lr * side * g, -2.0 * side, 2.0 * side)
        pos = np.clip(pos + v, half, side - half)   # 投影回画布内
        lam = min(lam * lam_ratio, lam_max)
        lam_c = max(lam_c * 0.985, 1e-3)
        gamma = max(gamma_end, gamma * 0.995)
    centers = {names[i]: (pos[i, 0], pos[i, 1]) for i in range(N)}
    wl_exact = hpwl_exact(centers, blocks, blocks, terminals, nets)
    D, _, excess = _density_grad(pos, half, side, nbins, d_tar)
    maxD = float(D.max())
    overflow_cap = float(np.maximum(D - 1.0, 0.0).sum())
    xmax = (pos + half).max(axis=0)
    return {
        "pos": centers,
        "wl_lse": float(wl_total),
        "wl_exact": float(wl_exact),
        "overflow_bin": float(excess),
        "overflow_cap": overflow_cap,
        "max_bin_density": maxD,
        "d_target": float(d_tar),
        "bbox_max": [float(xmax[0]), float(xmax[1])],
    }


# ---------------- 输出 ----------------
def write_outputs(stats, blocks, outdir, chip, tag):
    os.makedirs(outdir, exist_ok=True)
    pos = stats["pos"]
    with open(os.path.join(outdir, f"{chip}_{tag}_placement.csv"), "w") as f:
        f.write("block,x,y,w,h\n")
        for k, (x, y) in sorted(pos.items()):
            w, h = blocks[k]
            f.write(f"{k},{x:.4f},{y:.4f},{w},{h}\n")
    order = {"x": sorted(pos, key=lambda k: pos[k][0]),
             "y": sorted(pos, key=lambda k: pos[k][1]),
             "xy": sorted(pos, key=lambda k: pos[k][0] + pos[k][1])}
    with open(os.path.join(outdir, f"{chip}_{tag}_order.csv"), "w") as f:
        f.write("key,order\n")
        for key, seq in order.items():
            f.write(key + "," + " ".join(seq) + "\n")
    return order


def git_sha():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def write_meta(outdir, chip, side_abs, d_in, params, stats, mode):
    meta = {
        "chip": chip, "mode": mode, "side": side_abs, "d_input": d_in,
        "params": params, "git_sha": git_sha(), "numpy": np.__version__,
        "stats": {k: v for k, v in stats.items() if k != "pos"},
    }
    with open(os.path.join(outdir, f"{chip}_meta.json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def side_from_d(T, d):
    return int(np.ceil(np.sqrt(T * (1 + d))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--chip", required=True)
    ap.add_argument("--mode", choices=["order", "oracle", "both"], default="order")
    ap.add_argument("--side", type=float, default=None,
                    help=">1 视为绝对边长；<1 视为死区比例；缺省 sqrt(T)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--iters", type=int, default=1200)
    ap.add_argument("--oracle-d", default="0.08,0.10,0.12,0.14,0.15")
    ap.add_argument("--lr", type=float, default=0.02)
    ap.add_argument("--lam0", type=float, default=2.0)
    ap.add_argument("--lam-ratio", type=float, default=1.008)
    ap.add_argument("--lam-max", type=float, default=100.0)
    ap.add_argument("--gamma0", type=float, default=40.0)
    ap.add_argument("--gamma-end", type=float, default=4.0)
    ap.add_argument("--mom", type=float, default=0.6)
    args = ap.parse_args()

    blocks, terminals, nets = parse_instance(args.root, args.chip)
    T = float(sum(w * h for w, h in blocks.values()))
    jobs = []
    if args.mode in ("order", "both"):
        side_abs = args.side
        if side_abs is None or side_abs < 1:
            side_abs = side_from_d(T, args.side if args.side else 0.0)
        jobs.append((side_abs, None, "order"))
    if args.mode in ("oracle", "both"):
        for d in [float(x) for x in args.oracle_d.split(",") if x]:
            jobs.append((side_from_d(T, d), d, f"oracle_{d}"))
    for side_abs, d_in, tag in jobs:
        stats = analytic_place(blocks, terminals, nets, side_abs,
                               iters=args.iters, seed=args.seed,
                               lr=args.lr, lam0=args.lam0,
                               lam_ratio=args.lam_ratio, lam_max=args.lam_max,
                               gamma0=args.gamma0, gamma_end=args.gamma_end,
                               mom=args.mom)
        outdir = os.path.join(args.out, args.chip, tag)
        write_outputs(stats, blocks, outdir, args.chip, tag)
        write_meta(outdir, args.chip, side_abs, d_in, dict(
            iters=args.iters, seed=args.seed, lr=args.lr, lam0=args.lam0,
            lam_ratio=args.lam_ratio, lam_max=args.lam_max,
            gamma0=args.gamma0, gamma_end=args.gamma_end, mom=args.mom),
            stats, args.mode)
        print(f"[{args.chip}] tag={tag} side={side_abs} "
              f"wl_exact={stats['wl_exact']:.1f} "
              f"overflow_cap={stats['overflow_cap']:.4f} "
              f"maxD={stats['max_bin_density']:.3f} "
              f"bbox={stats['bbox_max']}")


if __name__ == "__main__":
    main()
