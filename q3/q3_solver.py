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
from q3_bisect import bisect, confirm_minimum, side_for  # noqa: E402

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


def full_solve(chip, dead, repeats, side, outdir=None):
    """在给定死区比例下多起点完整求解（run+run2×2，并行轮次取 HPWL 最优）。
    只接受可行轮次（bbox <= 轮廓 side）；保留 best 轮的 rpt/log。"""
    out = outdir or OUT
    os.makedirs(out, exist_ok=True)
    tasks = []
    for r in range(repeats):
        tasks.append((chip, dead, BASE_SEED + CHIP_IDX[chip] * 1000 + r,
                      os.path.join(out, f"q3_{chip}_r{r}.rpt"),
                      os.path.join(out, f"q3_{chip}_r{r}.log")))
    with ThreadPoolExecutor(max_workers=3) as ex:
        list(ex.map(lambda t: full_round(*t, side), tasks))

    best = None
    for r in range(repeats):
        rpt = os.path.join(out, f"q3_{chip}_r{r}.rpt")
        log = os.path.join(out, f"q3_{chip}_r{r}.log")
        lines = open(rpt).read().splitlines()
        W, H = map(int, lines[3].split())
        if W > side or H > side:
            continue
        hpwl = float(lines[1])
        if best is None or hpwl < best[0]:
            best = (hpwl, rpt, log)
    if best is None:
        return None
    rpt = os.path.join(out, f"q3_{chip}.rpt")
    log = os.path.join(out, f"q3_{chip}.log")
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


def run_one(chip, repeats, seeds=3, confirm_seeds=0, outdir=None):
    out = outdir or OUT
    dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
    work = os.path.join(out, "bisect_work")
    os.makedirs(work, exist_ok=True)
    trace = os.path.join(out, f"q3_{chip}_bisect.csv")

    coarse = max(1, seeds // 2)
    d_bisect = None
    iters = 0
    if os.path.exists(trace):
        rows = list(csv.DictReader(open(trace)))
        if len(rows) >= 5:
            d_bisect = float(rows[-1]["hi"])
            iters = len(rows)
    if d_bisect is None:
        d_bisect, iters = bisect(chip, total, work, trace,
                                 coarse_seeds=coarse, precise_seeds=seeds)
    cs = confirm_seeds if confirm_seeds > 0 else seeds
    d_star, confirm_steps = confirm_minimum(chip, d_bisect, total, work,
                                            verify_seeds=cs)

    side = side_for(d_star, total)
    hpwl = full_solve(chip, d_star, repeats, side, out)
    if hpwl is None:
        return {
            "chip": chip, "d_star": round(d_star, 6), "side": side,
            "hpwl": float("nan"), "iterations": iters,
            "confirm": str(confirm_steps), "time_s": 0.0, "legal": False,
            "note": "full solve at d* found no feasible layout",
        }
    rpt = os.path.join(out, f"q3_{chip}.rpt")
    lines = open(rpt).read().splitlines()
    time_s = float(lines[4])
    ok, msg = verify_layout(rpt, dims, outline=(side, side))
    confirmed = bool(confirm_steps) and confirm_steps[-1].get("below_infeas", False)
    return {
        "chip": chip, "d_star": round(d_star, 6), "side": side,
        "hpwl": round(hpwl, 2), "iterations": iters,
        "d_confirmed_minimum": confirmed,
        "confirm_steps": str(confirm_steps),
        "time_s": round(time_s, 2), "legal": ok, "note": msg,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=10, help="d* 处完整求解轮数")
    ap.add_argument("--seeds", type=int, default=3, help="判定种子数（n100/n200 定稿取 15，n300 取 10）")
    ap.add_argument("--confirm-seeds", type=int, default=0, help="确认种子数（0=与判定一致）")
    ap.add_argument("--outdir", default=OUT, help="输出目录（定稿用 output/final）")
    ap.add_argument("--chip", choices=CHIPS, default=None, help="只求解指定芯片（定稿逐芯片种子）")
    args = ap.parse_args()
    chips = [args.chip] if args.chip else CHIPS
    os.makedirs(args.outdir, exist_ok=True)
    run_dir = new_run_dir()
    print("run dir:", run_dir)

    with ThreadPoolExecutor(max_workers=3) as ex:
        results = list(ex.map(
            lambda c: run_one(c, args.repeats, args.seeds,
                              args.confirm_seeds, args.outdir), chips))

    csv_path = os.path.join(args.outdir, "q3_metrics.csv")
    existing = []
    if os.path.exists(csv_path):
        with open(csv_path) as fh:
            existing = [dict(r) for r in csv.DictReader(fh)]
    merged = {r["chip"]: r for r in existing}
    for r in results:
        merged[r["chip"]] = r
    rows = [merged[c] for c in CHIPS if c in merged]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(open(csv_path).read())

    viz = os.path.join(Q3, "visualization")
    for r in results:
        chip = r["chip"]
        chip_dir = os.path.join(run_dir, chip)
        os.makedirs(chip_dir, exist_ok=True)
        rpt = os.path.join(args.outdir, f"q3_{chip}.rpt")
        log = os.path.join(args.outdir, f"q3_{chip}.log")
        trace = os.path.join(args.outdir, f"q3_{chip}_bisect.csv")
        if os.path.exists(rpt):
            subprocess.run([sys.executable, os.path.join(viz, "plot_floorplan.py"),
                            "--rpt", rpt, "--side", str(r["side"]),
                            "--out", os.path.join(chip_dir, "floorplan.png")],
                           check=True)
        if os.path.exists(log):
            subprocess.run([sys.executable, os.path.join(viz, "plot_convergence.py"),
                            "--log", log, "--out", os.path.join(chip_dir, "convergence.png")],
                           check=True)
            subprocess.run([sys.executable, os.path.join(viz, "plot_snapshots.py"),
                            "--log", log, "--outdir", os.path.join(chip_dir, "snapshots")],
                           check=True)
        if os.path.exists(trace):
            subprocess.run([sys.executable, os.path.join(viz, "plot_bisect.py"),
                            "--trace", trace, "--dstar", str(r["d_star"]),
                            "--out", os.path.join(chip_dir, "bisect.png")],
                           check=True)
    print("figures ->", run_dir)


if __name__ == "__main__":
    main()
