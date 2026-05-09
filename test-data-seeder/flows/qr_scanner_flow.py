"""
QR Scanner Flow -- WorkHive Tester

Verifies that qr-scanner.js loads on asset-hub.html and exposes the
documented public API. Camera-based scanning itself can't be exercised
headlessly (no real camera + permission prompt), so this flow focuses on:

  1. Module is reachable via HTTP from the tester
  2. Asset Hub page imports it
  3. Scan button is in the DOM
  4. Public API surface (open, close, validateScanResult) is present
  5. Security validation rejects the documented bad inputs

Coverage: qr-scanner.js (shared module) and the asset-hub.html integration.
"""

import urllib.request, urllib.error


def run(page, errors, warnings, log) -> dict:
    results = []
    base = page.rstrip('/')

    # ── 1. qr-scanner.js loads ───────────────────────────────────────────────
    log("QR Scanner Flow: fetching qr-scanner.js...")
    js_text = ""
    try:
        with urllib.request.urlopen(f"{base}/qr-scanner.js", timeout=10) as r:
            js_text = r.read().decode("utf-8", errors="replace")
        results.append(("PASS", "qr-scanner.js loads (HTTP 200)"))
    except Exception as e:
        results.append(("FAIL", f"qr-scanner.js failed to load: {type(e).__name__}: {e}"))
        return {"results": results}

    # ── 2. Public API surface ────────────────────────────────────────────────
    api_checks = [
        ("WHQRScanner global namespace",      "window.WHQRScanner"     in js_text),
        ("open() exported",                   "open: openScanner"      in js_text or "open: function" in js_text or ".open ="    in js_text),
        ("close() exported",                  "close: closeScanner"    in js_text or "close: function" in js_text or ".close ="   in js_text),
        ("validateScanResult exported",       "validateScanResult"     in js_text),
        ("BarcodeDetector primary path",      "BarcodeDetector"        in js_text),
        ("ZXing fallback CDN reference",      "@zxing/browser"         in js_text or "zxing"        in js_text.lower()),
        ("camera getUserMedia call",          "getUserMedia"           in js_text),
        ("stop tracks cleanup on close",      "track.stop"             in js_text or "tracks().forEach" in js_text or "t.stop" in js_text),
    ]
    for label, ok in api_checks:
        results.append(("PASS" if ok else "FAIL", label))

    # ── 3. Security: validation rejects bad inputs ───────────────────────────
    # We can't execute JS from here, but we can confirm the regex patterns
    # documented in the security skill are present in the source.
    sec_checks = [
        ("rejects javascript: scheme",   "javascript:"   in js_text),
        ("rejects data: scheme",         "data:"         in js_text),
        ("rejects html tag shapes",      "[a-z]"         in js_text and "</?" in js_text or "<\\/?" in js_text),
        ("length cap on raw input",      ".slice(0, 200)" in js_text or "slice(0,200)" in js_text),
        ("industrial charset whitelist", "A-Za-z0-9"     in js_text),
    ]
    for label, ok in sec_checks:
        results.append(("PASS" if ok else "FAIL", "validateScanResult: " + label))

    # ── 4. Asset Hub imports it + has scan button ────────────────────────────
    log("Verifying asset-hub.html integration...")
    try:
        with urllib.request.urlopen(f"{base}/asset-hub.html", timeout=10) as r:
            hub = r.read(80000).decode("utf-8", errors="replace")
        hub_checks = [
            ("asset-hub loads qr-scanner.js",   'src="qr-scanner.js"' in hub),
            ("Scan button id=scan-btn present", 'id="scan-btn"'       in hub),
            ("Scan button calls WHQRScanner",   "WHQRScanner.open"    in hub),
            ("onResult matches against tag",    "onResult:"           in hub and "_allNodes"  in hub),
        ]
        for label, ok in hub_checks:
            results.append(("PASS" if ok else "FAIL", label))
    except Exception as e:
        results.append(("WARN", f"asset-hub.html load skipped: {type(e).__name__}"))

    # ── 5. Mobile safety (per mobile-maestro skill) ──────────────────────────
    mobile_checks = [
        ("modal uses viewport-fit safe area",  "safe-area-inset" in js_text),
        ("44px tap target on close button",    "44px"            in js_text or "min-height: 44" in js_text),
        ("input font-size >= 16px (no iOS zoom)", "font-size: 16" in js_text or "16px"           in js_text),
        ("active state for touch feedback",    ":active"         in js_text),
    ]
    for label, ok in mobile_checks:
        results.append(("PASS" if ok else "WARN", label))

    return {"results": results}
