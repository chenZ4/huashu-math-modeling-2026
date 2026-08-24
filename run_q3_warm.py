#!/usr/bin/env python3
"""P4: Q3 暖启动链二分。两级判定：
  L1: --feas-only + 暖启动序（种子并行；任一成功即判可行，并提新序）
  L2: L1 全失败 → 完整 solve + --descent 复核
暖启动序：上一可行 d 的布局按 (y,x) 提序，逐 d 链式传递。
协议对齐 final：lo 起点 0.075、hi=0.15、eps=1e-4、种子 15/15/10。
"""
import json
import math
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "common"))
from verify import parse_blocks, verify_layout
from analytic_placer import hpwl_of_rpt, parse_instance, git_sha, side_from_d

BIN = os.path.join(ROOT, "cpp_solver_opt", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "q3", "output", "warm")
BASE_SEED = 20260808
CHIP_IDX = {"n100": 0, "n200": 1, "n300": 2}
SEEDS = {"n100": 15, "n200": 15, "n300": 10}
ALPHA = 0.5
EPS = 1e-4
WORKERS = 8


def extract_order_from_rpt(rpt):
    lines = open(rpt, encoding="utf-8").read().splitlines()
    # 格式自适应：full rpt 头 5 行（cost/hpwl/area/W H/time）；feas rpt 头 3 行
    start = 3 if (len(lines) and lines[0] in ("0", "1")) else 5
    blocks = []
    for line in lines[start:]:
        p = line.split()
        if len(p) == 5:
            blocks.append((p[0], int(p[1]), int(p[2])))
    if not blocks:
        return None
    blocks.sort(key=lambda b: (b[2], b[1]))
    return [b[0] for b in blocks]


def write_order(chip, d, order):
    if order is None:
        return None
    ddir = os.path.join(OUT, "orders")
    os.makedirs(ddir, exist_ok=True)
    path = os.path.join(ddir, f"{chip}_d{d:.6f}.txt")
    with open(path, "w") as f:
        f.write(" ".join(order) + "\n")
    return path


def feas_check(chip, d, total, seed, warm_file):
    side = side_from_d(total, d)
    rpt = os.path.join(OUT, f"work_{chip}_d{d:.6f}_{seed}.rpt")
    cmd = [BIN, "q2", str(ALPHA),
           os.path.join(DATA, f"{chip}.blocks"),
           os.path.join(DATA, f"{chip}.nets"),
           os.path.join(DATA, f"{chip}.pl"),
           rpt, str(d), "--feas-only", "--seed", str(seed)]
    if warm_file:
        cmd += ["--init-order", warm_file]
    subprocess.run(cmd, check=True)
    first = open(rpt).read().splitlines()[0]
    return int(first) == 1, rpt


def check_feasible(chip, d, total, warm_file, trace):
    """两级判定。返回 (feasible, 新暖启动序文件)。"""
    seeds = SEEDS[chip]
    tasks = [(chip, d, total, BASE_SEED + CHIP_IDX[chip] * 1000 + s, warm_file)
             for s in range(seeds)]
    hits = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(feas_check, *t) for t in tasks]
        for fut in as_completed(futs):
            ok, rpt = fut.result()
            if ok:
                hits.append(rpt)
    if hits:
        order = extract_order_from_rpt(hits[0])
        new_warm = write_order(chip, d, order)
        trace.append({"d": d, "level": 1, "feasible": True,
                      "hits": len(hits), "seeds": seeds})
        return True, new_warm
    # L2: 完整求解复核
    side = side_from_d(total, d)
    rpt2 = os.path.join(OUT, f"l2_{chip}_d{d:.6f}.rpt")
    cmd = [BIN, "q2", str(ALPHA),
           os.path.join(DATA, f"{chip}.blocks"),
           os.path.join(DATA, f"{chip}.nets"),
           os.path.join(DATA, f"{chip}.pl"),
           rpt2, str(d), "--seed", str(BASE_SEED + CHIP_IDX[chip] * 1000),
           "--descent"]
    if warm_file:
        cmd += ["--init-order", warm_file]
    subprocess.run(cmd, check=True)
    lines = open(rpt2, encoding="utf-8").read().splitlines()
    W, H = (int(x) for x in lines[3].split())
    feas = W <= side and H <= side
    if feas:
        order = extract_order_from_rpt(rpt2)
        new_warm = write_order(chip, d, order)
    else:
        new_warm = warm_file
    trace.append({"d": d, "level": 2, "feasible": feas,
                  "hits": 0, "seeds": seeds})
    return feas, new_warm


def main():
    os.makedirs(OUT, exist_ok=True)
    results = {}
    for chip in ("n100", "n200", "n300"):
        dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
        b, t, n = parse_instance(ROOT, chip)
        trace = []
        # 初始暖启动：d=0.15（已知可行）快速判定
        ok, warm = check_feasible(chip, 0.15, total, None, trace)
        assert ok, f"{chip} d=0.15 infeasible?!"
        lo, hi = 0.075, 0.15
        while hi - lo > EPS:
            d = (lo + hi) / 2
            ok, warm_new = check_feasible(chip, d, total, warm, trace)
            if ok:
                hi = d
                warm = warm_new
            else:
                lo = d
        d_star = hi
        # 最终布局：多轮取优（对齐 final 协议 full_solve 精神），带暖启动+descent
        side = side_from_d(total, d_star)
        best = None
        for r in range(10):
            rpt = os.path.join(OUT, f"q3_{chip}_r{r}.rpt")
            cmd = [BIN, "q2", str(ALPHA),
                   os.path.join(DATA, f"{chip}.blocks"),
                   os.path.join(DATA, f"{chip}.nets"),
                   os.path.join(DATA, f"{chip}.pl"),
                   rpt, str(d_star), "--seed",
                   str(BASE_SEED + CHIP_IDX[chip] * 1000 + 200 + r),
                   "--descent"]
            if warm:
                cmd += ["--init-order", warm]
            subprocess.run(cmd, check=True)
            lines = open(rpt, encoding="utf-8").read().splitlines()
            W, H = (int(x) for x in lines[3].split())
            if W <= side and H <= side:
                hpwl = float(lines[1])
                if best is None or hpwl < best[0]:
                    best = (hpwl, rpt)
        if best is None:
            print(f"{chip}: d*={d_star:.6f} final layout NOT found "
                  f"(10 rounds) — trace: {[t['d'] for t in trace[-5:]]}")
            results[chip] = {"d_star": round(d_star, 6), "side": side,
                             "hpwl": None, "trace": trace}
            continue
        rpt = best[1]
        lines = open(rpt, encoding="utf-8").read().splitlines()
        W, H = (int(x) for x in lines[3].split())
        hpwl = float(lines[1])
        ok_l, msg = verify_layout(rpt, dims, outline=(side, side))
        ok_h = abs(hpwl_of_rpt(rpt, b, t, n) - hpwl) < 0.05
        assert ok_l and ok_h, f"{chip} d* verify fail {msg}"
        results[chip] = {"d_star": round(d_star, 6), "side": side,
                         "hpwl": hpwl, "trace": trace}
        print(f"{chip}: d*={d_star:.6f} side={side} hpwl={hpwl:.1f} "
              f"steps={len(trace)}")
    with open(os.path.join(OUT, "metrics.json"), "w") as f:
        json.dump({"results": results, "git_sha": git_sha()}, f,
                  ensure_ascii=False, indent=2)
    print("saved", os.path.join(OUT, "metrics.json"))


if __name__ == "__main__":
    main()
