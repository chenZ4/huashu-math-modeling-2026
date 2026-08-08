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
make test       # 编译并运行 bin/test_main（-DTREE_DEBUG 白盒测试）
make clean
```

## 求解器用法

```bash
./bin/main <mode:q1|q2> <alpha> <blocks> <nets> <pl> <rpt> [dead_ratio] [--log <file>]
```

- `mode=q1`：自由轮廓，代价 = λ·面积 + (1−λ)·长宽比对称惩罚（λ = alpha，默认 0.5）
- `mode=q2`：固定正方形轮廓（dead_ratio 默认 0.15），HPWL 为主
- `--log <file>`：每温度层记录 `phase iter T best_cost alpha feas`（收敛轨迹）

示例：

```bash
# Q1（自由轮廓，面积+长宽比）
./bin/main q1 0.5 data/raw/n100.blocks data/raw/n100.nets data/raw/n100.pl /tmp/q1.rpt --log /tmp/q1.log

# Q2（固定轮廓 + HPWL）
./bin/main q2 0.5 data/raw/n100.blocks data/raw/n100.nets data/raw/n100.pl /tmp/q2.rpt 0.15
```

输出 `.rpt` 格式：cost / hpwl / area / W H / time / 每模块 `name x y x+w y+h`。

## Q1 复现

```bash
conda activate math
python q1/q1_solver.py        # 求解三芯片 + 汇总 CSV + 出图
python q1/q1_solver.py --skip-solve   # 只重出图/汇总
```

产物：`q1/output/q1_metrics.csv`（面积/长宽比/利用率/合法性）、`q1/visualization/figs/*.png`（布图 + 收敛曲线）。

## 目录

```
data/raw/                 原始附件副本 n100/n200/n300（.blocks/.nets/.pl，只读）
data/parsed/              解析后的结构化数据
cpp_solver/               C++ B*-Tree + Fast-SA 求解器（改编自 NTU HW2 开源方案）
  src/floor_plan.hpp      B*-tree 表示 / 轮廓线定位 / 三种扰动算子 / 自适应代价
  src/main.cpp            求解入口（两阶段退火）
  src/test_main.cpp       白盒测试框架（拓扑不变量 / 算子边界 / Skyline / 全量对齐）
common/                   公共 Python 代码（解析 / 校验 / 可视化）
q1/ q2/ q3/ q4/           各问求解与产出（output / latex / sensitivity）
paper/                    论文写作
```

## 参考

- HW2 原始方案（保持纯净，仅作参考）：`HW2/`
- Chang 论文：`B题 VLSI布图规划设计/Modern Floorplanning Based on B ∗ -Tree and Fast Simulated.pdf`
