"""
Duct Sizing Chart — Phase 10a
Plots the ASHRAE Equal Friction chart: friction rate vs flow,
with standard duct sizes as iso-lines, design point highlighted,
and velocity limit zones shaded.

Standards: ASHRAE 2021 Fundamentals Ch.21 (Duct Design),
           SMACNA HVAC Duct Construction Standards, PSME Code
"""

import io
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


# ── ASHRAE equal-friction constant K (tropical, ρ=1.15 kg/m³) ────────────────
K_TROPICAL = 0.01740   # from duct_sizing.py

# Standard circular duct diameters (mm)
STD_DIAMETERS_MM = [100, 125, 150, 160, 200, 250, 300, 315, 355,
                    400, 450, 500, 560, 630, 710, 800, 900, 1000]

def _flow_for_d_fr(d_mm: float, fr_pam: float) -> float:
    """Flow (m³/hr) for a given diameter and friction rate (Pa/m)."""
    # fr = K * Q^1.75 / D^4.75  →  Q = (fr * D^4.75 / K)^(1/1.75)
    Q_m3s = (fr_pam * (d_mm**4.75) / K_TROPICAL) ** (1 / 1.75)
    return Q_m3s * 3600

def _velocity(Q_m3hr: float, d_mm: float) -> float:
    A = math.pi * (d_mm / 2000)**2
    return (Q_m3hr / 3600) / A if A > 0 else 0


