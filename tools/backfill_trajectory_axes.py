#!/usr/bin/env python3
"""backfill_trajectory_axes.py — give every trajectory four structured axes, so the program can be
counted by WHAT IT IMPROVES and by WHO IS WALKING, WHERE, and HOW THEY ARRIVED (Ian, 2026-09-07:
"my goal for this roadmap is the increase the Usability, Functionality, Adaptability, Internal Control
for my user's User Interface and User Experience, which is called UFAI UI UX for each page and full
stack saas layers").

WHY THIS EXISTS. On 2026-09-07 no row carried a UFAI dimension at all - the critic rubric grades codes
like B3/DP1/A1 and trajectory rows carry `layers` and `cells` but never say which of U/F/A/I they serve.
So "which page is thin on Internal Control?" could not be answered by anything but an impression. Nor
could "how many rows walk as a buyer, on a wide monitor, arriving from a deep link?", because persona,
device and entry lived only in free-text `story`. This is the same blindness `layers` had before
backfill_trajectory_layers.py ran, and it gets the same cure: a stated, deterministic derivation, an
idempotent atomic write, and a report that NAMES what it could not classify rather than defaulting.

THE FOUR FIELDS, and where each is read from - the platform's OWN vocabulary first, always:

  ufai     one or more of U/F/A/I. Three additive sources: the WAVE a row belongs to (the wave names in
           update_trajectory_scoreboard.py say what a wave is about), the LAYERS it crosses (security,
           auth, rate-limit and logging layers are Internal Control by nature; availability, caching,
           hosting, compute, scaling and CI are Adaptability), and the words of its TITLE.
  persona  the `cells` field already encodes `device|persona` on 1,179 rows in the platform's own
           tokens (worker, oversight, assistive-tech, machine-client, solo-owner, fleet-supervisor,
           driver-worker, adversary, ...). Those are used verbatim. Rows without cells fall back to
           title + story, mapped onto the SAME token set plus the journey personas the titles name
           (supervisor, seller, buyer, anon, admin, new-user, returner).
  device   likewise from `cells` (narrow-320, phone-390, desktop-1280, wide-1920, fixed-kiosk-print),
           else from title + story; `tablet-768` is added because provers measure it and no cell
           token names it.
  entry    how the person arrived: search-arrival, deep-link, email-push, qr-print, hub-nav, direct.

A row that matches nothing on an axis is left `unspecified` on that axis and NAMED in the report. The
last backfill's stated ["F"] default was printed on every run for the same reason: a default that is
silent becomes the answer.

  python tools/backfill_trajectory_axes.py            # write (idempotent; only fills missing fields)
  python tools/backfill_trajectory_axes.py --dry-run  # the matrices and the unclassified, no write
  python tools/backfill_trajectory_axes.py --force    # recompute every row (after a rule change)
  python tools/backfill_trajectory_axes.py --report   # the three matrices over the whole registry
"""
from __future__ import annotations

import argparse
import collections
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "trajectory_registry.json"

UFAI_NAMES = {"U": "Usability", "F": "Functionality", "A": "Adaptability", "I": "Internal Control"}

