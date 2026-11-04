#!/usr/bin/env python3
"""geo_sov_free_run.py - the monthly AI share-of-voice run on FREE-TIER live answer engines (KA-V, 2026-11-04).

geo_sov_audit.py is the scoreboard: a fixed prompt set (prompt_audit_queries.json), and per (prompt, engine) whether
the answer CITED a workhiveph.com page, MENTIONED WorkHive, or RECOMMENDED it. Its reading must come from engines
that search the live web as they answer - a base model does not know a new brand and cannot stand in. The sheet was
filled by hand, which left the 45 KA-V rows waiting on a person every month.

★FREE, AND ON THE TERMS OF EACH SERVICE (Ian, 2026-11-04: "find something else with a free tier"). Scripting the
consumer chat apps breaks their terms, so this uses the providers' own APIs, on the free tiers whose keys are already
in .env:
  groq_browser   Groq openai/gpt-oss-20b with its built-in browser_search tool (live web, sources returned)
  mistral_web    Mistral's conversations API with the web_search tool (live web, tool_reference sources)
  gemini_grounded  Gemini with Grounding with Google Search - opt-in (--with-gemini): this key's free tier is 20
                 requests a day per model, shared with local testing of the app's own AI features
Perplexity's paid API is not used.

Each cell records the evidence beside the verdict (the workhiveph.com sources, the sentence that named WorkHive), so a
reading can be audited and a drop traced. A cell an engine could not answer (a rate limit after one retry, an error) is
recorded as None and excluded from the rates by geo_sov_audit's own rule - never as a miss.

  python tools/geo_sov_free_run.py [--engines groq_browser,mistral_web] [--only id1,id2] [--with-gemini]
  -> geo_sov_runs/<YYYY-MM>.json   (then: python tools/geo_sov_audit.py --score geo_sov_runs/<YYYY-MM>.json)
  python tools/geo_sov_free_run.py --self-test
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
QUERIES = ROOT / "prompt_audit_queries.json"
OUT_DIR = ROOT / "geo_sov_runs"
if sys.platform == "win32" and sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding="utf-8", errors="replace")

HOST = "workhiveph.com"
MENTION = re.compile(r"\bwork\s?hive\b", re.I)
# "Tools like WorkHive offer a free worker-facing logbook layer" (Mistral, sap-maximo-integration) is a recommendation
# the first cue list missed; offers / such as / tools like are how an answer engine puts a product forward
RECOMMEND = re.compile(r"\b(recommend|try|consider|use|using|best|top|option|good choice|worth|free tool|platform|offers?|"
                       r"such as|tools? like|solutions? like)\w*", re.I)
NEGATIVE = re.compile(r"\b(avoid|not recommended|unreliable|limited|outdated|poor|lacks)\b", re.I)
MODELS = {"groq_browser": "openai/gpt-oss-20b", "mistral_web": "mistral-medium-latest", "gemini_grounded": "gemini-2.5-flash"}
GROQ_MODELS = ("openai/gpt-oss-20b", "openai/gpt-oss-120b")
# Mistral's web_search has its own rate limit below the chat one: at 2s apart it refused 38 of 55 ("web_search rate
# limit reached"), so it is asked every 12s and a refusal waits a minute before its one retry.
PACE = {"groq_browser": 3.0, "mistral_web": 12.0, "gemini_grounded": 7.0}
SPENT: set = set()   # engines whose free day ran out during this run - asked again on the next run, not 110 more times now


def env(name: str) -> str:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"')
    return ""


def _post(url: str, body: dict, headers: dict) -> tuple[int, object, float]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "User-Agent": "workhive-sov/1", **headers})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read().decode()), 0.0
    except urllib.error.HTTPError as e:
        wait = float(e.headers.get("retry-after") or 0) if e.headers else 0.0
        return e.code, e.read().decode()[:400], wait


def ask(engine: str, prompt: str) -> tuple[str, list[str]] | None:
    """(answer text, source urls) from one live engine, or None when it could not answer after one paced retry."""
    if engine == "groq_browser":
        # ★A FREE DAY IS A TOKEN BUDGET, PER MODEL (2026-11-04): Groq's free tier gives each model 200,000 tokens a day,
        # and a browser-search answer carries its search results in context - a few prompts spend a model's day. When
        # one model's day is spent (a 429 whose retry is minutes away) the other gpt-oss model, with its own budget, answers.
        for model in GROQ_MODELS:
            st, b, wait = _post("https://api.groq.com/openai/v1/chat/completions",
                                {"model": model, "messages": [{"role": "user", "content": prompt}],
                                 "tools": [{"type": "browser_search"}], "tool_choice": "required"},
                                {"Authorization": "Bearer " + env("GROQ_API_KEY")})
            if st == 200:
                m = b["choices"][0]["message"]
                urls = [s.get("url") for t in (m.get("executed_tools") or [])
                        for s in ((t.get("search_results") or {}).get("results") or []) if s.get("url")]
                return m.get("content") or "", urls
            if st == 429 and wait and wait <= 90:
                time.sleep(wait)
                return ask(engine, prompt)
        print(f"    {engine}: every gpt-oss model's free day is spent (HTTP {st}) - resume tomorrow", flush=True)
        SPENT.add(engine)
        return None
    for attempt in (1, 2):
        if engine == "groq_browser":
            raise AssertionError("handled above")
        elif engine == "mistral_web":
            # ★AN ANSWER FROM MEMORY IS NOT A LIVE READING. Left to choose, the model answered abc-spare-parts with 0 sources,
            # and Mistral refuses tool_choice 'required' for its built-in connectors - so it is told what an answer engine
            # is, and the second attempt asks for the search in the input itself (generic questions like "how to
            # calculate OEE" were still answered from memory). The prompt's own words are unchanged.
            text_in = prompt if attempt == 1 else prompt + "\n\n(Search the web for current sources and cite them.)"
            st, b, wait = _post("https://api.mistral.ai/v1/conversations",
                                {"model": MODELS[engine], "inputs": text_in, "tools": [{"type": "web_search"}], "store": False,
                                 "instructions": "You are a web answer engine. Search the web for every question before "
                                                 "answering, and cite the pages you used."},
                                {"Authorization": "Bearer " + env("MISTRAL_API_KEY")})
            if st == 200:
                text, urls = [], []
                for o in b.get("outputs") or []:
                    content = o.get("content")
                    if isinstance(content, str):
                        text.append(content)
                    for c in content if isinstance(content, list) else []:
                        if c.get("type") == "text":
                            text.append(c.get("text") or "")
                        elif c.get("type") == "tool_reference" and c.get("url"):
                            urls.append(c["url"])
                if urls:
                    return "".join(text), urls
                if attempt == 1:
                    time.sleep(PACE[engine])
                    continue
                print(f"    {engine}: answered without searching the web, twice - not recorded", flush=True)
                return None
        elif engine == "gemini_grounded":
            st, b, wait = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{MODELS[engine]}:generateContent",
                                {"contents": [{"parts": [{"text": prompt}]}], "tools": [{"google_search": {}}]},
                                {"x-goog-api-key": env("GEMINI_API_KEY")})
            if st == 200:
                c = b["candidates"][0]
                meta = c.get("groundingMetadata") or {}
                # grounding returns redirect URIs; the chunk TITLE carries the source's domain
                urls = [(ch.get("web") or {}).get("title") or (ch.get("web") or {}).get("uri") for ch in meta.get("groundingChunks") or []]
                return "".join(p.get("text", "") for p in c["content"]["parts"]), [u for u in urls if u]
        else:
            raise ValueError(engine)
        if st == 429 and attempt == 1 and wait <= 90:
            time.sleep(max(wait, 60 if engine == "mistral_web" else 20))
            continue
        print(f"    {engine}: HTTP {st} {str(b)[:120]}", flush=True)
        return None
    return None


def judge(text: str, urls: list[str]) -> dict:
    """The sheet's four fields from one answer, with the evidence that decided them."""
    ours = [u for u in urls if HOST in (u or "").lower()]
    cited = bool(ours) or HOST in text.lower()
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    named = [s.strip() for s in sentences if MENTION.search(s)]
    mentioned = bool(named)
    recommended = any(RECOMMEND.search(s) and not NEGATIVE.search(s) for s in named)
    negative = any(NEGATIVE.search(s) for s in named)
    return {"cited": cited, "mentioned": mentioned, "recommended": recommended,
            "sentiment": -1 if negative and not recommended else (1 if recommended else 0),
            "evidence": {"workhive_sources": ours[:5], "sources": len(urls), "named": named[:2]}}


