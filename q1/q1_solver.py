"""Q1 求解器：驱动 C++ 二进制求解三组芯片，汇总指标，产出可视化。"""
import argparse
import csv
import datetime
import math
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "cpp_solver", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")
Q1 = os.path.join(ROOT, "q1")
OUT = os.path.join(Q1, "output")
FIGS = os.path.join(Q1, "visualization", "figs")

CHIPS = ["n100", "n200", "n300"]
LAMBDA = 0.5
DEAD = 0.15


def new_run_dir():
    """新建运行目录 figs/<YYYYMMDD_HHMMSS>/，保留全部历史。"""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(FIGS, ts)
    os.makedirs(run_dir, exist_ok=True)
    return run_dir


def parse_blocks(blocks_path):
    """独立解析 .blocks，返回 {name: (w, h)} 与总面积。"""
    dims = {}
    total = 0
    for line in open(blocks_path):
        if "block 4" not in line:
            continue
        name = line.split()[0]
        nums = [int(x) for x in re.findall(r"\d+", line)]
        xs, ys = nums[2::2], nums[3::2]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        dims[name] = (w, h)
        total += w * h
    return dims, total


def verify(rpt, dims):
    """独立复核：块数/无重叠/尺寸保持/面积下界。返回 (ok, msg)。"""
    blocks = []
    for line in open(rpt).read().splitlines()[5:]:
        parts = line.split()
        if len(parts) == 5:
            name, x1, y1, x2, y2 = parts[0], *map(int, parts[1:])
            blocks.append((name, x1, y1, x2, y2))
    if len(blocks) != len(dims):
        return False, f"block count {len(blocks)} != {len(dims)}"
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            a, b = blocks[i], blocks[j]
            if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]:
                return False, f"overlap {a[0]} vs {b[0]}"
    for b in blocks:
        dw, dh = dims[b[0]]
        w, h = b[3] - b[1], b[4] - b[2]
        if min(w, h) != min(dw, dh) or max(w, h) != max(dw, dh):
            return False, f"dim mismatch {b[0]}"
    return True, "ok"


def run_one(chip, alpha, dead, repeats=3):
    blocks_path = os.path.join(DATA, f"{chip}.blocks")
    nets_path = os.path.join(DATA, f"{chip}.nets")
    pl_path = os.path.join(DATA, f"{chip}.pl")
    rpt = os.path.join(OUT, f"q1_{chip}.rpt")
    log = os.path.join(OUT, f"q1_{chip}.log")
    best = None
    for _ in range(repeats):
        subprocess.run([BIN, "q1", str(alpha), blocks_path, nets_path, pl_path,
                        rpt, str(dead), "--log", log], check=True)
        lines = open(rpt).read().splitlines()
        W, H = map(int, lines[3].split())
        area = int(lines[2])
        time_s = float(lines[4])
        aspect = max(W, H) / min(W, H)
        if best is None or (area, aspect) < (best[0], best[1]):
            best = (area, aspect, W, H, time_s)
    dims, total = parse_blocks(blocks_path)
    area, aspect, W, H, time_s = best
    util = total / (W * H)
    ok, msg = verify(rpt, dims)
    return {
        "chip": chip, "area": area, "W": W, "H": H, "aspect": round(aspect, 4),
        "utilization": round(util, 4), "time_s": round(time_s, 2),
        "legal": ok, "note": msg,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=LAMBDA, help="面积权重 λ")
    ap.add_argument("--repeats", type=int, default=3, help="每芯片求解轮数，取最优")
    ap.add_argument("--skip-solve", action="store_true", help="跳过求解，只汇总已存在结果")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    run_dir = new_run_dir()
    print("run dir:", run_dir)

    results = []
    if args.skip_solve:
        for chip in CHIPS:
            dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
            rpt = os.path.join(OUT, f"q1_{chip}.rpt")
            lines = open(rpt).read().splitlines()
            W, H = map(int, lines[3].split())
            area = int(lines[2])
            time_s = float(lines[4])
            aspect = max(W, H) / min(W, H)
            ok, msg = verify(rpt, dims)
            results.append({
                "chip": chip, "area": area, "W": W, "H": H,
                "aspect": round(aspect, 4), "utilization": round(total / (W * H), 4),
                "time_s": round(time_s, 2), "legal": ok, "note": msg,
            })
    else:
        with ThreadPoolExecutor(max_workers=3) as ex:
            results = list(ex.map(lambda c: run_one(c, args.alpha, DEAD, args.repeats),
                                  CHIPS))

    csv_path = os.path.join(OUT, "q1_metrics.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        w.writerows(results)
    print(open(csv_path).read())

    for r in results:
        chip = r["chip"]
        rpt = os.path.join(OUT, f"q1_{chip}.rpt")
        log = os.path.join(OUT, f"q1_{chip}.log")
        chip_dir = os.path.join(run_dir, chip)
        os.makedirs(chip_dir, exist_ok=True)
        subprocess.run([sys.executable, os.path.join(Q1, "visualization", "plot_floorplan.py"),
                        "--rpt", rpt, "--out", os.path.join(chip_dir, "floorplan.png")],
                       check=True)
        if os.path.exists(log):
            subprocess.run([sys.executable, os.path.join(Q1, "visualization", "plot_convergence.py"),
                            "--log", log, "--out", os.path.join(chip_dir, "convergence.png")],
                           check=True)
            subprocess.run([sys.executable, os.path.join(Q1, "visualization", "plot_snapshots.py"),
                            "--log", log, "--outdir", os.path.join(chip_dir, "snapshots")],
                           check=True)
    print("figures ->", run_dir)


if __name__ == "__main__":
    main()
