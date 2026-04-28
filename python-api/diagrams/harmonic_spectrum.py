"""
Harmonic Distortion Spectrum Chart — Phase 10a
Standards: IEEE 519-2022 (Recommended Practice for Harmonic Control),
           IEC 61000-3-2:2018
Returns SVG string for inline HTML rendering.

Chart layout:
  Left panel  — Harmonic spectrum bar chart (individual harmonic currents vs IEEE 519 limits)
  Right panel — Summary table (THD, TDD, K-factor, compliance status)
"""

import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


def generate(inputs: dict, results: dict) -> str:
    """Returns SVG string of the harmonic spectrum diagram."""

    # ── Extract results ───────────────────────────────────────────────────────
    harmonics     = results.get("individual_harmonics", [])
    THD           = float(results.get("THD_I_pct",    0))
    TDD           = float(results.get("TDD_pct",      0))
    tdd_limit     = float(results.get("TDD_limit_pct", 8))
    k_factor      = float(results.get("K_factor",     1))
    overall_pass  = bool(results.get("overall_pass",  False))
    isc_il        = float(results.get("isc_il_ratio", 20))
    I1            = float(results.get("fundamental_current_A",
                          inputs.get("fundamental_current_a", 100)))
    project       = str(inputs.get("project_name", "Harmonic Analysis"))

    if not harmonics:
        # Fallback from inputs if results empty
        for h in inputs.get("harmonics", []):
            harmonics.append({
                "order":       int(h.get("order", 3)),
                "current_pct": float(h.get("current_pct", 0)),
                "current_A":   I1 * float(h.get("current_pct", 0)) / 100,
                "limit_pct_of_IL": 4.0,
                "limit_A":     I1 * 4.0 / 100,
                "pass":        True,
            })

    orders   = [h["order"]       for h in harmonics]
    curr_pct = [h["current_pct"] for h in harmonics]
    lim_pct  = [h.get("limit_pct_of_IL", 4.0) for h in harmonics]
    passes   = [h.get("pass", True) for h in harmonics]

    # ── Colours ───────────────────────────────────────────────────────────────
    PASS_CLR = "#2e7d32"   # green
    FAIL_CLR = "#c0392b"   # red
    LIM_CLR  = "#F7A21B"   # amber (IEEE 519 limit line)
    BG       = "#0f1923"   # dark background
    PANEL    = "#162032"   # slightly lighter panel
    TEXT     = "#e8edf2"
    GRID     = "#1e2d3d"

    bar_colors = [PASS_CLR if p else FAIL_CLR for p in passes]

    # ── Figure ────────────────────────────────────────────────────────────────
    fig = plt.figure(figsize=(13, 5.8), facecolor=BG)
    fig.patch.set_facecolor(BG)

    gs = fig.add_gridspec(1, 2, width_ratios=[2.2, 1], wspace=0.08,
                          left=0.07, right=0.98, top=0.88, bottom=0.14)

    # ── Left: bar chart ───────────────────────────────────────────────────────
    ax = fig.add_subplot(gs[0])
    ax.set_facecolor(PANEL)

    x = np.arange(len(orders))
    bar_w = 0.5

    bars = ax.bar(x, curr_pct, width=bar_w, color=bar_colors,
                  edgecolor="none", zorder=3, alpha=0.92)

    # Limit markers (horizontal lines per bar)
    for i, lim in enumerate(lim_pct):
        ax.plot([x[i] - bar_w * 0.6, x[i] + bar_w * 0.6],
                [lim, lim], color=LIM_CLR, linewidth=2.0, zorder=4)

    # TDD limit reference line (dashed amber)
    if curr_pct:
        ax.axhline(tdd_limit, color=LIM_CLR, linewidth=1.2,
                   linestyle="--", zorder=2, alpha=0.7,
                   label=f"TDD limit {tdd_limit}%")

    # Value labels on bars
    for bar, val, p in zip(bars, curr_pct, passes):
        clr = TEXT if p else "#ff8a80"
        ax.text(bar.get_x() + bar.get_width() / 2,
                bar.get_height() + max(curr_pct) * 0.02,
                f"{val:.1f}%", ha="center", va="bottom",
                fontsize=8.5, color=clr, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels([f"{o}th" if o != 3 else "3rd" for o in orders],
                       color=TEXT, fontsize=9)
    ax.set_xlabel("Harmonic Order", color=TEXT, fontsize=9, labelpad=6)
    ax.set_ylabel("Current (% of I₁)", color=TEXT, fontsize=9, labelpad=6)
    ax.tick_params(colors=TEXT, labelsize=8.5)
    ax.spines[:].set_color(GRID)
    ax.grid(axis="y", color=GRID, linewidth=0.6, zorder=0)
    ax.set_ylim(0, max(max(curr_pct) * 1.25, tdd_limit * 1.4) if curr_pct else 10)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID)

    # Legend
    legend_handles = [
        mpatches.Patch(facecolor=PASS_CLR, label="PASS"),
        mpatches.Patch(facecolor=FAIL_CLR, label="FAIL"),
        plt.Line2D([0], [0], color=LIM_CLR, linewidth=2,
                   label=f"IEEE 519 individual limit"),
        plt.Line2D([0], [0], color=LIM_CLR, linewidth=1.2,
                   linestyle="--", label=f"TDD limit {tdd_limit}%"),
    ]
    ax.legend(handles=legend_handles, loc="upper right",
              fontsize=7.5, framealpha=0.25, labelcolor=TEXT,
              facecolor=PANEL, edgecolor=GRID)

    ax.set_title("Individual Harmonic Spectrum  |  IEEE 519-2022",
                 color=TEXT, fontsize=10, fontweight="bold", pad=10)

    # ── Right: summary panel ─────────────────────────────────────────────────
    ax2 = fig.add_subplot(gs[1])
    ax2.set_facecolor(PANEL)
    ax2.set_xticks([]); ax2.set_yticks([])
    for sp in ax2.spines.values(): sp.set_edgecolor(GRID)

    status_clr  = PASS_CLR if overall_pass else FAIL_CLR
    status_text = "COMPLIANT" if overall_pass else "NON-COMPLIANT"

    summary = [
        ("THD_I",           f"{THD:.2f} %"),
        ("TDD",             f"{TDD:.2f} %"),
        ("TDD Limit",       f"{tdd_limit} %  (ISC/IL={isc_il:.0f})"),
        ("K-Factor",        f"{k_factor:.2f}"),
        ("K Rating needed", f"K-{4 if k_factor <= 4 else 13 if k_factor <= 9 else 20}"),
        ("Fund. Current",   f"{I1:.1f} A"),
        ("Harmonics",       f"{len(harmonics)} measured"),
        ("IEEE 519-2022",   status_text),
    ]

    y_start = 0.88
    row_h   = 0.10

    for label, value in summary:
        is_status = label == "IEEE 519-2022"
        val_clr   = status_clr if is_status else TEXT
        weight    = "bold" if is_status else "normal"

        ax2.text(0.05, y_start, label,
                 transform=ax2.transAxes,
                 color="#8fa8c0", fontsize=8, va="top")
        ax2.text(0.97, y_start, value,
                 transform=ax2.transAxes,
                 color=val_clr, fontsize=8.5, va="top",
                 ha="right", fontweight=weight)

        ax2.plot([0.03, 0.97], [y_start - 0.01, y_start - 0.01],
                 color=GRID, linewidth=0.5,
                 transform=ax2.transAxes)
        y_start -= row_h

    ax2.text(0.5, 0.04, "Standard: IEEE 519-2022",
             transform=ax2.transAxes,
             color="#4a6070", fontsize=7, ha="center")
    ax2.set_title("Summary", color=TEXT, fontsize=10,
                  fontweight="bold", pad=10)

    # ── Main title ────────────────────────────────────────────────────────────
    fig.text(0.5, 0.95,
             f"HARMONIC DISTORTION SPECTRUM  —  {project.upper()}",
             ha="center", va="top", color=TEXT,
             fontsize=11, fontweight="bold")

    # ── Export SVG ───────────────────────────────────────────────────────────
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight",
                facecolor=BG, dpi=120)
    plt.close(fig)
    buf.seek(0)
    return buf.read().decode("utf-8")
