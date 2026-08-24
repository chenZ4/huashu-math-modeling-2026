#!/usr/bin/env python3
"""P5: Q1 n300 xy 序 × λ{0.5,0.55,0.6} × 16 轮 + descent（8 进程）。
对照：final n300 面积 285228 / 长宽比 1.6403（λ=0.5, 24 轮随机）。
"""
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
OUT = os.path.join(ROOT, "q1", "output", "xy_lambda")
ORDER = os.path.join(ROOT, "q2/output/analytic_init/order",
                     "order_n300_q1_sqrtT_xy.txt")
BASE_SEED = 20260808
T2 = 20
WORKERS = 8


def run_round(lam, seed):
    rpt = os.path.join(OUT, f"q1_n300_lam{lam}_r{seed - BASE_SEED}.rpt")
    if os.path.exists(rpt):
        return rpt, "skip"
    cmd = [BIN, "q1", str(lam),
           os.path.join(DATA, "n300.blocks"),
           os.path.join(DATA, "n300.nets"),
           os.path.join(DATA, "n300.pl"),
           rpt, "--seed", str(seed), "--t2-div", str(T2),
           "--descent", "--init-order", ORDER]
    subprocess.run(cmd, check=True)
    return rpt, "run"


def main():
    os.makedirs(OUT, exist_ok=True)
    dims, _ = parse_blocks(os.path.join(DATA, "n300.blocks"))
    for lam in (0.5, 0.55, 0.6):
        tasks = [(lam, BASE_SEED + 800 + r) for r in range(16)]
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(run_round, *t) for t in tasks]
            for fut in as_completed(futs):
                fut.result()
        areas, aspects = [], []
        for r in range(16):
            rpt = os.path.join(OUT, f"q1_n300_lam{lam}_r{800 + r}.rpt")
            lines = open(rpt, encoding="utf-8").read().splitlines()
            W, H = (int(x) for x in lines[3].split())
            area = float(lines[2])
            ok, msg = verify_layout(rpt, dims)
            if not ok:
                print(f"  VERIFY FAIL lam{lam} r{r}: {msg}")
                sys.exit(1)
            areas.append(area)
            aspects.append(max(W, H) / min(W, H))
        bi = areas.index(min(areas))
        stats = {"chip": "n300", "lambda": lam, "rounds": 16,
                 "min_area": min(areas), "median_area": statistics.median(areas),
                 "mean_area": round(statistics.mean(areas), 1),
                 "spread_pct": round((max(areas) - min(areas)) / min(areas) * 100, 1),
                 "best_aspect": round(aspects[bi], 4)}
        print(lam, stats)
        with open(os.path.join(OUT, f"metrics_lam{lam}.json"), "w") as f:
            json.dump({**stats, "git_sha": git_sha()}, f,
                      ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
