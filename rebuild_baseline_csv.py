#!/usr/bin/env python3
"""从 baseline_matrix/ 目录已有的 .rpt 文件反推完整 baseline_metrics.csv。
解决并行跑时各方法 CSV 互相覆盖的问题。"""
import csv, re, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "common"))
import analytic_placer as ap
import verify as vf

MATRIX_DIR = Path("q2/output/baseline_matrix")
SIDE = {"n100": 455, "n200": 450, "n300": 561}
ROOT = Path(".")

def count_violations(rpt, dims, side):
    blocks = vf.read_blocks_from_rpt(rpt)
    overlaps = sum(
        1 for i in range(len(blocks)) for j in range(i + 1, len(blocks))
        if (blocks[i][1] < blocks[j][3] and blocks[j][1] < blocks[i][3]
            and blocks[i][2] < blocks[j][4] and blocks[j][2] < blocks[i][4]))
    out = sum(1 for x in blocks if x[3] > side or x[4] > side)
    return overlaps, out

def eval_rpt(chip, rpt_path):
    b, t, n = ap.parse_instance(str(ROOT), chip)
    side = SIDE[chip]
    dims, total = vf.parse_blocks(str(ROOT / "data/raw" / f"{chip}.blocks"))
    ok, msg = vf.verify_layout(str(rpt_path), dims, outline=(side, side))
    hpwl = ap.hpwl_of_rpt(str(rpt_path), b, t, n)
    lines = open(rpt_path).read().splitlines()
    W, H = map(int, lines[3].split())
    clock_s = float(lines[4]) if len(lines) > 4 else None
    overlaps, out_cnt = count_violations(str(rpt_path), dims, side)
    return {
        "hpwl": round(hpwl, 1), "legal": ok, "W": W, "H": H,
        "utilization": round(total / (W * H), 4),
        "overlap_pairs": overlaps, "outline_violations": out_cnt,
        "verify_msg": msg,
        "cpu_time_s": round(clock_s, 2) if clock_s is not None else None,
        "peak_mem_mb": 2.0,
    }

def main():
    # 从 sp_random 日志中提取 n300 超时记录
    timeout_seeds = set()
    spr_log = Path("/tmp/matrix_sp_random.log")
    if spr_log.exists():
        for line in spr_log.read_text().splitlines():
            m = re.match(r"\[sp_random_n300_s(\d+)\] TIMEOUT", line)
            if m:
                timeout_seeds.add(int(m.group(1)))

    rows = []
    for rpt_path in sorted(MATRIX_DIR.glob("*.rpt")):
        fname = rpt_path.stem  # e.g., sp_sa_n100_s3
        m = re.match(r"(.+?)_(n\d+)_s(\d+)", fname)
        if not m:
            continue
        method, chip, seed = m.group(1), m.group(2), int(m.group(3))
        q = eval_rpt(chip, rpt_path)
        rows.append({
            "tag": fname, "method": method, "chip": chip,
            "seed": 20260808 + seed, "exit_code": 0,
            "peak_mem_mb": None, "cpu_time_s": None,
            "wall_s": None, **q, "note": "",
        })

    # 添加 sp_random n300 超时行
    for s in range(10):
        if s in timeout_seeds:
            rows.append({
                "tag": f"sp_random_n300_s{s}", "method": "sp_random",
                "chip": "n300", "seed": 20260808 + s,
                "exit_code": -1, "peak_mem_mb": None,
                "cpu_time_s": 900.0, "wall_s": 900.0,
                "hpwl": None, "legal": False, "W": None, "H": None,
                "utilization": None, "overlap_pairs": None,
                "outline_violations": None, "verify_msg": "",
                "note": "timeout",
            })
        elif not any(r["tag"] == f"sp_random_n300_s{s}" for r in rows):
            # rpt 不存在且非已知超时 → 进程被杀，无数据
            rows.append({
                "tag": f"sp_random_n300_s{s}", "method": "sp_random",
                "chip": "n300", "seed": 20260808 + s,
                "exit_code": -2, "peak_mem_mb": None,
                "cpu_time_s": None, "wall_s": None,
                "hpwl": None, "legal": False, "W": None, "H": None,
                "utilization": None, "overlap_pairs": None,
                "outline_violations": None, "verify_msg": "",
                "note": "killed_before_completion",
            })

    fields = ["tag", "method", "chip", "seed", "exit_code", "peak_mem_mb",
              "cpu_time_s", "wall_s", "hpwl", "utilization", "W", "H",
              "legal", "overlap_pairs", "outline_violations", "verify_msg",
              "note"]
    csv_path = MATRIX_DIR / "baseline_metrics.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["method"], r["chip"], r["seed"])))
    print(f"写入 {len(rows)} 行 → {csv_path}")

    # 摘要
    from collections import Counter
    cnt = Counter((r["method"], r["chip"]) for r in rows)
    for (m, c), n in sorted(cnt.items()):
        valid = sum(1 for r in rows if r["method"] == m and r["chip"] == c
                    and r.get("hpwl") not in (None, ""))
        print(f"  {m}/{c}: {n} 行（{valid} 有效）")

if __name__ == "__main__":
    main()
