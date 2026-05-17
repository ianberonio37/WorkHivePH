"""Day 3 Track D: Equipment Label OCR via Azure Doc Intelligence Read.

Layer 3.4 of the Azure $200 sprint. Unlike the other vision detectors
(defect, arc/spark, smoke/leak — Custom Vision ONNX models), equipment
label recognition uses the pre-trained Doc Intelligence Read model — no
training needed, OCR is a solved problem.

Pipeline:
  1. Submit an image (PDF, JPG, PNG) of an equipment nameplate
  2. Azure Doc Intelligence extracts all text lines
  3. Parse for manufacturer / model / serial number patterns
  4. Match against asset_nodes (hive-scoped)
  5. Return matched asset OR suggest a new asset_node payload

This is a one-shot enrichment tool. Once the match exists, future drone
passes use the asset_node.id directly — no repeated OCR calls.

Usage:
    python tools/day3_equipment_label_ocr.py --image path/to/nameplate.jpg --hive-id <uuid>
    python tools/day3_equipment_label_ocr.py --url https://.../nameplate.jpg --hive-id <uuid>
"""
from __future__ import annotations

import os
import sys
import io
import re
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

import psycopg2

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


# ── Env loading (mirrors doc_intelligence_test.py) ───────────────────────
ROOT = Path(__file__).resolve().parent.parent


def load_env(env_path: Path) -> dict[str, str]:
    if not env_path.exists():
        print(f"ERROR: {env_path} not found")
        sys.exit(2)
    env: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


# ── Azure Doc Intelligence Read submit/poll ──────────────────────────────
def submit_image_url(endpoint: str, key: str, image_url: str) -> str:
    """Submit by URL. Returns the Operation-Location polling URL."""
    url = f"{endpoint}/documentintelligence/documentModels/prebuilt-read:analyze?api-version=2024-11-30"
    body = json.dumps({"urlSource": image_url}).encode("utf-8")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type":              "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        if resp.status not in (200, 202):
            print(f"ERROR submit: HTTP {resp.status}")
            print(resp.read().decode("utf-8"))
            sys.exit(1)
        op_loc = resp.headers.get("Operation-Location") or resp.headers.get("operation-location")
        if not op_loc:
            print("ERROR: no Operation-Location header")
            sys.exit(1)
        return op_loc


def submit_image_bytes(endpoint: str, key: str, image_path: Path) -> str:
    """Submit local file as binary octet-stream."""
    url = f"{endpoint}/documentintelligence/documentModels/prebuilt-read:analyze?api-version=2024-11-30"
    body = image_path.read_bytes()
    # Detect content type from suffix
    suffix = image_path.suffix.lower()
    ctypes = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".pdf": "application/pdf",
        ".tiff": "image/tiff", ".bmp": "image/bmp",
    }
    content_type = ctypes.get(suffix, "application/octet-stream")
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Ocp-Apim-Subscription-Key": key,
            "Content-Type":              content_type,
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status not in (200, 202):
            print(f"ERROR submit: HTTP {resp.status}")
            print(resp.read().decode("utf-8"))
            sys.exit(1)
        op_loc = resp.headers.get("Operation-Location") or resp.headers.get("operation-location")
        return op_loc or ""


