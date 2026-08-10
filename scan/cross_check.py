"""定稿交叉核对：final/ 复现值 vs 挂机 scan best，逐位比较。
用法: conda activate math && python scan/cross_check.py
"""
import csv
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 挂机 best 期望值（scan/results 当前权威数据）
def load_scan_best(q, chip, params):
    """从 scan/results 读指定参数配置的最优值。params: dict 过滤条件。"""
    best = None
    for f in glob.glob(os.path.join(ROOT, "scan", "results", q, f"*{chip}*.csv")):
        try:
            with open(f) as fh:
                r = list(csv.DictReader(fh))[0]
        except (csv.Error, OSError, IndexError):
            continue
        for k, v in params.items():
            if abs(float(r[k]) - float(v)) > 1e-9:
                break
        else:
            if q == "q1":
                cand = (float(r["area"]), float(r["aspect"]))
            elif q == "q2":
                cand = float(r["hpwl"])
            else:
                cand = float(r["d_star"])
            if best is None or cand < best[0]:
                best = (cand, r)
    return best


def read_final_metrics(q, outdir):
    path = os.path.join(ROOT, q, "output", outdir, f"{q}_metrics.csv")
    with open(path) as fh:
        return {r["chip"]: r for r in csv.DictReader(fh)}


def check(q, chip, params, final_row, key_field, tol=1e-6):
    sb = load_scan_best(q, chip, params)
    if sb is None:
        print(f"  [SKIP] {q} {chip}: 挂机无匹配配置 {params}")
        return
    fv = float(final_row[key_field])
    sv = sb[0] if q == "q2" or q == "q3" else sb[0][0]
    ok = abs(fv - sv) <= tol
    status = "OK " if ok else "MISMATCH"
    print(f"  [{status}] {q} {chip}: final={fv} scan={sv:.6f}")
    return ok


def main():
    checks = []
    # Q1: 仅按 λ 过滤（q1 的 t2_div CSV 列记录默认 50 而实际默认 20，不可靠）
    q1 = read_final_metrics("q1", "final")
    checks.append(check("q1", "n100", {"lambda": 0.5},
                         q1["n100"], "area"))
    checks.append(check("q1", "n200", {"lambda": 0.5},
                         q1["n200"], "area"))
    checks.append(check("q1", "n300", {"lambda": 0.5},
                         q1["n300"], "area"))
    # Q2
    q2 = read_final_metrics("q2", "final")
    for chip, t2 in [("n100", 35), ("n200", 60), ("n300", 70)]:
        checks.append(check("q2", chip, {"t2_div": t2}, q2[chip], "hpwl"))
    # Q3
    q3 = read_final_metrics("q3", "final")
    for chip, seeds in [("n100", 15), ("n200", 15), ("n300", 10)]:
        checks.append(check("q3", chip, {"seeds": seeds}, q3[chip], "d_star"))
    bad = [c for c in checks if c is False]
    print(f"\n{'='*50}\n结果: {len(checks)-len(bad)}/{len(checks)} 通过"
          f"{'  ← 全部一致' if not bad else '  ← 有不一致，需排查!'}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
