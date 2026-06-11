"""
Brand-styled article figures for /learn/ pages: deterministic matplotlib -> SVG.

WAT split: the author (or the article generator's skeleton call) decides WHAT a
figure should say; this tool draws it the same way every time. Figures sit next
to the article (learn/<slug>/fig-N.svg) and are embedded with
<figure class="article-fig"> blocks by the scaffold.

Grounding rule (Content Grounding Gate): a figure is content like any prose
sentence. Platform-flow figures may only show steps that are REAL page
affordances; stat figures must carry a citation in `source`. render_figure()
refuses a stat spec without a source.

Primitives:
  step_flow(steps, out, title, source)    vertical numbered flow (platform flows)
  scan_path(stops, out, title, source)    document mock with numbered fixation dots
  bar_chart(labels, values, out, ...)     horizontal labeled bars (real numbers only)
  render_figure(spec, out)                dispatch from a JSON spec dict

Usage:
    python tools/article_viz.py --self-test     # synthetic teeth, no live inputs
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle

ROOT = Path(__file__).resolve().parent.parent

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# WorkHive brand (matches the article template's tailwind config)
ORANGE = "#F7A21B"
ORANGE_LIGHT = "#FDB94A"
BLUE = "#29B6D9"
BLUE_LIGHT = "#5FCCE8"
NAVY = "#162032"
CARD = "#1F2E45"
TEXT = "#F4F6FA"

_FONT_NAMES = {f.name for f in font_manager.fontManager.ttflist}
FONT = "Poppins" if "Poppins" in _FONT_NAMES else "DejaVu Sans"

_RC = {
    "font.family": FONT,
    "text.color": TEXT,
    "svg.fonttype": "path",   # text as paths: no client font dependency
    "figure.facecolor": "none",
    "axes.facecolor": "none",
    "savefig.facecolor": "none",
    "savefig.edgecolor": "none",
}


def _new_fig(width_in: float, height_in: float):
    fig, ax = plt.subplots(figsize=(width_in, height_in))
    ax.set_axis_off()
    return fig, ax


def _save(fig, out_path: Path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, format="svg", transparent=True, bbox_inches="tight",
                pad_inches=0.12)
    plt.close(fig)
    return out_path


def _title_and_source(ax, title: str | None, source: str | None, y_top: float, y_bot: float):
    if title:
        ax.text(0.0, y_top, title, fontsize=15, fontweight="bold",
                color=TEXT, ha="left", va="bottom")
    if source:
        ax.text(0.0, y_bot, f"Source: {source}", fontsize=8.5,
                color=TEXT, alpha=0.55, ha="left", va="top")


# ── Primitive 1: vertical numbered step flow ─────────────────────────────────

def step_flow(steps: list[str], out_path, title: str | None = None,
              source: str | None = None) -> Path:
    """Vertical flow of numbered steps. Reads well at phone width (the figure is
    intrinsically ~6.5in wide so the article column shows it near 1:1)."""
    if not steps or len(steps) < 2:
        raise ValueError("step_flow needs at least 2 steps")
    n = len(steps)
    row_h = 0.78
    with plt.rc_context(_RC):
        fig, ax = _new_fig(6.5, 0.62 + n * row_h + (0.34 if title else 0))
        ax.set_xlim(0, 10)
        top = n * row_h + 0.30
        ax.set_ylim(-0.42, top + (0.55 if title else 0.10))

        _title_and_source(ax, title, source, top + 0.12, -0.30)

        for i, label in enumerate(steps):
            y = top - 0.25 - i * row_h
            # connector arrow to the next step
            if i < n - 1:
                ax.add_patch(FancyArrowPatch(
                    (0.62, y - 0.27), (0.62, y - row_h + 0.30),
                    arrowstyle="-|>", mutation_scale=13,
                    color=BLUE, linewidth=1.6, alpha=0.85))
            # numbered badge
            ax.add_patch(Circle((0.62, y), 0.215, facecolor=ORANGE,
                                edgecolor="none", zorder=3))
            ax.text(0.62, y, str(i + 1), fontsize=11.5, fontweight="bold",
                    color=NAVY, ha="center", va="center", zorder=4)
            # step card
            ax.add_patch(FancyBboxPatch(
                (1.25, y - 0.295), 8.55, 0.59,
                boxstyle="round,pad=0.02,rounding_size=0.10",
                facecolor=CARD, edgecolor=BLUE, linewidth=1.0, alpha=0.92))
            ax.text(1.55, y, textwrap.fill(label, 58), fontsize=10.5,
                    color=TEXT, ha="left", va="center", zorder=4)
        return _save(fig, out_path)


# ── Primitive 2: document scan path (numbered fixation dots on a page mock) ──

def scan_path(stops: list[str], out_path, title: str | None = None,
              source: str | None = None) -> Path:
    """A stylized document with numbered fixation points down the page and the
    label for each stop on the right. For eye-tracking / reading-order stories."""
    if not stops or len(stops) < 2:
        raise ValueError("scan_path needs at least 2 stops")
    n = len(stops)
    with plt.rc_context(_RC):
        fig, ax = _new_fig(6.5, 1.1 + n * 0.74 + (0.34 if title else 0))
        ax.set_xlim(0, 10)
        top = n * 0.74 + 0.75
        ax.set_ylim(-0.42, top + (0.55 if title else 0.10))

        _title_and_source(ax, title, source, top + 0.12, -0.30)

        # the document
        doc_h = top - 0.10
        ax.add_patch(FancyBboxPatch(
            (0.30, 0.05), 3.1, doc_h,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            facecolor=CARD, edgecolor=BLUE, linewidth=1.2, alpha=0.92))
        # faux text lines on the document
        import numpy as _np
        rng = _np.linspace(0.42, doc_h - 0.32, max(8, n * 2 + 3))
        for k, ly in enumerate(rng):
            w = 2.45 if k % 3 else 1.6
            ax.plot([0.62, 0.62 + w], [ly, ly], color=TEXT, alpha=0.16,
                    linewidth=2.6, solid_capstyle="round")

        for i, label in enumerate(stops):
            y = top - 0.55 - i * 0.74
            ax.add_patch(Circle((2.10, y), 0.205, facecolor=ORANGE,
                                edgecolor=NAVY, linewidth=1.0, zorder=4))
            ax.text(2.10, y, str(i + 1), fontsize=10.5, fontweight="bold",
                    color=NAVY, ha="center", va="center", zorder=5)
            if i < n - 1:
                ax.add_patch(FancyArrowPatch(
                    (2.10, y - 0.235), (2.10, y - 0.74 + 0.24),
                    arrowstyle="-|>", mutation_scale=11,
                    color=ORANGE_LIGHT, linewidth=1.4, alpha=0.9, zorder=3))
            ax.plot([2.34, 3.75], [y, y], color=BLUE, alpha=0.55,
                    linewidth=1.0, linestyle=(0, (3, 2)))
            ax.text(3.9, y, textwrap.fill(label, 44), fontsize=10.5,
                    color=TEXT, ha="left", va="center")
        return _save(fig, out_path)


# ── Primitive 3: horizontal bar chart (real, cited numbers only) ─────────────

def bar_chart(labels: list[str], values: list[float], out_path,
              title: str | None = None, unit: str = "",
              source: str | None = None) -> Path:
    if not labels or len(labels) != len(values):
        raise ValueError("bar_chart needs equal-length labels and values")
    n = len(labels)
    with plt.rc_context(_RC):
        fig, ax = plt.subplots(figsize=(6.5, 0.9 + n * 0.62 + (0.3 if title else 0)))
        ypos = list(range(n))[::-1]
        colors = [ORANGE if i == 0 else BLUE for i in range(n)]
        ax.barh(ypos, values, height=0.52, color=colors, alpha=0.92)
        vmax = max(values) or 1
        for y, v in zip(ypos, values):
            ax.text(v + vmax * 0.02, y, f"{v:g}{unit}", fontsize=10.5,
                    fontweight="bold", color=TEXT, va="center")
        ax.set_yticks(ypos)
        ax.set_yticklabels([textwrap.fill(l, 26) for l in labels],
                           fontsize=10, color=TEXT)
        ax.set_xlim(0, vmax * 1.18)
        ax.tick_params(left=False, bottom=False, labelbottom=False)
        for spine in ax.spines.values():
            spine.set_visible(False)
        if title:
            ax.set_title(title, fontsize=15, fontweight="bold", color=TEXT,
                         loc="left", pad=14)
        if source:
            ax.text(0, -0.72, f"Source: {source}", fontsize=8.5, color=TEXT,
                    alpha=0.55, transform=ax.get_yaxis_transform())
        return _save(fig, out_path)


# ── Dispatcher (generator integration) ───────────────────────────────────────

KINDS = {"step_flow", "scan_path", "bar"}


def render_figure(spec: dict, out_path) -> Path:
    """Render one figure from a JSON spec. Stat figures (bar, scan_path) must
    carry a `source` citation; flow figures should list only real affordances
    (enforced upstream by the capability-grounding check on the figure text)."""
    kind = spec.get("kind")
    if kind not in KINDS:
        raise ValueError(f"unknown figure kind '{kind}' (have {sorted(KINDS)})")
    if kind in ("bar", "scan_path") and not spec.get("source"):
        raise ValueError(f"{kind} figure requires a `source` citation")
    if kind == "step_flow":
        return step_flow(spec["steps"], out_path, spec.get("title"), spec.get("source"))
    if kind == "scan_path":
        return scan_path(spec["stops"], out_path, spec.get("title"), spec.get("source"))
    return bar_chart(spec["labels"], spec["values"], out_path,
                     spec.get("title"), spec.get("unit", ""), spec.get("source"))


def figure_text(spec: dict) -> str:
    """All human-readable text a figure will show: feed this to the
    capability-grounding check the same way article prose is checked."""
    parts = [spec.get("title") or "", spec.get("source") or ""]
    parts += spec.get("steps", []) + spec.get("stops", []) + spec.get("labels", [])
    return ". ".join(p for p in parts if p)


# ── Self-test (synthetic only, per gate doctrine) ────────────────────────────

def self_test() -> int:
    tmp = ROOT / ".tmp" / "article_viz_selftest"
    failures = []

    def check(ok: bool, label: str):
        print(("  PASS  " if ok else "  FAIL  ") + label)
        if not ok:
            failures.append(label)

    # 1. each primitive renders a non-trivial SVG
    p1 = render_figure({"kind": "step_flow", "title": "T", "steps": ["Alpha step", "Beta step", "Gamma step"]}, tmp / "f1.svg")
    p2 = render_figure({"kind": "scan_path", "title": "T", "source": "Synthetic study (2099)", "stops": ["First stop", "Second stop", "Third stop"]}, tmp / "f2.svg")
    p3 = render_figure({"kind": "bar", "title": "T", "source": "Synthetic study (2099)", "labels": ["A", "B"], "values": [6.0, 7.4], "unit": "s"}, tmp / "f3.svg")
    for p in (p1, p2, p3):
        check(p.exists() and p.stat().st_size > 2000, f"{p.name} rendered ({p.stat().st_size if p.exists() else 0} bytes)")
        body = p.read_text(encoding="utf-8", errors="replace")
        check("<svg" in body and ORANGE.lower() in body.lower(), f"{p.name} is SVG and carries brand orange")

    # 2. teeth: ungrounded stat figure (no source) must be refused
    try:
        render_figure({"kind": "bar", "labels": ["A"], "values": [1]}, tmp / "bad.svg")
        check(False, "bar without source refused")
    except ValueError:
        check(True, "bar without source refused")

    # 3. teeth: unknown kind refused
    try:
        render_figure({"kind": "pie"}, tmp / "bad2.svg")
        check(False, "unknown kind refused")
    except ValueError:
        check(True, "unknown kind refused")

    # 4. figure_text surfaces every label (grounding hook contract)
    ft = figure_text({"kind": "step_flow", "title": "Ti", "steps": ["Alpha step", "Beta step"]})
    check("Alpha step" in ft and "Ti" in ft, "figure_text exposes title + steps")

    print(f"\n  article_viz self-test: {'PASS' if not failures else 'FAIL'} "
          f"({len(failures)} failure(s)) [font: {FONT}]")
    return 1 if failures else 0


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        sys.exit(self_test())
    print(__doc__)
