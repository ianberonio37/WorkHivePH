"""
Bulk-enrich capture_contracts.json skeletons using name-pattern heuristics
and same-page label / placeholder text.

For every alive capture whose description is still the auto-baseline
placeholder, this tool:
  1. Reads the originating page(s)
  2. Finds the <label for="X"> text and the <input ... placeholder=> text
     adjacent to the capture
  3. Infers field_kind from the HTML tag (input type / select / textarea)
  4. Writes back a richer description + field_kind

It does NOT touch hand-curated entries (those whose description doesn't
start with the auto-baseline prefix `(baseline skeleton`).

Run after audit_phantom_captures.py + generate_capture_contracts_baseline.py.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path


if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")


ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_PATH = ROOT / "canonical" / "capture_contracts.json"

BASELINE_PREFIX = "(baseline skeleton"


def _find_field_context(html: str, name: str) -> dict:
    """For a capture name, return label text + placeholder + tag kind."""
    # Capture the tag itself
    tag_match = re.search(
        r"""<(input|select|textarea|button)\b[^>]*\b(?:name|id)=["']""" + re.escape(name) + r"""["'][^>]*>""",
        html, re.IGNORECASE,
    )
    if not tag_match:
        return {}
    tag = tag_match.group(1).lower()
    tag_text = tag_match.group(0)
    # Type attr for inputs
    type_m = re.search(r"""\btype=["'](\w+)["']""", tag_text, re.IGNORECASE)
    input_type = (type_m.group(1).lower() if type_m else "text") if tag == "input" else tag
    # Placeholder
    placeholder_m = re.search(r"""\bplaceholder=["']([^"']+)["']""", tag_text, re.IGNORECASE)
    placeholder = placeholder_m.group(1) if placeholder_m else ""
    # aria-label fallback
    aria_m = re.search(r"""\baria-label=["']([^"']+)["']""", tag_text, re.IGNORECASE)
    aria = aria_m.group(1) if aria_m else ""

    # Look backward up to 400 chars for a <label for="X">...</label>
    head = html[: tag_match.start()]
    label_m = re.search(
        r"""<label\b[^>]*\bfor=["']""" + re.escape(name) + r"""["'][^>]*>([^<]+)</label>""",
        head[-1500:], re.IGNORECASE,
    )
    label = ""
    if label_m:
        # Strip nested span / em / strong tags
        label = re.sub(r"<[^>]+>", "", label_m.group(1)).strip()

    return {
        "tag":         tag,
        "input_type":  input_type,
        "label":       label,
        "placeholder": placeholder,
        "aria":        aria,
    }


def _field_kind_label(ctx: dict) -> str:
    tag = ctx.get("tag", "")
    t = ctx.get("input_type", "text")
    if tag == "select":   return "form (select)"
    if tag == "textarea": return "form (textarea)"
    if tag == "input":
        if t in ("number", "tel", "decimal"): return "form (number)"
        if t == "checkbox":                   return "form (checkbox)"
        if t == "radio":                      return "form (radio)"
        if t == "date":                       return "form (date)"
        if t in ("file", "image"):            return "form (upload)"
        if t == "search":                     return "form (search)"
        return "form (text)"
    return "form"


def main() -> int:
    if not CONTRACTS_PATH.exists():
        print("FAIL: canonical/capture_contracts.json missing")
        return 2

    contracts = json.loads(CONTRACTS_PATH.read_text(encoding="utf-8"))
    entries = contracts.get("captures") or []

    enriched = 0
    skipped_handcurated = 0
    skipped_no_label = 0

    # Cache page reads
    page_cache: dict[str, str] = {}

    for c in entries:
        desc = c.get("description", "")
        if not desc.startswith(BASELINE_PREFIX):
            skipped_handcurated += 1
            continue

        name = c.get("capture_id", "")
        surfaces = c.get("surfaces", []) or []
        if not name or not surfaces:
            continue

        # Try each origin page until we find a match
        ctx = {}
        for surface in surfaces:
            page_path = ROOT / surface
            if not page_path.exists():
                continue
            if surface not in page_cache:
                page_cache[surface] = page_path.read_text(encoding="utf-8", errors="replace")
            ctx = _find_field_context(page_cache[surface], name)
            if ctx:
                break

        if not ctx:
            skipped_no_label += 1
            continue

        # Build a human description from label/placeholder/aria
        label = ctx.get("label", "")
        placeholder = ctx.get("placeholder", "")
        aria = ctx.get("aria", "")
        primary_text = label or aria or placeholder or name.replace("-", " ").replace("_", " ")

        # Compose
        bits = [primary_text]
        if placeholder and placeholder != primary_text:
            bits.append(f"placeholder: \"{placeholder}\"")
        if aria and aria != primary_text and aria != placeholder:
            bits.append(f"aria: \"{aria}\"")

        c["field_kind"] = _field_kind_label(ctx)
        c["description"] = " — ".join(bits)[:400]
        # If contract is empty {}, leave it; user can flesh out value contract
        if not c.get("contract"):
            c["contract"] = {"type": "string" if ctx.get("tag") in ("input", "textarea") and ctx.get("input_type") != "number" else "number" if ctx.get("input_type") == "number" else "string"}
        enriched += 1

    contracts["captures"] = entries
    CONTRACTS_PATH.write_text(json.dumps(contracts, indent=2), encoding="utf-8")

    print("Capture-contracts enrichment:")
    print(f"  hand-curated preserved:   {skipped_handcurated}")
    print(f"  enriched from page HTML:  {enriched}")
    print(f"  skipped (label missing):  {skipped_no_label}")
    print(f"  total entries:            {len(entries)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
