"""Q2 求解器：固定正方形轮廓（dead_ratio=0.15），最小化总 HPWL。
多起点独立退火：每芯片并行跑 N 轮（不同随机种子），取 HPWL 最优。
独立于 q1/q3 的代码；仅共享 cpp_solver 核心与 common/ 基础库。"""
import argparse
import csv
import datetime
import math
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "common"))
from verify import parse_blocks, verify_layout

BIN = os.path.join(ROOT, "cpp_solver", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")
Q2 = os.path.join(ROOT, "q2")
OUT = os.path.join(Q2, "output")
FIGS = os.path.join(Q2, "visualization", "figs")

CHIPS = ["n100", "n200", "n300"]
CHIP_IDX = {c: i for i, c in enumerate(CHIPS)}
DEAD = 0.15
ALPHA = 0.5
BASE_SEED = 20260808
ROUND_WORKERS = 3
CHIP_WORKERS = 3


def new_run_dir():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(FIGS, ts)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def run_round(chip, alpha, dead, seed, rpt, log):
    subprocess.run([BIN, "q2", str(alpha),
                    os.path.join(DATA, f"{chip}.blocks"),
                    os.path.join(DATA, f"{chip}.nets"),
                    os.path.join(DATA, f"{chip}.pl"),
                    rpt, str(dead), "--log", log, "--seed", str(seed)],
                   check=True)


def run_one(chip, alpha, dead, rounds):
    dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
    side = math.ceil(math.sqrt(total * (1.0 + dead)))
    tasks = []
    for r in range(rounds):
        tasks.append((chip, alpha, dead,
                      BASE_SEED + CHIP_IDX[chip] * 1000 + r,
                      os.path.join(OUT, f"q2_{chip}_r{r}.rpt"),
                      os.path.join(OUT, f"q2_{chip}_r{r}.log")))
    with ThreadPoolExecutor(max_workers=ROUND_WORKERS) as ex:
        list(ex.map(lambda t: run_round(*t), tasks))

    best = None
    for r in range(rounds):
        rpt = os.path.join(OUT, f"q2_{chip}_r{r}.rpt")
        log = os.path.join(OUT, f"q2_{chip}_r{r}.log")
        lines = open(rpt).read().splitlines()
        W, H = map(int, lines[3].split())
        if W > side or H > side:
            continue
        hpwl = float(lines[1])
        time_s = float(lines[4])
        if best is None or hpwl < best[0]:
            best = (hpwl, W, H, int(lines[2]), time_s, rpt, log)

    if best is None:
        return {
            "chip": chip, "side": side, "hpwl": float("nan"),
            "utilization": 0.0, "repeats_used": 0, "seed_base": BASE_SEED,
            "time_s": 0.0, "legal": False,
            "note": "no feasible solution found in any round",
        }
    hpwl, W, H, area, time_s, best_rpt, best_log = best
    rpt = os.path.join(OUT, f"q2_{chip}.rpt")
    log = os.path.join(OUT, f"q2_{chip}.log")
    shutil.copy(best_rpt, rpt)
    shutil.copy(best_log, log)
    ok, msg = verify_layout(rpt, dims, outline=(side, side))
    return {
        "chip": chip, "side": side, "hpwl": round(hpwl, 2),
        "utilization": round(total / (side * side), 4),
        "repeats_used": rounds, "seed_base": BASE_SEED,
        "time_s": round(time_s, 2), "legal": ok, "note": msg,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=8, help="每芯片并行轮数")
    ap.add_argument("--skip-solve", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    run_dir = new_run_dir()
    print("run dir:", run_dir)

    results = []
    if args.skip_solve:
        for chip in CHIPS:
            dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
            side = math.ceil(math.sqrt(total * (1.0 + DEAD)))
            rpt = os.path.join(OUT, f"q2_{chip}.rpt")
            lines = open(rpt).read().splitlines()
            hpwl = float(lines[1])
            time_s = float(lines[4])
            ok, msg = verify_layout(rpt, dims, outline=(side, side))
            results.append({
                "chip": chip, "side": side, "hpwl": round(hpwl, 2),
                "utilization": round(total / (side * side), 4),
                "repeats_used": None, "seed_base": BASE_SEED,
                "time_s": round(time_s, 2), "legal": ok, "note": msg,
            })
    else:
        with ThreadPoolExecutor(max_workers=CHIP_WORKERS) as ex:
            results = list(ex.map(lambda c: run_one(c, ALPHA, DEAD, args.repeats),
                                  CHIPS))

    csv_path = os.path.join(OUT, "q2_metrics.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(open(csv_path).read())

    viz = os.path.join(Q2, "visualization")
    for r in results:
        chip = r["chip"]
        chip_dir = os.path.join(run_dir, chip)
        os.makedirs(chip_dir, exist_ok=True)
        rpt = os.path.join(OUT, f"q2_{chip}.rpt")
        log = os.path.join(OUT, f"q2_{chip}.log")
        subprocess.run([sys.executable, os.path.join(viz, "plot_floorplan.py"),
                        "--rpt", rpt, "--out", os.path.join(chip_dir, "floorplan.png")],
                       check=True)
        subprocess.run([sys.executable, os.path.join(viz, "plot_convergence.py"),
                        "--log", log, "--out", os.path.join(chip_dir, "convergence.png")],
                       check=True)
        subprocess.run([sys.executable, os.path.join(viz, "plot_snapshots.py"),
                        "--log", log, "--outdir", os.path.join(chip_dir, "snapshots")],
                       check=True)
    print("figures ->", run_dir)


if __name__ == "__main__":
    main()
