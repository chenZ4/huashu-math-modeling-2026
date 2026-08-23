#!/usr/bin/env python3
"""Q2 解析初始臂：--init-order + 定稿协议（t2-div 35/60/70，seed=20260808+r）。
输出：q2/output/analytic_init/（rpt+metrics+meta），每轮过 verify 与 HPWL 独立重算。
用法：python q2/analytic_init_run.py --chip n300 --key x --rounds 8
"""
import argparse
import csv
import json
import math
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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


def run_round(chip, seed, rpt, log, t2_div, order_file):
    cmd = [BIN, "q2", str(ALPHA),
           os.path.join(DATA, f"{chip}.blocks"),
           os.path.join(DATA, f"{chip}.nets"),
           os.path.join(DATA, f"{chip}.pl"),
           rpt, str(DEAD), "--log", log, "--seed", str(seed),
           "--t2-div", str(t2_div), "--init-order", order_file]
    subprocess.run(cmd, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chip", required=True, choices=["n100", "n200", "n300"])
    ap.add_argument("--key", required=True, choices=["x", "y", "xy", "rand"])
    ap.add_argument("--rounds", type=int, default=8)
    args = ap.parse_args()
    chip = args.chip

    dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
    side = math.ceil(math.sqrt(total * (1.0 + DEAD)))
    order_file = os.path.join(ORDER_DIR, f"order_{chip}_q2_d15_{args.key}.txt") \
        if args.key != "rand" else None
    if order_file and not os.path.exists(order_file):
        print("order file missing:", order_file)
        sys.exit(1)

    tasks = []
    for r in range(args.rounds):
        tasks.append((chip, BASE_SEED + r,
                      os.path.join(OUT, f"q2_{chip}_{args.key}_r{r}.rpt"),
                      os.path.join(OUT, f"q2_{chip}_{args.key}_r{r}.log"),
                      T2_DIV[chip], order_file))
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda t: run_round(*t), tasks))

    hpwls, legal, bad = [], [], 0
    b, t, n = parse_instance(ROOT, chip)
    for r in range(args.rounds):
        rpt = os.path.join(OUT, f"q2_{chip}_{args.key}_r{r}.rpt")
        lines = open(rpt, encoding="utf-8").read().splitlines()
        W, H = (int(x) for x in lines[3].split())
        hpwl = float(lines[1])
        hpwls.append(hpwl)
        ok_layout, msg = verify_layout(rpt, dims, outline=(side, side))
        ok_hpwl = abs(hpwl_of_rpt(rpt, b, t, n) - hpwl) < 0.05
        if not ok_layout or not ok_hpwl:
            print(f"  [{chip} r{r}] VERIFY FAIL: layout={ok_layout} hpwl={ok_hpwl} {msg}")
            sys.exit(1)
        if W <= side and H <= side:
            legal.append(hpwl)
        else:
            bad += 1
    if not legal:
        print(f"{chip} {args.key}: no legal runs")
        sys.exit(1)
    stats = {
        "chip": chip, "key": args.key, "rounds": args.rounds,
        "side": side, "t2_div": T2_DIV[chip], "n_legal": len(legal),
        "n_illegal": bad, "min": min(legal), "median": statistics.median(legal),
        "mean": round(statistics.mean(legal), 1), "max": max(legal),
        "std": round(statistics.pstdev(legal), 1),
        "spread_pct": round((max(legal) - min(legal)) / min(legal) * 100, 1),
        "med_min_ratio": round(statistics.median(legal) / min(legal), 2),
    }
    with open(os.path.join(OUT, f"q2_{chip}_{args.key}_metrics.json"), "w") as f:
        json.dump({**stats, "git_sha": git_sha(),
                   "order_file": order_file}, f, ensure_ascii=False, indent=2)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
