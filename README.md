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
./bin/main <alpha> <blocks> <nets> <pl> <rpt> [dead_ratio]
```

示例：

```bash
./bin/main 0.5 data/raw/n100.blocks data/raw/n100.nets data/raw/n100.pl /tmp/n100.rpt 0.15
```

输出 `.rpt` 格式：cost / hpwl / area / W H / time / 每模块 `name x y x+w y+h`。

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
