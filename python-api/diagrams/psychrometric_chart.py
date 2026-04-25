"""
Psychrometric Chart Diagram — Phase 10a
Plots the AHU process line on a Manila-climate psychrometric chart.
State points: Outdoor → Mixed Air → Off-Coil (ADP) → Supply → Room

Standards: ASHRAE 2021 Fundamentals Ch.1 (Psychrometrics),
           ASHRAE 62.1 (Ventilation), PSME Code
"""

import io
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import psychrolib

psychrolib.SetUnitSystem(psychrolib.SI)

PATM = 101325.0   # Pa (sea level — Manila)


def _rh_curve(T_range: np.ndarray, rh: float) -> np.ndarray:
    """Humidity ratio (kg/kg) for a constant-RH line across temperature range."""
    W = []
    for T in T_range:
        try:
            W.append(psychrolib.GetHumRatioFromRelHum(T, rh, PATM))
        except Exception:
            W.append(np.nan)
    return np.array(W)


def _state_point(T_C: float, rh: float) -> tuple:
    """Returns (T, W) for a state point."""
    try:
        W = psychrolib.GetHumRatioFromRelHum(T_C, rh, PATM)
    except Exception:
        W = 0.01
    return T_C, W


def generate(inputs: dict, results: dict) -> str:
    """Returns SVG string of psychrometric chart with AHU process line."""

    project = str(inputs.get("project_name", "AHU System"))

    # ── State points from AHU results ─────────────────────────────────────────
    # Outdoor air
    T_oa  = float(inputs.get("outdoor_temp_C",   35.0))
    rh_oa = float(inputs.get("outdoor_rh_pct",   70.0)) / 100

    # Room / return air
    T_room  = float(inputs.get("room_temp_C",    24.0))
    rh_room = float(inputs.get("room_rh_pct",    55.0)) / 100

    # Mixed air (from results or estimate)
    T_mix  = float(results.get("mixed_air_temp_C",
                    T_oa * 0.2 + T_room * 0.8))
    rh_mix = float(results.get("mixed_air_rh",
                    rh_oa * 0.2 + rh_room * 0.8))

    # Off-coil / ADP
    T_oc  = float(results.get("off_coil_temp_C",
                   inputs.get("supply_air_temp_C", 13.0)))
    rh_oc = float(results.get("off_coil_rh",       0.95))

    # Supply air (after fan heat)
    T_sup  = float(results.get("supply_temp_C",   T_oc + 1.0))
    rh_sup = float(results.get("supply_rh",        rh_oc * 0.92))

    # ── Chart range (tropical — 10 to 42°C) ──────────────────────────────────
    T_range = np.linspace(10, 42, 200)
    W_max   = 0.030   # 30 g/kg — covers Philippines humid conditions

    fig, ax = plt.subplots(figsize=(10, 6.5))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#f0f4f8")

    # ── Constant RH lines ────────────────────────────────────────────────────
    for rh_val in [0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00]:
        W_line = _rh_curve(T_range, rh_val)
        mask   = W_line <= W_max * 1.02
        color  = "#1565C0" if rh_val == 1.0 else "#90CAF9"
        lw     = 1.5 if rh_val == 1.0 else 0.7
        ax.plot(T_range[mask], W_line[mask] * 1000, color=color,
                linewidth=lw, alpha=0.8)
        # Label at T=38°C
        T_label = 38
        try:
            W_label = psychrolib.GetHumRatioFromRelHum(T_label, rh_val, PATM) * 1000
            if W_label <= W_max * 1000:
                ax.text(T_label + 0.3, W_label, f"{int(rh_val*100)}%",
                        fontsize=6.5, color="#1565C0", va="center")
        except Exception:
            pass

    # ── State points ─────────────────────────────────────────────────────────
    states = [
        (_state_point(T_oa,   rh_oa),   "OA",    "#B71C1C", "Outdoor Air"),
        (_state_point(T_room, rh_room), "RA",    "#1B5E20", "Return Air"),
        (_state_point(T_mix,  rh_mix),  "MA",    "#E65100", "Mixed Air"),
        (_state_point(T_oc,   rh_oc),   "CC",    "#0D47A1", "Coil Off-Coil"),
        (_state_point(T_sup,  rh_sup),  "SA",    "#4A148C", "Supply Air"),
    ]

    # Process lines
    pts = [(T, W * 1000) for (T, W), _, _, _ in states]
    line_segs = [
        (0, 2, "--"),   # OA → MA (mixing)
        (1, 2, "--"),   # RA → MA (mixing)
        (2, 3, "-"),    # MA → CC (cooling coil)
        (3, 4, "-"),    # CC → SA (fan heat)
        (4, 1, ":"),    # SA → RA (room process)
    ]
    seg_colors = ["#E65100", "#E65100", "#0D47A1", "#4A148C", "#1B5E20"]
    seg_labels = ["Mixing", "", "Cooling coil", "Fan heat", "Room process"]

    for (i, j, ls), col, lbl in zip(line_segs, seg_colors, seg_labels):
        x_vals = [pts[i][0], pts[j][0]]
        y_vals = [pts[i][1], pts[j][1]]
        ax.plot(x_vals, y_vals, color=col, linewidth=2.0,
                linestyle=ls, alpha=0.85, zorder=3,
                label=lbl if lbl else None)

    # Plot state points
    for (T, W), label, color, desc in states:
        W_g = W * 1000
        ax.scatter([T], [W_g], color=color, s=80, zorder=5)
        ax.annotate(
            f"{label}\n{T:.1f}°C\n{W_g:.1f} g/kg",
            xy=(T, W_g), xytext=(T + 0.8, W_g + 0.5),
            fontsize=7.5, color=color, fontweight="bold",
            arrowprops=dict(arrowstyle="-", color=color, lw=0.8),
            bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.8, ec=color, lw=0.8),
        )

    # ── Axes ─────────────────────────────────────────────────────────────────
    ax.set_xlabel("Dry-Bulb Temperature (°C)", fontsize=10)
    ax.set_ylabel("Humidity Ratio W (g water / kg dry air)", fontsize=10)
    ax.set_xlim(10, 42)
    ax.set_ylim(0, W_max * 1000)
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.xaxis.set_major_locator(plt.MultipleLocator(5))
    ax.yaxis.set_major_locator(plt.MultipleLocator(5))

    # ── Legend ────────────────────────────────────────────────────────────────
    handles, labels = ax.get_legend_handles_labels()
    filtered = [(h, l) for h, l in zip(handles, labels) if l]
    if filtered:
        ax.legend(*zip(*filtered), loc="upper left", fontsize=8, framealpha=0.9)

    # ── Title block ───────────────────────────────────────────────────────────
    fig.suptitle(f"Psychrometric Chart — AHU Process Line — {project}",
                 fontsize=11, fontweight="bold", y=0.99)
    ax.set_title(
        f"OA: {T_oa}°C / {int(rh_oa*100)}%RH   |   "
        f"Room: {T_room}°C / {int(rh_room*100)}%RH   |   "
        f"Supply: {T_sup:.1f}°C   |   "
        f"Coil off-coil: {T_oc:.1f}°C",
        fontsize=8.5, color="#555555", pad=4,
    )
    fig.text(0.01, 0.005,
             "Standard: ASHRAE 2021 Fundamentals Ch.1 | ASHRAE 62.1 | PSME Code | "
             "Sea-level (101.325 kPa)",
             fontsize=7, color="#aaaaaa")

    plt.tight_layout(rect=[0, 0.02, 1, 0.97])

    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", dpi=150)
    plt.close(fig)
    return buf.getvalue()
