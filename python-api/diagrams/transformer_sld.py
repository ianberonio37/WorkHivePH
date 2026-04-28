"""
Transformer SLD — schemdraw (IEC 60617 symbols) + matplotlib (data panel)
Standards: IEC 60617, PEC 2017 Art. 4.50, IEEE C57.12.00

schemdraw alignment:
  - Built on matplotlib (already in requirements.txt) — zero new infrastructure
  - Uses SVGLite backend: native vector SVG, no PNG embedding, ~15-20 KB
  - IEC 60617 symbol mapping per drawing-standards skill:
      elm.SourceSin  → 3-phase utility source (AC circle)
      elm.Fuse       → Surge arrester shunt branch (IEC 60617-04 convention)
      elm.Breaker    → Circuit breaker: VCB (HV) and MCCB (LV)
      elm.MeterA     → Current transformer CT (metering circle)
      elm.Transformer→ 2-winding transformer (coupled inductors IEC 60617)
      elm.Ground     → Earth electrode (3-line IEC 60617-11)

Drawing rules (drawing-standards skill):
  - Labels to the SIDE (loc='right' / 'left'), never above/below
  - HV=red, LV=blue, Earth=green, BK=navy per platform convention
  - Mandatory checklist: fault level, cable sizes, IC ratings, arc flash,
    phase labels, GEC size and type
"""

import schemdraw
import schemdraw.elements as elm
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import io
import tempfile
import os


