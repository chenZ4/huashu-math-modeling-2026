#!/usr/bin/env python3
"""对比实验矩阵统一测量：BLF / SP-random / SP-SA / B*-Tree-SA。

测量口径（全方法一致）：
  - Peak Memory: /usr/bin/time -l 的 maximum resident set size（macOS，字节）
  - CPU Time   : 同上 user+sys（进程级）
  - HPWL       : common/analytic_placer.hpwl_of_rpt 金标准独立重算
  - 合法性     : common/verify.verify_layout（无重叠/尺寸保持/不越界）
  - 违规数     : 独立 O(n²) 重叠对计数 + 轮廓越界块数
预算公平性：SP-SA 与 B*-Tree-SA 共用同一 SA 引擎与逐芯片 t2-div；
SP-random 同扰动预算但无 Metropolis 准则；BLF 为确定性单次贪心。

用法：
  python run_baseline_matrix.py --quick            # 冒烟：n100×1种子×全部方法
  python run_baseline_matrix.py --seeds 10         # 完整矩阵（挂机）
  python run_baseline_matrix.py --dry-run          # 只打印命令
"""
import argparse
import csv
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "common"))
import analytic_placer as ap  # noqa: E402
import verify as vf  # noqa: E402

ROOT = Path(__file__).parent
BIN = ROOT / "cpp_solver_opt" / "bin"
T2_DIV = {"n100": 35, "n200": 60, "n300": 70}  # 定稿参数，跨编码同预算


def outline_side(chip):
    dims, _ = vf.parse_blocks(str(ROOT / "data/raw" / f"{chip}.blocks"))
    total = sum(w * h for w, h in dims.values())
    return int(-(-((total * 1.15) ** 0.5) // 1)), dims, total


def build_cmd(method, chip, seed, rpt):
    b = str(ROOT / "data/raw" / f"{chip}.blocks")
    n = str(ROOT / "data/raw" / f"{chip}.nets")
    p = str(ROOT / "data/raw" / f"{chip}.pl")
    base = [str(BIN / ("blf" if method == "blf" else "main")), "q2", "0.5",
            b, n, p, rpt, "0.15"]
    if method == "blf":
        return base
    base += ["--seed", str(seed), "--t2-div", str(T2_DIV[chip])]
    if method == "sp_random":
        return base + ["--encoding", "sp", "--accept-all"]
    if method == "sp_sa":
        return base + ["--encoding", "sp"]
    if method == "bstar_mem":
        return base
    raise ValueError(method)


def measure(cmd, timeout_s):
    """跑 /usr/bin/time -l，返回 (peak_mb, cpu_s, wall_s, exit_code)。"""
    wrapped = ["/usr/bin/time", "-l"] + cmd
    t0 = time.time()
    proc = subprocess.run(wrapped, capture_output=True, text=True,
                          timeout=timeout_s)
    wall = time.time() - t0
    peak_mb = cpu_s = None
    m = re.findall(r"(\d+) *maximum resident set size", proc.stderr)
    if m:
        peak_mb = int(m[-1]) / (1024 * 1024)
    mu = re.search(r"([\d.]+) *user .*?([\d.]+) *sys", proc.stderr)
    if mu:
        cpu_s = float(mu.group(1)) + float(mu.group(2))
    return peak_mb, cpu_s, wall, proc.returncode


def count_violations(rpt, dims, side):
    """返回 (重叠对数, 越界块数)。"""
    blocks = vf.read_blocks_from_rpt(rpt)
    overlaps = 0
    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            a, b = blocks[i], blocks[j]
            if a[1] < b[3] and b[1] < a[3] and a[2] < b[4] and b[2] < a[4]:
                overlaps += 1
    out = sum(1 for x in blocks if x[3] > side or x[4] > side)
    return overlaps, out


def eval_quality(chip, rpt):
    blocks_, terminals_, nets = ap.parse_instance(str(ROOT), chip)
    side, dims, total = outline_side(chip)
    ok, msg = vf.verify_layout(rpt, dims, outline=(side, side))
    hpwl = ap.hpwl_of_rpt(rpt, blocks_, terminals_, nets)
    lines = open(rpt).read().splitlines()
    W, H = map(int, lines[3].split())
    overlaps, out_cnt = count_violations(rpt, dims, side)
    return {
        "hpwl": round(hpwl, 1), "legal": ok, "W": W, "H": H,
        "utilization": round(total / (W * H), 4),
        "overlap_pairs": overlaps, "outline_violations": out_cnt,
        "verify_msg": msg,
    }


def run_matrix(chips, methods, seeds, outdir, dry_run, timeout_s):
    outdir.mkdir(parents=True, exist_ok=True)
    rows = []
    csv_path = outdir / "baseline_metrics.csv"
    for chip in chips:
        for method in methods:
            reps = seeds if method != "blf" else 1  # BLF 确定性，单次
            for s in range(reps):
                tag = f"{method}_{chip}_s{s}"
                rpt = str(outdir / f"{tag}.rpt")
                cmd = build_cmd(method, chip, 20260808 + s, rpt)
                print(f"[{tag}] {' '.join(cmd)}")
                if dry_run:
                    continue
                try:
                    peak_mb, cpu_s, wall, code = measure(cmd, timeout_s)
                except subprocess.TimeoutExpired:
                    print(f"[{tag}] TIMEOUT >{timeout_s}s")
                    rows.append({"tag": tag, "note": "timeout"})
                    continue
                q = eval_quality(chip, rpt)
                row = {"tag": tag, "method": method, "chip": chip,
                       "seed": 20260808 + s, "exit_code": code,
                       "peak_mem_mb": round(peak_mb, 1)
                       if peak_mb is not None else None,
                       "cpu_time_s": round(cpu_s, 2)
                       if cpu_s is not None else None,
                       "wall_s": round(wall, 2), **q}
                rows.append(row)
                print(f"[{tag}] exit={code} legal={q['legal']} "
                      f"hpwl={q['hpwl']} util={q['utilization']} "
                      f"mem={row['peak_mem_mb']}MB cpu={row['cpu_time_s']}s "
                      f"viol={q['overlap_pairs']}/{q['outline_violations']}")
                _flush(csv_path, rows)
    if not dry_run:
        _flush(csv_path, rows)
        print(f"\nCSV → {csv_path}")


def _flush(csv_path, rows):
    if not rows:
        return
    fields = ["tag", "method", "chip", "seed", "exit_code", "peak_mem_mb",
              "cpu_time_s", "wall_s", "hpwl", "utilization", "W", "H",
              "legal", "overlap_pairs", "outline_violations", "verify_msg",
              "note"]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main():
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--chips", nargs="+",
                     default=["n100", "n200", "n300"])
    ap_.add_argument("--methods", nargs="+",
                     default=["blf", "sp_random", "sp_sa", "bstar_mem"])
    ap_.add_argument("--seeds", type=int, default=10)
    ap_.add_argument("--outdir", default="q2/output/baseline_matrix")
    ap_.add_argument("--timeout-s", type=int, default=3600)
    ap_.add_argument("--quick", action="store_true",
                     help="冒烟：仅 n100 × 1 种子")
    ap_.add_argument("--dry-run", action="store_true")
    args = ap_.parse_args()
    if args.quick:
        args.chips = ["n100"]
        args.seeds = 1
    run_matrix(args.chips, args.methods, args.seeds,
               Path(args.outdir), args.dry_run, args.timeout_s)


if __name__ == "__main__":
    main()
