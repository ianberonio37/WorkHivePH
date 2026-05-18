"""Day 5 — Layer 7: Seed multilingual_terms via Azure Translator F0 (free forever).

Builds a curated lookup table of ~250 industrial maintenance phrases pre-translated
to Tagalog (fil) and Visayan/Cebuano (ceb). Workers hit this cache before falling
back to the live LLM chain — gives instant, consistent terminology for the
most common terms (no LLM drift on "bearing", "lubrication", "lockout/tagout").

Free tier: 2,000,000 chars/month. This batch uses ~15,000 chars. Permanent room.

Source phrases organized by domain (matches multilingual_terms.domain field):
  equipment, problem, action, safety, measurement, documentation, role, status, time
"""
from __future__ import annotations

import os
import sys
import io
import json
import time
from pathlib import Path
from typing import Optional

import psycopg2
import requests
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env.azure")

# ── Curated phrase corpus ────────────────────────────────────────────────
# Keep concise — single nouns, short verb phrases. Long sentences translate
# poorly to a lookup; the LLM still handles them at runtime.
PHRASES: dict[str, list[tuple[str, str]]] = {
    "equipment": [
        ("motor", "electric motor / general"),
        ("pump", "pump / general"),
        ("bearing", "bearing / mechanical"),
        ("valve", "valve / general"),
        ("compressor", "compressor / pneumatic"),
        ("conveyor", "conveyor belt"),
        ("fan", "fan / ventilation"),
        ("gearbox", "gearbox / reducer"),
        ("seal", "mechanical seal"),
        ("filter", "filter element"),
        ("sensor", "sensor / instrument"),
        ("transformer", "electrical transformer"),
        ("breaker", "circuit breaker"),
        ("relay", "control relay"),
        ("contactor", "motor contactor"),
        ("cable", "electrical cable"),
        ("wire", "wire / conductor"),
        ("pipe", "pipe / piping"),
        ("hose", "flexible hose"),
        ("coupling", "shaft coupling"),
        ("belt", "drive belt"),
        ("chain", "drive chain"),
        ("gear", "gear / cog"),
        ("shaft", "rotating shaft"),
        ("blade", "fan/pump blade"),
        ("nozzle", "spray/discharge nozzle"),
        ("tank", "storage tank"),
        ("boiler", "steam boiler"),
        ("chiller", "chiller / cooling"),
        ("generator", "electric generator"),
        ("battery", "battery / storage"),
        ("panel", "control panel"),
        ("switch", "switch / disconnect"),
        ("gauge", "pressure/temperature gauge"),
        ("meter", "measurement device"),
    ],
    "problem": [
        ("leak", "fluid/gas leak"),
        ("oil leak", "oil leak / lubrication"),
        ("water leak", "water leak"),
        ("steam leak", "steam leak"),
        ("vibration", "abnormal vibration"),
        ("noise", "abnormal noise"),
        ("overheating", "overheating / hot"),
        ("smoke", "smoke from equipment"),
        ("spark", "electrical spark"),
        ("burn", "burn / burned"),
        ("corrosion", "rust / corrosion"),
        ("rust", "rust"),
        ("crack", "crack / fracture"),
        ("worn", "worn out"),
        ("loose", "loose / not tight"),
        ("broken", "broken / damaged"),
        ("stuck", "stuck / jammed"),
        ("blocked", "blocked / clogged"),
        ("dirty", "dirty / contaminated"),
        ("dry", "dry / no lubrication"),
        ("misalignment", "shaft misalignment"),
        ("imbalance", "rotor imbalance"),
        ("short circuit", "electrical short"),
        ("ground fault", "ground fault"),
        ("overload", "electrical/mechanical overload"),
        ("undervoltage", "low voltage"),
        ("overvoltage", "high voltage"),
        ("pressure drop", "pressure loss"),
        ("flow restriction", "reduced flow"),
        ("seal failure", "seal failed"),
        ("bearing failure", "bearing failed"),
        ("motor failure", "motor failed"),
        ("not starting", "will not start"),
        ("not stopping", "will not stop"),
        ("tripped", "breaker tripped"),
    ],
    "action": [
        ("inspect", "visual inspection"),
        ("check", "check / verify"),
        ("test", "functional test"),
        ("clean", "clean / wipe down"),
        ("lubricate", "apply lubrication"),
        ("grease", "apply grease"),
        ("oil", "apply oil"),
        ("replace", "replace / change out"),
        ("repair", "repair / fix"),
        ("adjust", "adjust / calibrate"),
        ("tighten", "tighten / torque"),
        ("loosen", "loosen / release"),
        ("install", "install / mount"),
        ("remove", "remove / dismount"),
        ("align", "align / center"),
        ("balance", "balance rotor"),
        ("measure", "measure / record"),
        ("record", "record / log"),
        ("report", "report problem"),
        ("escalate", "escalate to supervisor"),
        ("call supervisor", "call supervisor"),
        ("request parts", "request spare parts"),
        ("isolate", "isolate / shut down"),
        ("lock out", "lock out energy"),
        ("tag out", "tag the equipment"),
        ("start up", "start equipment"),
        ("shut down", "shut down equipment"),
        ("monitor", "monitor parameters"),
        ("log entry", "create logbook entry"),
        ("close work order", "close the work order"),
        ("open work order", "create a work order"),
        ("schedule pm", "schedule preventive maintenance"),
        ("complete pm", "complete preventive maintenance"),
        ("document", "document the work"),
        ("photograph", "take a photo"),
    ],
    "safety": [
        ("lockout tagout", "LOTO / lockout/tagout"),
        ("permit to work", "PTW / work permit"),
        ("hot work permit", "hot work permit"),
        ("confined space", "confined space entry"),
        ("ppe", "PPE / protective equipment"),
        ("hard hat", "safety helmet"),
        ("safety glasses", "safety glasses / goggles"),
        ("gloves", "safety gloves"),
        ("safety shoes", "safety footwear"),
        ("hearing protection", "ear protection"),
        ("respirator", "respirator / mask"),
        ("harness", "fall-arrest harness"),
        ("first aid", "first aid"),
        ("emergency stop", "emergency stop button"),
        ("evacuate", "evacuate the area"),
        ("hazard", "safety hazard"),
        ("risk", "risk / danger"),
        ("safe to work", "safe to proceed"),
        ("unsafe", "unsafe condition"),
        ("near miss", "near miss incident"),
        ("incident", "safety incident"),
        ("accident", "accident"),
        ("injury", "injury"),
        ("fire", "fire"),
        ("electrical shock", "electrical shock"),
        ("chemical spill", "chemical spill"),
        ("toolbox talk", "toolbox safety talk"),
        ("safety briefing", "safety briefing"),
    ],
    "measurement": [
        ("pressure", "pressure reading"),
        ("temperature", "temperature reading"),
        ("voltage", "voltage / electrical"),
        ("current", "electric current / amps"),
        ("speed", "rotational speed / RPM"),
        ("flow rate", "fluid flow rate"),
        ("level", "tank/sump level"),
        ("vibration level", "vibration amplitude"),
        ("noise level", "decibel level"),
        ("humidity", "relative humidity"),
        ("normal", "normal reading"),
        ("high", "high reading"),
        ("low", "low reading"),
        ("zero", "zero / no reading"),
        ("rising", "rising / increasing"),
        ("falling", "falling / decreasing"),
        ("stable", "stable / steady"),
        ("fluctuating", "unstable / changing"),
    ],
    "documentation": [
        ("logbook", "maintenance logbook"),
        ("work order", "work order / job ticket"),
        ("checklist", "inspection checklist"),
        ("report", "maintenance report"),
        ("manual", "equipment manual"),
        ("drawing", "engineering drawing"),
        ("nameplate", "equipment nameplate"),
        ("serial number", "serial number"),
        ("model number", "model number"),
        ("schedule", "PM schedule"),
        ("history", "maintenance history"),
        ("audit", "maintenance audit"),
    ],
    "role": [
        ("technician", "maintenance technician"),
        ("operator", "machine operator"),
        ("supervisor", "shift supervisor"),
        ("engineer", "maintenance engineer"),
        ("planner", "maintenance planner"),
        ("foreman", "foreman / lead hand"),
        ("contractor", "outside contractor"),
        ("apprentice", "trainee / apprentice"),
        ("manager", "plant manager"),
        ("electrician", "electrician"),
        ("mechanic", "mechanic / fitter"),
        ("welder", "welder"),
        ("operator on shift", "shift operator"),
    ],
    "status": [
        ("running", "running / operating"),
        ("stopped", "stopped / not running"),
        ("idle", "idle / standby"),
        ("offline", "offline / down"),
        ("online", "online / available"),
        ("under repair", "under repair"),
        ("waiting parts", "waiting for parts"),
        ("waiting permit", "waiting for permit"),
        ("ready", "ready / good to go"),
        ("not ready", "not ready"),
        ("urgent", "urgent / critical"),
        ("breakdown", "breakdown / failure"),
        ("preventive", "preventive maintenance"),
        ("corrective", "corrective repair"),
        ("predictive", "predictive maintenance"),
        ("emergency", "emergency / critical"),
    ],
    "time": [
        ("now", "now / immediately"),
        ("today", "today"),
        ("tomorrow", "tomorrow"),
        ("yesterday", "yesterday"),
        ("this week", "this week"),
        ("next week", "next week"),
        ("morning shift", "morning shift"),
        ("afternoon shift", "afternoon shift"),
        ("night shift", "night shift"),
        ("graveyard shift", "graveyard shift"),
        ("overtime", "overtime work"),
        ("holiday", "holiday / non-working day"),
        ("scheduled", "scheduled"),
        ("overdue", "overdue / past due"),
        ("on time", "on time"),
    ],
}


