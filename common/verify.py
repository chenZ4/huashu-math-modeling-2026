"""共享布局合法性复核：无重叠 / 尺寸保持 / 越界检查（三问共用）。"""
import re


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


def read_blocks_from_rpt(rpt):
    """解析 .rpt 第 6 行起的模块坐标行。"""
    blocks = []
    for line in open(rpt).read().splitlines()[5:]:
        parts = line.split()
        if len(parts) == 5:
            name, x1, y1, x2, y2 = parts[0], *map(int, parts[1:])
            blocks.append((name, x1, y1, x2, y2))
    return blocks


def verify_layout(rpt, dims, outline=None):
    """独立复核。outline: (W, H) 轮廓，None 时不查越界。返回 (ok, msg)。"""
    blocks = read_blocks_from_rpt(rpt)
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
        if outline is not None:
            if b[3] > outline[0] or b[4] > outline[1]:
                return False, f"out of outline {b[0]}"
    return True, "ok"
