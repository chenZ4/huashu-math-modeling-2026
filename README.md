# 2026 年第七届"华数杯"大学生数学建模竞赛 —— B题 VLSI 布图规划设计

## 环境

C++ 求解器：`g++`（Apple clang 21，`-std=c++17`），无第三方依赖（已移除 gnuplot/Boost）。

Python（可视化/校验/挂机）：conda 环境 `math`。

```bash
pip install -r requirements.txt
```

## 编译与测试

```bash
cd cpp_solver          # 【冻结版】交付基线（--seed 可复现，--t2-div 不可用）
make && make test      # 白盒测试（1134 断言）
make test-san          # ASan/UBSan 双轨

cd cpp_solver_opt      # 【优化版】--t2-div 参数实验/定稿（与冻结版同种子逐位一致）
make
```

## 四问结论速览（定稿值，经交叉核对与挂机扫描逐位一致）

| 问 | 目标 | 定稿结果 | vs 冻结 |
|----|------|----------|---------|
| Q1 | 自由轮廓面积最小 + 长宽比→1 | 面积 189198 / **183112** / **285228**（n100/n200/n300） | -0% / -0.4% / -0.8% |
| Q2 | 固定轮廓（d=0.15）HPWL 最小 | HPWL **225403.5** / **380261** / **530944.5**（t2-div 35/60/70） | -4.2% / -5.7% / -7.6% |
| Q3 | 最小可行死区比例 | d\* = **0.076072** / **0.084141** / **0.111773**（判定种子 15/15/10，双向确认通过） | -35% / -23% / -11% |
| Q4 | L/T 模块四向旋转最小面积 | **24 = 总面积下界 → 全局最优证明** | — |

- 论文数值速查 + 溯源：`paper/data_package/paper_values.md`
- 各问详细建模与算法：`qX/qX_work_guide.pdf`（论文手工作稿风格）
- 灵敏度分析：`图表/灵敏度/QN/qN_sensitivity_report.pdf`（LaTeX 分析 + 图 + 数据，按问收录）
- 灵敏度论文章节素材：`paper/sensitivity_analysis.pdf`

## 求解器用法

```bash
./bin/main <mode:q1|q2> <alpha> <blocks> <nets> <pl> <rpt> [dead_ratio] [--log <file>] [--feas-only] [--seed <n>] [--t2-div <n>]
```

- `mode=q1`：自由轮廓，代价 = λ·面积 + (1−λ)·长宽比对称惩罚（λ = alpha，默认 0.5）
- `mode=q2`：固定正方形轮廓（dead_ratio 默认 0.15），HPWL 为主
- `--log <file>`：每温度层记录 `phase iter T best_cost alpha feas` + 9 等分快照
  （已修复：快照逻辑不再影响求解结果，同种子带/不带 log 逐位一致）
- `--feas-only`：只判可行性（Q3 二分专用，找到首可行即返回）
- `--seed <n>`：随机种子（默认当前时间，配合 seed_base 可复现）
- `--t2-div <n>`：run2 精修初始温度除数（仅优化版；Q1 默认 20，Q2 默认 50）

示例：

```bash
# Q1（自由轮廓，面积+长宽比）
./bin/main q1 0.5 data/raw/n100.blocks data/raw/n100.nets data/raw/n100.pl /tmp/q1.rpt --log /tmp/q1.log --seed 20260808

# Q2（固定轮廓 + HPWL，t2-div 调优）
./bin/main q2 0.5 data/raw/n200.blocks data/raw/n200.nets data/raw/n200.pl /tmp/q2.rpt 0.15 --seed 20260808 --t2-div 60

# Q3 判定（--feas-only）
./bin/main q2 0.5 data/raw/n100.blocks data/raw/n100.nets data/raw/n100.pl /tmp/feas.rpt 0.12 --feas-only --seed 42
```

输出 `.rpt` 格式：cost / hpwl / area / W H / time / 每模块 `name x y x+w y+h`。

## 定稿复现流程（output 拆 baseline/final）

