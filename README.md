# 2026 年第七届"华数杯"大学生数学建模竞赛 —— B题 VLSI 布图规划设计

## 环境

C++ 求解器：`g++`（Apple clang 21，`-std=c++17`），无第三方依赖（已移除 gnuplot/Boost）。

Python（可视化/校验）：conda 环境 `math`。

```bash
pip install -r requirements.txt
```

## 编译与测试

```bash
cd cpp_solver
make            # 编译 bin/main（生产版，无调试钩子）
make test       # 白盒测试（1134 断言）
make test-san   # ASan/UBSan 双轨
make clean
```

## 四问结论速览

| 问 | 目标 | 结果 |
|----|------|------|
| Q1 | 自由轮廓面积最小 + 长宽比→1 | n100 长宽比 1.10 / n200 1.25 / n300 1.29，利用率 >0.95 |
| Q2 | 固定轮廓（d=0.15）HPWL 最小 | HPWL 235k/403k/574k，利用率 0.868 ≈ 理论极限 0.8696 |
| Q3 | 最小可行死区比例 | d\* = 0.117 / 0.109 / 0.125（双向确认通过） |
| Q4 | L/T 模块四向旋转最小面积 | **24 = 总面积下界 → 全局最优证明** |

论文数值速查 + 溯源：`paper/data_package/paper_values.md`；各问详细文档：`qX/qX_work_guide.pdf`。

## 求解器用法

```bash
./bin/main <mode:q1|q2> <alpha> <blocks> <nets> <pl> <rpt> [dead_ratio] [--log <file>] [--feas-only] [--seed <n>]
```

- `mode=q1`：自由轮廓，代价 = λ·面积 + (1−λ)·长宽比对称惩罚（λ = alpha，默认 0.5）
- `mode=q2`：固定正方形轮廓（dead_ratio 默认 0.15），HPWL 为主
- `--log <file>`：每温度层记录 `phase iter T best_cost alpha feas` + 9 等分快照
- `--feas-only`：只判可行性（Q3 二分专用，找到首可行即返回）
- `--seed <n>`：随机种子（默认当前时间，配合 seed_base 可复现）

示例：

```bash
# Q1（自由轮廓，面积+长宽比）
./bin/main q1 0.5 data/raw/n100.blocks data/raw/n100.nets data/raw/n100.pl /tmp/q1.rpt --log /tmp/q1.log --seed 20260808

# Q2（固定轮廓 + HPWL）
./bin/main q2 0.5 data/raw/n100.blocks data/raw/n100.nets data/raw/n100.pl /tmp/q2.rpt 0.15

# Q3 判定（--feas-only）
./bin/main q2 0.5 data/raw/n100.blocks data/raw/n100.nets data/raw/n100.pl /tmp/feas.rpt 0.12 --feas-only --seed 42
```

输出 `.rpt` 格式：cost / hpwl / area / W H / time / 每模块 `name x y x+w y+h`。

## 复现

```bash
conda activate math
python q1/q1_solver.py --repeats 8    # Q1 三芯片 + CSV + 出图
python q2/q2_solver.py --repeats 8    # Q2 三芯片 + CSV + 出图
python q3/q3_solver.py --repeats 8    # Q3 二分 + d* 求解 + CSV + 出图
python q4/q4_solver.py                # Q4 强算（秒级）
python q4/visualization/plot_q4.py --csv q4/output/q4_result.csv --out q4/visualization/figs/q4_optimal.png
```

## 目录

```
data/raw/                 原始附件副本 n100/n200/n300（.blocks/.nets/.pl，只读）
cpp_solver/               【冻结版】C++ B*-Tree + Fast-SA 核心（1134 断言，交付基线）
cpp_solver_opt/           【优化版】独立副本：vector 版 Skyline + --t2-div（参数实验场）
scan/                     参数扫描 + 灵敏度挂机工作区（scan.py / configs.py / plot_sensitivity.py）
eda/                      数据探索分析（8 张 EDA 图 + 统计汇总）
common/                   共享 Python 库（visualize / verify）
q1/ q2/ q3/ q4/           各问客制层（solver + output + visualization + work_guide + sensitivity）
paper/                    论文写作（data_package/ 数值速查表）
```

## 参考

- HW2 原始方案（保持纯净，仅作参考）：`HW2/`
- Chang 论文：`B题 VLSI布图规划设计/Modern Floorplanning Based on B ∗ -Tree and Fast Simulated.pdf`
