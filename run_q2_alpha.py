#!/usr/bin/env python3
"""P2: Q2 α×t2 两级扫描（--descent 全开，8 进程并行）。
第一级：n100 全矩阵 α{0,0.1,0.3}×t2{35,50,70} × 8 轮 → 锁定 (α*,t2*)
第二级：n200/n300 用锁定组合 × 8 轮。
对照：q2/output/final 已有数据（不重跑）。
"""
import json
import math
import os
import statistics
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "common"))
from verify import parse_blocks, verify_layout
from analytic_placer import hpwl_of_rpt, parse_instance, git_sha

BIN = os.path.join(ROOT, "cpp_solver_opt", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")
OUT = os.path.join(ROOT, "q2", "output", "alpha_scan")
BASE_SEED = 20260808
DEAD = 0.15
WORKERS = 8
ROUNDS = 8


def run_round(chip, alpha, t2, seed):
    rpt = os.path.join(OUT, f"q2_{chip}_a{alpha}_t2{t2}_r{seed - BASE_SEED}.rpt")
    if os.path.exists(rpt):
        return rpt, "skip"
    cmd = [BIN, "q2", str(alpha),
           os.path.join(DATA, f"{chip}.blocks"),
           os.path.join(DATA, f"{chip}.nets"),
           os.path.join(DATA, f"{chip}.pl"),
           rpt, str(DEAD), "--seed", str(seed),
           "--t2-div", str(t2), "--descent"]
    subprocess.run(cmd, check=True)
    return rpt, "run"


def evaluate(chip, alpha, t2):
    dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
    side = math.ceil(math.sqrt(total * (1.0 + DEAD)))
    b, t, n = parse_instance(ROOT, chip)
    legal = []
    n_illegal = 0
    for r in range(ROUNDS):
        rpt = os.path.join(OUT, f"q2_{chip}_a{alpha}_t2{t2}_r{100 + r}.rpt")
        lines = open(rpt, encoding="utf-8").read().splitlines()
        W, H = (int(x) for x in lines[3].split())
        hpwl = float(lines[1])
        ok_l, msg = verify_layout(rpt, dims,
                                  outline=(side, side) if (W <= side and H <= side) else None)
        ok_h = abs(hpwl_of_rpt(rpt, b, t, n) - hpwl) < 0.05
        if not ok_l or not ok_h:
            print(f"  VERIFY FAIL {chip} a{alpha} t2{t2} r{r}: {ok_l}/{ok_h} {msg}")
            sys.exit(1)
        if W <= side and H <= side:
            legal.append(hpwl)
        else:
            n_illegal += 1
    if not legal:
        return {"chip": chip, "alpha": alpha, "t2_div": t2, "n_legal": 0,
                "n_illegal": n_illegal, "min": None, "median": None}
    return {"chip": chip, "alpha": alpha, "t2_div": t2, "n_legal": len(legal),
            "n_illegal": n_illegal, "min": min(legal),
            "median": statistics.median(legal),
            "spread_pct": round((max(legal) - min(legal)) / min(legal) * 100, 1)}


def main():
    os.makedirs(OUT, exist_ok=True)
    stage = sys.argv[1] if len(sys.argv) > 1 else "n100"
    if stage == "n100":
        combos = [(a, t2) for a in (0.0, 0.1, 0.3) for t2 in (35, 50, 70)]
        chips = ["n100"]
    elif stage == "n200":
        combos = [(0.0, 70)]
        chips = ["n200"]
    else:
        combos = [(0.0, 70)]
        chips = ["n300"]
    tasks = [(c, a, t2, BASE_SEED + 100 + r)
             for c in chips for a, t2 in combos for r in range(ROUNDS)]
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(run_round, *t) for t in tasks]
        for i, fut in enumerate(as_completed(futs), 1):
            rpt, act = fut.result()
            if act == "run" and i % 8 == 0:
                print(f"[{i}/{len(tasks)}] ...")
    results = []
    for c in chips:
        for a, t2 in combos:
            res = evaluate(c, a, t2)
            results.append(res)
            print(f"{c} alpha={a} t2={t2}: legal={res['n_legal']}/{ROUNDS} "
                  f"min={res['min']} median={res['median']} "
                  f"spread={res.get('spread_pct')}%")
    with open(os.path.join(OUT, f"metrics_{stage}.json"), "w") as f:
        json.dump({"results": results, "git_sha": git_sha()}, f,
                  ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