# ── ufai from the WAVE. The letters are the T-program's wave codes; their meanings are the names in
# update_trajectory_scoreboard.py's WAVE_NAMES, read once and mapped here rather than re-typed.
WAVE_UFAI: dict[str, list[str]] = {
    "A": ["U"],          # Acquisition & first value
    "B": ["U", "F"],     # Field work phone-first
    "C": ["F", "I"],     # Supervisor ops
    "D": ["F"],          # Cross-page chains & two-sided
    "E": ["A"],          # Degraded conditions
    "F": ["U", "I"],     # Trust, language, access
    "G": ["I"],          # Multi-hive & role diversity
    "H": ["U"],          # Page depth: unwalked surfaces
    "I": ["I", "U"],     # AI features
    "J": ["F"],          # Marketplace economy
    "K": ["A"],          # Notifications & re-engagement
    "L": ["A"],          # Device & context matrix
    "M": ["A"],          # Data shape & scale
    "N": ["A", "F"],     # Concurrency & realtime
    "O": ["U"],          # Search, SEO & arrival
    "P": ["I"],          # Privacy, security & compliance
    "Q": ["U"],          # Wayfinding & comprehension
    "R": ["A"],          # Lifecycle & longitudinal
    "S": ["A"],          # Infra degradation & release safety
    "T": ["U"],          # Public Learn funnel
    "U": ["U"],          # Public Tools funnel
    "V": ["F"],          # Edge-function layer
    "W": ["I"],          # Security & adversarial personas
    "X": ["U"],          # Accessibility spectrum
    "Y": ["U"],          # New human personas
    "Z": ["A"],          # Data pathology deep
    "AA": ["I", "F"],    # Financial & economic edge
    "AB": ["I"],         # Federation & multi-org
    "AC": ["A"],         # Platform-evolution & longitudinal
    "AD": ["I"],         # Ops & observability surfaces
    "AE": ["A"],         # Compound systemic failures
    "VM": ["U", "F"],    # Vehicle lane
    "VD": ["F"],         # Real-document extraction
    "VP": ["U", "F"],    # Production deepwalk
}
# ★THE P-PROGRAM AND LAYER-UX WAVES HAVE THEIR OWN CODES, AND ONE OF THEM COLLIDES. The first dry-run
# stamped Internal Control on all 672 P rows: their wave codes are P-A..P-M, the prefix fallback
# returned "P", and the T-program's wave P is "Privacy, security & compliance". Two programs, one
# letter, opposite meanings. These maps are read from the seeders' own wave names
# (seed_p_program_catalog.WAVES, seed_layer_ux_wave.WAVES) and matched BEFORE any prefix fallback.
P_WAVE_UFAI: dict[str, list[str]] = {
    "P-A": ["U"],        # Frontend render & CSS integrity
    "P-B": ["I"],        # Auth, RLS & tenant depth
    "P-C": ["F", "I"],   # Data correctness & KPI truth
    "P-D": ["F", "A"],   # Realtime & subscriptions
    "P-E": ["A"],        # Caching, CDN & offline
    "P-F": ["I"],        # LLM / AI-chain grounding
    "P-G": ["U"],        # Accessibility deep
    "P-H": ["U", "A"],   # Mobile, touch & PWA deep
    "P-I": ["I"],        # Trust, interpretability & honesty
    "P-J": ["F"],        # Cross-page chains v2
    "P-K": ["A", "I"],   # Ops, observability & availability
    "P-L": ["A"],        # Compound & systemic
    "P-M": ["U"],        # Phone fit: wrap, overflow & reflow
}
LX_WAVE_UFAI: dict[str, list[str]] = {
    "LX-CI": ["A"],      # a release lands under you
    "LX-L": ["I"],       # a failure leaves a trace someone can find
    "LX-LB": ["A"],      # the hive grows and the page must say so
    "LX-H": ["A"],       # what the deployed origin actually serves
    "LX-RL": ["I"],      # refused, and told when you may come back
    "LX-S": ["I"],       # the boundary is legible
    "LX-FN": ["F"],      # the surfaces the program had never named
}
# ── a wave that DEFINES its device. Wave B is "Field work phone-first" by its own name, so a B row
# with no device word is on a phone by definition, not unspecified.
WAVE_DEVICE: dict[str, str] = {"B": "phone-390", "P-M": "phone-390", "P-H": "phone-390"}
# ── a lens that applies to everyone on any device is `any`, which is a classification, not a gap.
# The LX waves ask what a person feels when a LAYER misbehaves, on a page - the device is not part of
# the question. `unspecified` is kept only as a coding-error sentinel and is expected to read zero.
AGNOSTIC_PREFIXES = ("LX",)

