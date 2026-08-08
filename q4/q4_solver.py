"""Q4 求解器：L/T 型 + 矩形模块，四向旋转，最小包围盒面积（强算穷举）。
模型：矩形分解超块（L/T 各 2 矩形固定相对位置）+ 超块级 B*-Tree 穷举。
规模：树形 Catalan(4)=14 x 排列 4!=24 x 旋转 4^4=256 ≈ 8.6 万布局（秒级）。
最优性：B*-Tree 完备性 => 穷举覆盖全部布局拓扑；
若结果面积 == 模块总面积（理论下界）即证明全局最优。
"""
import csv
import datetime
import itertools
import math
import os

Q4 = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(Q4, "output")
FIGS = os.path.join(Q4, "visualization", "figs")

# ---- 模块定义：分解矩形 (x, y, w, h)，相对模块 bbox 原点 ----
MODULES = {
    "b1": [(0, 2, 4, 2), (1, 0, 2, 2)],   # T 型：顶横条 4x2 + 竖干 2x2，面积 12
    "b2": [(0, 0, 1, 4), (1, 0, 1, 2)],   # L 型：左竖条 1x4 + 右下横条 1x2，面积 6
    "b3": [(0, 0, 2, 1)],                 # 矩形 2x1，面积 2
    "b4": [(0, 0, 1, 4)],                 # 矩形 1x4，面积 4
}
NAMES = ["b1", "b2", "b3", "b4"]
TOTAL_AREA = 24


def rotate_90(rects):
    """模块整体逆时针旋转 90 度（角点变换 + 归一化平移）。"""
    new = []
    for (x, y, w, h) in rects:
        pts = [(x, y), (x + w, y), (x, y + h), (x + w, y + h)]
        nps = [(-yy, xx) for (xx, yy) in pts]
        minx = min(p[0] for p in nps)
        maxx = max(p[0] for p in nps)
        miny = min(p[1] for p in nps)
        maxy = max(p[1] for p in nps)
        new.append((minx, miny, maxx - minx, maxy - miny))
    minx = min(r[0] for r in new)
    miny = min(r[1] for r in new)
    return [(x - minx, y - miny, w, h) for (x, y, w, h) in new]


def all_rotations(rects):
    """4 个方向的分解矩形列表。返回 [(rects, label), ...]"""
    out = [rects]
    cur = rects
    for _ in range(3):
        cur = rotate_90(cur)
        out.append(cur)
    return out


ROTATIONS = {name: all_rotations(MODULES[name]) for name in NAMES}


def gen_shapes(n):
    """生成所有 n 节点二叉树形状（结构 id 0..n-1，前序编号）。
    返回 [(root, P, L, R)]，P/L/R 用结构 id，-1 表示空。"""
    shapes = []

    def build(lo, hi):
        if lo > hi:
            return [(-1, [], [], [])]
        res = []
        for a in range(hi - lo + 1):
            lefts = build(lo + 1, lo + a)
            rights = build(lo + a + 1, hi)
            for (lr, lp, ll, lr_) in lefts:
                for (rr, rp, rl, rr_) in rights:
                    n = hi - lo + 1
                    P = [-1] * n
                    L = [-1] * n
                    R = [-1] * n
                    root = 0
                    if a > 0:
                        L[0] = 1
                        P[1] = 0
                        for k in range(a):
                            P[1 + k] = (lp[k] + 1) if lp[k] != -1 else -1
                            L[1 + k] = (ll[k] + 1) if ll[k] != -1 else -1
                            R[1 + k] = (lr_[k] + 1) if lr_[k] != -1 else -1
                    if n - 1 - a > 0:
                        R[0] = a + 1
                        P[a + 1] = 0
                        for k in range(n - 1 - a):
                            P[a + 1 + k] = (rp[k] + a + 1) if rp[k] != -1 else -1
                            L[a + 1 + k] = (rl[k] + a + 1) if rl[k] != -1 else -1
                            R[a + 1 + k] = (rr_[k] + a + 1) if rr_[k] != -1 else -1
                    res.append((root, P, L, R))
        return res

    return build(0, n - 1)


def bbox_of(rects):
    """超块（分解矩形集）的 bbox 宽高。"""
    w = max(r[0] + r[2] for r in rects)
    h = max(r[1] + r[3] for r in rects)
    return w, h


