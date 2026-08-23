#!/usr/bin/env python3
"""Q3 解析初始臂抽查：在已确认 d* 处跑逐种子判定，对比随机臂成功判定率。
用法：python run_q3_spot.py
"""
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "common"))
from analytic_placer import parse_instance, side_from_d, git_sha

BIN = os.path.join(ROOT, "cpp_solver_opt", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "q3", "output", "analytic_init")
ORDER_DIR = os.path.join(ROOT, "q2", "output", "analytic_init", "order")

BASE_SEED = 20260808
CHIP_IDX = {"n100": 0, "n200": 1, "n300": 2}
D_STAR = {"n100": 0.076072, "n200": 0.084141, "n300": 0.111773}
SEEDS = {"n100": 15, "n200": 15, "n300": 10}
KEYS = {"n100": ["x", "xy"], "n200": ["xy"], "n300": ["y", "xy"]}
WORKERS = 8


def feas_check(chip, key, dead, seed, work_dir):
    order = os.path.join(ORDER_DIR, f"order_{chip}_q3_d12_{key}.txt")
    rpt = os.path.join(work_dir, f"f_{chip}_{key}_{seed}.rpt")
    cmd = [BIN, "q2", "0.5",
           os.path.join(DATA, f"{chip}.blocks"),
           os.path.join(DATA, f"{chip}.nets"),
           os.path.join(DATA, f"{chip}.pl"),
           rpt, str(dead), "--feas-only", "--seed", str(seed),
           "--init-order", order]
    subprocess.run(cmd, check=True)
    return float(open(rpt).read().splitlines()[0])


def main():
    os.makedirs(OUT, exist_ok=True)
    results = {}
    for chip, keys in KEYS.items():
        for key in keys:
            b, t, n = parse_instance(ROOT, chip)
            T = float(sum(w * h for w, h in b.values()))
            side = side_from_d(T, D_STAR[chip])
            work_dir = os.path.join(OUT, f"work_{chip}_{key}")
            os.makedirs(work_dir, exist_ok=True)
            tasks = []
            for s in range(SEEDS[chip]):
                tasks.append((chip, key, D_STAR[chip],
                              BASE_SEED + CHIP_IDX[chip] * 1000 + s, work_dir))
            hits = 0
            with ThreadPoolExecutor(max_workers=WORKERS) as ex:
                futs = [ex.submit(feas_check, *t) for t in tasks]
                for fut in as_completed(futs):
                    hits += int(fut.result())
            rate = hits / SEEDS[chip]
            results[f"{chip}_{key}"] = {
                "d_star": D_STAR[chip], "seeds": SEEDS[chip],
                "feasible_hits": hits, "rate": round(rate, 4)}
            print(f"{chip} {key}: d*={D_STAR[chip]} hits={hits}/"
                  f"{SEEDS[chip]} rate={rate:.1%}")
    with open(os.path.join(OUT, "spot_metrics.json"), "w") as f:
        json.dump({**results, "git_sha": git_sha()}, f, ensure_ascii=False,
                  indent=2)
    print("saved", os.path.join(OUT, "spot_metrics.json"))


if __name__ == "__main__":
    main()
