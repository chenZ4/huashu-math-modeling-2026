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
         "chips": ["n100"]},
        {"question": "q2", "name": "t2", "repeats": 2, "t2_div": 50,
         "chips": ["n100", "n200"]},
    ]


def stop_and_wait(t, timeout=300):
    with scan.state.lock:
        scan.state.stop_flag = True
    scan.state.cur_cfg = ""
    deadline = time.time() + timeout
    while t.is_alive() and time.time() < deadline:
        time.sleep(5)
    return not t.is_alive()


def test_flow():
    print("== 场景 1: 全流程（q1×n100 2轮 + q2×n100 2轮 + q2×n200 1轮并行）==")
    scan.RESULTS = tempfile.mkdtemp(prefix="scan_test_")
    scan.state = scan.State()
    cfgs = make_cfgs()
    t = threading.Thread(target=scan.worker_main, args=(cfgs, 4, 1.0), daemon=True)
    t.start()
    deadline = time.time() + 420
    while time.time() < deadline:
        files = []
        for q in ("q1", "q2"):
            d = os.path.join(scan.RESULTS, q)
            if os.path.isdir(d):
                files += [f for f in os.listdir(d) if f.endswith(".csv")]
        if len(files) >= 3:
            break
        time.sleep(5)
    check("3 个芯片任务落盘", len(files) >= 3, f"files={len(files)}")
    ok = True
    for q in ("q1", "q2"):
        d = os.path.join(scan.RESULTS, q)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if not f.endswith(".csv"):
                continue
            with open(os.path.join(d, f)) as fh:
                rows = list(csv.DictReader(fh))
            if len(rows) != 1:
                ok = False
                continue
            r = rows[0]
            if q == "q1":
                ok = ok and bool(r.get("area")) and bool(r.get("aspect"))
            else:
                ok = ok and bool(r.get("hpwl")) and "legal" in r
    check("落盘数据字段完整", ok)
    check("停止后收尾退出", stop_and_wait(t))
    return scan.RESULTS


def test_resume(results):
    print("== 场景 2: 断点续跑（已存在文件应 skip）==")
    scan.RESULTS = results
    scan.state = scan.State()
    t = threading.Thread(target=scan.worker_main,
                         args=(make_cfgs(), 4, 1.0), daemon=True)
    t.start()
    deadline = time.time() + 60
    while time.time() < deadline:
        with scan.state.lock:
            if scan.state.done >= 3 and scan.state.pass_no >= 2:
                break
        time.sleep(2)
    with scan.state.lock:
        done, pn = scan.state.done, scan.state.pass_no
    check("重跑 skip 生效且快速", done >= 3 and pn >= 2, f"done={done} pass={pn}")
    check("停止收尾", stop_and_wait(t, 400))


def test_best_accumulate(results):
    print("== 场景 3: 跨遍累积 best（force 重跑保留更优值）==")
    scan.RESULTS = results
    scan.state = scan.State()
    path = os.path.join(scan.RESULTS, "q1", "scan_t1_n100.csv")
    with open(path) as f:
        orig = dict(list(csv.DictReader(f))[0])
    bad = dict(orig)
    bad["area"] = str(int(float(orig["area"])) * 2)
    scan.atomic_write(path, bad)
    t = threading.Thread(target=scan.worker_main,
                         args=(make_cfgs(), 4, 1.0), daemon=True)
    t.start()
    deadline = time.time() + 180
    while time.time() < deadline:
        with open(path) as f:
            cur = list(csv.DictReader(f))[0]
        if float(cur["area"]) <= float(orig["area"]):
            break
        time.sleep(5)
    with open(path) as f:
        cur = list(csv.DictReader(f))[0]
    check("force 重跑恢复更优面积", float(cur["area"]) <= float(orig["area"]),
          f"orig={orig['area']} cur={cur['area']}")
    check("停止收尾", stop_and_wait(t, 400))


def test_timeout_guard():
    print("== 场景 4: 子进程超时兜底（ROUND_TIMEOUT=1 触发 TimeoutExpired）==")
    scan.RESULTS = tempfile.mkdtemp(prefix="scan_tmo_")
    scan.state = scan.State()
    old = scan.ROUND_TIMEOUT
    scan.ROUND_TIMEOUT = 1
    try:
        status, path = scan.run_chip({"question": "q1", "name": "tmo",
                                      "lambda": 0.5, "repeats": 2},
                                     "n100", False)
        check("超时后返回（fail 或 done），不崩溃", status in ("fail", "done"),
              f"status={status}")
    finally:
        scan.ROUND_TIMEOUT = old


def test_dirty_rpt():
    print("== 场景 5: 脏 rpt 解析兜底 ==")
    rpt = "/tmp/scan_dirty_test.rpt"
    with open(rpt, "w") as f:
        f.write("garbage\n")
    row = scan.rpt_metrics("n100", "q1", rpt,
                           {"lambda": 0.5, "t2_div": 50, "dead": 0.15,
                            "side": 0, "repeats": 1, "seed_base": 0})
    check("脏 rpt 返回 None（不击穿）", row is None)


def test_half_csv_recovery():
    print("== 场景 6: 半写 CSV 恢复（坏文件删除重算）==")
    scan.RESULTS = tempfile.mkdtemp(prefix="scan_half_")
    scan.state = scan.State()
    q1 = os.path.join(scan.RESULTS, "q1")
    os.makedirs(q1, exist_ok=True)
    bad_path = os.path.join(q1, "scan_t1_n100.csv")
    with open(bad_path, "w") as f:
        f.write("chip,area\nn100,12")  # 缺列的半写文件
    scan.state = scan.State()
    scan.run_chip({"question": "q1", "name": "t1", "lambda": 0.5, "repeats": 1},
                  "n100", False)
    with open(bad_path) as f:
        rows = list(csv.DictReader(f))
    check("坏文件被重算且字段完整", len(rows) == 1 and "aspect" in rows[0],
          f"fields={list(rows[0].keys()) if rows else 'empty'}")


def test_gui():
    print("== 场景 7: GUI 构建/命令显示/自动关窗 ==")
    scan.state = scan.State()
    scan.state.done = 1
    scan.state.cur_cfg = "test @ n100"
    scan.state.cur_round = 2
    scan.state.cur_repeats = 4
    scan.state.cur_cmd = "./bin/main q1 0.5 ... --seed 1"

    def fin():
        time.sleep(1)
        with scan.state.lock:
            scan.state.finished_flag = True

    threading.Thread(target=fin, daemon=True).start()
    import tkinter as tk
    root = tk.Tk()
    t0 = time.time()
    scan.build_gui(root)
    root.after(15000, root.destroy)
    root.mainloop()
    check("finished 自动关窗（<10s）", time.time() - t0 < 10,
          f"elapsed={time.time()-t0:.1f}s")


def test_caffeinate():
    print("== 场景 8: caffeinate 启停 ==")
    import subprocess
    p = subprocess.Popen(["caffeinate", "-i", "-s"])
    time.sleep(1)
    alive = p.poll() is None
    p.terminate()
    time.sleep(1)
    check("caffeinate 启动/终止正常", alive and p.poll() is not None)


if __name__ == "__main__":
    r = test_flow()
    test_resume(r)
    test_best_accumulate(r)
    test_timeout_guard()
    test_dirty_rpt()
    test_half_csv_recovery()
    test_gui()
    test_caffeinate()
    print("=" * 50)
    print(f"测试结果: PASS={PASS} FAIL={FAIL}")
    sys.exit(1 if FAIL else 0)
