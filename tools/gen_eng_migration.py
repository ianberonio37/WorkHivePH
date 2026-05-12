"""Generate the Engineering Design Tier D-f migration + annotate calc handlers.

Reads python-api/calcs/*.py, extracts standards from docstrings, and emits:
  1. supabase/migrations/20260512000014_eng_design_formulas.sql
     (registers ~58 engineering calc formulas in canonical_formulas)
  2. Inline edits to each calc handler — appends '# formula: <id>' on the
     line just before 'def calculate(...)'.
"""
import re, os, sys, glob, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CALCS_DIR = "python-api/calcs"
MIGRATION = "supabase/migrations/20260512000014_eng_design_formulas.sql"

BODY_NORM = {'ISO':'ISO','IEC':'IEC','SAE':'SAEJA','SAEJA':'SAEJA','NFPA':'NFPA',
             'NEC':'NEC','IEEE':'IEEE','ANSI':'ANSI','ASTM':'ASTM','ASHRAE':'ASHRAE',
             'IESNA':'IESNA','OSHA':'OSHA','ASME':'ASME'}

DISC_HINTS = {
    'bearing':'mechanical','shaft':'mechanical','gear':'mechanical',
    'beam':'mechanical','pressure_vessel':'mechanical','bolt':'mechanical',
    'pump':'mechanical','fan':'mechanical','vibration':'mechanical',
    'hoist':'mechanical','compressed_air':'pneumatic',
    'fluid_power':'hydraulic','hydraulic':'hydraulic',
    'cable':'electrical','wire':'electrical','voltage':'electrical',
    'transformer':'electrical','generator':'electrical','ups':'electrical',
    'load_':'electrical','short_circuit':'electrical','earthing':'electrical',
    'harmonic':'electrical','power_factor':'electrical',
    'lightning':'lightning_protection',
    'solar_pv':'solar_pv',
    'lighting':'lighting',
    'hvac_':'hvac','ahu_':'hvac','chiller':'hvac','cooling_tower':'hvac',
    'fcu_':'hvac','duct_':'hvac','ventilation':'hvac',
    'refrigerant':'hvac','heat_exchanger':'hvac','expansion_tank':'hvac',
    'stairwell_pressurization':'hvac',
    'fire_':'fire','sprinkler':'fire','clean_agent':'fire',
    'pipe_sizing':'plumbing','water_':'plumbing','drainage':'plumbing',
    'drain':'plumbing','roof_drain':'plumbing','storm_drain':'plumbing',
    'sewer_':'plumbing','septic':'plumbing','grease_trap':'plumbing',
    'hot_water':'plumbing','domestic_water':'plumbing',
    'wastewater':'plumbing','boiler':'plumbing',
    'noise':'acoustics',
    'elevator':'mechanical',
    'cable_tray':'electrical',
}

def discipline_for(filename):
    for k, v in DISC_HINTS.items():
        if k in filename: return v
    return 'general'

STD_RE = re.compile(
    r'(ISO|SMRP|SAE\s*JA|NFPA|ASME|ASTM|ANSI|IEC|IESNA|ASHRAE|NEC|OSHA|IEEE)[\s\-:]*(\d{2,5}(?:[\-:][\d\.]+)?)',
    re.IGNORECASE)

def parse_standards(docstring):
    out = []; seen = set()
    for m in STD_RE.finditer(docstring or ''):
        body = re.sub(r'\s+', '', m.group(1).upper())
        body = BODY_NORM.get(body, body)
        num  = m.group(2).replace(':', '-').rstrip('.')
        sid  = f'{body}_{num}'.lower().replace('-', '_').replace('.', '_')
        if sid in seen: continue
        seen.add(sid); out.append(sid)
    return out

def short_name(p): return os.path.splitext(os.path.basename(p))[0]
def calc_title(n): return ' '.join(w.capitalize() for w in n.split('_'))

rows_sql = []
edits = []

for path in sorted(glob.glob(os.path.join(CALCS_DIR, "*.py"))):
    name = short_name(path)
    if name == '__init__': continue
    content = open(path, encoding='utf-8').read()
    if not re.search(r'^def calculate', content, re.MULTILINE): continue
    m = re.match(r'\s*"""([\s\S]*?)"""', content)
    docstring = m.group(1) if m else ''
    stds = parse_standards(docstring)
    primary = stds[0] if stds else ''
    fid = f'{name}_{primary}' if primary else name
    fid = fid.lower().replace('-','_')
    desc_lines = []
    for line in docstring.split('\n'):
        line = line.strip()
        if not line:
            if desc_lines: break
            continue
        desc_lines.append(line)
        if len(desc_lines) >= 3: break
    desc = ' '.join(desc_lines)[:280].replace("'", "''")
    title = calc_title(name)
    domain = discipline_for(name)
    std_arr = ','.join(f"'{s}'" for s in stds) if stds else ''
    std_sql = f"ARRAY[{std_arr}]" if std_arr else "ARRAY[]::text[]"
    lib_source = f"python:{CALCS_DIR}/{name}.py:calculate"
    rows_sql.append(
        f"  ('{fid}', '{title}', '{domain}', {std_sql}, '{lib_source}', "
        f"'[]'::jsonb, '[]'::jsonb, '', '{desc}')"
    )
    edits.append((path, fid))

# Generate migration file
values_sql = ',\n'.join(rows_sql)
migration_sql = f"""-- Engineering Design Tier D-f: register {len(rows_sql)} calc handler
-- formulas in canonical_formulas (2026-05-12).
--
-- Each row is generated from the corresponding python-api/calcs/<name>.py
-- handler. The library_source field points at the actual Python function
-- that implements the formula. standard_ids are the cited bodies/numbers
-- from the docstring (already registered in canonical_standards).
--
-- Skills consulted: maintenance-expert (formula taxonomy), data-engineer
-- (canonical registry pattern), platform-guardian (forward-only ratchet).

BEGIN;

INSERT INTO public.canonical_formulas (formula_id, name, domain, standard_ids, library_source, inputs, outputs, formula_text, description) VALUES
{values_sql}
ON CONFLICT (formula_id) DO UPDATE
  SET name=EXCLUDED.name, domain=EXCLUDED.domain, standard_ids=EXCLUDED.standard_ids,
      library_source=EXCLUDED.library_source, inputs=EXCLUDED.inputs, outputs=EXCLUDED.outputs,
      formula_text=EXCLUDED.formula_text, description=EXCLUDED.description;

COMMIT;
"""
with open(MIGRATION, 'w', encoding='utf-8', newline='\n') as f:
    f.write(migration_sql)

# Apply inline edits: insert '# formula: <id>' on the line above 'def calculate'
edited_count = 0
already_tagged = 0
for path, fid in edits:
    content = open(path, encoding='utf-8').read()
    if f'# formula: {fid}' in content:
        already_tagged += 1
        continue
    # Insert just before 'def calculate'
    new = re.sub(r'^(def calculate)', f'# formula: {fid}\n\\1',
                 content, count=1, flags=re.MULTILINE)
    if new != content:
        open(path, 'w', encoding='utf-8', newline='\n').write(new)
        edited_count += 1

print(f'Wrote {MIGRATION} ({len(rows_sql)} formulas)')
print(f'Annotated {edited_count} Python files')
print(f'Already tagged: {already_tagged}')
