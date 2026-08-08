"""Q3 求解器：二分求最小死区比例 d*，在 d* 处完整求解更新 HPWL 与布局。
独立于 q1/q2 的代码；仅共享 cpp_solver 核心与 common/ 基础库。"""
import argparse
import csv
import datetime
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "common"))
sys.path.insert(0, os.path.join(ROOT, "q3"))
from verify import parse_blocks, verify_layout  # noqa: E402
from q3_bisect import bisect, verify_infeasible, side_for  # noqa: E402

BIN = os.path.join(ROOT, "cpp_solver", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")
Q3 = os.path.join(ROOT, "q3")
OUT = os.path.join(Q3, "output")
FIGS = os.path.join(Q3, "visualization", "figs")
WORK = os.path.join(OUT, "bisect_work")

CHIPS = ["n100", "n200", "n300"]
CHIP_IDX = {c: i for i, c in enumerate(CHIPS)}
ALPHA = 0.5
BASE_SEED = 20260808


def new_run_dir():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(FIGS, ts)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def full_solve(chip, dead, repeats, side):
    """在给定死区比例下多起点完整求解（run+run2×2，并行轮次取 HPWL 最优）。
    只接受可行轮次（bbox <= 轮廓 side）；保留 best 轮的 rpt/log。"""
    tasks = []
    for r in range(repeats):
        tasks.append((chip, dead, BASE_SEED + CHIP_IDX[chip] * 1000 + r,
                      os.path.join(OUT, f"q3_{chip}_r{r}.rpt"),
                      os.path.join(OUT, f"q3_{chip}_r{r}.log")))
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda t: full_round(*t, side), tasks))

    best = None
    for r in range(repeats):
        rpt = os.path.join(OUT, f"q3_{chip}_r{r}.rpt")
        log = os.path.join(OUT, f"q3_{chip}_r{r}.log")
        lines = open(rpt).read().splitlines()
        W, H = map(int, lines[3].split())
        if W > side or H > side:
            continue
        hpwl = float(lines[1])
        if best is None or hpwl < best[0]:
            best = (hpwl, rpt, log)
    if best is None:
        return None
    rpt = os.path.join(OUT, f"q3_{chip}.rpt")
    log = os.path.join(OUT, f"q3_{chip}.log")
    shutil.copy(best[1], rpt)
    shutil.copy(best[2], log)
    return best[0]


def full_round(chip, dead, seed, rpt, log, side):
    subprocess.run([BIN, "q2", str(ALPHA),
                    os.path.join(DATA, f"{chip}.blocks"),
                    os.path.join(DATA, f"{chip}.nets"),
                    os.path.join(DATA, f"{chip}.pl"),
                    rpt, str(dead), "--log", log, "--seed", str(seed)],
                   check=True)


def run_one(chip, repeats):
    dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
    os.makedirs(WORK, exist_ok=True)
    trace = os.path.join(OUT, f"q3_{chip}_bisect.csv")
    rpt_tmp = os.path.join(WORK, f"feas_{chip}.rpt")

    d_star, iters = bisect(chip, total, WORK, trace)

    side = side_for(d_star, total)
    hpwl = full_solve(chip, d_star, repeats, side)
    if hpwl is None:
        return {
            "chip": chip, "d_star": round(d_star, 6), "side": side,
            "hpwl": float("nan"), "iterations": iters,
            "below_d_check": round(max(0.0, d_star - 0.0001), 6),
            "below_confirmed_infeasible": None,
            "below_results": "n/a", "time_s": 0.0, "legal": False,
            "note": "full solve at d* found no feasible layout",
        }
    rpt = os.path.join(OUT, f"q3_{chip}.rpt")
    lines = open(rpt).read().splitlines()
    time_s = float(lines[4])
    ok, msg = verify_layout(rpt, dims, outline=(side, side))

    below_ok, below_results = verify_infeasible(chip, max(0.0, d_star - 0.0001),
                                                total, WORK, rpt_tmp)
    return {
        "chip": chip, "d_star": round(d_star, 6), "side": side,
        "hpwl": round(hpwl, 2), "iterations": iters,
        "below_d_check": round(max(0.0, d_star - 0.0001), 6),
        "below_confirmed_infeasible": below_ok,
        "below_results": str(below_results),
        "time_s": round(time_s, 2), "legal": ok, "note": msg,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=10, help="d* 处完整求解轮数")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    run_dir = new_run_dir()
    print("run dir:", run_dir)

    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(lambda c: run_one(c, args.repeats), CHIPS))

    csv_path = os.path.join(OUT, "q3_metrics.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(open(csv_path).read())

    viz = os.path.join(Q3, "visualization")
    for r in results:
        chip = r["chip"]
        chip_dir = os.path.join(run_dir, chip)
        os.makedirs(chip_dir, exist_ok=True)
        rpt = os.path.join(OUT, f"q3_{chip}.rpt")
        log = os.path.join(OUT, f"q3_{chip}.log")
        trace = os.path.join(OUT, f"q3_{chip}_bisect.csv")
        subprocess.run([sys.executable, os.path.join(viz, "plot_floorplan.py"),
                        "--rpt", rpt, "--side", str(r["side"]),
                        "--out", os.path.join(chip_dir, "floorplan.png")],
                       check=True)
        subprocess.run([sys.executable, os.path.join(viz, "plot_convergence.py"),
                        "--log", log, "--out", os.path.join(chip_dir, "convergence.png")],
                       check=True)
        subprocess.run([sys.executable, os.path.join(viz, "plot_snapshots.py"),
                        "--log", log, "--outdir", os.path.join(chip_dir, "snapshots")],
                       check=True)
        subprocess.run([sys.executable, os.path.join(viz, "plot_bisect.py"),
                        "--trace", trace, "--dstar", str(r["d_star"]),
                        "--out", os.path.join(chip_dir, "bisect.png")],
                       check=True)
    print("figures ->", run_dir)


if __name__ == "__main__":
    main()
