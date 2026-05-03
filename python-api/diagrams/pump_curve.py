"""
Pump Curve Diagram — Phase 10a
Generates a Q-H curve, system curve, and efficiency overlay from Pump Sizing results.
Returns an SVG string suitable for inline HTML rendering.

Standards: Hydraulic Institute (HI) curve format, PSME graphical conventions.
"""

import io
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D


def generate(inputs: dict, results: dict) -> str:
    """
    Returns SVG string of the pump Q-H + system curve diagram.
    Accepts results from Pump Sizing (TDH) calc.
    """
    # ── Extract calc results ──────────────────────────────────────────────────
    # Calc engine (pump_tdh.py) returns: flow_m3hr, TDH, static_head,
    # inputs_used.pump_efficiency, recommended_kw (selected motor size).
    Q_design  = float(results.get("flow_m3hr",    inputs.get("flow_rate", 10) * 60 / 1000))  # m³/hr
    H_design  = float(results.get("TDH",          inputs.get("static_head", 20)))            # m
    H_static  = float(results.get("static_head",  inputs.get("static_head", 10)))            # m
    pump_eff  = float(results.get("inputs_used", {}).get("pump_efficiency",
                                  results.get("pump_efficiency_pct", 70))) / 100
    # Display the SELECTED motor size (matches BOM/SOW), not the raw computed kW
    motor_kw  = float(results.get("recommended_kw", results.get("motor_kw", 0)))

    project   = str(inputs.get("project_name", "Pump System"))

    # ── Pump Q-H curve (synthetic — standard quadratic shape) ────────────────
    # Passes through: shutoff (Q=0, H=1.25*TDH), design (Q_d, H_d), runout (1.4*Q_d, 0.8*H_d)
    Q_max  = Q_design * 1.6
    H_shut = H_design * 1.25   # shutoff head (zero flow)
    H_run  = H_design * 0.75   # runout head

    # Fit quadratic H = a*Q² + b*Q + c through three points
    # (0, H_shut), (Q_design, H_design), (Q_max, H_run)
    A = np.array([
        [0,           0,          1],
        [Q_design**2, Q_design,   1],
        [Q_max**2,    Q_max,      1],
    ])
    b_vec = np.array([H_shut, H_design, H_run])
    try:
        coeffs = np.linalg.solve(A, b_vec)
    except np.linalg.LinAlgError:
        coeffs = np.array([0, 0, H_design])

    Q_arr = np.linspace(0, Q_max, 200)
    H_pump = np.polyval(coeffs, Q_arr)
    H_pump = np.clip(H_pump, 0, H_shut * 1.1)

    # ── System curve H_sys = H_static + k*Q² ─────────────────────────────────
    # k calibrated so system curve passes through design point
    k = (H_design - H_static) / (Q_design**2) if Q_design > 0 else 0
    H_sys = H_static + k * Q_arr**2

    # ── Efficiency curve (parabolic, peak at design point) ────────────────────
    eta_max = pump_eff
    eta_arr = eta_max * (1 - ((Q_arr - Q_design) / (Q_design * 0.8))**2)
    eta_arr = np.clip(eta_arr, 0, eta_max)

    # ── Figure ────────────────────────────────────────────────────────────────
    fig, ax1 = plt.subplots(figsize=(9, 5.5))
    fig.patch.set_facecolor("#f8f9fa")
    ax1.set_facecolor("#ffffff")

    # Pump curve
    ax1.plot(Q_arr, H_pump, color="#1565C0", linewidth=2.5, label="Pump H-Q curve")
    # System curve
    ax1.plot(Q_arr, H_sys,  color="#B71C1C", linewidth=2.0,
             linestyle="--", label="System curve")

    # Design operating point
    ax1.scatter([Q_design], [H_design], color="#2E7D32", s=120, zorder=5,
                label=f"Operating point ({Q_design:.2f} m³/hr, {H_design:.2f} m)")
    ax1.annotate(
        f"  BEP\n  Q={Q_design:.2f} m³/hr\n  H={H_design:.2f} m\n  η={pump_eff*100:.0f}%",
        xy=(Q_design, H_design), xytext=(Q_design * 1.05, H_design * 0.88),
        fontsize=8, color="#2E7D32",
        arrowprops=dict(arrowstyle="->", color="#2E7D32", lw=1.2),
    )

    # Static head line
    ax1.axhline(H_static, color="#795548", linewidth=1.0, linestyle=":",
                alpha=0.7, label=f"Static head = {H_static:.2f} m")

    ax1.set_xlabel("Flow rate Q (m³/hr)", fontsize=10)
    ax1.set_ylabel("Total Head H (m)", fontsize=10, color="#1565C0")
    ax1.tick_params(axis="y", labelcolor="#1565C0")
    ax1.set_xlim(0, Q_max * 1.05)
    ax1.set_ylim(0, H_shut * 1.15)
    ax1.grid(True, alpha=0.3, linestyle="--")

    # ── Efficiency overlay (secondary y-axis) ─────────────────────────────────
    ax2 = ax1.twinx()
    ax2.plot(Q_arr, eta_arr * 100, color="#F57C00", linewidth=1.8,
             linestyle="-.", alpha=0.85, label="Efficiency η (%)")
    ax2.set_ylabel("Pump Efficiency η (%)", fontsize=10, color="#F57C00")
    ax2.tick_params(axis="y", labelcolor="#F57C00")
    ax2.set_ylim(0, 105)

    # ── Legend ────────────────────────────────────────────────────────────────
    handles1, labels1 = ax1.get_legend_handles_labels()
    handles2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(handles1 + handles2, labels1 + labels2,
               loc="upper right", fontsize=8, framealpha=0.9)

    # ── Title block ───────────────────────────────────────────────────────────
    fig.suptitle(f"Pump Performance Curve — {project}", fontsize=11,
                 fontweight="bold", y=0.98)
    subtitle = (f"Design: Q={Q_design:.2f} m³/hr | TDH={H_design:.2f} m | "
                f"η={pump_eff*100:.0f}% | Motor={motor_kw:.2f} kW")
    ax1.set_title(subtitle, fontsize=8.5, color="#555555", pad=4)

    fig.text(0.01, 0.01, "Standard: Hydraulic Institute (HI) | PSME Code",
             fontsize=7, color="#aaaaaa")

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])

    # ── Export SVG ────────────────────────────────────────────────────────────
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", dpi=150)
    plt.close(fig)
    return buf.getvalue()
