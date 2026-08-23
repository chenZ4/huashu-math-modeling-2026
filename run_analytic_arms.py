#!/usr/bin/env python3
"""M4 解析臂批量执行（多线程）：Q2 n200 三键 + n300 y/xy 补全。
8 进程并行，每轮输出 rpt/log，结束后逐轮 verify + HPWL 重算，写 metrics json。
"""
import json
import math
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "common"))
from verify import parse_blocks, verify_layout
from analytic_placer import hpwl_of_rpt, parse_instance, git_sha

BIN = os.path.join(ROOT, "cpp_solver_opt", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "q2", "output", "analytic_init")
ORDER_DIR = os.path.join(OUT, "order")

BASE_SEED = 20260808
DEAD = 0.15
ALPHA = 0.5
T2_DIV = {"n100": 35, "n200": 60, "n300": 70}
JOBS = [("n200", "x", 8), ("n200", "y", 8), ("n200", "xy", 8),
        ("n300", "y", 8), ("n300", "xy", 8)]
WORKERS = 8


def run_round(chip, key, seed, t2_div, order_file):
    rpt = os.path.join(OUT, f"q2_{chip}_{key}_r{seed - BASE_SEED}.rpt")
    log = os.path.join(OUT, f"q2_{chip}_{key}_r{seed - BASE_SEED}.log")
    if os.path.exists(rpt):
        return rpt, "skip"
    cmd = [BIN, "q2", str(ALPHA),
           os.path.join(DATA, f"{chip}.blocks"),
           os.path.join(DATA, f"{chip}.nets"),
           os.path.join(DATA, f"{chip}.pl"),
           rpt, str(DEAD), "--log", log, "--seed", str(seed),
           "--t2-div", str(t2_div), "--init-order", order_file]
    subprocess.run(cmd, check=True)
    return rpt, "run"


def main():
    dims_cache, inst_cache = {}, {}
    tasks = []
    for chip, key, rounds in JOBS:
        order_file = os.path.join(ORDER_DIR, f"order_{chip}_q2_d15_{key}.txt")
        assert os.path.exists(order_file), order_file
        for r in range(rounds):
            tasks.append((chip, key, BASE_SEED + r, T2_DIV[chip], order_file))
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(run_round, *t) for t in tasks]
        done = 0
        for fut in as_completed(futs):
            done += 1
            rpt, act = fut.result()
            if act == "run":
                print(f"[{done}/{len(tasks)}] {os.path.basename(rpt)}")
    # 统计 + 复核
    for chip, key, rounds in JOBS:
        if chip not in dims_cache:
            dims_cache[chip], _ = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
            inst_cache[chip] = parse_instance(ROOT, chip)
        side = math.ceil(math.sqrt(
            sum(w * h for w, h in dims_cache[chip].values()) * (1.0 + DEAD)))
        hpwls, legal, bad = [], [], 0
        for r in range(rounds):
            rpt = os.path.join(OUT, f"q2_{chip}_{key}_r{r}.rpt")
            lines = open(rpt, encoding="utf-8").read().splitlines()
            W, H = (int(x) for x in lines[3].split())
            hpwl = float(lines[1])
            hpwls.append(hpwl)
            ok_l, msg = verify_layout(rpt, dims_cache[chip],
                                      outline=(side, side) if (W <= side and H <= side) else None)
            ok_h = abs(hpwl_of_rpt(rpt, *inst_cache[chip]) - hpwl) < 0.05
            if not ok_l or not ok_h:
                print(f"  VERIFY FAIL {chip} {key} r{r}: layout={ok_l} hpwl={ok_h} {msg}")
                sys.exit(1)
            if W <= side and H <= side:
                legal.append(hpwl)
            else:
                bad += 1
        stats = {
            "chip": chip, "key": key, "rounds": rounds, "side": side,
            "t2_div": T2_DIV[chip], "n_legal": len(legal), "n_illegal": bad,
            "min": min(legal) if legal else None,
            "median": statistics.median(legal) if legal else None,
            "mean": round(statistics.mean(legal), 1) if legal else None,
            "max": max(legal) if legal else None,
            "spread_pct": round((max(legal) - min(legal)) / min(legal) * 100, 1)
            if legal else None,
            "med_min_ratio": round(statistics.median(legal) / min(legal), 2)
            if legal else None,
        }
        with open(os.path.join(OUT, f"q2_{chip}_{key}_metrics.json"), "w") as f:
            json.dump({**stats, "git_sha": git_sha()}, f, ensure_ascii=False, indent=2)
        print(f"== {chip} {key}: {json.dumps(stats, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
