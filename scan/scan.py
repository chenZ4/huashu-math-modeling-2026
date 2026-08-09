"""参数扫描 + 灵敏度挂机工作区（GUI 进度弹窗 / 停止按钮 / 时间驱动）。
稳定版（混沌补丁 + Q3 支持）：原子写、子进程超时、脏数据校验、线程异常隔离。
运行模型：
  - 三芯片并行：每个配置的 n100/n200/n300 同时跑（芯片级并行）
  - 时间驱动：--max-hours 内持续运行；一遍跑完且时间未到则重跑（跨遍累积 best）
用法:
  python scan/scan.py --dry-run
  python scan/scan.py --workers 9 --max-hours 24   # 挂机（GUI 弹窗）
停止语义：点停止按钮后，当前正在跑的轮（一次 bin/main）自然跑完即退出。
"""
import argparse
import csv
import datetime
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scan"))
sys.path.insert(0, os.path.join(ROOT, "common"))
sys.path.insert(0, os.path.join(ROOT, "q3"))
from configs import BIN, DATA, scan_configs, sensitivity_configs  # noqa: E402
from verify import parse_blocks  # noqa: E402

RESULTS = os.path.join(ROOT, "scan", "results")
LOGS = os.path.join(ROOT, "scan", "logs")
DEFAULT_REPEATS = 30
ROUND_TIMEOUT = 900


class State:
    def __init__(self):
        self.lock = threading.Lock()
        self.total = 0
        self.done = 0
        self.pass_no = 1
        self.pass_done = 0
        self.cur_cfg = ""
        self.cur_round = 0
        self.cur_repeats = 0
        self.cur_cmd = ""
        self.stop_flag = False
        self.finished_flag = False
        self.last_results = []
        self.start_time = time.time()
        self.max_hours = 24
        self.failed = 0

    def eta(self):
        with self.lock:
            done, total = self.done, self.total
        if done == 0:
            return "--:--:--"
        elapsed = time.time() - self.start_time
        remain = elapsed / done * (total - done)
        return str(datetime.timedelta(seconds=int(max(0, remain))))

    def elapsed_str(self):
        return str(datetime.timedelta(seconds=int(time.time() - self.start_time)))


state = State()


def rpt_metrics(chip, question, rpt, extra):
    """解析 .rpt。失败/脏数据返回 None（由调用方判废该轮）。"""
    try:
        lines = open(rpt).read().splitlines()
        if len(lines) < 5:
            return None
        dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
        row = {"chip": chip, "question": question}
        row.update(extra)
        if question == "q1":
            W, H = map(int, lines[3].split())
            area = int(lines[2])
            if W <= 0 or H <= 0 or area <= 0 or total <= 0:
                return None
            row["area"] = area
            row["aspect"] = round(max(W, H) / min(W, H), 4)
            row["util"] = round(total / (W * H), 4)
        else:
            W, H = map(int, lines[3].split())
            hpwl = float(lines[1])
            if W <= 0 or H <= 0 or not (hpwl == hpwl) or hpwl < 0:
                return None
            side = int(extra.get("side", 0))
            row["hpwl"] = round(hpwl, 2)
            row["bbox"] = lines[3].strip()
            row["legal"] = (W <= side and H <= side) if side else ""
        return row
    except (IndexError, ValueError, TypeError, OSError):
        return None


def side_for(chip, dead):
    dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
    return int(__import__("math").ceil((total * (1 + dead)) ** 0.5))


def better(a, b, q):
    """a 是否优于 b（q1: (area, aspect) 字典序；q2: hpwl 更小）。"""
    if q == "q1":
        return (a["area"], a["aspect"]) < (b["area"], b["aspect"])
    return a["hpwl"] < b["hpwl"]