```bash
conda activate math

# Q1（λ=0.5；n200 取 t2-div=30；逐芯片轮次）
python q1/q1_solver.py --chip n100 --repeats 8  --outdir q1/output/final
python q1/q1_solver.py --chip n200 --repeats 24 --t2-div 30 --outdir q1/output/final
python q1/q1_solver.py --chip n300 --repeats 24 --outdir q1/output/final
python q1/q1_solver.py --skip-solve --outdir q1/output/final   # 合并 metrics + 出图

# Q2（逐芯片 t2-div）
python q2/q2_solver.py --chip n100 --repeats 16 --t2-div 35 --outdir q2/output/final
python q2/q2_solver.py --chip n200 --repeats 24 --t2-div 60 --outdir q2/output/final
python q2/q2_solver.py --chip n300 --repeats 24 --t2-div 70 --outdir q2/output/final
python q2/q2_solver.py --skip-solve --outdir q2/output/final

# Q3（判定种子 15/15/10）
python q3/q3_solver.py --chip n100 --seeds 15 --outdir q3/output/final
python q3/q3_solver.py --chip n200 --seeds 15 --outdir q3/output/final
python q3/q3_solver.py --chip n300 --seeds 10 --outdir q3/output/final

# Q4（穷举，秒级）
python q4/q4_solver.py

# 交叉核对：定稿 final vs 挂机 scan best（逐位一致）
python scan/cross_check.py
```

- `qX/output/baseline/`：冻结版原始交付（存档）
- `qX/output/final/`：定稿复现（opt 版 + 最优参数，交叉核对通过）
- 图：`qX/visualization/figs/final/<chip>/`（11-12 张/芯片）+ `figs/baseline/`（冻结对照）

## 灵敏度分析

```bash
python q1/sensitivity/q1_sensitivity.py   # S1 λ / S2 轮次 / S3 精修温度
python q2/sensitivity/q2_sensitivity.py   # S1 t2-div / S2 死区比例 / S3 轮次
python q3/sensitivity/q3_sensitivity.py   # S1 判定种子 / S2 二分精度 / S3 判定·确认解耦
python q4/sensitivity/q4_sensitivity.py   # S1 旋转消融 / S2 尺寸扰动（穷举变体）
```

- CSV 汇总：`qX/sensitivity/S*.csv`；报告：`qX/sensitivity/qX_sensitivity_report.pdf`
- 灵敏度输出：根目录 `图表/灵敏度/QN/`（图 + S 系列数据）

## 参数扫描挂机（scan/）

```bash
cd scan
python scan.py --dry-run                # 预览 96 配置
python scan.py --workers 9 --max-hours 24 --no-gui   # 挂机（断点续跑/原子写/超时兜底）
python test_scan.py                     # 挂机程序自测（12/12）
```

- 配置：`scan/configs.py`；结果：`scan/results/{q1,q2,q3}/*.csv`（每配置跨遍最佳）
- 定稿参数即由此锁定（λ=0.5、t2-div 35/60/70、判定种子 15/15/10）

## 目录

```
data/raw/                 原始附件副本 n100/n200/n300（.blocks/.nets/.pl，只读）
cpp_solver/               【冻结版】C++ B*-Tree + Fast-SA 核心（1134 断言，交付基线）
cpp_solver_opt/           【优化版】vector Skyline + --t2-div（定稿/参数实验用）
scan/                     参数扫描挂机（scan.py / configs.py / cross_check.py / results / logs）
eda/                      数据探索分析（EDA 图 + 统计汇总）
common/                   共享 Python 库（visualize / verify）
q1/ q2/ q3/ q4/           各问客制层（solver + output[baseline/final] + visualization[baseline/final] + work_guide + sensitivity）
图表/                     论文素材总集（按题目分类：Q1-Q4 图/表/说明 + 公共/）
paper/                    论文写作（data_package/ 数值速查表 + sensitivity_analysis.pdf）
B题 VLSI布图规划设计/      题面与参考文献
HW2/                      HW2 原始方案（仅参考，保持纯净）
```

## 参考

- HW2 原始方案（保持纯净，仅作参考）：`HW2/`
- Chang 论文：`B题 VLSI布图规划设计/Modern Floorplanning Based on B ∗ -Tree and Fast Simulated.pdf`
