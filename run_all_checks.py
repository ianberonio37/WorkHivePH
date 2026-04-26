"""
Master Validation Runner — Engineering Design Calculator

Runs all 4 validation layers in sequence. Stop on first failure.
Use this as the standard practice after ANY change to the platform.

Usage:  python run_all_checks.py
        python run_all_checks.py --fast   (skip Layer 3 live API calls)

When to run:
  - After changing any Python handler in python-api/calcs/
  - After changing any renderer function in engineering-design.html
  - After changing the BOM/SOW edge function
  - After adding a new calc type anywhere in the stack
  - Before any UI testing session

Exit code 0 = all layers PASS (safe to do UI spot-check)
Exit code 1 = at least one layer FAILED (fix before touching the browser)
"""
import subprocess, sys, os, time
# Force UTF-8 output on Windows so emoji/special chars don't crash the console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PYTHON = sys.executable
FAST   = "--fast" in sys.argv

LAYERS = [
    {
        "id":     "Layer 1",
        "name":   "Python API Unit Test",
        "script": "validate_fields.py",
        "desc":   "Calls live Python API for all 33 handled calc types. Saves results_keys.json.",
        "skip_if_fast": False,
    },
    {
        "id":     "Layer 2a",
        "name":   "Renderer Contract Test",
        "script": "validate_renderers.py",
        "desc":   "Checks every r.field in every render*Report() against results_keys.json.",
        "skip_if_fast": False,
    },
    {
        "id":     "Layer 2b",
        "name":   "BOM/SOW Contract Test",
        "script": "validate_bom_sow.py",
        "desc":   "Checks every rec.field in the BOM/SOW edge function against results_keys.json.",
        "skip_if_fast": False,
    },
    {
        "id":     "Layer 3",
        "name":   "Edge Function Integration Test",
        "script": "validate_integration.py",
        "desc":   "Calls live Supabase edge function. Verifies source='python' for Python-handled calcs.",
        "skip_if_fast": True,
    },
]

DIVIDER = "=" * 70

def run_layer(layer):
    script = layer["script"]
    if not os.path.exists(script):
        return None, f"Script not found: {script}"
    result = subprocess.run(
        [PYTHON, script],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    stdout = result.stdout or ""
    stderr = result.stderr or ""
    return result.returncode, stdout + stderr


print(f"\n{DIVIDER}")
print("  WorkHive Engineering Calc — Full Validation Suite")
print(f"{DIVIDER}")
if FAST:
    print("  Mode: FAST (Layer 3 live API calls skipped)")
print()

results = []
for layer in LAYERS:
    if FAST and layer["skip_if_fast"]:
        print(f"  SKIP  {layer['id']}: {layer['name']}  (--fast mode)")
        results.append(("SKIP", layer))
        continue

    print(f"  RUN   {layer['id']}: {layer['name']}")
    print(f"        {layer['desc']}")

    start   = time.time()
    code, output = run_layer(layer)
    elapsed = time.time() - start

    # Print the script output indented
    for line in output.strip().splitlines():
        print(f"        {line}")

    if code is None:
        status = "ERROR"
    elif code == 0:
        status = "PASS"
    else:
        status = "FAIL"

    results.append((status, layer))
    print(f"  {status}  {layer['id']} completed in {elapsed:.1f}s\n")

    if status in ("FAIL", "ERROR"):
        print(f"{DIVIDER}")
        print(f"  STOPPED at {layer['id']}: {layer['name']}")
        print(f"  Fix the issues above before running the next layer.")
        print(f"{DIVIDER}")
        sys.exit(1)

# ── Final summary ─────────────────────────────────────────────────────────────
print(f"{DIVIDER}")
print("  SUMMARY")
print(f"{DIVIDER}")
for status, layer in results:
    icon = "PASS" if status == "PASS" else ("SKIP" if status == "SKIP" else "FAIL")
    print(f"  {icon}  {layer['id']}: {layer['name']}")

all_pass = all(s in ("PASS", "SKIP") for s, _ in results)
print(f"\n{'ALL LAYERS PASS' if all_pass else 'VALIDATION FAILED'}")
if all_pass:
    print("""
Standard practice from this point:
  1. All 4 layers passed automatically.
  2. Do a UI spot-check: 1 calc per discipline (6 calcs total).
  3. Hard refresh browser (Ctrl+Shift+R) before each spot-check.
  4. Ship.
""")
sys.exit(0 if all_pass else 1)
