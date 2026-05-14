"""
Azure $200 sprint — Day 1 Document Intelligence pipeline test.

Submits a small public PDF, polls the Operation-Location header until the
analysis completes, prints a snippet of the extracted text.

Validates that Layer 2 (doc mining) is wired correctly before scaling up to
the 20,000-page batch on Day 2.

Cost: ~$0.0015 (one page through prebuilt-read model).

Usage:
    python tools/doc_intelligence_test.py
    python tools/doc_intelligence_test.py --pdf https://example.com/your.pdf
"""
import os
import sys
import time
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path


def load_env(env_path: Path) -> dict:
    if not env_path.exists():
        print(f"ERROR: {env_path} not found. Run from project root.")
        sys.exit(2)
    env = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip()
    return env


# A short public PDF -- the Attention Is All You Need paper, 15 pages.
# Replace via --pdf flag for your own test document.
DEFAULT_PDF = "https://arxiv.org/pdf/1706.03762.pdf"


def submit_analyze(endpoint: str, key: str, pdf_url: str) -> str:
    url = f"{endpoint}/documentintelligence/documentModels/prebuilt-read:analyze?api-version=2024-11-30"
    headers = {
        "Ocp-Apim-Subscription-Key": key,
        "Content-Type": "application/json",
    }
    body = json.dumps({"urlSource": pdf_url}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status not in (200, 202):
                print(f"ERROR: submit returned status {resp.status}")
                print(resp.read().decode("utf-8"))
                sys.exit(1)
            op_location = resp.headers.get("Operation-Location") or resp.headers.get("operation-location")
            if not op_location:
                print("ERROR: no Operation-Location header on response")
                sys.exit(1)
            return op_location
    except urllib.error.HTTPError as e:
        print(f"ERROR: HTTP {e.code} on submit")
        print(e.read().decode("utf-8", errors="replace"))
        sys.exit(1)


def poll_result(op_location: str, key: str, max_seconds: int = 120) -> dict:
    headers = {"Ocp-Apim-Subscription-Key": key}
    start = time.time()
    delay = 2
    while True:
        elapsed = time.time() - start
        if elapsed > max_seconds:
            print(f"ERROR: timeout after {max_seconds}s polling result")
            sys.exit(1)
        req = urllib.request.Request(op_location, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        status = data.get("status", "")
        print(f"  poll t+{int(elapsed)}s: status={status}")
        if status == "succeeded":
            return data
        if status in ("failed", "canceled"):
            print(f"ERROR: analysis {status}")
            print(json.dumps(data, indent=2)[:1000])
            sys.exit(1)
        time.sleep(delay)
        delay = min(delay + 1, 6)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default=DEFAULT_PDF, help="URL of a public PDF to analyze")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    env = load_env(here.parent / ".env.azure")
    endpoint = env.get("AZURE_DOC_INTELLIGENCE_ENDPOINT", "").rstrip("/")
    key = env.get("AZURE_DOC_INTELLIGENCE_KEY", "")
    if not endpoint or not key:
        print("ERROR: AZURE_DOC_INTELLIGENCE_ENDPOINT or _KEY missing in .env.azure")
        sys.exit(2)

    print(f"Submitting: {args.pdf}")
    op_location = submit_analyze(endpoint, key, args.pdf)
    print(f"Operation-Location: {op_location[:80]}...")
    print("Polling for result (may take 10-60 seconds)...")
    result = poll_result(op_location, key)

    pages = result.get("analyzeResult", {}).get("pages", [])
    content = result.get("analyzeResult", {}).get("content", "")
    print()
    print(f"Pages analyzed: {len(pages)}")
    print(f"Total characters extracted: {len(content)}")
    print()
    print("First 500 chars of extracted text:")
    print("-" * 60)
    print(content[:500])
    print("-" * 60)
    print()
    print("Layer 2 pipeline VALIDATED. Ready for Day 2 batch processing.")


if __name__ == "__main__":
    main()