# ── Azure Translator F0 batch call ───────────────────────────────────────
TRANSLATOR_KEY    = os.getenv("AZURE_TRANSLATOR_KEY")
TRANSLATOR_REGION = os.getenv("AZURE_TRANSLATOR_REGION", "global")
# NOTE: Azure Translator supports Filipino (`fil`) but NOT Cebuano/Visayan.
# We translate to Tagalog only here; visayan_term stays NULL and can be filled
# later via the free LLM chain (Groq llama-3.3-70b prompted for Cebuano) or
# crowd-sourced corrections from PH workers.
TRANSLATOR_URL = "https://api.cognitive.microsofttranslator.com/translate?api-version=3.0&from=en&to=fil"


def translate_batch(english_terms: list[str]) -> list[dict[str, str]]:
    """Translator accepts up to 100 items per request. Returns parallel list of
    {tagalog} dicts (visayan stays empty — Translator F0 has no ceb)."""
    if not english_terms:
        return []

    headers = {
        "Ocp-Apim-Subscription-Key": TRANSLATOR_KEY,
        "Ocp-Apim-Subscription-Region": TRANSLATOR_REGION,
        "Content-Type": "application/json",
    }
    body = [{"Text": t} for t in english_terms]
    res = requests.post(TRANSLATOR_URL, headers=headers, json=body, timeout=30)
    if not res.ok:
        raise RuntimeError(f"Translator {res.status_code}: {res.text[:200]}")

    data = res.json()
    out: list[dict[str, str]] = []
    for item in data:
        tagalog = ""
        for t in item.get("translations", []):
            if t.get("to") == "fil":
                tagalog = t.get("text", "")
        out.append({"tagalog": tagalog, "visayan": ""})
    return out


