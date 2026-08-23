#!/usr/bin/env python3
"""Q1 解析初始臂（n300，3 键 × 8 轮，8 进程并行）。"""
import json
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "common"))
from verify import parse_blocks, verify_layout
from analytic_placer import git_sha

BIN = os.path.join(ROOT, "cpp_solver_opt", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "q1", "output", "analytic_init")
ORDER_DIR = os.path.join(ROOT, "q2", "output", "analytic_init", "order")

BASE_SEED = 20260808
T2_DIV = 20
JOBS = [("n300", "x"), ("n300", "y"), ("n300", "xy")]
WORKERS = 8


def run_round(chip, key, seed):
    rpt = os.path.join(OUT, f"q1_{chip}_{key}_r{seed - BASE_SEED}.rpt")
    log = os.path.join(OUT, f"q1_{chip}_{key}_r{seed - BASE_SEED}.log")
    if os.path.exists(rpt):
        return rpt, "skip"
    order = os.path.join(ORDER_DIR, f"order_{chip}_q1_sqrtT_{key}.txt")
    cmd = [BIN, "q1", "0.5",
           os.path.join(DATA, f"{chip}.blocks"),
           os.path.join(DATA, f"{chip}.nets"),
           os.path.join(DATA, f"{chip}.pl"),
           rpt, "--log", log, "--seed", str(seed),
           "--t2-div", str(T2_DIV), "--init-order", order]
    subprocess.run(cmd, check=True)
    return rpt, "run"


def main():
    os.makedirs(OUT, exist_ok=True)
    dims, _ = parse_blocks(os.path.join(DATA, "n300.blocks"))
    tasks = [(c, k, BASE_SEED + r) for c, k in JOBS for r in range(8)]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(run_round, *t) for t in tasks]
        for i, fut in enumerate(as_completed(futs), 1):
            rpt, act = fut.result()
            if act == "run":
                print(f"[{i}/{len(tasks)}] {os.path.basename(rpt)}")
    for chip, key in JOBS:
        areas, aspects = [], []
        for r in range(8):
            rpt = os.path.join(OUT, f"q1_{chip}_{key}_r{r}.rpt")
            lines = open(rpt, encoding="utf-8").read().splitlines()
            W, H = (int(x) for x in lines[3].split())
            area = float(lines[2])
            ok, msg = verify_layout(rpt, dims)
            if not ok:
                print(f"  VERIFY FAIL {chip} {key} r{r}: {msg}")
                sys.exit(1)
            areas.append(area)
            aspects.append(max(W, H) / min(W, H))
        best_i = areas.index(min(areas))
        stats = {
            "chip": chip, "key": key, "rounds": 8,
            "min_area": min(areas), "median_area": statistics.median(areas),
            "mean_area": round(statistics.mean(areas), 1),
            "spread_pct": round((max(areas) - min(areas)) / min(areas) * 100, 1),
            "best_aspect": round(aspects[best_i], 4),
        }
        with open(os.path.join(OUT, f"q1_{chip}_{key}_metrics.json"), "w") as f:
            json.dump({**stats, "git_sha": git_sha()}, f, ensure_ascii=False,
                      indent=2)
        print(f"== {chip} {key}: {json.dumps(stats, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
