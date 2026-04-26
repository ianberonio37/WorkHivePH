"""
WorkHive Platform Guardian — Phase 6a: Auto-Fix Recipes
=========================================================
Applies known fix recipes when validators detect specific FAIL patterns.
Each recipe is deterministic and scoped — it changes the minimum required.

Usage:
  python autofix.py                # detect + fix all eligible patterns
  python autofix.py --dry-run      # show what would be fixed, don't write
  python autofix.py --recipe NAME  # run one specific recipe only
  python autofix.py --list         # list all available recipes

Integration with orchestrator:
  python run_platform_checks.py --fast --autofix
  (orchestrator calls autofix.py after detecting FAILs)

How a recipe works:
  1. DETECT  — scan the target file for the broken pattern
  2. VERIFY  — confirm the fix is needed (not already applied)
  3. PATCH   — apply the minimal targeted change
  4. CONFIRM — describe what changed

Output: autofix_report.json
"""
import re, json, os, sys, datetime

DRY_RUN = "--dry-run" in sys.argv
ONLY    = next((a.split("=")[1] for a in sys.argv if a.startswith("--recipe=")), None)
LIST    = "--list" in sys.argv

AUTOFIX_REPORT = "autofix_report.json"


def read_file(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_file(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ── Recipe base class ─────────────────────────────────────────────────────────

class Recipe:
    id          = "base"
    label       = "Base recipe"
    file        = ""
    description = ""
    confidence  = "HIGH"   # HIGH = safe to auto-apply; MEDIUM = review; LOW = manual only

    def detect(self, content) -> tuple[bool, str]:
        """Returns (is_broken, detail_string)"""
        raise NotImplementedError

    def patch(self, content) -> tuple[str, str]:
        """Returns (patched_content, description_of_change)"""
        raise NotImplementedError

    def run(self, dry_run=False):
        content = read_file(self.file)
        if content is None:
            return {"status": "ERROR", "reason": f"{self.file} not found"}

        broken, detail = self.detect(content)
        if not broken:
            return {"status": "SKIP", "reason": f"Pattern not found — already fixed or not applicable. {detail}"}

        if dry_run:
            return {"status": "DRY", "reason": f"Would fix: {detail}"}

        patched, change_desc = self.patch(content)
        if patched == content:
            return {"status": "SKIP", "reason": "Patch produced no change — may need manual fix"}

        write_file(self.file, patched)
        return {"status": "FIXED", "change": change_desc, "detail": detail}


# ── Concrete recipes ──────────────────────────────────────────────────────────

class FixCalcCountAssistant(Recipe):
    id          = "calc-count-assistant"
    label       = "Stale calc count in assistant.html"
    file        = "assistant.html"
    description = "Updates the engineering calc type count to 46 when it's out of date"
    confidence  = "HIGH"
    CORRECT_COUNT = 46

    def detect(self, content):
        m = re.search(
            r"engineering.design[\s\S]{0,800}?(\d+)\s*calc(?:ulation)?\s*type",
            content, re.IGNORECASE
        )
        if not m:
            return False, "Calc count pattern not found"
        found = int(m.group(1))
        if found == self.CORRECT_COUNT:
            return False, f"Count is already {self.CORRECT_COUNT}"
        return True, f"Count is {found}, should be {self.CORRECT_COUNT}"

    def patch(self, content):
        m = re.search(
            r"(engineering.design[\s\S]{0,800}?)(\d+)(\s*calc(?:ulation)?\s*type)",
            content, re.IGNORECASE
        )
        if not m:
            return content, "No change"
        old_count = m.group(2)
        patched = content[:m.start(2)] + str(self.CORRECT_COUNT) + content[m.end(2):]
        return patched, f"Changed calc count from {old_count} to {self.CORRECT_COUNT}"


class FixSkillMatrixDisciplines(Recipe):
    id          = "skill-matrix-disciplines"
    label       = "Wrong discipline names in floating-ai.js PLATFORM TOOLS"
    file        = "floating-ai.js"
    description = "Fixes Skill Matrix discipline names (HVAC/Civil → Facilities Management/Production Lines)"
    confidence  = "HIGH"
    WRONG  = "Mechanical, Electrical, Instrumentation, HVAC, Civil/Structural"
    CORRECT = "Mechanical, Electrical, Instrumentation, Facilities Management, Production Lines"

    def detect(self, content):
        if self.WRONG in content:
            return True, f"Found wrong discipline list: {self.WRONG}"
        return False, "Discipline names are already correct"

    def patch(self, content):
        patched = content.replace(self.WRONG, self.CORRECT)
        return patched, f"Updated Skill Matrix discipline names to: {self.CORRECT}"


class FixEngDesignInPlatformTools(Recipe):
    id          = "eng-design-platform-tools"
    label       = "engineering-design.html missing from floating-ai.js PLATFORM TOOLS"
    file        = "floating-ai.js"
    description = "Adds the Engineering Design Calculator to the AI widget's PLATFORM TOOLS section"
    confidence  = "HIGH"
    MARKER   = "- Parts Tracker: Retired."
    NEW_TOOL = (
        "- Engineering Design Calculator (engineering-design.html): "
        "46 calculation types across Mechanical, HVAC, Electrical, Fire Protection, "
        "Plumbing, Structural, and Machine Design disciplines. "
        "Each calc generates a print-ready report with BOM and Scope of Works. "
        "Built to Philippine standards (PEC 2017, PSME, NSCP, ASHRAE, NFPA).\n"
    )

    def detect(self, content):
        tools_start = content.find("PLATFORM TOOLS")
        if tools_start == -1:
            return False, "PLATFORM TOOLS section not found"
        tools_block = content[tools_start:tools_start + 3000]
        if "engineering-design" in tools_block:
            return False, "engineering-design already in PLATFORM TOOLS"
        return True, "engineering-design not found in PLATFORM TOOLS"

    def patch(self, content):
        if self.MARKER not in content:
            return content, "Marker not found — cannot safely insert"
        patched = content.replace(self.MARKER, self.NEW_TOOL + self.MARKER)
        return patched, "Added Engineering Design Calculator to PLATFORM TOOLS before Parts Tracker note"


class FixPMCatToLogCat(Recipe):
    id          = "pm-cat-to-log-cat"
    label       = "PM_CAT_TO_LOG_CAT maps to invalid logbook categories"
    file        = "pm-scheduler.html"
    description = "Remaps HVAC/Utilities/Civil/Structural to valid logbook categories"
    confidence  = "HIGH"
    VALID = ["Mechanical", "Electrical", "Hydraulic", "Pneumatic",
             "Instrumentation", "Lubrication", "Other"]
    REMAPS = {
        "'HVAC'":               "'Mechanical'",
        "'Utility Systems'":    "'Mechanical'",
        "'Civil / Structural'": "'Other'",
        "'Utilities'":          "'Mechanical'",
    }

    def detect(self, content):
        m = re.search(r"PM_CAT_TO_LOG_CAT\s*=\s*\{([^}]+)\}", content, re.DOTALL)
        if not m:
            return False, "PM_CAT_TO_LOG_CAT not found"
        block = m.group(1)
        pairs = re.findall(r"['\"]([^'\"]+)['\"]\s*:\s*['\"]([^'\"]+)['\"]", block)
        bad = [(k, v) for k, v in pairs if v not in self.VALID]
        if not bad:
            return False, "All mappings are valid"
        return True, f"Invalid mappings: {bad}"

    def patch(self, content):
        patched = content
        changes = []
        for wrong, right in self.REMAPS.items():
            if wrong + ": " + wrong in patched or wrong + ":" + wrong in patched:
                continue
            # Look for pattern: 'HVAC':  'HVAC' or similar
            # Replace the VALUE only when it doesn't match a valid category
            old_pat = re.compile(r"(" + re.escape(wrong) + r"\s*:\s*)" + re.escape(wrong))
            if old_pat.search(patched):
                patched = old_pat.sub(r"\g<1>" + right, patched)
                changes.append(f"{wrong} -> {right}")
            # Also handle cross-category maps like 'HVAC': 'HVAC' (same name)
            for bad_val in ["'HVAC'", "'Utilities'", "'Civil / Structural'"]:
                if bad_val not in [v for _, v in re.findall(r":\s*(" + re.escape(bad_val) + r")", patched)]:
                    continue
                right_for_bad = self.REMAPS.get(bad_val, "'Mechanical'")
                pat = re.compile(r"(" + re.escape(wrong) + r"\s*:\s*)" + re.escape(bad_val))
                if pat.search(patched):
                    patched = pat.sub(r"\g<1>" + right_for_bad, patched)
                    changes.append(f"value {bad_val} -> {right_for_bad}")

        if not changes:
            return content, "No specific patterns matched"
        return patched, f"Fixed: {'; '.join(changes)}"


class FixQtyAfterInLogbook(Recipe):
    id          = "qty-after-logbook"
    label       = "Missing qty_after in logbook inventory_transactions inserts"
    file        = "logbook.html"
    description = "Adds qty_after: newQty to both parts deduction inserts in logbook.html"
    confidence  = "HIGH"
    # The broken pattern: insert without qty_after
    BROKEN_PATTERN = r"qty_change:\s*-p\.qty,\s*type:\s*'use',"
    FIXED_PATTERN  = "qty_change: -p.qty, qty_after: newQty, type: 'use',"

    def detect(self, content):
        m = re.search(self.BROKEN_PATTERN, content)
        if not m:
            return False, "qty_change pattern not found or already fixed"
        # Check it's not already accompanied by qty_after nearby
        snippet = content[m.start():m.start() + 100]
        if "qty_after" in snippet:
            return False, "qty_after already present near qty_change"
        return True, "Found qty_change without qty_after"

    def patch(self, content):
        old = re.search(self.BROKEN_PATTERN, content)
        if not old:
            return content, "Pattern not found"
        # Replace all occurrences
        patched = re.sub(self.BROKEN_PATTERN, self.FIXED_PATTERN, content)
        count = len(re.findall(self.BROKEN_PATTERN, content))
        return patched, f"Added qty_after: newQty to {count} inventory_transactions insert(s)"


# ── Recipe registry ───────────────────────────────────────────────────────────

ALL_RECIPES = [
    FixCalcCountAssistant(),
    FixSkillMatrixDisciplines(),
    FixEngDesignInPlatformTools(),
    FixPMCatToLogCat(),
    FixQtyAfterInLogbook(),
]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    if LIST:
        print("\n  Available auto-fix recipes:\n")
        for r in ALL_RECIPES:
            print(f"  [{r.confidence:6s}] {r.id}")
            print(f"           {r.description}")
        return 0

    print("\n" + "=" * 70)
    print("  WorkHive Platform Guardian — Auto-Fix")
    print(f"  {now_str}  |  {'DRY RUN' if DRY_RUN else 'WRITE mode'}")
    print("=" * 70)

    recipes = [r for r in ALL_RECIPES if not ONLY or r.id == ONLY]
    if ONLY and not recipes:
        print(f"\n  ERROR: Recipe '{ONLY}' not found. Run with --list to see options.")
        return 1

    results  = []
    fixed    = 0
    skipped  = 0
    errors   = 0

    for recipe in recipes:
        print(f"\n  [{recipe.confidence:6s}]  {recipe.label}")
        result = recipe.run(dry_run=DRY_RUN)
        status = result["status"]

        if status == "FIXED":
            print(f"  FIXED   {result.get('change', '')}")
            fixed += 1
        elif status == "DRY":
            print(f"  DRY     {result.get('reason', '')}")
            skipped += 1
        elif status == "SKIP":
            print(f"  SKIP    {result.get('reason', '')}")
            skipped += 1
        elif status == "ERROR":
            print(f"  ERROR   {result.get('reason', '')}")
            errors += 1

        results.append({
            "recipe": recipe.id,
            "label":  recipe.label,
            "file":   recipe.file,
            **result,
        })

    print(f"\n{'=' * 70}")
    print(f"  {fixed} fixed  {skipped} skipped  {errors} errors")

    with open(AUTOFIX_REPORT, "w") as f:
        json.dump({
            "timestamp":  now_str,
            "dry_run":    DRY_RUN,
            "fixed":      fixed,
            "skipped":    skipped,
            "errors":     errors,
            "results":    results,
        }, f, indent=2)
    print(f"  Saved {AUTOFIX_REPORT}")

    if fixed and not DRY_RUN:
        print(f"\n  {fixed} file(s) patched. Re-run validators to confirm:")
        print(f"  python run_platform_checks.py --fast\n")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