# ── Main ─────────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 72)
    print("DAY 5: SEED multilingual_terms VIA AZURE TRANSLATOR F0")
    print("=" * 72)
    print(f"Translator key: {'set' if TRANSLATOR_KEY else 'MISSING'}")
    print(f"Region: {TRANSLATOR_REGION}")
    print()

    if not TRANSLATOR_KEY:
        print("[FAIL] AZURE_TRANSLATOR_KEY missing in .env.azure")
        return 1

    # Flatten
    all_rows: list[tuple[str, str, str]] = []  # (domain, english_term, context)
    for domain, items in PHRASES.items():
        for term, context in items:
            all_rows.append((domain, term, context))
    total = len(all_rows)
    print(f"Total phrases to translate: {total}")
    print(f"Domains: {', '.join(PHRASES.keys())}")
    print()

    # Batch translate (50 at a time to stay well under the 100-item cap)
    BATCH = 50
    translations: list[dict[str, str]] = []
    for i in range(0, total, BATCH):
        batch_terms = [r[1] for r in all_rows[i:i + BATCH]]
        print(f"Translating batch {i // BATCH + 1} ({len(batch_terms)} terms)...")
        try:
            t = translate_batch(batch_terms)
            translations.extend(t)
            print(f"  [OK] returned {len(t)} translations")
        except Exception as e:
            print(f"  [FAIL] {e}")
            return 1
        time.sleep(0.2)  # gentle pacing

    if len(translations) != total:
        print(f"[FAIL] expected {total} translations, got {len(translations)}")
        return 1

    # Insert into Postgres
    print(f"\nInserting {total} rows into multilingual_terms...")
    conn = psycopg2.connect(host="127.0.0.1", port=54322,
                            user="postgres", password="postgres", database="postgres")
    cur = conn.cursor()

    # Clear prior Day 5 entries (idempotent) — match on english_term within domain
    # Then insert fresh translations
    for (domain, term, context), trans in zip(all_rows, translations):
        cur.execute(
            "DELETE FROM multilingual_terms WHERE domain = %s AND english_term = %s",
            (domain, term),
        )
        cur.execute(
            "INSERT INTO multilingual_terms (domain, english_term, tagalog_term, visayan_term, context) "
            "VALUES (%s, %s, %s, %s, %s)",
            (domain, term, trans["tagalog"], trans["visayan"], context),
        )
    conn.commit()
    print(f"[OK] Inserted {total} rows")

    # Quick sanity: how many got non-empty translations
    cur.execute("SELECT COUNT(*) FROM multilingual_terms WHERE tagalog_term IS NOT NULL AND tagalog_term != ''")
    fil_filled = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM multilingual_terms WHERE visayan_term IS NOT NULL AND visayan_term != ''")
    ceb_filled = cur.fetchone()[0]
    cur.execute("SELECT domain, COUNT(*) FROM multilingual_terms GROUP BY domain ORDER BY domain")
    print(f"\nCoverage:")
    print(f"  Total rows:       {total}")
    print(f"  With Tagalog:     {fil_filled}")
    print(f"  With Visayan:     {ceb_filled}")
    print(f"\nBy domain:")
    for dom, cnt in cur.fetchall():
        print(f"  {dom}: {cnt}")

    # Sample
    cur.execute("SELECT english_term, tagalog_term, visayan_term FROM multilingual_terms ORDER BY random() LIMIT 5")
    print(f"\nSample (random 5):")
    for en, tl, ceb in cur.fetchall():
        print(f"  {en:25s} -> tl: {tl:20s} | ceb: {ceb}")

    cur.close()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
