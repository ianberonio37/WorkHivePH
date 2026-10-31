"""validate_no_call_to_nothing.py - a page calls a function that nothing defines.

WHY (2026-10-30, HS L3, walked live): hive.html's live PM handler called showHiveToast(...) - a name defined in no page
and no script, since the "Hive Board PM integration" commit that wrote the call. Every teammate's PM completion threw
ReferenceError inside the realtime callback and the "completed PM" toast never once appeared. Nothing ran the line
until a person stood in the room when a teammate finished a PM; no gate read it.

WHAT IT READS: every product page's inline <script> blocks (the root's .html files). A BARE call - `name(`, not
`.name(` / `new name(` / a declaration - whose name is defined NOWHERE in the product's pages and scripts (no
`function name`, no `name =`, `name:`, no parameter or destructured binding, no `window.name`), is not a browser or
library global, and is not behind a `typeof name` guard on that page. Being defined in some other page is enough to
pass: the rule catches a name that exists nowhere at all, which is always a fault.

INSTRUMENT NOTES: names are collected from the RAW script text (a definition misread as "defined" can only lose a
finding, never invent one); calls are read from the code with strings, comments and regex literals removed, so a word
in a sentence or a CSS value ('var(--x)', 'rgba(') is never read as a call. A regex literal holding a quote (/'/g) is
skipped whole - read as a string opening, it swallowed the code after it and hid real definitions (308 false calls on
the first run).

  python tools/validate_no_call_to_nothing.py           # exit 1 on any call to nothing
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# browser, language and library globals a page may call bare
GLOBALS = set('''
setTimeout clearTimeout setInterval clearInterval requestAnimationFrame cancelAnimationFrame queueMicrotask
requestIdleCallback cancelIdleCallback fetch alert confirm prompt open close print atob btoa structuredClone
encodeURIComponent decodeURIComponent encodeURI decodeURI escape unescape parseInt parseFloat isNaN isFinite
Number String Boolean Array Object Symbol BigInt Date RegExp Error TypeError RangeError SyntaxError Promise Map Set
WeakMap WeakSet JSON Math Intl Proxy Reflect URL URLSearchParams Blob File FileReader FormData Headers Request
Response AbortController TextEncoder TextDecoder Image Audio Option Event CustomEvent MutationObserver
IntersectionObserver ResizeObserver PerformanceObserver Worker SharedWorker WebSocket EventSource BroadcastChannel
getComputedStyle matchMedia scrollTo scrollBy postMessage importScripts require define import eval
Function Uint8Array Int8Array Uint16Array Int16Array Uint32Array Int32Array Float32Array Float64Array ArrayBuffer
DataView Notification NodeFilter DOMParser XMLSerializer XMLHttpRequest crypto Chart L mermaid marked DOMPurify
html2canvas html2pdf jsPDF QRCode Html5Qrcode Tesseract pdfjsLib JsBarcode supabase gtag dataLayer Sentry plausible
lucide Papa XLSX dayjs moment echarts d3 Prism hljs katex ApexCharts Sortable Hammer createImageBitmap
OffscreenCanvas Path2D DOMMatrix DOMRect FontFace CSS CSSStyleSheet ClipboardItem SpeechSynthesisUtterance
webkitSpeechRecognition SpeechRecognition AudioContext webkitAudioContext MediaRecorder MediaStream ReadableStream
WritableStream TransformStream CompressionStream DecompressionStream reportError
if for while switch catch return typeof function await async of in do with super this void delete yield throw
'''.split())

SCRIPT = re.compile(r'<script(?![^>]*\bsrc=)(?![^>]*type="application/(?:ld\+)?json")[^>]*>(.*?)</script>', re.S | re.I)
CALL = re.compile(r'(?<![\w$.])(?<!new )(?<!function )([A-Za-z_$][\w$]*)\s*\(')
DEFS = [
    re.compile(r'\bfunction\s*\*?\s*([A-Za-z_$][\w$]*)'),
    re.compile(r'\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)'),
    re.compile(r'(?<![\w$.])([A-Za-z_$][\w$]*)\s*=(?!=)'),
    re.compile(r'\bwindow\.([A-Za-z_$][\w$]*)\s*='),
    re.compile(r'(?:^|[,{(]\s*)([A-Za-z_$][\w$]*)\s*(?=[,)=]|\)\s*=>)', re.M),   # parameters / destructuring
    re.compile(r'([A-Za-z_$][\w$]*)\s*\([^()]*\)\s*\{'),                       # method shorthand
    re.compile(r'\bclass\s+([A-Za-z_$][\w$]*)'),
    re.compile(r'(?:^|[{,]\s*)([A-Za-z_$][\w$]*)\s*:', re.M),
]
REGEX_PREV = set('(,=:[!&|?{};+-*%<>~^')
REGEX_KW = re.compile(r'\b(return|typeof|case|in|of|delete|void|throw)$')


def product_files():
    # the product is the root's pages and scripts (subfolders are tools, seeders, other apps' templates)
    for f in sorted(os.listdir(ROOT)):
        if f.endswith('.html') or f.endswith('.js'):
            yield os.path.join(ROOT, f)


def strip_code(js):
    """The code with strings, comments and regex literals removed; a template literal keeps its ${...} code."""
    out, i, n = [], 0, len(js)
    while i < n:
        c = js[i]
        if js.startswith('//', i):
            j = js.find('\n', i)
            i = n if j < 0 else j
            continue
        if js.startswith('/*', i):
            j = js.find('*/', i + 2)
            i = n if j < 0 else j + 2
            continue
        if c == '/':
            k = len(out) - 1
            while k >= 0 and out[k] in ' \t\r\n':
                k -= 1
            prev = out[k] if k >= 0 else ''
            tail = ''.join(out[max(0, k - 7):k + 1])
            if prev == '' or prev in REGEX_PREV or REGEX_KW.search(tail):
                j, cls = i + 1, False
                while j < n and js[j] != '\n':
                    if js[j] == '\\':
                        j += 2
                        continue
                    if js[j] == '[':
                        cls = True
                    elif js[j] == ']':
                        cls = False
                    elif js[j] == '/' and not cls:
                        break
                    j += 1
                out.append(' /r/ ')
                i = j + 1
                while i < n and js[i].isalpha():
                    i += 1
                continue
        if c in '"\'':
            j = i + 1
            while j < n and js[j] != c and js[j] != '\n':
                j += 2 if js[j] == '\\' else 1
            out.append('""')
            i = j + 1
            continue
        if c == '`':
            j, buf = i + 1, []
            while j < n:
                if js[j] == '\\':
                    j += 2
                    continue
                if js.startswith('${', j):
                    k, d = j + 2, 1
                    while k < n and d:
                        if js[k] == '{':
                            d += 1
                        elif js[k] == '}':
                            d -= 1
                        k += 1
                    buf.append(' ' + strip_code(js[j + 2:k - 1]) + ' ')
                    j = k
                    continue
                if js[j] == '`':
                    break
                j += 1
            out.append('``' + ''.join(buf))
            i = j + 1
            continue
        out.append(c)
        i += 1
    return ''.join(out)


def main():
    defined, pages = set(GLOBALS), {}
    for path in product_files():
        src = io.open(path, encoding='utf-8', errors='replace').read()
        if path.endswith('.html'):
            # an HTML comment that mentions "<script>" (resume.html: "must be in DOM before the <script> block runs")
            # would open a script block in the middle of the markup
            src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
        raw = '\n'.join(SCRIPT.findall(src)) if path.endswith('.html') else src
        for rx in DEFS:
            defined.update(rx.findall(raw))
        if path.endswith('.html'):
            pages[path] = strip_code(raw)
    seen = []
    for path, code in sorted(pages.items()):
        guarded = set(re.findall(r'typeof\s+(?:window\.)?([A-Za-z_$][\w$]*)', code))
        names = set()
        for m in CALL.finditer(code):
            name = m.group(1)
            if name in defined or name in guarded or name in names:
                continue
            names.add(name)
            seen.append((os.path.relpath(path, ROOT), name))
    for rel, name in seen:
        print(f'  FAIL {rel}: calls {name}() - defined in no page and no script, and not behind a typeof guard')
    print(f"{'FAIL' if seen else 'PASS'} no-call-to-nothing - {len(seen)} bare call(s) to a name nothing defines across {len(pages)} page(s)")
    return 1 if seen else 0


if __name__ == '__main__':
    sys.exit(main())