# ── ufai from the LAYERS a row crosses (fallback when wave and title say nothing)
LAYER_UFAI: dict[str, str] = {
    "S": "I", "AU": "I", "RL": "I", "L": "I",
    "AV": "A", "CA": "A", "H": "A", "C": "A", "LB": "A", "CI": "A",
}
# ── ufai from the TITLE's words (additive). Anchored - the "SLO inside SLOWER" lesson.
TITLE_UFAI: list[tuple[str, str]] = [
    (r"reads?|finds?|understands?|legib|comprehens|wayfind|findab|onboard|first[- ]time|language|"
     r"Tagalog|Filipino|tap target|keyboard|screen reader|contrast|one-handed|glove|jargon|help\b|"
     r"guide|explain|empty state|copy\b|label", "U"),
    (r"completes?|end-to-end|chain|hand-?off|import|export|ripple|lineage|mirror|converts?|"
     r"funnel|lists? a|creates?|approves?|schedules?|the job|works? (correctly|at all)|actually", "F"),
    (r"offline|degrad|outage|fails?|down\b|slow|3G|scale|grows|at 20|volume|thousand|1000|expir|"
     r"release|deploy|version|stale|cold start|storm|shift|3am|month.?end|dormant|returns after|"
     r"interrupt|phone rings|landscape|tablet|1920|kiosk|wall", "A"),
    (r"refus|audit|consent|tenant|RLS|BOLA|cross-hive|another hive|adversar|attack|spoof|abuse|"
     r"hostile|who sees|deletion|forget me|quota|limit|rate.?limit|429|moderat|approval|permission|"
     r"secret|leak|privacy|honest|trust|provenance|what an AI|hallucinat|self-review|reputation", "I"),
]

# ── persona from cells (verbatim tokens) and, failing that, from words
PERSONA_TOKENS = ["worker", "oversight", "assistive-tech", "machine-client", "solo-owner",
                  "fleet-supervisor", "driver-worker", "adversary", "motorcycle-rider",
                  "jeepney-operator", "van-fleet-SMB", "delivery-rider", "fleet-owner+driver", "hive-worker"]
PERSONA_WORDS: list[tuple[str, str]] = [
    (r"\bsupervisor|approval queue|moderat|co-supervisor", "fleet-supervisor"),
    (r"\bseller|supplier|contractor|provider|service hail", "seller"),
    (r"\bbuyer\b|procure|purchas", "buyer"),
    (r"\banon|stranger|signed-out|visitor|from search|lands on|arrives|crawler", "anon"),
    (r"owner|founder|platform admin|operator|console", "oversight"),
    (r"attack|adversar|hostile|malicious|spoof|forged|ex-employee|scrap", "adversary"),
    (r"screen reader|low.?vision|keyboard.?only|tremor|gloved|colou?r.?blind|a11y|accessib", "assistive-tech"),
    (r"graduate|first.?time|new (user|member|worker)|onboard|fresh sign-?up|signs? up|creates? a hive", "new-user"),
    (r"dormant|returns after|day.?2|week one|month three|returner|returning user|session expired", "returner"),
    (r"solo|self-employed|one-person", "solo-owner"),
    (r"driver|rider|jeepney|fleet", "driver-worker"),
    (r"edge function|webhook|cron|scheduled|machine|api-direct|contract & failure", "machine-client"),
    (r"\bworker|technician|logs? a|records? a|one-handed|voice journal", "worker"),
]
# ── device from cells, else from words
DEVICE_TOKENS = ["narrow-320", "phone-390", "desktop-1280", "wide-1920", "fixed-kiosk-print", "wide-1280"]
DEVICE_WORDS: list[tuple[str, str]] = [
    (r"kiosk|wall[- ]display|big screen|print\b|poster|\bQR\b", "fixed-kiosk-print"),
    (r"\b320\b|low-end android|narrow", "narrow-320"),
    (r"tablet|\b768\b", "tablet-768"),
    (r"\b1920\b|wide[- ]screen|the wide|PC\b|desktop monitor", "wide-1920"),
    (r"\b1280\b|desktop|laptop", "desktop-1280"),
    (r"phone|mobile|\b390\b|one-handed|thumb|pocket", "phone-390"),
]
# ── entry path
ENTRY_WORDS: list[tuple[str, str]] = [
    (r"from search|search result|google|snippet|SEO|crawler|arrival|lands on|learn arrival|tools arrival", "search-arrival"),
    (r"deep.?link|shared link|from a (message|link)|bookmark|\?calc=|destination", "deep-link"),
    (r"e-?mail|inbox|push\b|notification tap|digest", "email-push"),
    (r"\bQR\b|print|poster", "qr-print"),
    (r"\bhub\b|nav|menu|from the board", "hub-nav"),
]

