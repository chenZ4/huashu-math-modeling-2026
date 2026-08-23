import csv
import math
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.sys.path.insert(0, os.path.join(ROOT, "common"))
from verify import parse_blocks  # noqa: E402

BIN = os.path.join(ROOT, "cpp_solver", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")

D_LO = 0.0
D_HI = 0.15
EPS = 1e-4
PRECISE_THRESHOLD = 0.01
BASE_SEED = 20260808
CHIP_IDX = {"n100": 0, "n200": 1, "n300": 2}
COARSE_SEEDS = 2
PRECISE_SEEDS = 3
VERIFY_SEEDS = 3


def side_for(dead, total):
    return math.ceil(math.sqrt(total * (1.0 + dead)))


def _one_check(chip, dead, total, seed, work_dir):
    rpt = os.path.join(work_dir, f"feas_{seed}.rpt")
    cmd = [BIN, "q2", "0.5",
           os.path.join(DATA, f"{chip}.blocks"),
           os.path.join(DATA, f"{chip}.nets"),
           os.path.join(DATA, f"{chip}.pl"),
           rpt, str(dead), "--feas-only", "--seed", str(seed)]
    subprocess.run(cmd, check=True)
    lines = open(rpt).read().splitlines()
    feasible = int(lines[0]) == 1
    W, H = map(int, lines[1].split())
    hpwl = float(lines[2])
    side = side_for(dead, total)
    assert side * side >= total, f"theoretical lower bound violated: side={side}"
    return feasible, (W, H), hpwl


def feas_check_parallel(chip, dead, total, work_dir, n_seeds, tag):
    """并行 n_seeds 个独立种子判定，任一可行即可行。返回 (feasible, 明细)。"""
    seeds = [BASE_SEED + CHIP_IDX[chip] * 10000 + tag * 100 + i
             for i in range(n_seeds)]
    with ThreadPoolExecutor(max_workers=n_seeds) as ex:
        results = list(ex.map(lambda s: _one_check(chip, dead, total, s, work_dir),
                              seeds))
    feasible = any(r[0] for r in results)
    return feasible, results


def bisect(chip, total, work_dir, trace_path, eps=EPS,
            coarse_seeds=COARSE_SEEDS, precise_seeds=PRECISE_SEEDS):
    """二分 [D_LO, D_HI]，<eps 早停。返回 (d_star, 迭代步数)。"""
    lo, hi = D_LO, D_HI
    rows = []
    it = 0
    while hi - lo >= eps:
        it += 1
        mid = (lo + hi) / 2.0
        n_seeds = coarse_seeds if (hi - lo) >= PRECISE_THRESHOLD else precise_seeds
        t0 = time.time()
        feasible, results = feas_check_parallel(chip, mid, total, work_dir,
                                                n_seeds, it)
        dt = time.time() - t0
        bb = results[0][1]
        if feasible:
            hi = mid
        else:
            lo = mid
        rows.append([it, lo, hi, mid, side_for(mid, total),
                     f"{bb[0]}x{bb[1]}", int(feasible), n_seeds, round(dt, 1)])
    with open(trace_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["iter", "lo", "hi", "mid", "side", "bbox", "feasible",
                    "attempts", "time_s"])
        w.writerows(rows)
    return hi, it


def verify_at(chip, d_check, total, work_dir, tag, n_seeds=VERIFY_SEEDS):
    """在 d_check 处做 n_seeds 次并行判定。返回 (all_feasible, results)。"""
    feasible, results = feas_check_parallel(chip, d_check, total, work_dir,
                                            n_seeds, tag)
    return feasible, results


def confirm_minimum(chip, d_star, total, work_dir, verify_seeds=VERIFY_SEEDS):
    """双向确认：d* 本身必须可行（不可行则上移 +EPS 重验）；
    d*-EPS 处多种子必须全不可行（有可行则下移重验）。
    返回 (final_d, 确认记录)。"""
    steps = []
    for k in range(12):
        feas_here, r_here = verify_at(chip, d_star, total, work_dir, 900 + k,
                                        n_seeds=verify_seeds)
        if not feas_here:
            d_star = min(D_HI, d_star + EPS)
            steps.append({"d": round(d_star, 6), "d_feas": False,
                          "note": "up-shift"})
            continue
        below = max(0.0, d_star - EPS)
        feas_below, r_below = verify_at(chip, below, total, work_dir, 950 + k,
                                           n_seeds=verify_seeds)
        steps.append({"d": round(d_star, 6), "below": round(below, 6),
                      "d_feas": True, "below_infeas": not feas_below,
                      "below_results": [r[0] for r in r_below]})
        if not feas_below:
            return d_star, steps
        d_star = below
    return d_star, steps
