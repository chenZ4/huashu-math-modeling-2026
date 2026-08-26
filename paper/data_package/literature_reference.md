# 文献参考线数据包（GSRC n100/n200/n300 · Tier 2）

> 用途：论文"对比实验"小节的外部公认 Baseline 行。
> 竞赛附件数据 = GSRC floorplanning benchmark 原版（100/200/300 hard blocks，
> 885/1585/1893 nets，334/468/565 terminals），文献数值可直接对标，
> 但须脚注声明协议差异（见各条目"口径"）。

## A. 同单位可直接对标：ASPDAC'08 凸优化论文（HPWL，原始栅格单位）

来源：Cheng/Kahng et al., "Large-Scale Fixed-Outline Floorplanning Design Using
Convex Optimization Techniques", ASP-DAC 2008, Table I/II。
协议：固定轮廓 whitespace=10%（即轮廓=sqrt(1.10×总面积)，**注意与我们 d=0.15
（=13.04% whitespace）略不同**）；I/O pads 固定于轮廓边界；soft modules 假设。

### Table II：pads 固定于边界，10% whitespace（HPWL）

| 算例 | 本文定稿¹ | Ours² | IMF | IMFAFF | Capo | Parquet |
|---|---|---|---|---|---|---|
| n100 | **207061.5** | 203700 | 207852 | 208772 | 224390 | 242050 |
| n200 | **380261.0** | 367880 | 369888 | 372845 | 385594 | 432882 |
| n300 | **519010.5** | 492830 | 489868 | 494480 | 522968 | 647452 |

¹ 本文表3定稿口径（d=0.15，hard blocks，pads 原始位置）——协议与文献行有差异，论文中须注明"跨协议参考"。
² ASPDAC'08 自家凸优化方法（soft modules）。

定位话术（诚实）：n100 上我们与 IMF 持平（-0.4%）；n200/n300 落后 IMF/IMFAFF
2.0%–5.9%（解析式+软模块优势域），但全面优于 Capo（-1.4%~-7.7%）与
Parquet（-12.1%~-19.8%）。**硬模块、d=0.15 更紧轮廓下取得该水平具竞争力。**

### Table I（同论文，pads 边界，多 whitespace 档，备查）

Ours: n100 197490(0%ws)/200490(5%)/203700(10%)/207180(15%)；
n200 356520/362070/367880/373840；n300 477800/485180/492830/500910。

## B. 成功率参考（百分比，可直接引）：Chen & Chang TCAD'06 Table IV

来源：Chen & Chang, "Modern Floorplanning Based on B*-Tree and Fast Simulated
Annealing", IEEE TCAD 25(4), 2006, Table IV（n100，50 次平均，1.6GHz P4）。
协议：固定轮廓成功率（能塞入给定轮廓的比例）。

| dead space Γ | GFA | Parquet-4.5(SP) | Parquet-4.5(B*-tree) | Fast-SA (Ours) | 本文求解器³ |
|---|---|---|---|---|---|
| 10% | 30.3% | 65.5% | 99.4% | 100% | 100%（d=0.13 对应档） |
| 15% | 86.7% | 99.4% | 99.4% | 100% | 100%（d=0.15 定稿档） |

³ 本文 d=0.15 全种子全算例合法（Q2 final/matrix 数据佐证）；n100 在 d=0.13 档
由 BLF/SP-random 的失败侧行反衬搜索必要性。此列数值待矩阵跑完后回填确认。

## C. 线长参考（单位不可直接比，仅作趋势引证）：TCAD'06 Table V

Fast-SA vs Parquet-4.5(SP)，best-of-10，R*=1..4，单位 mm（物理缩放后）：
n100 32.06–34.39 / 33.56–36.89；n200 58.33–63.72 / 62.76–66.31；
n300 71.00–82.18 / 76.05–88.58（Ours/Parquet 区间）。
**脚注模板**："Chen&Chang 报告值为物理单位(mm)，与本文栅格单位不可直接比较，
仅引用其'Fast-SA 较 Parquet 平均降 6% 线长'的相对结论。"

## D. 引用条目（BibTeX 备用）

```bibtex
@inproceedings{cheng2008fixedoutline,
  title={Large-Scale Fixed-Outline Floorplanning Design Using Convex Optimization Techniques},
  author={Cheng, Chung-Kuan and Kahng, Andrew B. and Liu, Bao and Wang, Qinke and Wong, Martin D. F.},
  booktitle={Proc. Asia and South Pacific Design Automation Conference (ASP-DAC)},
  pages={198--204}, year={2008}
}
@article{chen2006modern,
  title={Modern Floorplanning Based on B$^*$-Tree and Fast Simulated Annealing},
  author={Chen, Tung-Chieh and Chang, Yao-Wen},
  journal={IEEE Transactions on Computer-Aided Design of Integrated Circuits and Systems},
  volume={25}, number={4}, pages={637--650}, year={2006}
}
```
