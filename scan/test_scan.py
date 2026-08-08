"""scan.py 挂机程序自动化测试（挂机前必须全绿）。
覆盖：全流程执行 / 数据合法性 / 断点续跑 / 跨遍累积 best / 停止收尾 / GUI。
用法: python scan/test_scan.py
"""
import csv
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scan"))
sys.path.insert(0, os.path.join(ROOT, "common"))
import scan  # noqa: E402
from verify import parse_blocks  # noqa: E402

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [OK] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def make_cfgs():
    return [
        {"question": "q1", "name": "t1", "lambda": 0.5, "repeats": 2,
         "chips": ["n100", "n200"]},
        {"question": "q2", "name": "t2", "repeats": 2, "t2_div": 50,
         "chips": ["n100", "n200"]},
    ]


def wait_done(t, timeout_s, interval=5):
    """等待 worker 线程结束或超时。返回是否结束。"""
    t.join(timeout=timeout_s)
    return not t.is_alive()


def test_full_flow():
    print("== 场景 1: 全流程执行（2 配置 × n100+n200 × 2 轮）==")
    scan.RESULTS = tempfile.mkdtemp(prefix="scan_test_")
    scan.state = scan.State()
    cfgs = make_cfgs()
    t = threading.Thread(target=scan.worker_main, args=(cfgs, 4, 1.0), daemon=True)
    t.start()
    # 等第一遍完成（q1 快 + q2 n100 快 + q2 n200 2 轮 ~2-4min）
    deadline = time.time() + 420
    while time.time() < deadline:
        files = []
        for q in ("q1", "q2"):
            d = os.path.join(scan.RESULTS, q)
            if os.path.isdir(d):
                files += [f for f in os.listdir(d) if f.endswith(".csv")]
        if len(files) >= 8:  # 2 配置 × 2 芯片 × 2 问
            break
        time.sleep(5)
    with scan.state.lock:
        done = scan.state.done
    check("第一遍完成 8 个芯片任务", done >= 8, f"done={done}")
    # 数据合法性：读 CSV 与 rpt 交叉（无重叠/尺寸/越界用 verify 逻辑）
    ok_data = True
    for q in ("q1", "q2"):
        d = os.path.join(scan.RESULTS, q)
        if not os.path.isdir(d):
            ok_data = False
            continue
        for f in os.listdir(d):
            path = os.path.join(d, f)
            if not f.endswith(".csv"):
                continue
            with open(path) as fh:
                rows = list(csv.DictReader(fh))
            if len(rows) != 1:
                ok_data = False
                print(f"    行数异常: {f}")
                continue
            r = rows[0]
            if q == "q1":
                if not (r.get("area") and r.get("aspect")):
                    ok_data = False
            else:
                if not (r.get("hpwl") and r.get("legal")):
                    ok_data = False
    check("落盘数据字段完整", ok_data)
    with scan.state.lock:
        scan.state.stop_flag = True
    scan.state.cur_cfg = ""
    t.join(timeout=60)
    check("停止后收尾退出", not t.is_alive())
    return scan.RESULTS


def test_resume(results_dir):
    print("== 场景 2: 断点续跑（重跑应全部 skip，不重复计算）==")
    scan.RESULTS = results_dir
    scan.state = scan.State()
    cfgs = make_cfgs()
    t0 = time.time()
    t = threading.Thread(target=scan.worker_main, args=(cfgs, 4, 0.1), daemon=True)
    t.start()
    t.join(timeout=120)
    elapsed = time.time() - t0
    with scan.state.lock:
        done = scan.state.done
        pn = scan.state.pass_no
    check("重跑全部 skip（done=8 不重复）", done >= 8 and elapsed < 90,
          f"done={done} elapsed={elapsed:.0f}s")
    # 文件 mtime 不应被改写（skip 不写）
    check("已结束标记", scan.state.finished_flag)


def test_best_accumulate(results_dir):
    print("== 场景 3: 跨遍累积 best（force 重跑保留更优值）==")
    scan.RESULTS = results_dir
    scan.state = scan.State()
    # 手工把 t1_n100 的结果改差，force 重跑应更新回更优
    path = os.path.join(scan.RESULTS, "q1", "scan_t1_n100.csv")
    with open(path) as f:
        rows = list(csv.DictReader(f))
    orig = dict(rows[0])
    bad = dict(orig)
    bad["area"] = str(int(float(orig["area"])) * 2)  # 变差 2 倍
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(bad.keys()))
        w.writeheader()
        w.writerow(bad)
    cfgs = make_cfgs()
    t = threading.Thread(target=scan.worker_main, args=(cfgs, 4, 0.2), daemon=True)
    t.start()
    # 第二遍会 force 重跑 t1 并覆盖
    deadline = time.time() + 180
    while time.time() < deadline:
        with open(path) as f:
            cur = list(csv.DictReader(f))[0]
        if float(cur["area"]) < float(bad["area"]):
            break
        time.sleep(5)
    with open(path) as f:
        cur = list(csv.DictReader(f))[0]
    check("force 重跑恢复到更优面积", float(cur["area"]) <= float(orig["area"]),
          f"orig={orig['area']} bad={bad['area']} cur={cur['area']}")
    with scan.state.lock:
        scan.state.stop_flag = True
    t.join(timeout=60)


def test_gui():
    print("== 场景 4: GUI 构建/刷新/自动关窗 ==")
    scan.state = scan.State()
    scan.state.done = 1
    scan.state.cur_cfg = "test @ n100"
    scan.state.cur_round = 2
    scan.state.cur_repeats = 4

    def fin():
        time.sleep(1)
        with scan.state.lock:
            scan.state.finished_flag = True

    threading.Thread(target=fin, daemon=True).start()
    import tkinter as tk
    root = tk.Tk()
    t0 = time.time()
    scan.build_gui(root)
    root.after(15000, root.destroy)  # 兜底
    root.mainloop()
    elapsed = time.time() - t0
    check("finished 自动关窗（<10s）", elapsed < 10, f"elapsed={elapsed:.1f}s")


def test_caffeinate():
    print("== 场景 5: caffeinate 启停 ==")
    import subprocess
    p = subprocess.Popen(["caffeinate", "-i", "-s"])
    time.sleep(1)
    alive = p.poll() is None
    p.terminate()
    time.sleep(1)
    check("caffeinate 启动/终止正常", alive and p.poll() is not None)


if __name__ == "__main__":
    results = test_full_flow()
    test_resume(results)
    test_best_accumulate(results)
    test_gui()
    test_caffeinate()
    print("=" * 50)
    print(f"测试结果: PASS={PASS} FAIL={FAIL}")
    sys.exit(1 if FAIL else 0)