def read_csv_best(path, q):
    """读历史 best（跨遍累积）。坏文件/缺必需字段返回 None（调用方删除重算）。"""
    try:
        with open(path) as f:
            rows = list(csv.DictReader(f))
        if len(rows) != 1:
            return None
        r = rows[0]
        required = {"q1": ("area", "aspect"), "q2": ("hpwl", "legal"),
                    "q3": ("d_star", "confirmed")}
        for k in required.get(q, ()):
            if r.get(k) is None or r.get(k) == "":
                return None
        for k in ("area", "hpwl", "aspect", "util", "d_star"):
            v = r.get(k)
            if v is not None:
                fv = float(v)
                if fv != fv or fv < 0:
                    return None
        return {k: (float(v) if k in ("area", "hpwl", "aspect", "util",
                                      "d_star", "lambda", "t2_div", "dead",
                                      "side", "seeds", "eps")
                    else v) for k, v in r.items()}
    except (ValueError, IndexError, OSError):
        return None


def atomic_write(path, row):
    """原子写：tmp + flush + fsync + replace（防半写文件被断点读取）。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row.keys()))
        w.writeheader()
        w.writerow(row)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def run_chip(cfg, chip, force):
    """单芯片：q1/q2 跑 SA 轮次取最优；q3 跑参数化二分求 d*。落盘。"""
    q = cfg["question"]
    if q == "q3":
        return _run_chip_q3(cfg, chip, force)
    return _run_chip_sa(cfg, chip, force)


def _run_chip_q3(cfg, chip, force):
    """Q3：参数化判定种子/二分精度的 d* 搜索（复用 q3_bisect）。"""
    from q3_bisect import bisect, confirm_minimum
    group = cfg.get("group", "scan")
    cname = cfg["name"]
    out_path = os.path.join(RESULTS, "q3", f"{group}_{cname}_{chip}.csv")
    seeds = cfg.get("seeds", 3)
    confirm_seeds = cfg.get("confirm_seeds", seeds)
    eps = cfg.get("eps", 1e-4)
    prev_best = None
    if os.path.exists(out_path):
        prev_best = read_csv_best(out_path, "q3")
        if prev_best is None:
            os.remove(out_path)
            print(f"[WARN] 坏历史 CSV 已删除重算: {os.path.basename(out_path)}")
    if prev_best is not None and not force:
        return ("skip", out_path)
    dims, total = parse_blocks(os.path.join(DATA, f"{chip}.blocks"))
    work_dir = os.path.join(RESULTS, "q3", "work", f"{cname}_{chip}")
    os.makedirs(work_dir, exist_ok=True)
    trace = os.path.join(work_dir, "trace.csv")
    with state.lock:
        state.cur_cfg = f"{cname} @ {chip} (q3 seeds={seeds} eps={eps})"
    try:
        d_b, _ = bisect(chip, total, work_dir, trace, eps=eps,
                        coarse_seeds=max(1, seeds // 2), precise_seeds=seeds)
        d_s, steps = confirm_minimum(chip, d_b, total, work_dir,
                                     verify_seeds=confirm_seeds)
    except Exception as e:
        print(f"[FAIL] q3 {cname} @ {chip}: {e}")
        with state.lock:
            state.cur_cfg = ""
        return ("fail", out_path)
    confirmed = bool(steps) and steps[-1].get("below_infeas", False)
    row = {"chip": chip, "question": "q3", "d_star": round(d_s, 6),
           "side": side_for(chip, d_s), "confirmed": confirmed,
           "seeds": seeds, "eps": eps}
    if prev_best and confirmed is False and prev_best.get("confirmed"):
        row = prev_best
    elif prev_best and confirmed and prev_best.get("d_star") is not None and \
            prev_best["d_star"] < row["d_star"]:
        row = prev_best
    atomic_write(out_path, row)
    with state.lock:
        state.cur_cfg = ""
    return ("done", out_path)


def _run_chip_sa(cfg, chip, force):
    """q1/q2：跑 repeats 轮 SA 取最优，跨遍累积 best，原子落盘。"""
    q = cfg["question"]
    group = cfg.get("group", "scan")
    cname = cfg["name"]
    out_path = os.path.join(RESULTS, q, f"{group}_{cname}_{chip}.csv")
    repeats = cfg.get("repeats", DEFAULT_REPEATS)
    prev_best = None
    if os.path.exists(out_path):
        prev_best = read_csv_best(out_path, q)
        if prev_best is None:
            os.remove(out_path)
            print(f"[WARN] 坏历史 CSV 已删除重算: {os.path.basename(out_path)}")
    if prev_best is not None and not force:
        return ("skip", out_path)

    rpt = f"/tmp/scan_{q}_{cname}_{chip}.rpt"
    best = None
    failures = 0
    with state.lock:
        state.cur_cfg = f"{cname} @ {chip}"
        state.cur_repeats = repeats
    for r in range(repeats):
        with state.lock:
            state.cur_round = r + 1
            if state.stop_flag:
                state.cur_cfg = ""
                return ("stop", out_path)
        seed = 20260808 + r
        cmd = [BIN, "q1" if q == "q1" else "q2", str(cfg.get("lambda", 0.5)),
               os.path.join(DATA, f"{chip}.blocks"),
               os.path.join(DATA, f"{chip}.nets"),
               os.path.join(DATA, f"{chip}.pl"),
               rpt, str(cfg.get("dead", 0.15)), "--seed", str(seed)]
        if q == "q2":
            cmd += ["--t2-div", str(cfg.get("t2_div", 50))]
        elif q == "q1" and cfg.get("t2_div"):
            cmd += ["--t2-div", str(cfg["t2_div"])]
        with state.lock:
            state.cur_cmd = " ".join(cmd)
        try:
            subprocess.run(cmd, check=True, timeout=ROUND_TIMEOUT)
        except subprocess.TimeoutExpired:
            print(f"[WARN] 轮超时被终止: {chip} r{r} ({ROUND_TIMEOUT}s)")
            failures += 1
            continue
        except subprocess.CalledProcessError:
            print(f"[WARN] 子进程失败: {chip} r{r}")
            failures += 1
            continue
        extra = {
            "lambda": cfg.get("lambda", 0.5),
            "t2_div": cfg.get("t2_div", 50),
            "dead": cfg.get("dead", 0.15),
            "side": side_for(chip, cfg.get("dead", 0.15)) if q == "q2" else 0,
            "repeats": repeats, "seed_base": 20260808,
        }
        row = rpt_metrics(chip, q, rpt, extra)
        if row is None:
            failures += 1
            continue
        if best is None or better(row, best, q):
            best = row
    if failures >= repeats and best is None:
        with state.lock:
            state.cur_cfg = ""
        return ("fail", out_path)
    if prev_best and best and better(prev_best, best, q):
        best = prev_best
    if best is None:
        with state.lock:
            state.cur_cfg = ""
        return ("fail", out_path)
    atomic_write(out_path, best)
    with state.lock:
        state.cur_cfg = ""
        state.cur_cmd = ""
    return ("done", out_path)


def run_config(cfg, force):
    """配置：三芯片并行（每芯片独立落盘）。失败芯片不拖累其他。"""
    with ThreadPoolExecutor(max_workers=3) as ex:
        futures = {ex.submit(run_chip, cfg, c, force): c for c in cfg["chips"]}
        results = []
        for f in as_completed(futures):
            try:
                results.append(f.result())
            except Exception as e:
                chip = futures[f]
                print(f"[FAIL] {cfg['name']} @ {chip}: {e}")
                results.append(("fail", None))
        return results


def worker_main(cfgs, workers, max_hours):
    """时间驱动：多遍循环（pass1 断点 skip，pass2+ 重跑累积 best），时间到停。"""
    try:
        _worker_loop(cfgs, workers, max_hours)
    except Exception:
        import traceback
        traceback.print_exc()
        with state.lock:
            state.failed += 1
            state.last_results.append("!! worker 异常（见日志）")
            state.last_results = state.last_results[-3:]
    finally:
        with state.lock:
            state.finished_flag = True


def _worker_loop(cfgs, workers, max_hours):
    cfgs = sorted(cfgs, key=lambda c: 0 if "n300" in c["chips"] else 1)
    while True:
        with state.lock:
            if state.stop_flag:
                break
            over = time.time() - state.start_time > max_hours * 3600
        if over:
            print(f"== 达到 {max_hours}h 上限：收尾退出 ==")
            break
        force = state.pass_no > 1
        with state.lock:
            state.pass_done = 0
            state.total = len(cfgs) * 3
        print(f"== 第 {state.pass_no} 遍开始（{'重跑累积 best' if force else '断点续跑'}） ==")
        with ThreadPoolExecutor(max_workers=workers) as ex:
            future_map = {ex.submit(run_config, c, force): c for c in cfgs}
            for fut in as_completed(future_map):
                cfg = future_map[fut]
                try:
                    results = fut.result()
                except Exception as e:
                    with state.lock:
                        state.failed += 1
                    print(f"[FAIL] {cfg['name']}: {e}")
                    continue
                for status, path in results:
                    if status == "done":
                        with state.lock:
                            state.done += 1
                            state.pass_done += 1
                            state.last_results.append(
                                f"{os.path.basename(path)}: "
                                f"{open(path).read().splitlines()[-1]}")
                            state.last_results = state.last_results[-3:]
                        print(f"[P{state.pass_no} {state.done}] done {os.path.basename(path)}")
                    elif status == "skip":
                        with state.lock:
                            state.done += 1
                            state.pass_done += 1
                        print(f"[P{state.pass_no} {state.done}] skip {os.path.basename(path)}")
                with state.lock:
                    stop = state.stop_flag
                if stop:
                    for f in future_map:
                        if f != fut and not f.done():
                            f.cancel()
                    break
        if state.stop_flag:
            print("== 停止请求：当前轮完成后退出 ==")
            break
        with state.lock:
            state.pass_no += 1


def build_gui(root):
    from tkinter import ttk
    global state
    frame = ttk.Frame(root, padding=12)
    frame.pack(fill="both", expand=True)

    ttk.Label(frame, text="参数扫描挂机面板（三芯片并行 · 时间驱动）",
              font=("", 14, "bold")).pack()
    lbl_prog = ttk.Label(frame, text="进度: 0/0  0.0%")
    lbl_prog.pack(pady=(8, 2))
    bar = ttk.Progressbar(frame, maximum=100, length=420)
    bar.pack()
    lbl_eta = ttk.Label(frame, text="ETA: --:--:--  已运行: 00:00:00")
    lbl_eta.pack(pady=2)
    lbl_cur = ttk.Label(frame, text="当前: -")
    lbl_cur.pack(pady=2)
    lbl_cmd = ttk.Label(frame, text="命令: -", foreground="#555", justify="left",
                        wraplength=460, font=("", 8))
    lbl_cmd.pack(pady=2)
    lbl_recent = ttk.Label(frame, text="最近结果:\n-", justify="left",
                           wraplength=440)
    lbl_recent.pack(pady=4)
    lbl_status = ttk.Label(frame, text="运行中（停止后等待当前轮完成）",
                           foreground="green")
    lbl_status.pack(pady=4)

    def on_stop():
        with state.lock:
            state.stop_flag = True
        btn_stop.config(state="disabled", text="停止请求已发出…")
        lbl_status.config(text="停止请求已发出：当前轮结束后退出",
                          foreground="orange")

    btn_stop = ttk.Button(frame, text="停止（当前轮结束后）", command=on_stop)
    btn_stop.pack(pady=6)

    def on_close():
        with state.lock:
            state.stop_flag = True
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.after(300, lambda: refresh(root, lbl_prog, bar, lbl_eta, lbl_cur,
                                    lbl_cmd, lbl_recent, lbl_status, btn_stop))


def refresh(root, lbl_prog, bar, lbl_eta, lbl_cur, lbl_cmd, lbl_recent,
            lbl_status, btn_stop):
    with state.lock:
        done, total, pn, pd = state.done, state.total, state.pass_no, state.pass_done
        cur = state.cur_cfg
        r, rr = state.cur_round, state.cur_repeats
        cmd = state.cur_cmd
        recent = list(state.last_results)
        stop = state.stop_flag
        finished = state.finished_flag
    pct = pd / max(1, total) * 100
    lbl_prog.config(text=f"第 {pn} 遍  本遍: {pd}/{total}  {pct:.1f}%  (累计 {done})")
    bar["value"] = pct
    lbl_eta.config(text=f"ETA: {state.eta()}  已运行: {state.elapsed_str()}")
    cur_txt = f"{cur}  (轮 {r}/{rr})" if cur else "空闲/收尾"
    lbl_cur.config(text=f"当前: {cur_txt}")
    lbl_cmd.config(text=f"命令: {cmd}" if cmd else "命令: -")
    lbl_recent.config(text="最近结果:\n" + ("\n".join(recent) if recent else "-"))
    if finished:
        lbl_status.config(text="已结束。结果在 scan/results/（断点可续跑）",
                          foreground="blue")
        btn_stop.config(state="disabled", text="已结束")
        root.after(3000, root.destroy)
        return
    if stop:
        lbl_status.config(text="停止请求已发出：当前轮结束后退出",
                          foreground="orange")
    root.after(1000, lambda: refresh(root, lbl_prog, bar, lbl_eta, lbl_cur,
                                     lbl_cmd, lbl_recent, lbl_status, btn_stop))


def run_gui():
    import tkinter as tk
    root = tk.Tk()
    root.title("scan 挂机面板")
    root.geometry("480x400")
    root.attributes("-topmost", True)
    build_gui(root)
    root.mainloop()


def main():
    global state
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=9)
    ap.add_argument("--max-hours", type=float, default=24.0)
    ap.add_argument("--group", choices=["scan", "sens"], default=None)
    ap.add_argument("--no-gui", action="store_true")
    ap.add_argument("--no-caffeinate", action="store_true")
    ap.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    args = ap.parse_args()

    cfgs = []
    if args.group in (None, "scan"):
        cfgs += scan_configs()
    if args.group in (None, "sens"):
        cfgs += sensitivity_configs()
    for c in cfgs:
        c.setdefault("repeats", args.repeats)
    state = State()
    state.max_hours = args.max_hours

    print(f"计划 {len(cfgs)} 配置 × 3 芯片并行, workers={args.workers}, "
          f"repeats上限={args.repeats}, max_hours={args.max_hours}")
    if args.dry_run:
        for c in cfgs:
            print(f"  [{c['question']}] {c['name']} chips={c['chips']} "
                  f"repeats={c['repeats']} t2_div={c.get('t2_div','-')}")
        return

    os.makedirs(RESULTS, exist_ok=True)
    os.makedirs(LOGS, exist_ok=True)

    caffeinate_proc = None
    if not args.no_caffeinate:
        caffeinate_proc = subprocess.Popen(["caffeinate", "-i", "-s"])
        print("caffeinate 已启动（防休眠）")

    try:
        if args.no_gui:
            worker_main(cfgs, args.workers, args.max_hours)
        else:
            t = threading.Thread(target=worker_main,
                                 args=(cfgs, args.workers, args.max_hours),
                                 daemon=True)
            t.start()
            run_gui()
            t.join(timeout=120)
    finally:
        if caffeinate_proc is not None:
            caffeinate_proc.terminate()
            print("caffeinate 已终止")

    with state.lock:
        done, failed, pn = state.done, state.failed, state.pass_no
    print(f"== 结束：完成 {done} 个芯片任务（第 {pn} 遍），失败 {failed} ==")
    print(f"结果目录: {RESULTS}（重跑自动续传/累积 best）")


if __name__ == "__main__":
    main()
