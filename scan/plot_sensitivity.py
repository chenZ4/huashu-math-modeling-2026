"""灵敏度图生成器：读 scan/results/{q1,q2}/sens_*.csv 出图（挂机后运行）。"""
import csv
import glob
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "scan", "results")
OUT = os.path.join(ROOT, "scan", "results", "figs")


def load(name_pattern, q):
    rows = []
    for path in sorted(glob.glob(os.path.join(RESULTS, q, f"{name_pattern}*.csv"))):
        with open(path) as f:
            for r in csv.DictReader(f):
                rows.append(r)
    return rows


def save(fig, name):
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name), dpi=300, bbox_inches="tight")
    plt.close(fig)


def main():
    # Q1 S1: lambda vs area/aspect
    rows = load("sens_s1_lam", "q1")
    if rows:
        fig, ax1 = plt.subplots(figsize=(7, 5))
        for chip in set(r["chip"] for r in rows):
            pts = [(float(r["lambda"]), float(r["area"]))
                   for r in rows if r["chip"] == chip]
            pts.sort()
            ax1.plot([p[0] for p in pts], [p[1] for p in pts], "o-", label=f"{chip} area")
        ax1.set_xlabel("lambda")
        ax1.set_ylabel("area")
        ax1.legend()
        ax1.set_title("Q1 Sensitivity: lambda vs area")
        save(fig, "q1_s1_lambda.png")

    # Q1 S3: repeats vs best area
    rows = load("sens_s3_r", "q1")
    if rows:
        fig, ax = plt.subplots(figsize=(7, 5))
        pts = sorted((int(r["repeats"]), float(r["area"])) for r in rows)
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-")
        ax.set_xlabel("repeats")
        ax.set_ylabel("best area")
        ax.set_title("Q1 Sensitivity: repeats convergence")
        save(fig, "q1_s3_repeats.png")

    # Q2 S3: t2_div vs hpwl
    rows = load("sens_s3_t2", "q2")
    if rows:
        fig, ax = plt.subplots(figsize=(7, 5))
        for chip in set(r["chip"] for r in rows):
            pts = [(int(r["t2_div"]), float(r["hpwl"]))
                   for r in rows if r["chip"] == chip]
            pts.sort()
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", label=chip)
        ax.set_xlabel("t2_div")
        ax.set_ylabel("HPWL")
        ax.legend()
        ax.set_title("Q2 Sensitivity: run2 temperature divisor")
        save(fig, "q2_s3_t2div.png")

    # Q2 S4: dead ratio vs hpwl
    rows = load("sens_s4_d", "q2")
    if rows:
        fig, ax = plt.subplots(figsize=(7, 5))
        for chip in set(r["chip"] for r in rows):
            pts = [(float(r["dead"]), float(r["hpwl"]))
                   for r in rows if r["chip"] == chip]
            pts.sort()
            ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", label=chip)
        ax.set_xlabel("dead-space ratio d")
        ax.set_ylabel("HPWL")
        ax.legend()
        ax.set_title("Q2 Sensitivity: dead ratio vs HPWL")
        save(fig, "q2_s4_dead.png")

    print("sensitivity figures ->", OUT)


if __name__ == "__main__":
    main()
