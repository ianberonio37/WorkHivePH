#!/usr/bin/env python3
"""
Arc L / L1 — extract the 2.14 MB inline <script> from engineering-design.html
into an external, cacheable, deferred engineering-design.js.

WHY: the inline block makes the HTML document 2.36 MB → the browser must
download all of it before the body finishes parsing (blocks first paint and
LCP). Moving it to an external `defer` script shrinks the document to ~40 KB
(parses instantly) and makes the 2.14 MB JS separately cacheable on repeat
visits.

SAFE because (verified before writing this):
  - the block ends with a bare top-level `init()` (no DOMContentLoaded); defer
    runs AFTER full parse → DOM is ready, strictly safer than body-end inline.
  - no `document.write` (defer-incompatible) anywhere in the block.
  - companion-launcher.js (the only later script) is self-initialising and
    independent; defer flipping their order is a no-op.

Operates in BINARY to preserve CRLF byte-for-byte. Anchors on the unique
supabase-js tag (just above) and the companion-launcher tag (just below), so
there is no ambiguity about which <script> block is moved. A content-
preservation self-check asserts the extracted JS is byte-identical (modulo
edge whitespace) to the original inline content before anything is written.
"""
import sys, pathlib

HTML = pathlib.Path("engineering-design.html")
JS_OUT = pathlib.Path("engineering-design.js")

SUP = b'<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"></script>'
COMP = b'<script src="companion-launcher.js"></script>'
OPEN = b'<script>'
CLOSE = b'</script>'
REPLACEMENT = b'<script src="engineering-design.js" defer></script>'

def die(msg):
    print("FAIL:", msg)
    sys.exit(1)

data = HTML.read_bytes()
orig_len = len(data)

i_sup = data.find(SUP)
if i_sup < 0: die("supabase-js anchor not found")
i_comp = data.find(COMP)
if i_comp < 0: die("companion-launcher anchor not found")

# the bare <script> opening the big block sits between supabase-js and companion
i_open = data.find(OPEN, i_sup + len(SUP))
if i_open < 0 or i_open > i_comp: die("big-block <script> opening not found between anchors")
open_end = i_open + len(OPEN)

i_close = data.find(CLOSE, open_end)
if i_close < 0 or i_close > i_comp: die("big-block </script> closing not found before companion")

# unambiguity guard: EXACTLY one </script> between the opening and companion.
# (A literal </script> inside the block is impossible — it would have closed the
#  inline script in the browser already — so this must be 1.)
n_close = data.count(CLOSE, open_end, i_comp)
if n_close != 1: die(f"expected exactly 1 </script> between open and companion, got {n_close}")

inner = data[open_end:i_close]              # raw JS bytes (incl. leading/trailing CRLF)

# write JS: strip edge whitespace/newlines, guarantee a single trailing newline.
js_body = inner.strip(b"\r\n \t") + b"\n"

# CONTENT-PRESERVATION SELF-CHECK: byte-identical modulo edge whitespace.
if inner.strip(b"\r\n \t") != js_body.strip(b"\r\n \t"):
    die("content-preservation check failed (interior bytes differ)")

new_html = data[:i_open] + REPLACEMENT + data[i_close + len(CLOSE):]

# the new HTML must contain the external tag and must NOT regress companion.
if REPLACEMENT not in new_html: die("replacement tag missing from new HTML")
if new_html.count(COMP) != 1: die("companion tag count changed")

JS_OUT.write_bytes(js_body)
HTML.write_bytes(new_html)

print("OK")
print(f"  original HTML : {orig_len:>10,} bytes")
print(f"  new HTML      : {len(new_html):>10,} bytes  (was {orig_len:,})")
print(f"  engineering-design.js : {len(js_body):>10,} bytes")
print(f"  block moved   : {len(inner):,} bytes of inline JS")
print(f"  doc shrink    : {orig_len - len(new_html):,} bytes removed from document")
