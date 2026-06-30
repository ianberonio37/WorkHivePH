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


def _parse_dim_to_mm(dim: str) -> float:
    """Extract mm from segment dim like 'Ø500 mm' or '600 x 300 mm'.
    For rectangular, returns the equivalent circular diameter (geometric mean).
    """
    if not dim:
        return 0.0
    s = str(dim).replace("Ø", "").replace("mm", "").strip()
    if "x" in s.lower() or "×" in s:
        sep = "x" if "x" in s.lower() else "×"
        parts = [p.strip() for p in s.lower().split(sep)]
        try:
            a, b = float(parts[0]), float(parts[1])
            # Equivalent circular diameter for rectangular: De = 1.30 (a*b)^0.625 / (a+b)^0.25
            return 1.30 * (a * b) ** 0.625 / (a + b) ** 0.25
        except Exception:
            return 0.0
    try:
        return float(s.split()[0])
    except Exception:
        return 0.0


def generate(inputs: dict, results: dict) -> str:
    """Returns SVG string of the ASHRAE equal-friction duct sizing chart."""

    project    = str(inputs.get("project_name", "Duct System"))
    fr_design  = float(inputs.get("friction_rate", inputs.get("friction_rate_pam", 1.0)))

    # Multi-segment data from the calc engine. The duct calc returns results.sections[]
    # where each section carries flow_m3hr + a `circular` block {D_std_mm, velocity_ms}
    # (it sizes both circular & rectangular; the equal-friction chart plots the circular Ø).
    # (Legacy `segments[]` / flow_lps / dim / vel_check shape kept as a fallback so any
    #  older caller still renders.) Reading the wrong key here silently fell back to a
    #  hardcoded 300mm/5.0 default — the diagram showed a fake size, not the calc's.
    segments = results.get("sections") or results.get("segments") or []
    seg_points = []
    for seg in segments:
        try:
            Q_m3hr = float(seg.get("flow_m3hr", float(seg.get("flow_lps", 0)) * 3.6))
            circ   = seg.get("circular") if isinstance(seg.get("circular"), dict) else {}
            d_mm   = float(circ.get("D_std_mm",
                            circ.get("diameter_mm", _parse_dim_to_mm(seg.get("dim", "")))))
            v_ms   = float(circ.get("velocity_ms", seg.get("velocity_ms", 0)))
            name   = str(seg.get("label", seg.get("name", "")))
            check  = "OK" if seg.get("velocity_ok", True) else str(seg.get("velocity_note", "HIGH"))
            if Q_m3hr > 0 and d_mm > 0:
                seg_points.append({
                    "Q_m3hr": Q_m3hr, "d_mm": d_mm, "v_ms": v_ms,
                    "name": name, "check": check,
                })
        except Exception:
            continue

    # Fallback to single-point legacy mode if no segments
    if not seg_points:
        Q_design = float(inputs.get("flow_m3hr", 0) or
                         inputs.get("flow_cfm", 0) * 1.699 or 1000)
        d_sel_mm = float(results.get("diameter_mm",
                          results.get("circular", {}).get("diameter_mm", 300)))
        v_design = float(results.get("velocity_ms",
                          results.get("circular", {}).get("velocity_ms", 5.0)))
        seg_points = [{
            "Q_m3hr": Q_design, "d_mm": d_sel_mm, "v_ms": v_design,
            "name": "Design", "check": "OK",
        }]

    # Worst segment for chart annotation focus + iso-line emphasis
    worst = max(seg_points, key=lambda p: (p["check"] != "OK", p["v_ms"]))
    Q_design = worst["Q_m3hr"]
    d_sel_mm = worst["d_mm"]
    v_design = worst["v_ms"]

    # ── Chart axes ────────────────────────────────────────────────────────────
    fr_range = np.logspace(-1, 1, 300)   # 0.1 to 10 Pa/m
    Q_range  = np.logspace(1, 6, 300)    # 10 to 1,000,000 m³/hr (log scale)

    fig, ax = plt.subplots(figsize=(10, 6.5))
    fig.patch.set_facecolor("#f8f9fa")
    ax.set_facecolor("#ffffff")

    # ── Constant-diameter iso-lines ───────────────────────────────────────────
    labeled_diameters = {100, 150, 200, 300, 400, 500, 630, 800, 1000}
    seg_diameters     = {round(p["d_mm"]) for p in seg_points}
    for d_mm in STD_DIAMETERS_MM:
        Q_line = [_flow_for_d_fr(d_mm, fr) for fr in fr_range]
        is_in_use = any(abs(d_mm - sd) < 26 for sd in seg_diameters)  # within +/-25mm
        color  = "#1565C0" if is_in_use else "#90CAF9"
        lw     = 1.8       if is_in_use else 0.8
        zorder = 5         if is_in_use else 2
        ax.plot(Q_line, fr_range, color=color, linewidth=lw,
                alpha=1.0 if is_in_use else 0.5, zorder=zorder)
        if d_mm in labeled_diameters or is_in_use:
            Q_lbl = _flow_for_d_fr(d_mm, 0.5)
            if 10 < Q_lbl < 1e6:
                ax.text(Q_lbl * 1.05, 0.5,
                        f"O{d_mm}",
                        fontsize=6.5, color=color, va="center",
                        fontweight="bold" if is_in_use else "normal")

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

    # ── Per-segment design points (color-coded by velocity check) ─────────────
    color_map = {"OK": "#2E7D32", "WARNING": "#F57C00", "HIGH": "#B71C1C"}
    for i, p in enumerate(seg_points):
        clr = color_map.get(p["check"], "#B71C1C")
        is_worst = (p is worst)
        ax.scatter([p["Q_m3hr"]], [fr_design],
                   color=clr, s=180 if is_worst else 110,
                   zorder=11 if is_worst else 9,
                   marker="*" if is_worst else "o",
                   edgecolors="white", linewidths=0.8)
        # Stagger label offsets so multi-segment annotations don't overlap
        offset_x = 1.6 + (i % 3) * 0.4
        offset_y = 1.5 + ((i // 3) % 3) * 0.6
        label_txt = (f"  {p['name']}\n  Q={p['Q_m3hr']:.0f} m3/hr\n"
                     f"  O{p['d_mm']:.0f}mm  v={p['v_ms']:.1f} m/s")
        if p["check"] != "OK":
            label_txt += f"\n  [{p['check']}]"
        ax.annotate(
            label_txt,
            xy=(p["Q_m3hr"], fr_design),
            xytext=(p["Q_m3hr"] * offset_x, fr_design * offset_y),
            fontsize=7.5, color=clr,
            fontweight="bold" if is_worst else "normal",
            arrowprops=dict(arrowstyle="->", color=clr,
                            lw=1.4 if is_worst else 0.9),
            bbox=dict(boxstyle="round,pad=0.25", fc="white",
                      alpha=0.92, ec=clr, lw=0.8),
        )

    # Worst-case labelled handle for the legend (used below)
    ax.scatter([], [], color="#B71C1C", s=150, marker="*",
               label=f"Worst: {worst['name']} O{worst['d_mm']:.0f}mm v={worst['v_ms']:.1f} m/s")

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
    legend_extras = [
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color_map["OK"],
                   markersize=8, label='OK velocity'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color_map["WARNING"],
                   markersize=8, label='WARNING'),
        plt.Line2D([0], [0], marker='o', color='w', markerfacecolor=color_map["HIGH"],
                   markersize=8, label='HIGH velocity'),
    ]
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles=handles + legend_extras,
              loc="lower right", fontsize=7.5, framealpha=0.9, ncol=2)

    # ── Title block ───────────────────────────────────────────────────────────
    n_seg = len(seg_points)
    fig.suptitle(f"ASHRAE Equal Friction Duct Sizing Chart - {project}",
                 fontsize=11, fontweight="bold", y=0.99)
    ax.set_title(
        f"{n_seg} segment(s) plotted | Worst: {worst['name']} O{worst['d_mm']:.0f}mm "
        f"@ {worst['v_ms']:.1f} m/s ({worst['check']}) | fr={fr_design:.2f} Pa/m",
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