def poll_result(op_location: str, key: str, max_seconds: int = 90) -> dict:
    req_headers = {"Ocp-Apim-Subscription-Key": key}
    start = time.time()
    delay = 2
    while True:
        if time.time() - start > max_seconds:
            print(f"ERROR: timeout after {max_seconds}s")
            sys.exit(1)
        req = urllib.request.Request(op_location, headers=req_headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        status = data.get("status", "")
        elapsed = int(time.time() - start)
        print(f"  poll t+{elapsed}s: status={status}")
        if status == "succeeded":
            return data
        if status in ("failed", "canceled"):
            print(f"ERROR: analysis {status}")
            print(json.dumps(data, indent=2)[:1000])
            sys.exit(1)
        time.sleep(delay)
        delay = min(delay + 1, 6)


# ── Nameplate parsing ─────────────────────────────────────────────────────
LABEL_PATTERNS = {
    "manufacturer": [
        re.compile(r"(?i)\b(?:manufacturer|mfg|brand|make)\s*[:\-]\s*([A-Z][\w &\-]{2,40})"),
    ],
    "model": [
        # Longer/more-specific patterns first so "Model No." wins over "Model".
        re.compile(r"(?i)\bmodel\s*no\.?\s*[:\-]?\s*([A-Z0-9][\w\-./]{2,30})"),
        re.compile(r"(?i)\bcat\.?\s*no\.?\s*[:\-]?\s*([A-Z0-9][\w\-./]{2,30})"),
        re.compile(r"(?i)\b(?:model|type)\s*[:\-]\s*([A-Z0-9][\w\-./]{2,30})"),
    ],
    "serial_no": [
        re.compile(r"(?i)\b(?:s/?n|serial\s*(?:no\.?)?|ser\.?)\s*[:\-]?\s*([A-Z0-9][\w\-]{3,30})"),
    ],
    "rated_power": [
        re.compile(r"(?i)\b(\d+(?:\.\d+)?)\s*(kW|HP|W|kVA)\b"),
    ],
    "voltage": [
        re.compile(r"(?i)\b(\d{2,4})\s*V(?:AC|DC)?\b"),
    ],
}


def parse_nameplate(text: str) -> dict[str, str]:
    """Extract structured fields from raw OCR text."""
    found: dict[str, str] = {}
    for field, patterns in LABEL_PATTERNS.items():
        for pat in patterns:
            m = pat.search(text)
            if m:
                val = m.group(1).strip().rstrip(".,;:")
                if val:
                    found[field] = val
                    break
    return found


# ── Asset matching against asset_nodes ────────────────────────────────────
def match_against_assets(parsed: dict[str, str], hive_id: str) -> list[dict]:
    """Return ranked asset_nodes matches for a given hive."""
    if not parsed:
        return []

    conn = psycopg2.connect(
        host="127.0.0.1", port=54322,
        user="postgres", password="postgres",
        database="postgres",
    )
    cur = conn.cursor()

    # Strategy: exact match on serial_no > exact model > fuzzy manufacturer+model
    candidates: list[dict] = []
    seen_ids: set[str] = set()

    def add_rows(rows: list[tuple], score: int, reason: str) -> None:
        for r in rows:
            if r[0] in seen_ids:
                continue
            seen_ids.add(r[0])
            candidates.append({
                "id":           str(r[0]),
                "tag":          r[1],
                "name":         r[2],
                "manufacturer": r[3],
                "model":        r[4],
                "serial_no":    r[5],
                "score":        score,
                "match_reason": reason,
            })

    if parsed.get("serial_no"):
        cur.execute("""
            SELECT id, tag, name, manufacturer, model, serial_no
              FROM public.asset_nodes
             WHERE hive_id = %s AND serial_no ILIKE %s
             LIMIT 5
        """, (hive_id, f"%{parsed['serial_no']}%"))
        add_rows(cur.fetchall(), score=100, reason="serial_no exact match")

    if parsed.get("model"):
        cur.execute("""
            SELECT id, tag, name, manufacturer, model, serial_no
              FROM public.asset_nodes
             WHERE hive_id = %s AND model ILIKE %s
             LIMIT 5
        """, (hive_id, f"%{parsed['model']}%"))
        add_rows(cur.fetchall(), score=70, reason="model match")

    if parsed.get("manufacturer"):
        cur.execute("""
            SELECT id, tag, name, manufacturer, model, serial_no
              FROM public.asset_nodes
             WHERE hive_id = %s AND manufacturer ILIKE %s
             LIMIT 10
        """, (hive_id, f"%{parsed['manufacturer']}%"))
        add_rows(cur.fetchall(), score=40, reason="manufacturer match")

    cur.close()
    conn.close()

    # Sort by score desc
    return sorted(candidates, key=lambda c: c["score"], reverse=True)


# ── Main ──────────────────────────────────────────────────────────────────
def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="Local image path (jpg/png/pdf)")
    parser.add_argument("--url",   help="Public image URL")
    parser.add_argument("--hive-id", help="Hive UUID for asset_nodes matching (optional)")
    parser.add_argument("--text",  help="Skip OCR; provide raw text directly (for testing)")
    args = parser.parse_args(argv)

    if not (args.image or args.url or args.text):
        print("ERROR: provide --image, --url, or --text")
        return 2

    print("=" * 70)
    print("DAY 3 TRACK D: EQUIPMENT LABEL OCR")
    print("=" * 70)

    content = ""

    if args.text:
        print("\n[TEST MODE] Using --text directly (no Azure call)")
        content = args.text
    else:
        # Load Azure credentials
        env = load_env(ROOT / ".env.azure")
        endpoint = env.get("AZURE_DOC_INTELLIGENCE_ENDPOINT", "").rstrip("/")
        key      = env.get("AZURE_DOC_INTELLIGENCE_KEY", "")
        if not endpoint or not key:
            print("ERROR: AZURE_DOC_INTELLIGENCE_ENDPOINT or KEY missing in .env.azure")
            return 1

        print(f"\nEndpoint: {endpoint}")
        if args.image:
            image_path = Path(args.image)
            if not image_path.exists():
                print(f"ERROR: image not found: {image_path}")
                return 1
            print(f"Submitting image: {image_path.name} ({image_path.stat().st_size / 1024:.1f} KB)")
            op_loc = submit_image_bytes(endpoint, key, image_path)
        else:
            print(f"Submitting URL: {args.url}")
            op_loc = submit_image_url(endpoint, key, args.url)

        print(f"Operation-Location: {op_loc[:80]}...")
        print("Polling for OCR result...")
        result = poll_result(op_loc, key)
        content = result.get("analyzeResult", {}).get("content", "")
        pages   = result.get("analyzeResult", {}).get("pages", [])
        print(f"\n[OK] Pages: {len(pages)}, chars: {len(content)}")

    print("\n--- OCR text (first 500 chars) ---")
    print(content[:500])
    print("--- end ---")

    # Parse
    parsed = parse_nameplate(content)
    print("\n--- Parsed fields ---")
    if parsed:
        for k, v in parsed.items():
            print(f"  {k}: {v}")
    else:
        print("  (no structured fields detected)")

    # Match against asset_nodes
    if args.hive_id and parsed:
        print(f"\n--- Matching against asset_nodes (hive: {args.hive_id[:8]}...) ---")
        matches = match_against_assets(parsed, args.hive_id)
        if matches:
            for m in matches[:5]:
                print(f"  score={m['score']:3d} | {m['tag'] or '(no tag)':20s} | {m['name'] or '(no name)':30s} | reason: {m['match_reason']}")
            print(f"\n[OK] Top match: asset_nodes.id = {matches[0]['id']}")
        else:
            print("  no matches — this would be a NEW asset registration")
            print("\nSuggested asset_nodes payload:")
            print(json.dumps({
                "hive_id":      args.hive_id,
                "manufacturer": parsed.get("manufacturer"),
                "model":        parsed.get("model"),
                "serial_no":    parsed.get("serial_no"),
                "name":         f"{parsed.get('manufacturer', '?')} {parsed.get('model', '?')}".strip(),
                "lifecycle":    "operating",
                "status":       "pending_approval",
            }, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