_C = lambda rules: [(re.compile(p, re.I), v) for p, v in rules]  # noqa: E731
TITLE_UFAI_C, PERSONA_WORDS_C, DEVICE_WORDS_C, ENTRY_WORDS_C = map(_C, (TITLE_UFAI, PERSONA_WORDS, DEVICE_WORDS, ENTRY_WORDS))
_WAVE_RE = re.compile(r"^([A-Z]{1,2})(?:-|\d|$)")


def _wave_ufai(row: dict) -> list[str]:
    """What the row's WAVE says it improves - the program-specific codes first, the T letters after,
    and the id prefix only for the vehicle waves whose `wave` field is the prefix itself."""
    w = str(row.get("wave") or "")
    if w in P_WAVE_UFAI:
        return P_WAVE_UFAI[w]
    if w in LX_WAVE_UFAI:
        return LX_WAVE_UFAI[w]
    m = _WAVE_RE.match(w)
    if m and m.group(1) in WAVE_UFAI and not str(row.get("id", "")).startswith(("P", "LX")):
        return WAVE_UFAI[m.group(1)]
    m2 = re.match(r"^(VP|VD|VM)", str(row.get("id") or ""))
    return WAVE_UFAI.get(m2.group(1), []) if m2 else []


def _wave_device(row: dict) -> str:
    w = str(row.get("wave") or "")
    if w in WAVE_DEVICE:
        return WAVE_DEVICE[w]
    m = _WAVE_RE.match(w)
    if m and not str(row.get("id", "")).startswith(("P", "LX")):
        return WAVE_DEVICE.get(m.group(1), "")
    return ""


def ufai_for(row: dict) -> list[str]:
    out: list[str] = []
    def add(x: str) -> None:
        if x and x not in out:
            out.append(x)
    for x in _wave_ufai(row):
        add(x)
    text = (row.get("title") or "")
    for rx, dim in TITLE_UFAI_C:
        if rx.search(text):
            add(dim)
    # ★LAYERS ARE WHERE A ROW TOUCHES, NOT WHAT IT IMPROVES. The first dry-run made layers additive and
    # reported Internal Control on 1,016 rows - because every row that merely CROSSES the auth layer
    # ("sign in on a phone", a Usability question) was stamped I. A number that generous is the rule,
    # not the program. Layers now speak only when the wave and the title said nothing: a row with no
    # stated intent that crosses the security layer is about control, one that crosses caching or
    # availability is about adaptability - and that lean is counted in the report.
    if not out:
        for lyr in (row.get("layers") or []):
            add(LAYER_UFAI.get(lyr, ""))
    # a P-program row's lens is its title; an LX row's is its layer - both are covered above. A row
    # that crosses only F/D/A layers and names nothing is Usability by the program's definition (a
    # user-journey arc) - stated here, and counted in the report as a lean on the definition.
    return out


def _from_cells(row: dict, idx: int, tokens: list[str]) -> str:
    for c in (row.get("cells") or []):
        parts = str(c).split("|")
        if len(parts) > idx and parts[idx] in tokens:
            return parts[idx]
    return ""


def _first(rules, text: str) -> str:
    for rx, v in rules:
        if rx.search(text):
            return v
    return ""


def axes_for(row: dict) -> dict:
    text = (row.get("title") or "") + " " + (row.get("story") or "")
    # ★A JOURNEY THAT NAMES NO DEVICE APPLIES ON ANY. "Fresh signup -> creates a hive -> invites a
    # teammate" is not a phone journey or a desktop one; it is the journey. `any` says so, and is a
    # classification rather than a gap - but it is a LEAN, counted and named in the report, because a
    # device-agnostic row is exactly the cell the PX wave exists to fill with device-specific ones.
    # `unspecified` survives only as a coding-error sentinel and should read zero.
    leans: list[str] = []
    persona = _from_cells(row, 1, PERSONA_TOKENS) or _first(PERSONA_WORDS_C, text)
    if not persona:
        persona, _ = "any", leans.append("persona")
    device = _from_cells(row, 0, DEVICE_TOKENS) or _first(DEVICE_WORDS_C, text) or _wave_device(row)
    if not device:
        device, _ = "any", leans.append("device")
    entry = _first(ENTRY_WORDS_C, text) or "direct"
    ufai = ufai_for(row)
    if not ufai:
        ufai, _ = ["U"], leans.append("ufai")   # the program's definition: a user-journey arc
    return {"ufai": ufai, "persona": persona, "device": device, "entry": entry, "_leans": leans}


