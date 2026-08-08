"""Q3 二分搜索：求解最小可行死区比例 d*。
独立于 q1/q2 的代码；判定调用共享 C++ 核心的 --feas-only 模式。"""
import csv
import math
import os
import subprocess
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys_path = None
if ROOT not in os.sys.path:
    os.sys.path.insert(0, os.path.join(ROOT, "common"))
from verify import parse_blocks  # noqa: E402

BIN = os.path.join(ROOT, "cpp_solver", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")

D_LO = 0.0
D_HI = 0.15
EPS = 1e-4
PRECISE_THRESHOLD = 0.01
JUDGE_ATTEMPTS = 3


def side_for(dead, total):
    return math.ceil(math.sqrt(total * (1.0 + dead)))


def feas_check(chip, dead, total, work_dir, rpt_path):
    """一次可行性判定。返回 (feasible, side, bbox, hpwl)。"""
    cmd = [BIN, "q2", "0.5",
           os.path.join(DATA, f"{chip}.blocks"),
           os.path.join(DATA, f"{chip}.nets"),
           os.path.join(DATA, f"{chip}.pl"),
           rpt_path, str(dead), "--feas-only"]
    subprocess.run(cmd, check=True)
    lines = open(rpt_path).read().splitlines()
    feasible = int(lines[0]) == 1
    W, H = map(int, lines[1].split())
    hpwl = float(lines[2])
    side = side_for(dead, total)
    assert side * side >= total, f"theoretical lower bound violated: side={side}"
    return feasible, side, (W, H), hpwl


def bisect(chip, total, work_dir, trace_path):
    """二分 [D_LO, D_HI]，<EPS 早停。返回 (d_star, 迭代步数)。"""
    lo, hi = D_LO, D_HI
    rows = []
    rpt_path = os.path.join(work_dir, "feas_tmp.rpt")
    it = 0
    while hi - lo >= EPS:
        it += 1
        mid = (lo + hi) / 2.0
        attempts = 1 if (hi - lo) >= PRECISE_THRESHOLD else JUDGE_ATTEMPTS
        feasible = False
        last_side, last_bbox, last_hpwl = None, None, None
        t0 = time.time()
        for _ in range(attempts):
            f, s, bb, hp = feas_check(chip, mid, total, work_dir, rpt_path)
            last_side, last_bbox, last_hpwl = s, bb, hp
            if f:
                feasible = True
                break
        dt = time.time() - t0
        if feasible:
            hi = mid
        else:
            lo = mid
        rows.append([it, lo, hi, mid, last_side, f"{last_bbox[0]}x{last_bbox[1]}",
                     int(feasible), attempts, round(dt, 1)])
    with open(trace_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["iter", "lo", "hi", "mid", "side", "bbox", "feasible",
                    "attempts", "time_s"])
        w.writerows(rows)
    return hi, it


def verify_infeasible(chip, d_check, total, work_dir, rpt_path):
    """在 d_check 处做 JUDGE_ATTEMPTS 次判定，必须全不可行。"""
    results = []
    for _ in range(JUDGE_ATTEMPTS):
        f, _, _, _ = feas_check(chip, d_check, total, work_dir, rpt_path)
        results.append(f)
    return not any(results), results