def place(shape, perm, rots):
    """按树形+排列+旋转放置 4 超块，返回 (合法?, 包围盒面积, 每模块 [(name, rot, x, y, rects)])."""
    root, P, L, R = shape
    placed = []          # 全局已放置矩形 (x, y, w, h, owner)
    mods = []            # 每模块: (name, rot_idx, x, y, rects_abs)
    xs = [0] * 4
    ys = [0] * 4

    def support(rect):
        """rect 需要的 y 支撑顶：与已放置矩形 x 区间相交的最大顶。"""
        top = 0
        rx0, ry0, rw, _ = rect
        for (px, py, pw, ph, _) in placed:
            if px < rx0 + rw and rx0 < px + pw:
                if py + ph > top:
                    top = py + ph
        return top

    def dfs(sid):
        name = NAMES[perm[sid]]
        rects = ROTATIONS[name][rots[sid]]
        if sid == root:
            xs[sid] = 0
        else:
            p = P[sid]
            pname = NAMES[perm[p]]
            pw, _ = bbox_of(ROTATIONS[pname][rots[p]])
            if L[p] == sid:
                xs[sid] = xs[p] + pw
            else:
                xs[sid] = xs[p]
        # 超块 y = max(内部矩形所需 y)
        y = 0
        for (rx, ry, rw, rh) in rects:
            need = support((xs[sid] + rx, ry, rw, rh)) - ry
            if need > y:
                y = need
        ys[sid] = y
        for (rx, ry, rw, rh) in rects:
            placed.append((xs[sid] + rx, y + ry, rw, rh, name))
        mods.append((name, rots[sid], xs[sid], y, rects))
        if L[sid] != -1:
            dfs(L[sid])
        if R[sid] != -1:
            dfs(R[sid])

    dfs(root)
    # 矩形级重叠检查（6 实际矩形两两）
    for i in range(len(placed)):
        for j in range(i + 1, len(placed)):
            a, b = placed[i], placed[j]
            if a[0] < b[0] + b[2] and b[0] < a[0] + a[2] and \
               a[1] < b[1] + b[3] and b[1] < a[1] + a[3]:
                return False, 0, None
    maxx = max(r[0] + r[2] for r in placed)
    maxy = max(r[1] + r[3] for r in placed)
    return True, maxx * maxy, mods


def brute_bbox_version(shape, perm, rots):
    """bbox 放置版（超块按 bbox 支撑）——必合法对照。"""
    root, P, L, R = shape
    placed_bbox = []   # (x, y, w, h)
    xs = [0] * 4
    ys = [0] * 4

    def support(x, w):
        top = 0
        for (px, py, pw, ph) in placed_bbox:
            if px < x + w and x < px + pw:
                if py + ph > top:
                    top = py + ph
        return top

    def dfs(sid):
        name = NAMES[perm[sid]]
        bw, bh = bbox_of(ROTATIONS[name][rots[sid]])
        if sid == root:
            xs[sid] = 0
        else:
            p = P[sid]
            pname = NAMES[perm[p]]
            pw, _ = bbox_of(ROTATIONS[pname][rots[p]])
            if L[p] == sid:
                xs[sid] = xs[p] + pw
            else:
                xs[sid] = xs[p]
        ys[sid] = support(xs[sid], bw)
        placed_bbox.append((xs[sid], ys[sid], bw, bh))
        if L[sid] != -1:
            dfs(L[sid])
        if R[sid] != -1:
            dfs(R[sid])

    dfs(root)
    maxx = max(r[0] + r[2] for r in placed_bbox)
    maxy = max(r[1] + r[3] for r in placed_bbox)
    return maxx * maxy


def solve():
    os.makedirs(OUT, exist_ok=True)
    shapes = gen_shapes(4)
    best_area = None
    best_sol = None
    bbox_best = None
    n_valid = 0
    for shape in shapes:
        for perm in itertools.permutations(range(4)):
            for rots in itertools.product(range(4), repeat=4):
                ok, area, mods = place(shape, perm, rots)
                if not ok:
                    continue
                n_valid += 1
                if best_area is None or area < best_area:
                    best_area = area
                    best_sol = (shape, perm, rots, mods)
                ba = brute_bbox_version(shape, perm, rots)
                if bbox_best is None or ba < bbox_best:
                    bbox_best = ba
    return best_area, best_sol, bbox_best, n_valid, len(shapes) * 24 * 256


def main():
    best_area, best_sol, bbox_best, n_valid, n_total = solve()
    shape, perm, rots, mods = best_sol
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(FIGS, ts)
    os.makedirs(run_dir, exist_ok=True)

    print(f"强算穷举：{n_total} 组合，合法布局 {n_valid}")
    print(f"最小包围盒面积 = {best_area}（模块总面积下界 = {TOTAL_AREA}）")
    print(f"bbox 放置版最小 = {bbox_best}（精确版必须 <= 它）")
    assert best_area >= TOTAL_AREA, "违反面积下界"
    assert best_area <= bbox_best, "精确版面积应 <= bbox 版"
    print(f"最优摆放（模块, 旋转角, 左下角坐标）：")
    for (name, rot, x, y, rects) in mods:
        print(f"  {name}: 旋转 {rot*90}°, 位置 ({x}, {y})")

    with open(os.path.join(OUT, "q4_result.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["module", "rotation_deg", "x", "y", "rects"])
        for (name, rot, x, y, rects) in mods:
            w.writerow([name, rot * 90, x, y, ";".join(
                f"{rx},{ry},{rw},{rh}" for (rx, ry, rw, rh) in rects)])
        w.writerow([])
        w.writerow(["min_area", best_area, "total_area_lb", TOTAL_AREA,
                    "bbox_version_min", bbox_best, "valid_layouts", n_valid])

    with open(os.path.join(run_dir, "q4_result.csv"), "w") as f:
        f.write(open(os.path.join(OUT, "q4_result.csv")).read())
    print("结果 ->", os.path.join(OUT, "q4_result.csv"))


if __name__ == "__main__":
    main()
