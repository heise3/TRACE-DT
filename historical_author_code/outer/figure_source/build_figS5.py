from __future__ import annotations

import argparse

import hashlib

import json

import math

import shutil

import textwrap

from datetime import datetime, timezone

from pathlib import Path

import matplotlib as mpl

import matplotlib.pyplot as plt

import numpy as np

import pandas as pd

from matplotlib.colors import LinearSegmentedColormap

from matplotlib.lines import Line2D

from matplotlib.patches import Patch

from matplotlib.transforms import Bbox

from PIL import Image

BLUE = "#3F6F9F"

BLUE_LIGHT = "#BFD2E3"

VIOLET = "#7966A8"

AMBER = "#D49A42"

VERMILION = "#C65A46"

TEAL = "#4C918D"

GRAPHITE = "#30343B"

MID = "#6E7781"

LIGHT = "#E8EBEF"

PALE = "#F5F7F9"

def configure() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 7.1,
            "axes.titlesize": 8.0,
            "axes.labelsize": 7.1,
            "xtick.labelsize": 6.5,
            "ytick.labelsize": 6.5,
            "legend.fontsize": 6.0,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 0.7,
            "xtick.major.width": 0.6,
            "ytick.major.width": 0.6,
            "xtick.major.size": 2.4,
            "ytick.major.size": 2.4,
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "savefig.facecolor": "white",
            "figure.facecolor": "white",
            "legend.frameon": False,
        }
    )

def read_tsv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, sep="\t")

def resolve_supp_source(source_root: Path, name: str) -> Path:
    """Support both the historical nested tree and the frozen flat source bundle."""
    nested = source_root / "r17_supplement" / name
    flat = source_root / name
    if nested.exists():
        return nested
    if flat.exists():
        return flat
    raise FileNotFoundError(f"Supplementary source table not found: {name}")

EXACT_NODE_LABELS = {
    "bladder urothelial cancer": "urinary bladder cancer",
    "adult diffuse glioma": "brain glioma",
}

def label_panel(ax: plt.Axes, label: str, x: float = -0.10, y: float = 1.035) -> None:
    ax.text(
        x,
        y,
        label,
        transform=ax.transAxes,
        fontsize=8.2,
        fontweight="bold",
        ha="left",
        va="bottom",
        gid="panel_label",
    )

def clean(ax: plt.Axes, grid: str | None = None) -> None:
    ax.spines["left"].set_color("#8B929A")
    ax.spines["bottom"].set_color("#8B929A")
    ax.tick_params(length=2.4, color="#8B929A")
    if grid:
        ax.grid(axis=grid, color=LIGHT, linewidth=0.55, zorder=0)

def copy_source(path: Path, source_dir: Path, name: str | None = None) -> Path:
    source_dir.mkdir(parents=True, exist_ok=True)
    target = source_dir / (name or path.name)
    if path.resolve() != target.resolve():
        shutil.copy2(path, target)
    return target

