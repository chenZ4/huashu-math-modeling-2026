#!/usr/bin/env python3
"""M4 预置：生成解析式初始序（Q1: sqrt(T)、Q2: d=0.15、Q3: d=0.12）与 oracle 表。
输出：q*/output/analytic_init/order/order_{chip}_{key}.txt + placement/meta + oracle csv。
"""
import csv
import math
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from common import analytic_placer as ap

OUT_BASE = os.path.join(ROOT, "q2", "output", "analytic_init")
CHIPS = ["n100", "n200", "n300"]
# 各问所用死区比例（Q3 取 0.12 ≥ 所有已确认 d*）
TASKS = {"q1_sqrtT": None, "q2_d15": 0.15, "q3_d12": 0.12}


def main():
    for chip in CHIPS:
        b, t, n = ap.parse_instance(ROOT, chip)
        T = float(sum(w * h for w, h in b.values()))
        for tag, d in TASKS.items():
            if d is None:
                side = int(math.ceil(math.sqrt(T)))
            else:
                side = ap.side_from_d(T, d)
            outdir = os.path.join(OUT_BASE, "order")
            os.makedirs(outdir, exist_ok=True)
            stats = ap.analytic_place(b, t, n, side, iters=1200, seed=42)
            pos = stats["pos"]
            orders = {
                "x": sorted(pos, key=lambda k: pos[k][0]),
                "y": sorted(pos, key=lambda k: pos[k][1]),
                "xy": sorted(pos, key=lambda k: pos[k][0] + pos[k][1]),
            }
            for key, seq in orders.items():
                with open(os.path.join(outdir, f"order_{chip}_{tag}_{key}.txt"),
                          "w") as f:
                    f.write(" ".join(seq) + "\n")
            ap.write_meta(outdir, chip, side, d, dict(iters=1200, seed=42,
                                                     tag=tag), stats, "order")
            print(f"{chip} {tag} side={side} wl={stats['wl_exact']:.0f} "
                  f"cap={stats['overflow_cap']:.2f} maxD={stats['max_bin_density']:.2f}")

    # oracle 表（逐 d 的解析溢出率，佐证 Q3 阈值）
    orow = os.path.join(OUT_BASE, "oracle", "oracle.csv")
    os.makedirs(os.path.dirname(orow), exist_ok=True)
    with open(orow, "w") as f:
        f.write("chip,d,side,wl_exact,overflow_cap,max_bin_density\n")
        for chip in CHIPS:
            b, t, n = ap.parse_instance(ROOT, chip)
            T = float(sum(w * h for w, h in b.values()))
            for d in (0.06, 0.08, 0.10, 0.12, 0.14, 0.15):
                side = ap.side_from_d(T, d)
                st = ap.analytic_place(b, t, n, side, iters=1200, seed=42)
                f.write(f"{chip},{d},{side},{st['wl_exact']:.1f},"
                        f"{st['overflow_cap']:.4f},{st['max_bin_density']:.4f}\n")
                print(f"oracle {chip} d={d} side={side} "
                      f"cap={st['overflow_cap']:.2f} wl={st['wl_exact']:.0f}")
    print("done")


if __name__ == "__main__":
    main()
