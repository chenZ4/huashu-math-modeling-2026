#!/usr/bin/env python3
"""P3: 精英重启。从 final 最优 rpt 提取模块序（按 (y,x)），作 --init-order
配合 --descent + 各芯片最优 (α,t2) 加码多轮。
n100 先验门：elite 序 vs 随机序各 8 轮，改善才继续 n200/n300。
"""
import argparse
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
OUT = os.path.join(ROOT, "q2", "output", "elite")
ORDER_DIR = os.path.join(OUT, "orders")
BASE_SEED = 20260808
DEAD = 0.15
WORKERS = 8
# 各芯片锁定参数（P2 α×t2 扫描）
PARAMS = {"n100": (0.1, 70), "n200": (0.0, 70), "n300": (0.1, 70)}
BEST_RPT = {"n100": "q2/output/final/q2_n100_r4.rpt",
            "n200": "q2/output/final/q2_n200_r8.rpt",
            "n300": "q2/output/final/q2_n300_r6.rpt"}


def extract_order(chip):
    rpt = os.path.join(ROOT, BEST_RPT[chip])
    blocks = []
    for line in open(rpt, encoding="utf-8").read().splitlines()[5:]:
        p = line.split()
        if len(p) == 5:
            blocks.append((p[0], int(p[1]), int(p[2])))
    blocks.sort(key=lambda b: (b[2], b[1]))   # (y, x) 行主序
    order = [b[0] for b in blocks]
    assert len(order) == int(chip[1:]), (len(order), chip)
    assert len(set(order)) == len(order), "duplicate in order"
    os.makedirs(ORDER_DIR, exist_ok=True)
    path = os.path.join(ORDER_DIR, f"elite_{chip}.txt")
    with open(path, "w") as f:
        f.write(" ".join(order) + "\n")
    return path


def run_round(chip, seed, alpha, t2, order_file, tag):
    rpt = os.path.join(OUT, f"q2_{chip}_{tag}_r{seed - BASE_SEED}.rpt")
    if os.path.exists(rpt):
        return rpt, "skip"
    cmd = [BIN, "q2", str(alpha),
           os.path.join(DATA, f"{chip}.blocks"),
           os.path.join(DATA, f"{chip}.nets"),
           os.path.join(DATA, f"{chip}.pl"),
           rpt, str(DEAD), "--seed", str(seed), "--t2-div", str(t2),
           "--descent"]
    if order_file:
        cmd += ["--init-order", order_file]
    subprocess.run(cmd, check=True)
    return rpt, "run"


def evaluate(chip, tag, rounds, offset):
    dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
    side = math.ceil(math.sqrt(total * (1.0 + DEAD)))
    b, t, n = parse_instance(ROOT, chip)
    legal = []
    n_illegal = 0
    for r in range(rounds):
        rpt = os.path.join(OUT, f"q2_{chip}_{tag}_r{offset + r}.rpt")
        lines = open(rpt, encoding="utf-8").read().splitlines()
        W, H = (int(x) for x in lines[3].split())
        hpwl = float(lines[1])
        ok_l, msg = verify_layout(rpt, dims,
                                  outline=(side, side) if (W <= side and H <= side) else None)
        ok_h = abs(hpwl_of_rpt(rpt, b, t, n) - hpwl) < 0.05
        if not ok_l or not ok_h:
            print(f"  VERIFY FAIL {chip} {tag} r{r}: {ok_l}/{ok_h} {msg}")
            sys.exit(1)
        if W <= side and H <= side:
            legal.append(hpwl)
        else:
            n_illegal += 1
    return {"chip": chip, "tag": tag, "n_legal": len(legal),
            "n_illegal": n_illegal,
            "min": min(legal) if legal else None,
            "median": statistics.median(legal) if legal else None,
            "spread_pct": round((max(legal) - min(legal)) / min(legal) * 100, 1)
            if legal else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["gate", "full"], default="gate")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    if args.stage == "gate":
        chip = "n100"
        alpha, t2 = PARAMS[chip]
        order_file = extract_order(chip)
        tasks = ([(chip, BASE_SEED + 200 + r, alpha, t2, order_file, "elite")
                  for r in range(8)]
                 + [(chip, BASE_SEED + 300 + r, alpha, t2,
                     os.path.join(ORDER_DIR, "__none__.txt"), "rand")
                    for r in range(8)])
        # rand 组不用 --init-order：单独处理
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = []
            for t in tasks:
                if t[5] == "elite":
                    futs.append(ex.submit(run_round, *t))
                else:
                    rpt = os.path.join(OUT, f"q2_{chip}_rand_r{t[1] - BASE_SEED}.rpt")
                    cmd = [BIN, "q2", str(t[2]),
                           os.path.join(DATA, f"{chip}.blocks"),
                           os.path.join(DATA, f"{chip}.nets"),
                           os.path.join(DATA, f"{chip}.pl"),
                           rpt, str(DEAD), "--seed", str(t[1]),
                           "--t2-div", str(t[3]), "--descent"]
                    futs.append(ex.submit(lambda c=cmd: subprocess.run(c, check=True)))
            for fut in as_completed(futs):
                fut.result()
        e = evaluate(chip, "elite", 8, 200)
        r = evaluate(chip, "rand", 8, 300)
        print("gate elite:", e)
        print("gate rand :", r)
        gate = (e["min"] is not None and
                (r["min"] is None or e["min"] <= r["min"]))
        print("GATE", "PASS" if gate else "FAIL")
        with open(os.path.join(OUT, "gate_metrics.json"), "w") as f:
            json.dump({"elite": e, "rand": r, "gate_pass": gate,
                       "git_sha": git_sha()}, f, ensure_ascii=False, indent=2)
        return

    # full：各芯片 24~50 轮（先验门未过 → 纯加码，不传 init-order）
    rounds = {"n100": 24, "n200": 24, "n300": 50}
    for chip, R in rounds.items():
        alpha, t2 = PARAMS[chip]
        tasks = [(chip, BASE_SEED + 400 + r, alpha, t2, None, "boost")
                 for r in range(R)]
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            futs = [ex.submit(run_round, *t) for t in tasks]
            for i, fut in enumerate(as_completed(futs), 1):
                fut.result()
                if i % 8 == 0:
                    print(f"{chip} [{i}/{R}]")
        res = evaluate(chip, "boost", R, 400)
        print(chip, res)
        with open(os.path.join(OUT, f"boost_{chip}_metrics.json"), "w") as f:
            json.dump({**res, "alpha": alpha, "t2_div": t2,
                       "git_sha": git_sha()}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
