# 支撑材料说明

2026 年第七届"华数杯"大学生数学建模竞赛 B 题《VLSI 布图规划设计》
支撑材料。本包包含支撑论文模型、结果与结论的全部必要文件：
源程序、数据与中间结果、图表、论文说明文档与参考文献。

## 包内结构

```
支撑材料/
|-- 00_说明/            本说明（README.md）+ 支撑材料清单.md
|-- 01_源程序/
|   |-- cpp_solver/      冻结版 C++ 核心（B*-Tree + 快速模拟退火，src + Makefile）
|   |-- cpp_solver_opt/  优化版（vector Skyline + --t2-div，src + Makefile）
|   |-- common/          共享 Python 库（verify 合法性复核 / visualize 绘图）
|   |-- scan/            参数扫描挂机（scan / configs / cross_check / 绘图）
|   |-- eda/             数据探索分析（eda.py）
|   |-- q1/ q2/ q3/ q4/  各问求解脚本、灵敏度分析、可视化脚本
|   `-- requirements.txt
|-- 02_数据与中间结果/
|   |-- 定稿结果/        各问定稿数值（metrics / rpt 坐标 / 二分轨迹）
|   |-- 参数扫描/        96 配置扫描结果（每配置最优 CSV）
|   `-- 灵敏度数据/      S 系列灵敏度数据与 EDA 统计表
|-- 03_图表/             论文全部图表（按题目分类 + 灵敏度 + 公共，含图表索引）
|-- 04_论文与说明/       论文章节成稿（数据分析/灵敏度分析/模型评价/模型假设等）
|-- 05_参考文献/         B*-Tree + 快速模拟退火参考文献
```

## 编译

```bash
cd cpp_solver        # 冻结版（1134 断言白盒测试 + ASan/UBSan）
make && make test
cd ../cpp_solver_opt  # 优化版（定稿数值由此产生）
make
```

## 定稿复现（论文数值来源：02_数据与中间结果/定稿结果/）

```bash
conda activate math

# Q1（λ=0.5；n200 取 t2-div=30；逐芯片轮次）
python q1/q1_solver.py --chip n100 --repeats 8  --outdir q1/output/final
python q1/q1_solver.py --chip n200 --repeats 24 --t2-div 30 --outdir q1/output/final
python q1/q1_solver.py --chip n300 --repeats 24 --outdir q1/output/final

# Q2（逐芯片 t2-div 35/60/70）
python q2/q2_solver.py --chip n100 --repeats 16 --t2-div 35 --outdir q2/output/final
python q2/q2_solver.py --chip n200 --repeats 24 --t2-div 60 --outdir q2/output/final
python q2/q2_solver.py --chip n300 --repeats 24 --t2-div 70 --outdir q2/output/final

# Q3（判定种子 15/15/10）
python q3/q3_solver.py --chip n100 --seeds 15 --outdir q3/output/final
python q3/q3_solver.py --chip n200 --seeds 15 --outdir q3/output/final
python q3/q3_solver.py --chip n300 --seeds 10 --outdir q3/output/final

# Q4（穷举，秒级）
python q4/q4_solver.py
```

所有运行使用固定随机种子（seed_base = 20260808），同参数同种子结果
逐位一致；定稿复现值与参数扫描最优值交叉核对 9/9 逐位一致。

## 说明

- 原始数据（.blocks/.nets/.pl）由赛题提供，不包含在本包内；
- 包内 Python 源程序仅对注释做了精简，代码逻辑与原始版本一致；
- 论文数值以 `02_数据与中间结果/定稿结果/` 为准。