def _atomic_write(path: Path, text: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def matrices(rows: list[dict]) -> str:
    scoped = [r for r in rows if r.get("status") != "descoped"]
    out = []
    # UFAI totals
    uc = collections.Counter(x for r in scoped for x in (r.get("ufai") or []))
    out.append("  UFAI          " + " · ".join(f"{k} {UFAI_NAMES[k]} {uc.get(k, 0)}" for k in "UFAI"))
    # UFAI x layer
    lay = collections.defaultdict(collections.Counter)
    for r in scoped:
        for l in (r.get("layers") or []):
            for x in (r.get("ufai") or []):
                lay[l][x] += 1
    out.append("  UFAI x LAYER  " + " · ".join(f"{l}[" + "/".join(str(lay[l].get(x, 0)) for x in "UFAI") + "]"
                                                 for l in sorted(lay, key=lambda z: -sum(lay[z].values()))))
    # UFAI x page: the thinnest pages on each dimension are what matters
    pg = collections.defaultdict(collections.Counter)
    for r in scoped:
        for p in (r.get("pages") or []):
            if isinstance(p, str) and p.endswith(".html") and "/" not in p:
                for x in (r.get("ufai") or []):
                    pg[p][x] += 1
    out.append("  UFAI x PAGE   thinnest per dimension: " + " · ".join(
        f"{x}:" + ",".join(f"{p[:-5]} {pg[p].get(x, 0)}" for p in sorted(pg, key=lambda z: pg[z].get(x, 0))[:3])
        for x in "UFAI"))
    # persona x device
    pd = collections.Counter((r.get("persona"), r.get("device")) for r in scoped)
    personas = sorted({p for p, _ in pd}, key=lambda z: -sum(v for (p, _), v in pd.items() if p == z))
    devices = sorted({d for _, d in pd}, key=lambda z: -sum(v for (_, d), v in pd.items() if d == z))
    out.append("  PERSONA x DEVICE")
    out.append("  " + "%-18s" % "" + "".join("%9s" % d[:8] for d in devices))
    for p in personas:
        out.append("  " + "%-18s" % p[:17] + "".join("%9d" % pd.get((p, d), 0) for d in devices))
    ec = collections.Counter(r.get("entry") for r in scoped)
    out.append("  ENTRY         " + " · ".join(f"{k} {v}" for k, v in ec.most_common()))
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="recompute every row, not only the unfilled")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    doc = json.loads(REGISTRY.read_text(encoding="utf-8"))
    rows = doc["trajectories"]

    if args.report:
        print(matrices(rows))
        return 0

    filled = 0
    leaned = collections.defaultdict(list)
    for r in rows:
        have = all(r.get(k) for k in ("ufai", "persona", "device", "entry"))
        if have and not args.force:
            continue
        ax = axes_for(r)
        for axis in ax.pop("_leans"):
            leaned[axis].append(r["id"])
        for k, v in ax.items():
            r[k] = v
        filled += 1

    print(f"  {filled} row(s) {'recomputed' if args.force else 'filled'} of {len(rows)}")
    for axis, ids in leaned.items():
        what = {"ufai": "lean on the program's definition (U)", "device": "apply on ANY device",
                "persona": "apply to ANY persona"}[axis]
        print(f"  {len(ids)} row(s) named no {axis} and {what}: {', '.join(ids[:8])}{' ...' if len(ids) > 8 else ''}")
    print()
    print(matrices(rows))

    if args.dry_run:
        print("\n  (nothing written)")
        return 0
    doc["trajectories"] = rows
    _atomic_write(REGISTRY, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    print(f"\n  wrote {REGISTRY.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
