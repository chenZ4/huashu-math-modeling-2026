# 论文数值速查表（数据包 · 定稿版）
生成时间: 2026-08-10 09:00
> 论文手使用说明：所有数值以本表为准；完整数据在对应 final/ CSV 中；
> baseline/ = 冻结版原始交付（存档），final/ = 定稿复现（opt 版 + 最优参数，已交叉核对与挂机 best 逐位一致）。

## Q1 自由轮廓（面积最小 + 长宽比→1，λ=0.5，逐芯片参数，固定种子可复现）
| 芯片 | 参数 | 面积 | W×H | 长宽比 | 利用率 | 合法性 |
|---|---|---|---|---|---|---|
| n100 | t2=20, 8轮 | 189198 | 414×457 | 1.1039 | 0.9487 | True |
| n200 | t2=30, 24轮 | 183112 | 376×487 | 1.2952 | 0.9595 | True |
| n300 | t2=20, 24轮 | 285228 | 417×684 | 1.6403 | 0.9577 | True |

数据源: `q1/output/final/q1_metrics.csv` / `q1/output/final/q1_<chip>.rpt`

## Q2 固定轮廓（d=0.15，HPWL 最小，逐芯片 t2-div）
| 芯片 | 参数 | 轮廓 side | HPWL | 利用率 | 理论利用率上界 1/1.15 | 合法性 |
|---|---|---|---|---|---|---|
| n100 | α=0.1, t2=70, 8轮+局部下降 | 455 | **207061.5** | 0.867 | 0.8696 | True |
| n200 | t2=60, 24轮 | 450 | 380261.0 | 0.8676 | 0.8696 | True |
| n300 | t2=70, 60轮+局部下降 | 561 | **519010.5** | 0.868 | 0.8696 | True |

> 2026-08-24 更新（T2/T1 实验）：n100 新纪录 q2/output/alpha_scan/q2_n100_a0.1_t270_r106.rpt；
> n300 新纪录 q2/output/elite/q2_n300_boost3_r602.rpt；均过 verify+HPWL 金标准。
> n200 未破（380261.0 保持）。

数据源: `q2/output/final/q2_metrics.csv` / `q2/output/final/q2_<chip>.rpt`

## Q3 最小死区比例（判定种子 15/15/10 + 双向确认，全部 confirmed=True）
| 芯片 | 判定种子 | d* | 轮廓 side | HPWL | 确认通过 | 合法性 |
|---|---|---|---|---|---|---|
| n100 | 15 | 0.076072 | 440 | 288184.0 | True | True |
| n200 | 15 | 0.084141 | 待补 | 待补 | True | True |
| n300 | 10 | 0.111773 | 552 | 826375.0 | True | True |

数据源: `q3/output/final/q3_metrics.csv`（confirm 完整记录在 `confirm_steps` 列）

## Q4 全局最优（超块 B*-Tree 强算穷举 86,016 布局）
| 指标 | 值 |
|---|---|
| 最小包围盒面积 | **24** = 模块总面积下界（全局最优证明） |
| 包围盒 | 4×6 |
| bbox 放置版对照 | 32（精确支撑节省 25%） |

数据源: `q4/output/final/q4_result.csv`

## 提升对比（定稿 final vs 冻结 baseline）
| 问 | n100 | n200 | n300 |
|---|---|---|---|
| Q1 面积 | 0% | -0.40% | -0.77% |
| Q2 HPWL | -4.16% | -5.71% | -7.55% |
| Q3 d* | -35.2% | -22.8%（待最终确认） | -10.5% |

## 结果溯源（论文引用 → 文件 → 复现）
| 论文引用值 | 文件 | 复现命令 |
|---|---|---|
| Q1 面积/长宽比 | q1/output/final/q1_metrics.csv | `python q1/q1_solver.py --chip <c> --repeats <n> [--t2-div <t>] --outdir q1/output/final`（seed=20260808+r 固定） |
| Q2 HPWL | q2/output/final/q2_metrics.csv | `python q2/q2_solver.py --chip <c> --repeats <n> --t2-div <t> --outdir q2/output/final` |
| Q3 d* | q3/output/final/q3_metrics.csv | `python q3/q3_solver.py --chip <c> --seeds <s> --outdir q3/output/final` |
| Q4 面积 24 | q4/output/final/q4_result.csv | `python q4/q4_solver.py` |

## 已知限制（论文表述提示）
- Q1/Q2/Q3 为多起点启发式搜索：结果为多轮取优（best-of-N），轮间存在方差
- Q3 d* 为'在当前搜索强度（判定种子数）下验证过的最小可行比例'——种子 3→15 改善 35-45%，论文须注明搜索强度
- Q4 尺寸取自题目附图；最优性由下界可达严格证明
- 求解器 `--log` 快照逻辑曾导致结果偏移（已修复：snapshots 后显式重放置），
  冻结版 baseline 数值为修复前 log 版，定稿 final 为修复后数值（交叉核对通过）
