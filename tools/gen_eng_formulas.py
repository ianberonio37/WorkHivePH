"""Scan python-api/calcs/ and emit (a) SQL VALUES rows for canonical_formulas
and (b) edit list of (file, formula_id) to annotate each calc handler with
'# formula: <id>'."""
import re, os, sys, glob, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CALCS_DIR = "python-api/calcs"
out_sql = []
out_edits = []

# Map body name -> registry body code used in canonical_standards
BODY_NORM = {
    'ISO': 'ISO', 'IEC': 'IEC', 'SAE': 'SAEJA', 'SAEJA': 'SAEJA',
    'NFPA': 'NFPA', 'NEC': 'NEC', 'IEEE': 'IEEE', 'ANSI': 'ANSI',
    'ASTM': 'ASTM', 'ASHRAE': 'ASHRAE', 'IESNA': 'IESNA', 'OSHA': 'OSHA',
    'ASME': 'ASME',
}

DISC_HINTS = {
    'bearing': 'mechanical', 'shaft': 'mechanical', 'gear': 'mechanical',
    'beam': 'mechanical', 'pressure_vessel': 'mechanical', 'bolt': 'mechanical',
    'pump': 'mechanical', 'fan': 'mechanical', 'vibration': 'mechanical',
    'hoist': 'mechanical', 'compressed_air': 'pneumatic',
    'fluid_power': 'hydraulic', 'hydraulic': 'hydraulic',
    'cable': 'electrical', 'wire': 'electrical', 'voltage': 'electrical',
    'transformer': 'electrical', 'generator': 'electrical', 'ups': 'electrical',
    'load_': 'electrical', 'short_circuit': 'electrical', 'earthing': 'electrical',
    'harmonic': 'electrical', 'power_factor': 'electrical',
    'lightning': 'lightning_protection',
    'solar_pv': 'solar_pv',
    'lighting': 'lighting',
    'hvac_': 'hvac', 'ahu_': 'hvac', 'chiller': 'hvac', 'cooling_tower': 'hvac',
    'fcu_': 'hvac', 'duct_': 'hvac', 'ventilation': 'hvac',
    'refrigerant': 'hvac', 'heat_exchanger': 'hvac', 'expansion_tank': 'hvac',
    'stairwell_pressurization': 'hvac',
    'fire_': 'fire', 'sprinkler': 'fire', 'clean_agent': 'fire',
    'pipe_sizing': 'plumbing', 'water_': 'plumbing', 'drainage': 'plumbing',
    'drain': 'plumbing', 'roof_drain': 'plumbing', 'storm_drain': 'plumbing',
    'sewer_': 'plumbing', 'septic': 'plumbing', 'grease_trap': 'plumbing',
    'hot_water': 'plumbing', 'domestic_water': 'plumbing',
    'wastewater': 'plumbing', 'boiler': 'plumbing',
    'noise': 'acoustics',
    'elevator': 'mechanical',
    'cable_tray': 'electrical',
}

def discipline_for(filename: str) -> str:
    for k, v in DISC_HINTS.items():
        if k in filename: return v
    return 'general'

STD_RE = re.compile(
    r'(ISO|SMRP|SAE\s*JA|NFPA|ASME|ASTM|ANSI|IEC|IESNA|ASHRAE|NEC|OSHA|IEEE)[\s\-:]*(\d{2,5}(?:[\-:][\d\.]+)?)',
    re.IGNORECASE)

def parse_standards(docstring: str) -> list[str]:
    """Return list of standard_ids cited in this calc's docstring."""
    out = []
    seen = set()
    for m in STD_RE.finditer(docstring or ''):
        body = re.sub(r'\s+', '', m.group(1).upper())
        body = BODY_NORM.get(body, body)
        num  = m.group(2).replace(':', '-').rstrip('.')
        sid  = f'{body}_{num}'.lower().replace('-', '_').replace('.', '_')
        if sid in seen: continue
        seen.add(sid)
        out.append(sid)
    return out

def short_name(filename: str) -> str:
    return os.path.splitext(os.path.basename(filename))[0]

def calc_title(name: str) -> str:
    """bearing_life -> Bearing Life"""
    return ' '.join(w.capitalize() for w in name.split('_'))

def primary_standard_for(filename: str, stds: list[str]) -> str:
    """Pick a primary standard for the formula_id suffix."""
    if not stds: return ''
    return stds[0]

for path in sorted(glob.glob(os.path.join(CALCS_DIR, "*.py"))):
    name = short_name(path)
    if name == '__init__': continue
    content = open(path, encoding='utf-8').read()
    # Has 'def calculate'?
    if not re.search(r'^def calculate', content, re.MULTILINE): continue
    # Parse docstring (first triple-quoted block at top of file)
    m = re.match(r'\s*"""([\s\S]*?)"""', content)
    docstring = m.group(1) if m else ''
    stds = parse_standards(docstring)
    primary = primary_standard_for(path, stds)
    fid = f'{name}_{primary}' if primary else name
    fid = fid.lower().replace('-','_')
    # Description: first non-blank lines of docstring (up to first blank line)
    desc_lines = []
    for line in docstring.split('\n'):
        line = line.strip()
        if not line:
            if desc_lines: break
            continue
        desc_lines.append(line)
        if len(desc_lines) >= 4: break
    desc = ' '.join(desc_lines)[:280].replace("'", "''")
    title = calc_title(name)
    domain = discipline_for(name)
    std_arr = ','.join(f"'{s}'" for s in stds) if stds else ''
    std_sql = f"ARRAY[{std_arr}]" if std_arr else "ARRAY[]::text[]"
    lib_source = f"python:{CALCS_DIR}/{name}.py:calculate"
    # Build the SQL row
    out_sql.append(
        f"('{fid}', '{title}', '{domain}', {std_sql}, "
        f"'{lib_source}', '[]'::jsonb, '[]'::jsonb, '', '{desc}')"
    )
    out_edits.append((path, fid))

print(f"-- {len(out_sql)} engineering calc formulas\n")
print(',\n'.join(out_sql))
print()
print("---EDITS---")
for path, fid in out_edits:
    print(f"{path}\t{fid}")