def generate(inputs: dict, results: dict) -> str:
    """Returns SVG string of the ASHRAE equal-friction duct sizing chart."""

    project    = str(inputs.get("project_name", "Duct System"))
    Q_design   = float(inputs.get("flow_m3hr", 0) or
                        inputs.get("flow_cfm", 0) * 1.699 or 1000)
    fr_design  = float(inputs.get("friction_rate_pam", 1.0))

    # From results
    d_sel_mm   = float(results.get("diameter_mm",
                        results.get("circular", {}).get("diameter_mm", 300)))
    v_design   = float(results.get("velocity_ms",
                        results.get("circular", {}).get("velocity_ms", 5.0)))

    # ── Chart axes ────────────────────────────────────────────────────────────
    fr_range = np.logspace(-1, 1, 300)   # 0.1 to 10 Pa/m
    Q_range  = np.logspace(1, 6, 300)    # 10 to 1,000,000 m³/hr (log scale)

    fig, ax = plt.subplots(figsize=(10, 6.5))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#ffffff")

    # ── Constant-diameter iso-lines ───────────────────────────────────────────
    labeled_diameters = {100, 150, 200, 300, 400, 500, 630, 800, 1000}
    for d_mm in STD_DIAMETERS_MM:
        Q_line = [_flow_for_d_fr(d_mm, fr) for fr in fr_range]
        is_selected = abs(d_mm - d_sel_mm) < 1
        color  = "#1565C0" if is_selected else "#90CAF9"
        lw     = 2.5       if is_selected else 0.8
        zorder = 5         if is_selected else 2
        ax.plot(Q_line, fr_range, color=color, linewidth=lw,
                alpha=1.0 if is_selected else 0.6, zorder=zorder)
        if d_mm in labeled_diameters or is_selected:
            # Label at fr=0.5 Pa/m
            Q_lbl = _flow_for_d_fr(d_mm, 0.5)
            if 10 < Q_lbl < 1e6:
                ax.text(Q_lbl * 1.05, 0.5,
                        f"Ø{d_mm}",
                        fontsize=6.5, color=color, va="center",
                        fontweight="bold" if is_selected else "normal")

    # ── Velocity limit zones ──────────────────────────────────────────────────
    # Shade regions where velocity > SMACNA limits
    # For each fr, find Q where v = limit, then shade above
    v_limits = [(4.0, "#FFF9C4", "v < 4 m/s\n(low vel.)"),
                (8.0, "#FFE0B2", "4–8 m/s\n(SMACNA OK)"),
                (12.0,"#FFCCBC","8–12 m/s\n(high vel.)")]

    # Instead, shade recommended velocity band (4–8 m/s) for selected duct
    if d_sel_mm > 0:
        v_lo, v_hi = 4.0, 8.0
        # Q at v_lo and v_hi for selected diameter
        A_sel = math.pi * (d_sel_mm / 2000)**2
        Q_lo  = v_lo * A_sel * 3600
        Q_hi  = v_hi * A_sel * 3600
        ax.axvline(Q_lo, color="#2E7D32", linewidth=1.0, linestyle=":",
                   alpha=0.7, label=f"v_min = {v_lo} m/s")
        ax.axvline(Q_hi, color="#B71C1C", linewidth=1.0, linestyle=":",
                   alpha=0.7, label=f"v_max = {v_hi} m/s")
        ax.axvspan(Q_lo, Q_hi, alpha=0.07, color="#4CAF50",
                   label="Recommended velocity range")

    # ── Design point ──────────────────────────────────────────────────────────
    ax.scatter([Q_design], [fr_design], color="#B71C1C", s=150,
               zorder=10, marker="*",
               label=f"Design: Q={Q_design:.0f} m³/hr, fr={fr_design:.2f} Pa/m")
    ax.annotate(
        f"  Q={Q_design:.0f} m³/hr\n  fr={fr_design:.2f} Pa/m\n"
        f"  Ø{d_sel_mm:.0f}mm\n  v={v_design:.1f} m/s",
        xy=(Q_design, fr_design),
        xytext=(Q_design * 2, fr_design * 2.0),
        fontsize=8, color="#B71C1C", fontweight="bold",
        arrowprops=dict(arrowstyle="->", color="#B71C1C", lw=1.5),
        bbox=dict(boxstyle="round,pad=0.3", fc="white", alpha=0.9,
                  ec="#B71C1C", lw=1.0),
    )

    # Recommended friction rate band (0.8–1.5 Pa/m — ASHRAE)
    ax.axhspan(0.8, 1.5, alpha=0.07, color="#1565C0",
               label="ASHRAE recommended fr (0.8–1.5 Pa/m)")
    ax.axhline(0.8, color="#1565C0", linewidth=0.8, linestyle="--", alpha=0.5)
    ax.axhline(1.5, color="#1565C0", linewidth=0.8, linestyle="--", alpha=0.5)

    # ── Axes ─────────────────────────────────────────────────────────────────
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("Volume Flow Rate Q (m³/hr)", fontsize=10)
    ax.set_ylabel("Friction Rate fr (Pa/m)", fontsize=10)
    ax.set_xlim(50, 200000)
    ax.set_ylim(0.1, 10)
    ax.grid(True, which="both", alpha=0.2, linestyle="--")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(
        lambda x, _: f"{x:,.0f}" if x >= 1000 else f"{x:.0f}"))

    # ── Legend ────────────────────────────────────────────────────────────────
    patch_sel = mpatches.Patch(color="#1565C0", label=f"Selected: Ø{d_sel_mm:.0f}mm")
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=[patch_sel] + handles, labels=[f"Selected: Ø{d_sel_mm:.0f}mm"] + labels,
              loc="lower right", fontsize=7.5, framealpha=0.9, ncol=2)

    # ── Title block ───────────────────────────────────────────────────────────
    fig.suptitle(f"ASHRAE Equal Friction Duct Sizing Chart — {project}",
                 fontsize=11, fontweight="bold", y=0.99)
    ax.set_title(
        f"Selected duct: Ø{d_sel_mm:.0f}mm | Q={Q_design:.0f} m³/hr | "
        f"fr={fr_design:.2f} Pa/m | v={v_design:.1f} m/s",
        fontsize=8.5, color="#555555", pad=4,
    )
    fig.text(0.01, 0.005,
             "Standard: ASHRAE 2021 Fundamentals Ch.21 | SMACNA HVAC Duct Construction | PSME Code",
             fontsize=7, color="#aaaaaa")

    plt.tight_layout(rect=[0, 0.02, 1, 0.97])

    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", dpi=150)
    plt.close(fig)
    return buf.getvalue()
