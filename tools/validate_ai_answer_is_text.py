"""validate_ai_answer_is_text.py - a model's answer reaches the screen only when it IS text.

THE CLASS (LM-S walks, 2026-10-07): eight render paths took a field of a model response - answer, reply, summary,
description, lessons_text, executive_summary, hero_finding, headline - and wrote it to the screen or into a form
through a path that stringifies whatever it is given: String(x), el.textContent = x, el.value = x, escHtml(x), or
x.replace(...). A model that returned structured output instead of text then put the literal words "[object Object]"
in a worker's chat (the companion on 29 pages), in Asset Brain's answer box, in a seller's listing description, in the
PH Intelligence report and in the alert feed - or threw ("actions.map is not a function") where a list was expected.
No gate saw any of it: the XSS and escHtml gates check that text is ESCAPED, not that it is TEXT.

THE RULE: inside the response-handling window of a call to a model function (the lines after functions.invoke('<fn>')
or a fetch of /functions/v1/<fn>), a model field may be written through one of those stringifying paths only on a
line that also checks its type (typeof ... === 'string', or Array.isArray for a list).

    python tools/validate_ai_answer_is_text.py            # PASS / FAIL over the production pages
    python tools/validate_ai_answer_is_text.py --selftest # the rule's teeth on fixed fixtures
"""
from __future__ import annotations

import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# the edge functions whose response is model output (the LM walker's MODEL_FNS, plus the gateway)
MODEL_FNS = {
    "ai-gateway", "ai-orchestrator", "asset-brain-query", "semantic-search", "agentic-rag-loop", "voice-journal-agent",
    "voice-logbook-entry", "voice-report-intent", "voice-action-router", "resume-polish", "resume-extract",
    "marketplace-listing-assist", "project-orchestrator", "intelligence-report", "fmea-populator", "batch-risk-scoring",
    "analytics-orchestrator", "shift-planner-orchestrator", "visual-defect-capture", "equipment-label-ocr",
}
FIELDS = ("answer|reply|summary|headline|description|lessons_text|executive_summary|hero_finding|lessons_synthesis|"
          "briefing|seasonal_insight|recommendation")
REF = r"[A-Za-z_$][\w$]*(?:\??\.[\w$]+)*"
BAD = [
    ("String() of a model field", re.compile(r"String\(\s*\(*\s*[^;]*?\b" + REF + r"\??\.(?:" + FIELDS + r")\b")),
    ("a model field written to text or a form value",
     re.compile(r"\.(?:value|textContent|innerText)\s*=\s*(?:" + REF + r"\??\.(?:" + FIELDS + r")|data\??\.name)\b(?!\s*\()")),
    ("a model field passed to the HTML escaper", re.compile(r"\b(?:e|escHtml)\(\s*\(?\s*" + REF + r"\??\.(?:" + FIELDS + r")\b")),
    ("a model field used as a string without a check", re.compile(r"\.(?:" + FIELDS + r")\s*(?:\|\|\s*'[^']*'\s*\)\s*)?\.replace\(")),
]
CHECKED = re.compile(r"typeof\b|Array\.isArray|_answerText\(|_txt\(|nTxt\(")
CALL = re.compile(r"""functions\.invoke\(\s*['"]([\w-]+)['"]|functions/v1/([\w-]+)""")
WINDOW = 90
NEXT_FN = re.compile(r"^\s*(?:async\s+)?function\s+[\w$]+\s*\(")
SKIP_DIRS = {"tools", "tests", "node_modules", "supabase", ".tmp", "test-data-seeder", "seeders", "workflows"}


def scan_text(text: str, name: str) -> list[str]:
    lines = text.splitlines()
    windows: set[int] = set()
    for i, ln in enumerate(lines):
        for m in CALL.finditer(ln):
            if (m.group(1) or m.group(2)) in MODEL_FNS:
                end = min(len(lines), i + WINDOW)
                for j in range(i + 1, end):
                    if NEXT_FN.match(lines[j]):
                        end = j
                        break
                windows.update(range(i, end))
    out = []
    for i in sorted(windows):
        ln = lines[i]
        code = ln.split("//", 1)[0] if not ln.lstrip().startswith(("//", "*", "/*")) else ""
        if not code.strip() or CHECKED.search(code):
            continue
        for label, rx in BAD:
            if rx.search(code):
                out.append(f"{name}:{i + 1}: {label}: {code.strip()[:140]}")
                break
    return out


def production_files() -> list[Path]:
    files = []
    for p in list(ROOT.glob("*.html")) + list(ROOT.glob("*.js")):
        if p.name.startswith(("test", "_", "survey_")) or p.name.endswith((".test.js", ".spec.js", "_battery.js")):
            continue
        files.append(p)
    return sorted(files)


def selftest() -> int:
    bad = {
        "companion": "const { data } = await _wc.functions.invoke('ai-gateway', { body });\n"
                     "return String((data && data.data && data.data.answer) || (data && data.answer) || '').trim();",
        "asset-brain": "const r = await db.functions.invoke('asset-brain-query', { body });\nansEl.innerHTML = e(data.answer || '(no answer)');",
        "listing": "const { data } = await db.functions.invoke('marketplace-listing-assist', { body });\ndescEl.value = data.description;",
        "narrative": "const { data } = await db.functions.invoke('project-orchestrator', { body });\n"
                     "const h = `${(data.executive_summary || '').replace(/&/g,'&amp;')}`;",
        "fetch": "const r = await fetch(`${URL}/functions/v1/ai-gateway`, o);\nconst answer = String((data && data.answer) || '').trim();",
        "data-name": "const { data } = await db.functions.invoke('project-orchestrator', { body });\n$('wiz-name').value = data.name;",
    }
    good = {
        "typed": "const { data } = await db.functions.invoke('ai-gateway', { body });\n"
                 "const a = (data && typeof data.answer === 'string') ? data.answer.trim() : '';",
        "helper": "const { data } = await _wc.functions.invoke('ai-gateway', { body });\nreturn _answerText(data);",
        "not-ai": "const { data } = await db.functions.invoke('export-hive-data', { body });\nel.textContent = data.summary;",
        "db-read": "const { data } = await db.from('work_orders').select('*');\nel.value = data.description;",
        "db-name": "const { data } = await db.functions.invoke('project-orchestrator', { body });\n$('f-name').value = _detail.name;",
        "next-fn": "const { data } = await db.functions.invoke('project-orchestrator', { body });\n}\nfunction openDetail() {\n"
                   "  $('f-desc').value = _detail.description || '';",
    }
    fails = []
    for k, src in bad.items():
        if not scan_text(src, k):
            fails.append(f"bad fixture '{k}' was NOT flagged")
    for k, src in good.items():
        hits = scan_text(src, k)
        if hits:
            fails.append(f"good fixture '{k}' WAS flagged: {hits}")
    for f in fails:
        print("  SELFTEST FAIL", f)
    print(f"selftest: {len(bad)} bad fixtures flagged, {len(good)} good fixtures clean" if not fails else "selftest FAILED")
    return 1 if fails else 0


def main() -> int:
    if "--selftest" in sys.argv:
        return selftest()
    hits = []
    files = production_files()
    for p in files:
        hits += scan_text(io.open(p, encoding="utf-8", errors="replace").read(), p.name)
    if hits:
        print(f"FAIL ai_answer_is_text - {len(hits)} model field(s) reach the screen without a text check:")
        for h in hits:
            print("  " + h)
        return 1
    print(f"PASS ai_answer_is_text - every model field in {len(files)} production files reaches the screen only as checked text")
    return 0


if __name__ == "__main__":
    sys.exit(main())
