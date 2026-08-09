"""参数扫描 + 灵敏度参数空间定义。

扫参组（挂机找更优参数）与灵敏度组（每问 S 系列）统一在这里配置。
每个配置 = (question, name, params)，由 scan.py 遍历执行。
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BIN = os.path.join(ROOT, "cpp_solver_opt", "bin", "main")
DATA = os.path.join(ROOT, "data", "raw")

# ---------------- 扫参组 ----------------
# q1: λ × repeats（n100/n200 全扫，n300 精选）
Q1_LAMBDAS = [0.45, 0.5, 0.55]
Q1_REPEATS = [8, 16]
Q2_REPEATS = [12, 16, 24]
Q2_T2_DIVS = [20, 30, 50]

def scan_configs():
    cfgs = []
    for lam in Q1_LAMBDAS:
        for rep in Q1_REPEATS:
            cfgs.append({"question": "q1", "name": f"lam{lam}_r{rep}",
                         "lambda": lam, "repeats": rep,
                         "chips": ["n100", "n200"]})
    for rep in Q2_REPEATS:
        for t2 in Q2_T2_DIVS:
            cfgs.append({"question": "q2", "name": f"r{rep}_t2{t2}",
                         "repeats": rep, "t2_div": t2,
                         "chips": ["n100", "n200"]})
    # Q3：判定种子 × 二分精度（n100/n200 快；n300 精选）
    for seeds in (3, 5):
        for eps in (1e-3, 1e-4):
            cfgs.append({"question": "q3", "name": f"seed{seeds}_e{eps}",
                         "seeds": seeds, "eps": eps,
                         "chips": ["n100", "n200"]})
    # n300 精选（成本高）
    cfgs.append({"question": "q1", "name": "lam0.5_r16_n300",
                 "lambda": 0.5, "repeats": 16, "chips": ["n300"]})
    cfgs.append({"question": "q2", "name": "r16_t230_n300",
                 "repeats": 16, "t2_div": 30, "chips": ["n300"]})
    cfgs.append({"question": "q2", "name": "r24_t250_n300",
                 "repeats": 24, "t2_div": 50, "chips": ["n300"]})
    cfgs.append({"question": "q3", "name": "seed5_e1e-4_n300",
                 "seeds": 5, "eps": 1e-4, "chips": ["n300"]})

    # ============ 第二波（扩空间） ============
    # Q1 λ 加密（11 点 × n100/n200）
    Q1_LAM_FINE = [0.375, 0.40, 0.425, 0.45, 0.475, 0.50,
                   0.525, 0.55, 0.575, 0.60, 0.625]
    for lam in Q1_LAM_FINE:
        cfgs.append({"question": "q1", "name": f"w2_lam{lam}_r16",
                     "lambda": lam, "repeats": 16, "chips": ["n100", "n200"]})
    # Q1 n300 精选（6 点）
    for lam in [0.40, 0.45, 0.475, 0.50, 0.525, 0.55]:
        cfgs.append({"question": "q1", "name": f"w2_lam{lam}_n300",
                     "lambda": lam, "repeats": 16, "chips": ["n300"]})
    # Q1 repeats 加密
    cfgs.append({"question": "q1", "name": "w2_lam0.5_r24",
                 "lambda": 0.5, "repeats": 24, "chips": ["n100", "n200"]})
    # Q1 run2 温度（t2-div 对 q1 模式）
    for t2 in (10, 15, 20, 30):
        cfgs.append({"question": "q1", "name": f"w2_q1t2{t2}",
                     "lambda": 0.5, "repeats": 16, "t2_div": t2,
                     "chips": ["n100", "n200"]})
    # Q2 t2 加密（9 点 × n100/n200）
    Q2_T2_FINE = [20, 25, 30, 35, 40, 45, 50, 60, 70]
    for t2 in Q2_T2_FINE:
        cfgs.append({"question": "q2", "name": f"w2_r16_t2{t2}",
                     "repeats": 16, "t2_div": t2,
                     "chips": ["n100", "n200"]})
    # Q2 t2 n300 精选（7 点）
    for t2 in [30, 35, 40, 45, 50, 60, 70]:
        cfgs.append({"question": "q2", "name": f"w2_r16_t2{t2}_n300",
                     "repeats": 16, "t2_div": t2, "chips": ["n300"]})
    # Q2 repeats 加密（× t2=50）
    for rep in (20, 32):
        cfgs.append({"question": "q2", "name": f"w2_r{rep}_t250",
                     "repeats": rep, "t2_div": 50,
                     "chips": ["n100", "n200"]})
    # Q3 seeds 加密
    for seeds in (7, 10, 15):
        cfgs.append({"question": "q3", "name": f"w2_seed{seeds}_e1e-4",
                     "seeds": seeds, "eps": 1e-4,
                     "chips": ["n100", "n200"]})
    cfgs.append({"question": "q3", "name": "w2_seed5_e1e-4_n300",
                 "seeds": 5, "eps": 1e-4, "chips": ["n300"]})
    for seeds in (7, 10):
        cfgs.append({"question": "q3", "name": f"w2_seed{seeds}_n300",
                     "seeds": seeds, "eps": 1e-4, "chips": ["n300"]})
    # Q3 分离参数（判定 3/5 × 确认 7/10）
    for seeds in (3, 5):
        for cs in (7, 10):
            cfgs.append({"question": "q3",
                         "name": f"w2_sep_s{seeds}_c{cs}",
                         "seeds": seeds, "confirm_seeds": cs, "eps": 1e-4,
                         "chips": ["n100", "n200"]})
    cfgs.append({"question": "q3", "name": "w2_sep_s5_c10_n300",
                 "seeds": 5, "confirm_seeds": 10, "eps": 1e-4,
                 "chips": ["n300"]})
    return cfgs

# ---------------- 灵敏度组 ----------------
def sensitivity_configs():
    cfgs = []
    # Q1: S1 λ 权衡（5 点，repeats 8）；S3 轮次收敛；S4 同 seed 复现
    for lam in [0.40, 0.45, 0.50, 0.55, 0.60]:
        cfgs.append({"question": "q1", "group": "sens", "name": f"s1_lam{lam}",
                     "lambda": lam, "repeats": 8, "chips": ["n100"]})
    for rep in [4, 8, 12, 16]:
        cfgs.append({"question": "q1", "group": "sens", "name": f"s3_r{rep}",
                     "lambda": 0.5, "repeats": rep, "chips": ["n100"]})
    # Q2: S3 t2-div；S4 死区比例
    for t2 in [20, 30, 50]:
        cfgs.append({"question": "q2", "group": "sens", "name": f"s3_t2{t2}",
                     "repeats": 8, "t2_div": t2, "chips": ["n100", "n200"]})
    for d in [0.10, 0.12, 0.15, 0.18]:
        cfgs.append({"question": "q2", "group": "sens", "name": f"s4_d{d}",
                     "repeats": 8, "t2_div": 50, "dead": d,
                     "chips": ["n100", "n200"]})
    # Q3 灵敏度：判定种子 / 判定重复性 / 二分精度
    for seeds in (1, 3, 5):
        cfgs.append({"question": "q3", "group": "sens", "name": f"s1_seed{seeds}",
                     "seeds": seeds, "eps": 1e-4, "chips": ["n100"]})
    for eps in (1e-3, 1e-4, 1e-5):
        cfgs.append({"question": "q3", "group": "sens", "name": f"s3_e{eps}",
                     "seeds": 3, "eps": eps, "chips": ["n100"]})
    return cfgs