def main() -> int:
    if "--self-test" in sys.argv:
        return self_test()
    arg = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d  # noqa: E731
    engines = arg("--engines", "groq_browser,mistral_web").split(",")
    if "--with-gemini" in sys.argv and "gemini_grounded" not in engines:
        engines.append("gemini_grounded")
    only = {x for x in arg("--only", "").split(",") if x}
    queries = [q for q in json.loads(QUERIES.read_text(encoding="utf-8"))["queries"] if not only or q["id"] in only]
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    OUT_DIR.mkdir(exist_ok=True)
    out_f = OUT_DIR / f"{month}.json"
    # one writer at a time: the scheduled daily pass and a hand-started run would otherwise both rewrite the month's file
    lock = ROOT / ".tmp" / "geo_sov_run.lock"
    lock.parent.mkdir(exist_ok=True)
    if lock.exists() and time.time() - lock.stat().st_mtime < 3 * 3600:
        print(f"another share-of-voice pass holds {lock.relative_to(ROOT)} - not starting a second writer")
        return 0
    lock.write_text(str(datetime.now(timezone.utc)), encoding="utf-8")
    try:
        return _run(engines, queries, month, out_f)
    finally:
        lock.unlink(missing_ok=True)


def _run(engines: list, queries: list, month: str, out_f: Path) -> int:
    sheet = json.loads(out_f.read_text(encoding="utf-8")) if out_f.exists() else {"_meta": {}, "results": {}}
    sheet["_meta"].update({"month": month, "engines": sorted(set(sheet["_meta"].get("engines", [])) | set(engines)),
                           "models": {e: MODELS[e] for e in engines}, "runner": "tools/geo_sov_free_run.py",
                           "free_tier": True, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    for i, q in enumerate(queries, 1):
        row = sheet["results"].setdefault(q["id"], {})
        for e in engines:
            if (row.get(e) or {}).get("cited") is not None:
                continue                      # already read this month: resume, never re-spend a free call
            if e in SPENT:
                continue                      # its free day is spent: the rest of the prompts wait for tomorrow's run
            got = ask(e, q["query"])
            row[e] = judge(*got) if got else {"cited": None, "mentioned": None, "recommended": None, "sentiment": None,
                                               "evidence": {"error": "the engine could not answer"}}
            out_f.write_text(json.dumps(sheet, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
            time.sleep(PACE[e])
        cells = " ".join(f"{e}:{'C' if (row.get(e) or {}).get('cited') else '-'}{'M' if (row.get(e) or {}).get('mentioned') else '-'}"
                         for e in engines)
        print(f"[{i}/{len(queries)}] {q['id']:<34} {cells}", flush=True)
    print(f"wrote {out_f.relative_to(ROOT)}  ->  python tools/geo_sov_audit.py --score {out_f.relative_to(ROOT).as_posix()}")
    if "--score" in sys.argv:     # the daily run scores the month too, so the voice trip reads the newest sheet
        import subprocess
        r = subprocess.run([sys.executable, str(ROOT / "tools" / "geo_sov_audit.py"), "--score", str(out_f)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print((r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr).strip() else "scored")
    return 0


def self_test() -> int:
    ok = True

    def t(name, cond):
        nonlocal ok
        ok &= bool(cond)
        print(("ok  " if cond else "XX  ") + name)
    j = judge("For small plants, try WorkHive, a free platform. Fiix is paid.", ["https://workhiveph.com/learn/x/", "https://fiix.com"])
    t("a workhiveph.com source is CITED and kept as evidence", j["cited"] and j["evidence"]["workhive_sources"])
    t("a sentence naming WorkHive with a recommending word is RECOMMENDED, sentiment 1", j["recommended"] and j["sentiment"] == 1)
    j2 = judge("Options include Fiix and UpKeep.", ["https://fiix.com"])
    t("an answer that never names WorkHive is not mentioned and not cited", not j2["mentioned"] and not j2["cited"])
    j3 = judge("WorkHive exists but users report it is unreliable.", [])
    t("a negative sentence about WorkHive is mentioned, not recommended, sentiment -1",
      j3["mentioned"] and not j3["recommended"] and j3["sentiment"] == -1)
    t("'Work Hive' spelled apart still counts as a mention", judge("Work Hive is listed.", [])["mentioned"])
    t("'tools like WorkHive offer ...' (the sap-maximo answer) is a recommendation",
      judge("Tools like WorkHive offer a free worker-facing logbook layer.", [])["recommended"])
    print("self-test " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