def figure_s5(
    source_root: Path,
    r17_outputs: Path,
    dirs: dict[str, Path],
    copied: Path,
    audit: Path,
) -> list[Path]:
    summary_path = resolve_supp_source(source_root, "S5_counterfactual_summary.tsv")
    summary = read_tsv(summary_path)
    copy_source(summary_path, copied)
    labels = ["Primary 23", "Date-strict 23", "Unrestricted 23", "OT-only 24"]
    summary["analysis"] = pd.Categorical(summary["analysis"], labels, ordered=True)
    summary = summary.sort_values("analysis").reset_index(drop=True)

    condition_paths = {name: source_root / ("S5_" + name.replace(" ", "_") + "_O2_conditioned.tsv") for name in ["Primary", "Date-strict", "Unrestricted", "OT-only 24"]}
    conditioned = []
    for analysis, path in condition_paths.items():
        frame = read_tsv(path)
        frame["analysis"] = analysis
        conditioned.append(frame)
        copy_source(path, copied, f"S5_{analysis.replace(' ', '_')}_O2_conditioned.tsv")
    conditioned = pd.concat(conditioned, ignore_index=True)

    perturb = pd.DataFrame(
        [
            {
                "analysis": "Date-strict",
                "Eligibility states": 782 / 118126,
                "Nomination seats": 695 / 36800,
                "Affected cells": 143 / 736,
            },
            {
                "analysis": "Unrestricted",
                "Eligibility states": 10629 / 118126,
                "Nomination seats": 7915 / 36800,
                "Affected cells": 614 / 736,
            },
        ]
    )
    perturb.to_csv(copied / "S5_normalized_perturbation_summary.tsv", sep="\t", index=False)

    fig = plt.figure(figsize=(7.16, 4.1))
    gs = fig.add_gridspec(
        2, 2, width_ratios=[1.05, 1.35], height_ratios=[1.0, 0.82],
        left=0.16, right=0.985, bottom=0.17, top=0.84, wspace=0.38, hspace=0.55
    )
    ax_a = fig.add_subplot(gs[:, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[1, 1])

    label_panel(ax_a, "a", x=-0.18)
    y = np.arange(len(summary))[::-1]
    ax_a.hlines(y, summary["lower"], summary["upper"], color=BLUE_LIGHT, lw=6, zorder=2)
    ax_a.scatter(summary["deterministic"], y, color=BLUE, s=34, edgecolor="white", lw=0.5, label="Deterministic", zorder=3)
    ax_a.scatter(summary["expected"], y, color=VIOLET, marker="D", s=22, edgecolor="white", lw=0.4, label="Independent-product expectation", zorder=4)
    ax_a.set_yticks(y, summary["analysis"].astype(str))
    ax_a.set_xlim(0.25, 0.64)
    ax_a.set_xlabel("Global membership substitution")
    ax_a.set_title("Tie-aware counterfactual bounds", loc="left", fontweight="bold")
    ax_a.legend(
        loc="upper left", bbox_to_anchor=(0.0, -0.13),
        ncol=2, handletextpad=0.35, columnspacing=0.8, borderaxespad=0
    )
    clean(ax_a, grid="x")

    label_panel(ax_b, "b", x=-0.12, y=1.07)
    long = perturb.melt(id_vars="analysis", var_name="metric", value_name="fraction")
    metric_order = ["Eligibility states", "Nomination seats", "Affected cells"]
    analysis_order = ["Date-strict", "Unrestricted"]
    x = np.arange(len(metric_order))
    for analysis, color, offset in [("Date-strict", BLUE, -0.11), ("Unrestricted", VIOLET, 0.11)]:
        sub = long.loc[long["analysis"].eq(analysis)].set_index("metric").loc[metric_order]
        ax_b.scatter(x + offset, sub["fraction"] * 100, color=color, s=30, label=analysis, zorder=3)
        for xx, value in zip(x + offset, sub["fraction"] * 100):
            ax_b.text(xx, value + 2.3, f"{value:.1f}%", ha="center", fontsize=5.0, color=color)
    ax_b.set_xticks(x, ["Eligibility\nstates", "Nomination\nseats", "Affected\ncells"])
    ax_b.set_ylim(-5, 94)
    ax_b.set_ylabel("Changed fraction (%)", labelpad=4)
    ax_b.set_title("Perturbation reaches different layers", loc="left", fontweight="bold")
    ax_b.legend(ncol=2, loc="upper left")
    clean(ax_b, grid="y")

    label_panel(ax_c, "c", x=-0.13)
    filtered = conditioned.loc[conditioned["direct_toggle_factor"].isin(["O4", "O5"])].copy()
    col_keys = [("O4", 0), ("O4", 1), ("O5", 0), ("O5", 1)]
    row_keys = ["Primary", "Date-strict", "Unrestricted", "OT-only 24"]
    matrix = np.zeros((4, 4), dtype=float)
    for i, analysis in enumerate(row_keys):
        for j, (factor, stratum) in enumerate(col_keys):
            row = filtered.loc[
                filtered["analysis"].eq(analysis)
                & filtered["direct_toggle_factor"].eq(factor)
                & filtered["O2_stratum"].eq(stratum)
            ]
            matrix[i, j] = float(row["substitution_deterministic_mean"].iloc[0])
    cmap = LinearSegmentedColormap.from_list("mech", ["#F7F8FA", BLUE_LIGHT, BLUE, GRAPHITE])
    ax_c.imshow(matrix, aspect="auto", vmin=0, vmax=0.70, cmap=cmap)
    for i in range(4):
        for j in range(4):
            color = "white" if matrix[i, j] > 0.42 else GRAPHITE
            ax_c.text(j, i, f"{matrix[i, j]:.2f}", ha="center", va="center", fontsize=5.1, color=color)
    ax_c.set_xticks(
        np.arange(4),
        ["O4 · data-\nsource", "O4 · lineage", "O5 · data-\nsource", "O5 · lineage"],
        fontsize=5.2
    )
    ax_c.set_yticks(np.arange(4), row_keys, fontsize=5.5)
    ax_c.set_title("O2-conditioned O4/O5 reversal persists", loc="left", fontweight="bold")
    ax_c.tick_params(length=0)
    for spine in ax_c.spines.values():
        spine.set_visible(False)

    return save_figure(fig, dirs, "Figure_S5_Eligibility_and_context_counterfactuals", audit)

def save_figure(fig, dirs, stem, audit):
    output = dirs['PDF']
    output.mkdir(parents=True, exist_ok=True)
    # Native vector export retains all eight mean markers above the interval bands.
    means = fig.axes[0].collections[1:3]
    assert [len(c.get_offsets()) for c in means] == [4, 4]
    assert all(c.get_zorder() > fig.axes[0].collections[0].get_zorder() for c in means)
    audit.mkdir(parents=True, exist_ok=True)
    (audit/'S5_MARKER_QA.json').write_text(json.dumps({'status':'PASS', 'marker_counts':[4,4], 'marker_zorders':[c.get_zorder() for c in means], 'band_zorder':fig.axes[0].collections[0].get_zorder(), 'coordinates':[c.get_offsets().tolist() for c in means]}, indent=2), encoding='utf-8')
    outputs=[]
    for ext in ['pdf','svg','png']:
        p=output/('Figure_S5.'+ext)
        fig.savefig(p, dpi=300, bbox_inches='tight',pad_inches=0.035)
        outputs.append(p)
    plt.close(fig)
    return outputs

if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--audit', type=Path, required=True)
    args=parser.parse_args()
    configure()
    figure_s5(args.data,args.data,{'PDF':args.output},args.data,args.audit)
