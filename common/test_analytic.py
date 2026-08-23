#!/usr/bin/env python3
"""analytic_placer 白盒测试（纯 assert，无 pytest 依赖）。
运行：python common/test_analytic.py  （在仓库根目录）
失败即 exit 1。
"""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from common import analytic_placer as ap  # noqa: E402

PASS = 0


def ok(name, cond, detail=""):
    global PASS
    if not cond:
        print(f"  FAIL {name} {detail}")
        sys.exit(1)
    PASS += 1
    print(f"  PASS {name}")


def test_parse_known():
    print("[T1] 已知答案解析（对账 dataset_stats 金标准）")
    b, t, n = ap.parse_instance(ROOT, "n100")
    ok("n100 blocks==100", len(b) == 100)
    ok("n100 T==179501", sum(w * h for w, h in b.values()) == 179501)
    ok("n100 nets==885", len(n) == 885)
    ok("n100 pins==1873", sum(len(x) for x in n) == 1873)
    ok("n100 terminals==334", len(t) == 334)
    b2, _, n2 = ap.parse_instance(ROOT, "n200")
    ok("n200 T==175696", sum(w * h for w, h in b2.values()) == 175696)
    ok("n200 nets==1585", len(n2) == 1585)
    b3, _, n3 = ap.parse_instance(ROOT, "n300")
    ok("n300 T==273170", sum(w * h for w, h in b3.values()) == 273170)
    ok("n300 pins==4358", sum(len(x) for x in n3) == 4358)


def test_hpwl_golden():
    print("[T2] HPWL 金标准：独立重算 q2_n100_r0.rpt == 292891.5")
    b, t, n = ap.parse_instance(ROOT, "n100")
    rpt = os.path.join(ROOT, "q2/output/final/q2_n100_r0.rpt")
    ref = float(open(rpt, encoding="utf-8").read().splitlines()[1])
    val = ap.hpwl_of_rpt(rpt, b, t, n)
    ok("golden == 292891.5", abs(val - 292891.5) < 0.05, val)
    ok("golden == rpt line2", abs(val - ref) < 0.05, (val, ref))


def test_grad_wl():
    print("[T3] WL 项梯度有限差分 < 1e-6")
    rng = np.random.default_rng(7)
    pts = rng.uniform(0, 500, size=(6, 2))
    gamma = 30.0
    _, gx, gy = ap._lse_wl_grad(pts, gamma)
    eps = 1e-6
    for i in range(4):
        for k in range(2):
            p2, p1 = pts.copy(), pts.copy()
            p2[i, k] += eps
            p1[i, k] -= eps
            num = (ap._lse_wl_grad(p2, gamma)[0] - ap._lse_wl_grad(p1, gamma)[0]) / (2 * eps)
            ana = gx[i] if k == 0 else gy[i]
            ok(f"grad wl[{i},{k}]", abs(num - ana) < 1e-6, (num, ana))


def test_grad_density():
    print("[T4] 密度项梯度有限差分 < 1e-5（边缘避开 bin 边界）")
    rng = np.random.default_rng(11)
    side, nbins, bw = 500.0, 10, 50.0
    # 半宽均非 25 的整数倍，中心放 bin 中央，保证差分不跨边界
    dims = np.array([[61, 40], [79, 51], [41, 89], [69, 31], [53, 57]], dtype=float)
    half = dims / 2.0
    pos = rng.uniform(60, 440, size=(5, 2))
    for i in range(5):
        pos[i, 0] = (np.floor(pos[i, 0] / bw) + 0.5) * bw
        pos[i, 1] = (np.floor(pos[i, 1] / bw) + 0.5) * bw
    tar = 0.5
    _, g, _ = ap._density_grad(pos, half, side, nbins, tar)
    eps = 1e-6
    for i in range(4):
        for k in range(2):
            p2, p1 = pos.copy(), pos.copy()
            p2[i, k] += eps
            p1[i, k] -= eps
            Dp = ap._density_grad(p2, half, side, nbins, tar)[0]
            Dm = ap._density_grad(p1, half, side, nbins, tar)[0]
            Pp = np.sum((Dp - tar) ** 2)
            Pm = np.sum((Dm - tar) ** 2)
            num = (Pp - Pm) / (2 * eps)
            ana = g[i, k]
            ok(f"grad dens[{i},{k}]", abs(num - ana) < 1e-5, (num, ana))


def test_synthetic_convergence():
    print("[T5] 合成小例：2 块 1 网 GD 收敛到接触")
    blocks = {"b0": (30, 20), "b1": (20, 30)}
    terminals = {}
    nets = [["b0", "b1"]]
    side = 200.0
    st = ap.analytic_place(blocks, terminals, nets, side,
                           iters=800, lam0=0.0, lam_c0=0.0,
                           lr=0.02, mom=0.6, seed=1)
    d = float(np.hypot(st["pos"]["b0"][0] - st["pos"]["b1"][0],
                       st["pos"]["b0"][1] - st["pos"]["b1"][1]))
    ok("final distance < side/8", d < side / 8, d)


def test_determinism():
    print("[T6] 固定种子完全确定")
    b, t, n = ap.parse_instance(ROOT, "n100")
    T = float(sum(w * h for w, h in b.values()))
    side = int(np.ceil(np.sqrt(T)))
    kw = dict(iters=120, seed=9)
    s1 = ap.analytic_place(b, t, n, side, **kw)
    s2 = ap.analytic_place(b, t, n, side, **kw)
    ok("same seed -> identical", s1["pos"] == s2["pos"]
       and s1["wl_exact"] == s2["wl_exact"])
    s3 = ap.analytic_place(b, t, n, side, iters=120, seed=10)
    ok("diff seed -> diff", s1["pos"] != s3["pos"])


def test_oracle_consistency():
    print("[T7] oracle 一致性：d=0.05 超容量溢出 > d=0.15 超容量溢出")
    b, t, n = ap.parse_instance(ROOT, "n100")
    T = float(sum(w * h for w, h in b.values()))
    o5 = ap.analytic_place(b, t, n, ap.side_from_d(T, 0.05), iters=400, seed=3)
    o15 = ap.analytic_place(b, t, n, ap.side_from_d(T, 0.15), iters=400, seed=3)
    ok("overflow_cap(d=0.15) <= overflow_cap(d=0.05)",
       o15["overflow_cap"] <= o5["overflow_cap"],
       (o15["overflow_cap"], o5["overflow_cap"]))


if __name__ == "__main__":
    for fn in (test_parse_known, test_hpwl_golden, test_grad_wl,
               test_grad_density, test_synthetic_convergence,
               test_determinism, test_oracle_consistency):
        fn()
    print(f"ALL {PASS} TESTS PASSED")