def generate(inputs: dict, results: dict) -> str:
    """Returns clean SVG string — schemdraw schematic + matplotlib data panel."""

    # ── Extract calc values ───────────────────────────────────────────────────
    rated_kva = float(results.get('rated_kva',           100))
    v1        = float(results.get('primary_voltage',     13800))
    v2        = float(results.get('secondary_voltage',   400))
    phases    = int(results.get('phases',                3))
    winding   = str(results.get('winding_connection',    'Dyn11'))
    imp_pct   = float(results.get('impedance_pct',       5.0))
    I2        = float(results.get('I2_full_load_A',      0))
    Isc_kA    = float(results.get('Isc_secondary_kA',   0))
    eta       = float(results.get('efficiency_fl_pct',   0))
    VR        = float(results.get('voltage_regulation_pct', 0))
    loading   = float(results.get('loading_pct',         0))
    num_units = int(results.get('num_units',             1))
    project   = str(inputs.get('project_name',           'Power Transformer'))

    is_3ph   = phases == 3
    ph_str   = '3Ø' if is_3ph else '1Ø'
    fault_kA = 25   # standard PH utility fault level at 13.8 kV

    # LV cable (PEC Table 3.10 Cu THWN-2 at 75°C)
    amps = [20,27,36,50,66,84,104,127,167,207,240]
    szs  = [2.5,4,6,10,16,25,35,50,70,95,120]
    lv_cable = next((f'{szs[i]}' for i,a in enumerate(amps) if a >= I2*1.25), '120')
    lv_mccb  = next((s for s in [15,20,30,40,50,60,70,80,90,100,125,150,175,200,225,250]
                     if s >= I2*1.25), 250)
    gec_mm2  = (6 if lv_mccb<=100 else 10 if lv_mccb<=125 else 16
                if lv_mccb<=160 else 25 if lv_mccb<=200 else 35)

    # ── Platform colours ──────────────────────────────────────────────────────
    HV = '#c0392b'    # red   — HV primary
    LV = '#1565c0'    # blue  — LV secondary
    GN = '#2e7d32'    # green — earthing
    BK = '#1a2e4a'    # navy  — transformer/CT

    # ── 1. schemdraw schematic (vertical SLD, left panel) ────────────────────
    d = schemdraw.Drawing(inches_per_unit=0.52, fontsize=8)

    # Utility source — IEC 60617: AC source circle + sine symbol
    d.add(elm.SourceSin().up(2.5).color(HV)
          .label(f'{v1:,.0f} V / {ph_str} / 50 Hz\nFault level: {fault_kA} kA',
                 loc='right', color=HV, fontsize=7.5))

    d.add(elm.Line().down(0.6).color(HV))

    # Surge arrester — shunt branch per IEC 60617 (protective shunt device)
    # elm.Fuse is used as SA body (both are protective elements in IEC 60617-04)
    d.push()
    d.add(elm.Line().left(1.5).color(HV))
    d.add(elm.Fuse().down().color(HV)
          .label(f'SA — {ph_str} sets\nStation class, {v1:,.0f} V\nIEC 60099-4',
                 loc='right', color=HV, fontsize=7))
    d.add(elm.Ground().color(HV))
    d.pop()

    # VCB — elm.Breaker: IEC 60617 circuit breaker symbol
    d.add(elm.Breaker().down().color(HV)
          .label(f'VCB / Load-Break Switch\n{v1:,.0f} V  |  IC ≥ {Isc_kA:.3f} kA\nPEC 2017 Art. 4.50',
                 loc='right', color=HV, fontsize=7))

    d.add(elm.Line().down(0.4).color(HV))

    # CT/VT — elm.MeterA: bushing CT circle (IEC 60617-06)
    d.add(elm.MeterA().down().color(BK)
          .label('CT / VT Set\nClass 0.5S | 5P20\nIEEE C57.13',
                 loc='right', color=BK, fontsize=7))

    d.add(elm.Line().down(0.4).color(HV))

    # Transformer — elm.Transformer: two coupled inductors (IEC 60617-04)
    d.add(elm.Transformer(t1=4, t2=4).down().color(BK)
          .label(f'{rated_kva:.0f} kVA × {num_units}  |  {winding}\n'
                 f'{v1:,.0f} / {v2} V  |  Uz = {imp_pct}%\nONAN  —  IEC 60076-1',
                 loc='right', color=BK, fontsize=7))

    d.add(elm.Line().down(0.4).color(LV))

    # LV MCCB — elm.Breaker in LV blue
    # Arc flash warning mandatory per SLD checklist (NFPA 70E / PEC 2017)
    d.add(elm.Breaker().down().color(LV)
          .label(f'Main LV MCCB — {lv_mccb} A  |  IC ≥ {Isc_kA:.3f} kA  |  TPN\n'
                 f'LV cable: {lv_cable} mm² Cu THWN-2 / EMT conduit  |  VD ≤ 3%\n'
                 f'⚡ Arc flash study required — NFPA 70E / PEC 2017',
                 loc='right', color=LV, fontsize=7))

    d.add(elm.Line().down(0.4).color(LV))

    # LV bus bar — junction dot + horizontal lines
    bus = d.add(elm.Dot(open=True).color(LV))
    d.add(elm.Line().right(2.5).at(bus.start).color(LV))
    d.add(elm.Line().left(2.5).at(bus.start).color(LV))

    # Phase labels on bus (mandatory per SLD checklist)
    if is_3ph:
        phases_list = [('L1', HV), ('L2', HV), ('L3', HV), ('N', LV), ('PE', GN)]
        bx, by = bus.start
        for i, (ph, c) in enumerate(phases_list):
            d.add(elm.Label().at((bx - 2.0 + i * 1.0, by + 0.22))
                  .label(ph, color=c, fontsize=7.5, halign='center'))

    # Earthing — elm.Ground: IEC 60617-11 (3 decreasing horizontal lines)
    # GEC label mandatory: size + electrode type (per SLD checklist)
    d.add(elm.Line().left(0.9).at(bus.start).color(GN))
    d.add(elm.Ground().color(GN)
          .label(f'GEC: {gec_mm2} mm² Cu bare\nGround rod 2.4 m\nPEC Art. 2.50 / IEEE 80',
                 loc='left', color=GN, fontsize=7))

    # Export schemdraw as native vector SVG (SVGLite backend — no matplotlib needed)
    with tempfile.NamedTemporaryFile(suffix='.svg', delete=False, mode='w') as f:
        tmp_svg = f.name
    d.save(tmp_svg)
    with open(tmp_svg) as f:
        schem_svg = f.read()
    os.unlink(tmp_svg)

    # ── 2. Data panel (matplotlib) ────────────────────────────────────────────
    rows = [
        ('Transformer Rating',       f'{rated_kva:.0f} kVA × {num_units}',     BK),
        ('Primary Voltage (HV)',     f'{v1:,.0f} V / {ph_str}',                HV),
        ('Secondary Voltage (LV)',   f'{v2} V / {ph_str}',                     LV),
        ('Winding Connection',       winding,                                   BK),
        ('Impedance (Uz%)',          f'{imp_pct} %',                            BK),
        ('Utility Fault Level',      f'{fault_kA} kA  (NAPOCOR/Meralco std.)', HV),
        ('Primary I₁ (full load)',   f'{results.get("I1_full_load_A",0):.2f} A', HV),
        ('Secondary I₂ (full load)', f'{I2:.2f} A',                            LV),
        ('Short-Circuit Isc',        f'{Isc_kA:.3f} kA',                      '#c0392b'),
        ('LV Cable',                 f'{lv_cable} mm² Cu THWN-2',              LV),
        ('Main LV MCCB',             f'{lv_mccb} A  |  IC ≥ {Isc_kA:.3f} kA', LV),
        ('GEC',                      f'{gec_mm2} mm² Cu bare',                 GN),
        ('Voltage Regulation',       f'{VR:.2f} %',                            BK),
        ('Efficiency (100% load)',   f'{eta:.2f} %',                            GN),
        ('Loading',                  f'{loading:.1f} %',                        HV if loading>80 else GN),
        ('Cooling',                  'ONAN',                                    BK),
        ('Standard',                'IEC 60076-1:2011 / PEC 2017',             '#5a6a7a'),
    ]

    fig, ax = plt.subplots(figsize=(6, 10))
    fig.patch.set_facecolor('#f8faff')
    ax.set_facecolor('#f8faff')
    ax.axis('off')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)

    # Header
    ax.text(0.5, 0.98, 'NAMEPLATE & CALCULATION DATA',
            ha='center', va='top', fontsize=10, fontweight='bold', color='white',
            bbox=dict(facecolor=BK, edgecolor=BK, boxstyle='square,pad=0.4'))

    y = 0.93
    rh = 0.048
    for i, (label, value, vc) in enumerate(rows):
        bg = '#eef3fa' if i % 2 == 0 else '#f8faff'
        ax.axhspan(y - rh, y, xmin=0, xmax=1, facecolor=bg, alpha=0.9, zorder=0)
        ax.text(0.02, y - rh/2, label,  ha='left',  va='center', fontsize=7.5, color='#5a6a7a')
        ax.text(0.98, y - rh/2, value,  ha='right', va='center', fontsize=8,   color=vc, fontweight='bold')
        ax.axhline(y - rh, color='#d0d8e8', linewidth=0.4)
        y -= rh

    ax.set_title(f'{project}\nIEC 60617 / PEC 2017 / IEEE C57.12.00',
                 fontsize=8, color='#5a6a7a', pad=6)

    buf_panel = io.BytesIO()
    fig.savefig(buf_panel, format='svg', bbox_inches='tight', facecolor='#f8faff', dpi=100)
    plt.close(fig)
    buf_panel.seek(0)
    panel_svg = buf_panel.read().decode('utf-8')

    # ── 3. Composite: horizontal layout [schematic | data panel] ─────────────
    # Extract viewBox dimensions from each SVG to compute composite canvas
    import re

    def _get_dims(svg_str):
        m = re.search(r'viewBox=["\']([^"\']+)["\']', svg_str)
        if m:
            parts = m.group(1).split()
            return float(parts[2]), float(parts[3])
        m = re.search(r'width=["\']([0-9.]+)', svg_str)
        h = re.search(r'height=["\']([0-9.]+)', svg_str)
        return (float(m.group(1)) if m else 600,
                float(h.group(1)) if h else 800)

    sw, sh = _get_dims(schem_svg)
    pw, ph_ = _get_dims(panel_svg)

    total_w = sw + pw + 20
    total_h = max(sh, ph_)

    # Strip XML declaration and root <svg> tag from each, re-wrap in composite
    def _strip_svg(svg_str):
        svg_str = re.sub(r'<\?xml[^>]*\?>', '', svg_str).strip()
        # Remove outer <svg...> opening tag but keep contents + </svg>
        svg_str = re.sub(r'^<svg[^>]*>', '', svg_str, count=1).strip()
        svg_str = re.sub(r'</svg>\s*$', '', svg_str).strip()
        return svg_str

    schem_inner = _strip_svg(schem_svg)
    panel_inner = _strip_svg(panel_svg)

    composite = f'''<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     viewBox="0 0 {total_w:.0f} {total_h:.0f}"
     style="display:block;width:100%;height:auto;background:#f8faff;">

  <!-- Title bar -->
  <rect x="0" y="0" width="{total_w:.0f}" height="28" fill="{BK}"/>
  <text x="{total_w/2:.0f}" y="18" text-anchor="middle"
        font-family="Segoe UI,Arial,sans-serif" font-size="11"
        font-weight="bold" fill="white">
    POWER TRANSFORMER — SINGLE LINE DIAGRAM  |  {rated_kva:.0f} kVA × {num_units} unit(s)
  </text>

  <!-- Schematic panel (schemdraw SVG) -->
  <g transform="translate(0, 28)">
    <svg viewBox="0 0 {sw:.0f} {sh:.0f}" width="{sw:.0f}" height="{sh:.0f}">
      {schem_inner}
    </svg>
  </g>

  <!-- Divider -->
  <line x1="{sw:.0f}" y1="28" x2="{sw:.0f}" y2="{total_h:.0f}"
        stroke="#d0d8e8" stroke-width="1"/>

  <!-- Data panel (matplotlib SVG) -->
  <g transform="translate({sw+10:.0f}, 28)">
    <svg viewBox="0 0 {pw:.0f} {ph_:.0f}" width="{pw:.0f}" height="{ph_:.0f}">
      {panel_inner}
    </svg>
  </g>
</svg>'''

    return composite
