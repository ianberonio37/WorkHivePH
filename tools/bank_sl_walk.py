#!/usr/bin/env python3
"""bank_sl_walk.py - bank SL (sub-layer) rows (§SL, 2026-10-14) from the evidence their instrument produces.

Two modes, one per instrument a row declares (`sl.instrument`):

  --prover <results.json>   CONTRACT rows (instrument "library sweep ..."): a registered batch prover over every page.
                            A row banks only when the prover's readings for ITS page are clean in EVERY engine it ran
                            (the sub-layers this file knows how to read from tools/prove_page_survives_optional_failures
                            .mjs: H1 needs the as-served reading clean in Chromium AND WebKit), and the named gates PASS.
  --walk <SL id> --steps f  WALK rows: a chrome-devtools MCP walk as the page's cast, recorded through
                            tools/record_mcp_walk.py (which refuses a receipt without the sub-layer, the persona and
                            steps at both viewports). An engine-sensitive row (sl.engine webkit) also needs --webkit
                            <results.json> holding clean WebKit readings for the page: no MCP drives WebKit, so the
                            Playwright WebKit run is that half, named in the receipt's witness and checked here.

The registry is written only when everything holds; a row is never moved on a partial reading. Writes indent=2, the
format the seeders and HEAD use (one writer flipping the whole 56 MB file to indent=1 is how a 4,399-row seed nearly
committed a 1.7M-line diff, 2026-10-14).

  python tools/bank_sl_walk.py --prover .tmp/sl_walk1_results.json --sublayer H1
  python tools/bank_sl_walk.py --walk SL916 --steps .tmp/w4_steps/SL916.json --witness "..." [--webkit .tmp/sl_walk1_results.json]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "tools"))
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

PROVER = "tools/prove_page_survives_optional_failures.mjs"
# the gates that hold each sub-layer this banker settles (all registered in run_platform_checks.py)
GATES = {
    "H1": ["page-survives-optional-failures", "csp-covers-what-ships", "deploy-headers-local"],
    "S3": ["csp-exact", "csp-exact-profiles", "csp-covers-what-ships", "deploy-headers-local"],
    "S4": ["stored-text-escaped", "handler-values-escaped", "dom_xss_fields"],
    "CA2": ["cache-contract", "deploy-headers-local"],
    "CI1": ["page-gate-teeth", "csp-covers-what-ships", "scripts-parse"],
    "CI4": ["page-registries", "design-detector-ratchet", "csp-exact-profiles"],
    "F5": ["page-craft", "design-detector-ratchet", "design-tokens"],
    "CI3": ["page-ratchets", "design-detector-ratchet"],
    "F2": ["page-fit", "phone-fit", "phone-fit-320", "phone-fit-1280"],
    "H4": ["rollout", "skew-heal", "sw-shell-membership"],
    "CI2": ["page-journeys", "public-journeys", "live-page-journeys", "live-page-journeys-webkit"],
    "F3": ["page-reachable", "clickable-keyboard-a11y", "aria-label-coverage", "icon-button-label", "arc-u-focus-trap"],
    "H2": ["cache-contract", "deploy-headers-local"],
    "S5": ["no-secret-served", "committed_env_secret"],
    "A3": ["page-survives-optional-failures", "realtime-blocked-socket"],
    "AV1": ["page-survives-optional-failures", "realtime-blocked-socket"],
    "F1": ["skeleton-labelled", "failed-read-is-not-empty", "loading-state", "empty-state"],
    "F4": ["jargon-glossed", "glossary-registry", "user-facing-jargon"],
    "C1": ["device-clock-day"],
    "CA3": ["skew-heal", "skew-heal-live"],
    "CA1": ["sw-shell-membership", "sw-offline", "cache-contract", "pwa-sw-central-register", "sw-proxy-within-csp"],
    "CA4": ["kept-copy-says-so", "offline-is-not-no", "sw-offline", "sw-navigation-fallback", "sw-shell-membership"],
    "H3": ["pwa", "pwa-sw-central-register", "sw-install-survives-loss", "deploy-payload"],
    "D2": ["ownership-by-account", "bug-repro-ratchet"],
    "D3": ["deletes-are-recoverable", "cascade-confirm-parity", "success-is-checked", "offline_queue_confirm", "skew-heal"],
    "L1": ["error-capture-everywhere", "production-errors-read", "error-capture"],
    "AU2": ["role-reconciled", "role-checks", "storage-keys"],
    "AU3": ["ownership-by-account", "bug-repro-ratchet"],
    "AU4": ["gated-offers", "role-reconciled", "admin-gates"],
    "AU1": ["session-states-honest"],
    "BRH-D": ["skew-heal", "skew-heal-live"],
    "BRH-H": ["hive-startup", "hive-restore-adoption"],
    "BRH-G": ["hive-startup", "hive-restore-adoption"],
    "BRH-E": ["scope-empty", "hive-startup", "hive-restore-adoption"],
    "BRH-J": ["live-page-journeys"],
    "BRH-K": ["design-detector-ratchet", "scripts-parse"],
}
# how the walk induced its condition, per sub-layer (the basis states it; walk 1's wording is the default)
CONDITION = {
    "CA1": ("two devices with the service worker allowed, each installed from the home page: one on the current build; one that installed the previous build (sw.js served once at registration with its CACHE_NAME renamed '-prev') and was moved to the current build by the browser's own update check - new bytes at the same URL, exactly a deploy"),
    "D2": ("the same signed-in account read each page twice per viewport - the device remembering its own display name, then another real person's (wh_last_worker written before the page loaded) - and the two reads compared, text and controls, with the names masked apart (<ME> / <OTHER>)"),
    "H3": ("on the local edge substitute (tools/serve_vercel_headers.py --local-stack: the production path layout and vercel.json's headers, the pages pointed at the local stack), the worker allowed and installed from the home page; Chromium's installability verdict read in the browser's persistent context as the row's cast"),
    "CA4": ("the service worker allowed and installed from the home page; kept: the page opened once online, then the network cut (context.setOffline) and the page opened again; fallback: a second device with the worker installed and the page never opened, the network cut, the page opened"),
    "D3": ("a probe row the cast owns, seeded on the LOCAL stack per viewport. A page that deletes ran its own delete "
           "function (the one its delete control calls) and its real confirm was answered; then the person's own client "
           "read the row hidden, the toast's Undo was pressed and the row read back; deleted again, the page's own "
           "Recently deleted button opened the list and its Restore was pressed. A page that only reads had the probe "
           "deleted and restored by its author (wh_trash / wh_restore) while the page's own reads and counts were "
           "captured; a public page was read as served and each retention claim held against what the platform does"),
    "CA3": ("utils.js served as the real file and as yesterday's copy (the page's own guarded functions undefined) until the page fetched it past the cache, in fresh contexts with the signed-in state restored"),
    "C1": ("a differential: the page opened twice at the same pinned instant (2026-10-16T02:00Z - Friday morning in Manila, Thursday night in New York) on a Manila device clock and a New York one, both answered consent alike and the skew check answered at that instant, both signed in and warmed before either was read"),
    "F4": ("as served - the page read from its live render (innerText, what a person reads) with every domain term checked for its gloss on the same page and every flagged figure read with its card, column header and the page's stated window"),
    "F1": ("each list read induced in turn - answered empty (an empty hive: [] and Content-Range */0; an object read hollowed), answered 500, and held 9 s and read at 1.5 s - through a context with service workers BLOCKED, every rest read, rpc and edge function the page makes on load except the identity, hive and gate reads its start-up needs"),
    "AU2": ("the device role written into the page's own storage before the page loaded - the honest role and a false "
            "one, the same signed-in person with the server's hive_members.role set on the LOCAL database"),
    "AU3": ("the device's remembered display name (wh_last_worker) written into the page's own storage before it loaded - "
            "the person's own, then another real member's (another hive-less owner's for the solo cast); every text line "
            "and control compared with the two names masked APART (<ME> / <OTHER>), so a swap of who is who shows"),
}
# BRH-L and SL AU4 share the AU4 gates but not the walk: L asks what is OFFERED (the hub, the search, the page's links),
# SL AU4 asks what the SERVER does when the control is used anyway - so each kind states its own condition (a BRH row
# looks up "BRH-<cls>" first). Until 2026-10-14 both read the L text, and 12 SL AU4 bases described a hub walk that
# never happened on them.
CONDITION["BRH-L"] = ("the same surfaces read as a person the destination refuses (Bryan Garcia, a worker of Baguio "
                      "Textile Mills; signed out for the public landing page) and as one it admits (Leandro Marquez, its "
                      "supervisor and a platform admin): the hub in each display mode, the search overlay, the page "
                      "controls; a latent door induced where no local data shows it (asset-hub's telemetry empty state "
                      "revealed, ph-intelligence's readiness answered Stair 3 for the walk)")
CONDITION["AU4"] = ("each admin or founder control's own server operation attempted through the page's own client as a "
                    "person the page refuses (Bryan Garcia, a worker of Baguio Textile Mills; Jun Salvador, an owner with "
                    "no hive, on integrations), then the page read as the person it admits (Leandro Marquez, its "
                    "supervisor and a platform admin); a postgres witness of every row those operations could touch, "
                    "taken before and after")
CONDITION["AU1"] = ("three session states per viewport, each read through the MCP browser: HONEST (the session as it is), DEAD "
                    "(the access token expired and its refresh token replaced with one the server refuses), OUT (no session, "
                    "the display name left on the device) - the readout is the page's text length, the sign-in wall, the "
                    "session sentence, every identity claim (the name in the person's own slot or after an identity verb), "
                    "every Sign-in door offered, and every write")
CONDITION["BRH-D"] = ("two loads per viewport through the MCP browser: CLEAN (the real utils.js - the page must neither "
                      "refetch it nor reload) and SKEW (yesterday's utils.js: the current file with the page's own guarded "
                      "functions unset at its end, served to every <script> load until the page fetches utils.js past the "
                      "cache, as an HTTP or service-worker copy would be) - the readout is each utils.js request in order, "
                      "the navigations, and which of the page's functions exist once it settles")
CONDITION["BRH-H"] = ("per viewport through the MCP browser, each reading in a fresh tab whose init script set the device "
                      "before any page script: BASE (the device as it normally is - the comparison point) and WIPED (the "
                      "stored hive, its name, role and list removed) - the readout is the document loads, whether the "
                      "after-load recovery reloaded (wh_hive_recovered), the hive at the end, and the page's text against "
                      "the baseline; a refusing page is read again as the person it admits")
CONDITION["BRH-G"] = ("per viewport through the MCP browser, in a fresh tab whose init script set the stored hive name to "
                      "'Old Plant Name' before any page script - the readout is whether that name is shown, whether the "
                      "hive's real name is shown, and the stored name once the page settles; a supervisors-only page is "
                      "read by the hive's supervisor, the person it shows the name to")
CONDITION["BRH-E"] = ("per viewport through the MCP browser, in a fresh tab whose init script removed the stored hive (its "
                      "id, name, role and list) and SPENT the after-load recovery (wh_hive_recovered) before any page "
                      "script - the state a member met when a page fell into personal mode - read against the same page "
                      "with the device as it normally is: the hive the page settled in, and whether the row's own "
                      "'No X yet.' sentence is on screen")
CONDITION["BRH-J"] = ("the journey driven through the MCP browser as the row's cast, one viewport per call, with the "
                      "product's own visible controls (a pointer press on the button a person sees, the confirm the "
                      "page asks, the hub's own mode button) - its data seeded and restored outside the browser between "
                      "calls on the LOCAL database, and the outcome read back from that database")
CONDITION["BRH-K"] = ("the page read in the LIVE render as the row's cast (the landing page signed out, as the visitor who meets "
                      "it; a page that refuses the cast also read as the person it admits), per viewport in a fresh tab: one "
                      "probe per antipattern on the computed styles, the live stylesheets and the rendered text - the offline "
                      "banner raised with the page's own offline event")
GATES["ENH-R"] = ["provenance-at-foot", "skew-heal", "scripts-parse", "design-detector-ratchet"]
GATES["D1"] = ["figure-sources-written", "provenance-at-foot", "skew-heal", "scripts-parse"]
GATES["D4"] = ["file-storage-owned", "media-fails-alone", "skew-heal", "scripts-parse"]
GATES["A1"] = ["refusal-has-a-sentence", "offline-is-not-no", "write-failure-speaks", "skew-heal", "scripts-parse"]
GATES["A2"] = ["double-submit-lock", "refresh-retry-dedup", "cb_double_fire", "skew-heal", "scripts-parse"]
CONDITION["A2"] = ("the page read as served in its own browser context (service workers blocked), signed in as the row's "
                   "cast, with tools/prove_double_fire.mjs's write-holding shim installed before any page script: every "
                   "mutating request (POST/PATCH/PUT/DELETE to rest, rpc or functions) counted and HELD in the page, so "
                   "nothing landed; each of the page's write flows reached the way a person reaches it (the prover's own "
                   "FLOWS, read RPCs named and let through), its submit pressed, then pressed again while the first write "
                   "was in flight - graded on whether the second press fired a further write and whether the surface "
                   "showed it was busy; a flow whose press fired no write, or a page that offers this cast no write, "
                   "ungraded and said so; the retry half named on each receipt (utils.js re-sends GET only; a person's "
                   "retry after a lost reply is held by refresh-retry-dedup)")
CONDITION["A1"] = ("the page read as served in its own browser context (service workers blocked, so no worker could answer a "
                   "read the injection meant to fail), signed in as the row's cast: a healthy read, then the page's own "
                   "data reads failed from the first byte by an init script patching fetch before any page script - 500 "
                   "internal server error, then PostgREST's stock 42501 permission denied, then (on a page that calls one "
                   "at start-up) every edge call answered with the platform's real 429 body; each settled 11 s and every "
                   "live region the page showed recorded; graded on the sentences the page NEWLY said: failure- or "
                   "refusal-shaped with a next step, no machine text, no new empty state over a failed read, the refusal "
                   "named as a refusal and an outage never blamed on permission or on the device's connection, a visitor "
                   "never addressed as a member, the page not bounced; a condition the page never reached ungraded; edge "
                   "calls carried x-wh-walk-no-model")
CONDITION["D4"] = ("the page read as served, signed in as the row's cast, the file handed to the page's OWN control "
                   "(setInputFiles on its input: a JPEG drawn in the page, or a text file carrying a unique marker), "
                   "edge calls carrying x-wh-walk-no-model: a bucket picker driven through pick, a second pick, Remove, "
                   "an unsaved close or leaving the page, and a save - each upload asked of the bucket by its public URL "
                   "(no-store) and a storage tap recording every object, its owner and how long it lived; an inline photo "
                   "saved, re-read after a reload, removed and re-read; a read-only intake's every request recorded and "
                   "its marker searched for in every text and json column and in storage; probe rows removed after")
CONDITION["D1"] = ("the page read as served, signed in as the row's cast, its start-up settled, caches cleared first: every "
                   "visible figure of the page's content counted - a number inside a control left to that control, a "
                   "number that is part of a picture (aria-hidden inside role=img) left to the picture, a registry chrome "
                   "number not data - and each one left required to be tappable; a REAL tap on a figure required to open "
                   "its card naming what it shows and what it reads, Escape to close it and give the focus back; the "
                   "page's Sources area read for its page-level line; page errors recorded")
CONDITION["ENH-R"] = ("the page read as served, signed in as the row's cast, its start-up settled, the service worker and HTTP "
                      "cache cleared first so the walk read the current scripts: every visible source line, Show-details "
                      "explainer and how-it-is-computed note OUTSIDE the Sources area counted (must be none), every collapsed "
                      "slot that still took space (none), every visible leaf of the content BELOW the area, clipped boxes "
                      "excluded (none), the area's own lines read, the explainer opened and closed with a real click, the "
                      "area's words checked for fixed chrome over them at the bottom of the scroll, the load's layout shift "
                      "and every page error recorded")
CONDITION_DEFAULT = "the condition induced by the MCP's initScript before any page script"
# a bug-hunt class is walked by the sub-layer that meets its defect (its gates and wording follow that sub-layer)
BRH_CLASS_SUBLAYER = {"F": "AU2", "L": "AU4", "M": "AU1",   # BRH.2: L - a control offered to a person the page behind it refuses; M - copy that contradicts the session (the AU1 three-state walk settles it)
                      "D": "BRH-D",                         # D - version skew silenced by a typeof guard: no SL sub-layer walks it, so it is its own key
                      "H": "BRH-H", "G": "BRH-G",           # H/G - the stored hive and its name settled in the page's start-up (whStartupHive)
                      "E": "BRH-E",                         # E - an empty state never speaks for the personal list while the hive holds X
                      "J": "BRH-J",
                      "K": "BRH-K"}                         # K - design slop the detector ratchet held, fixed and walked in the live render                         # J - a live-as-a-user journey that was not live (pinned in live-page-journeys)
# which prover settles a contract sub-layer, and which of its readings: (condition or None, engines that must ALL be clean)
PROVER_READS = {
    "H1": {"prover": PROVER, "gate": "page-survives-optional-failures", "condition": "as-served",
           "engines": ("chromium", "webkit")},
    "L1": {"prover": "tools/prove_error_capture_everywhere.mjs", "gate": "error-capture-everywhere", "condition": None,
           "engines": ("chromium", "webkit")},
    # S3 names ORIGINS, which are engine-independent; WebKit's socket strictness is H1's reading
    "S3": {"prover": "tools/prove_csp_exact.mjs", "gate": "csp-exact", "condition": "as-served", "engines": ("chromium",)},
    # CA2/H2 are a header CONTRACT, walked over HTTP against the local edge substitute (no browser engine involved)
    # CI1 is a property of the GATES over the page, proven by breaking a temporary copy (no browser engine involved)
    "F5": {"prover": "tools/prove_page_craft.py", "gate": "page-craft", "condition": "craft", "engines": ("static",)},
    "CI3": {"prover": "tools/prove_page_ratchets.py", "gate": "page-ratchets", "condition": "ratchets", "engines": ("static",)},
    "F2": {"prover": "tools/prove_page_fit.py", "gate": "page-fit", "condition": "fit", "engines": ("chromium",)},
    "H4": {"prover": "tools/prove_rollout.mjs", "gate": "rollout", "condition": "returning-device", "engines": ("chromium",)},
    "CI2": {"prover": "tools/prove_page_journeys.py", "gate": "page-journeys", "condition": "journey",
            "engines": ("chromium", "webkit")},
    "F3": {"prover": "tools/prove_page_reachable.mjs", "gate": "page-reachable", "condition": "reachable",
           "engines": ("chromium",)},
    "CI4": {"prover": "tools/prove_page_registries.py", "gate": "page-registries", "condition": "registries",
            "engines": ("static",)},
    "CI1": {"prover": "tools/prove_page_gate_teeth.py", "gate": "page-gate-teeth", "condition": "breach", "engines": ("static",)},
    "CA2": {"prover": "tools/prove_cache_contract.py", "gate": "cache-contract", "condition": "as-served", "engines": ("http",)},
    "H2": {"prover": "tools/prove_cache_contract.py", "gate": "cache-contract", "condition": "as-served", "engines": ("http",)},
    "S4": {"prover": "tools/prove_stored_text_escaped.mjs", "gate": "stored-text-escaped", "condition": "poisoned",
           "engines": ("chromium",)},
    "S5": {"prover": "tools/prove_no_secret_served.mjs", "gate": "no-secret-served", "condition": "as-served",
           "engines": ("chromium",)},
}
GATE_SCRIPTS = {"csp-covers-what-ships": "tools/validate_csp_covers_what_ships.py",
                "deploy-headers-local": "tools/prove_deploy_headers.py",
                "realtime-blocked-socket": "tools/prove_realtime_blocked_socket.mjs",
                "production-errors-read": "tools/validate_production_error_groups.py",
                "error-capture": "tools/validate_error_capture.py",
                "csp-exact-profiles": "tools/build_csp_profiles.py",
                "cache-contract": "tools/prove_cache_contract.py",
                "scripts-parse": "tools/validate_scripts_parse.mjs",
                "design-detector-ratchet": "tools/prove_design_detector_ratchet.py",
                "design-tokens": "validate_design_tokens.py",
                "dom_xss_fields": "tools/validate_dom_xss_fields.py",
                "handler-values-escaped": "tools/validate_handler_values_escaped.py",
                "committed_env_secret": "tools/validate_committed_env_secret.py",
                "clickable-keyboard-a11y": "tools/validate_clickable_keyboard_a11y.py",
                "aria-label-coverage": "validate_aria_label_coverage.py",
                "icon-button-label": "validate_icon_button_label.py",
                "arc-u-focus-trap": "tools/validate_arc_u_focus_trap.py",
                "skew-heal": "tools/render_skew_heal.py",
                "sw-shell-membership": "tools/validate_sw_shell_membership.py"}
# the browser lenses whose RECORD a static prover reads are not re-run at bank time (a 50-minute pass each): the prover's
# own results carry their run times, and the gate is checked by that record, never skipped silently
RECORD_GATES = {"phone-fit": "phone-fit@390", "phone-fit-320": "phone-fit@320", "phone-fit-1280": "phone-fit@1280",
                "public-journeys": "public", "live-page-journeys": "journeys-chromium",
                "live-page-journeys-webkit": "journeys-webkit", "rollout": "rollout"}
GATE_ARGS = {"csp-exact-profiles": ("--check",), "skew-heal": ("--check",)}


def _basis(sublayer: str, t: dict, page: str, per: dict, gate_lines: list, results_path: str, results: dict,
           today: str) -> str:
    spec = PROVER_READS[sublayer]
    head = (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via {spec['prover']} (gate {spec['gate']}; real "
            + " AND ".join(e.capitalize() for e in spec["engines"]))
    tail = f" Gates: {', '.join(gate_lines)}. Receipt {results_path} (generated {results.get('generated')})."
    if sublayer == "L1":
        who = "anonymous" if t.get("persona") == "anon" else f"signed in as {t.get('persona')} through the product's own form"
        person = next((r.get("person") for rs in per.values() for r in rs if r.get("person")), None)
        real = ", ".join(f"{x['engine']} {x['rows_in_table']}" for x in results.get("real") or [])
        return (head + f", {who}): L1 on {page} - an uncaught error AND an unhandled rejection thrown after start-up were "
                f"each captured in both engines with the page's own pathname and the engine in the user agent"
                + (f", and the person ({person})" if person else ", with no identity (an anonymous row, as the policy requires)")
                + f". The anonymous path is proven by a REAL write per engine through migration 20261014000002's policy "
                f"({real} row(s), read back and removed); teeth: the pre-change shared scripts capture nothing. Read half: "
                f"production-errors-read answers every group in production_error_groups.json." + tail)
    if sublayer == "CI3":
        r = per["static"][0]
        return (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via {spec['prover']} (gate {spec['gate']}; HELD means "
                f"MEASURED - each ratchet's own record of its last run is read): CI3 on {page} - {'; '.join(r.get('held') or [])}. "
                f"The phone-fit pool was a hand-written 51 pages and the axe list 12; on 2026-10-15 both became the "
                f"program's pages (a public page read signed out, as its visitor), each page's first measurement its floor. "
                f"Phone-fit run {results.get('phone_run')}, axe run {results.get('axe_run')}. Teeth: a page missing from a "
                f"ratchet's run, and a count above its floor, are each caught ({(results.get('teeth') or {}).get('bit')})." + tail)
    if sublayer == "H4":
        r = per["chromium"][0]
        v1, v2 = r.get("v1") or {}, r.get("v2") or {}
        return (head + "): H4 on " + page + f" - a RETURNING DEVICE built for real: a fresh profile visited the page while "
                f"the origin served commit {results.get('from')} ({results.get('old_cache')}, file by file from git through "
                f"serve_vercel_headers --ref), so the old worker installed and kept its copies; then the same origin served the "
                f"working tree ({results.get('now_cache')}). Visit 1: {'/'.join(v1.get('builds') or []) or 'no differing file'} "
                f"({v1.get('informative')} differing file(s) read{', after ' + str(v1.get('reloads')) + ' reload(s)' if v1.get('reloads') else ''}) "
                f"- one build, never half new and half old; visit 2: {'/'.join(v2.get('builds') or []) or 'no differing file'}; "
                f"caches after: {', '.join(r.get('caches') or [])}. Teeth: the new page with an OLD "
                f"{(results.get('teeth') or {}).get('planted')} is caught as mixed ({(results.get('teeth') or {}).get('bit')})." + tail)
    if sublayer == "CI2":
        c, w = per["chromium"][0], per["webkit"][0]
        runs = results.get("runs") or {}
        if c.get("page_class") == "public":
            what = (f"signed out, as the visitor it is for, the reader's job walked by tools/prove_public_journeys.mjs - "
                    f"Chromium: {c.get('how')}; WebKit: {w.get('how')}")
        else:
            what = (f"the page's registered jobs-to-be-done (tools/live_page_journeys.mjs, the same registry in both engines) - "
                    f"Chromium: {c.get('how')}; WebKit: {w.get('how')}")
        return (head + f"): CI2 on {page} - {what}. Runs: " + ", ".join(f"{k} {v}" for k, v in runs.items())
                + f". Teeth: a page whose WebKit walk is taken away, and a page whose only journeys turn gap, each read "
                  f"open ({(results.get('teeth') or {}).get('bit')})." + tail)
    if sublayer == "F3":
        r = per["chromium"][0]
        who = "signed out, as the visitor it is for" if r.get("as") == "signed out" else "signed in through the harness"
        return (head + f", {who}): F3 on {page} - {r.get('reached')}/{r.get('controls')} offered control(s) reached by a "
                f"REAL Tab walk at 1280 (a composite widget's roving members by one of them), each with a visible focus "
                f"(its computed look against its look at rest, the parent's for :focus-within); axe-core's own name rules "
                f"({', '.join(['button-name', 'link-name', 'label', 'select-name', 'input-button-name', 'aria-command-name', 'aria-input-field-name', 'aria-toggle-field-name'])}) "
                f"read 0; and every target at 390 on a phone context is at least 44x44 CSS px (WCAG 2.5.5 - a link inline "
                f"in a sentence exempt by name, a checkbox or radio measured with its label). Counts {r.get('counts')}. "
                f"Teeth (same run, same contexts): a planted unnamed icon button, invisible focus, 20px target and "
                f"tabindex=-1 link read {(results.get('teeth') or {}).get('slop')}, their clean twin "
                f"{(results.get('teeth') or {}).get('clean')}." + tail)
    if sublayer == "F2":
        r = per["chromium"][0]
        runs = results.get("runs") or {}
        who = ("signed out, as the visitor it is for" if t.get("sl", {}).get("page_class") == "public"
               else "signed in through the harness (Leandro Marquez, a supervisor and platform admin - a retired page "
                    "measured as the overlay it shows him)")
        return (head + f", {who}): F2 on {page} - the phone-fit lens's own record reads "
                + ", ".join(f"{k.split('@')[1]} wide: {v} issue(s)" for k, v in (r.get("read") or {}).items())
                + " - no horizontal overflow, no element outside the viewport, no clipped or spilled text, no unbroken "
                  "token wider than its box, no element overflowing its clipping container, no occluded control, and "
                  "every more/menu trigger's menu inside the viewport; 320 and 390 are phones (mobile, touch, DPR 2), "
                  "1280 a desktop (no touch, DPR 1). Runs: "
                + ", ".join(f"{k} {v}" for k, v in runs.items())
                + f". Teeth: a page missing from an axis, and one issue on an axis, are each caught "
                  f"({(results.get('teeth') or {}).get('bit')})." + tail)
    if sublayer == "F5":
        r = per["static"][0]
        teeth = results.get("teeth") or {}
        return (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via {spec['prover']} (gate {spec['gate']}; each reading from "
                f"the instrument that owns it): F5 on {page} - the design ratchet's own pipeline (impeccable detect + the "
                f"declared-dot leg, motion antipatterns included) reads {r.get('detector')} primary finding(s); "
                f"{r.get('rogue_radii')} corner(s) off DESIGN.md's radius scale by validate_design_tokens' own rule; "
                f"{r.get('bare_hex')} brand colour(s) written as bare hex in CSS. The 119 public pages reached 0 on "
                f"2026-10-15: 765 corners mapped onto the scale BY ROLE (section cards 16px, pills 999px, buttons and the "
                f"skip link 8px, inline code and chips 8px) and 2,523 brand colours made token references "
                f"(var(--wh-*, #fallback): they load no tokens.css), in the pages and in the generators that write them. "
                f"Teeth: a planted off-scale corner, a bare brand hex and a 9px label each fail a clean page "
                f"({teeth.get('bit')})." + tail)
    if sublayer == "CI4":
        r = per["static"][0]
        teeth = results.get("teeth") or {}
        return (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via {spec['prover']} (gate {spec['gate']}; every registry "
                f"read from its own source, never retyped): CI4 on {page} ({r.get('class')} page) - listed in "
                f"{len(r.get('listed') or [])} registries: {'; '.join(r.get('listed') or [])}. No sitemap entry, hub href, "
                f"SW shell page or founder name points at a page that does not exist ({len(results.get('dangling') or [])} "
                f"dangling). Found on the way: the five founder pages were outside the design ratchet's scope, which now "
                f"reads them (floor re-measured with the reason recorded). Teeth: a public, a production and a founder "
                f"page each taken out of its class's registry, and a planted dangling sitemap entry, were all caught "
                f"({teeth.get('bit')})." + tail)
    if sublayer == "CI1":
        r = per["static"][0]
        return (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via {spec['prover']} (gate {spec['gate']}; the registered "
                f"gates' own detectors run on the page and on a temporary BREACHED copy, never the file itself): CI1 on "
                f"{page} - csp-covers-what-ships reads the page clean against the policy vercel.json resolves for its path "
                f"and reddens when the copy loads a script from an origin that policy does not name ({r.get('covers_said')}); "
                f"scripts-parse reads it clean and reddens on an inline script that does not parse. Two registered gates "
                f"hold this page's contract, each shown to bite on it." + tail)
    if sublayer in ("CA2", "H2"):
        r = per["http"][0]
        c = r.get("checked") or {}
        teeth = results.get("teeth") or {}
        return (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via {spec['prover']} (gate {spec['gate']}; over HTTP "
                f"against tools/serve_vercel_headers.py, the local substitute for the Vercel edge serving vercel.json's own "
                f"rules - the dev seeder on :5000 is a rewriting test proxy that answers no-store, fresher than every "
                f"class, and is not a surface a person is served from): {sublayer} on {page} - {c.get('html')} page path(s) "
                f"(a directory page also at the path the deploy serves it, trailingSlash false), {c.get('code')} script/"
                f"stylesheet(s) and {c.get('image')} image(s) it loads, and sw.js, each with its class's Cache-Control "
                f"(HTML max-age=0 + must-revalidate; scripts/styles the same plus an ETag/Last-Modified validator; images "
                f"a year, immutable; sw.js no-store), and the server sent exactly what vercel.json says. Found and fixed "
                f"on the way: the 119 public directory pages had NO cache header at their served path. Teeth: under "
                f"{teeth.get('commit')}'s vercel.json {teeth.get('failed_under_commit')}/{teeth.get('directory_pages')} "
                f"directory pages fail, and with scripts cached an hour {teeth.get('failed_with_hour_scripts')}/"
                f"{teeth.get('pages')} pages fail." + tail)
    if sublayer in ("S4", "S5"):
        r = per["chromium"][0]
        who = ("as the visitor it is for (signed out)" if t.get("persona") == "anon"
               else f"signed in as {t.get('persona')} through the product's own form")
        teeth = results.get("teeth") or {}
        if sublayer == "S4":
            if r.get("noText"):
                reading = (f"its {r.get('responses')} database read(s) carry no free text - the page renders no stored "
                           f"text that could become markup ({r.get('chars')} characters on screen)")
            else:
                reading = (f"{r.get('fields')} poisoned field(s) in {r.get('responses')} response(s) "
                           f"({', '.join(r.get('poisonedReads') or [])}), rendered as TEXT {r.get('shown')} time(s), "
                           f"{r.get('visible')} visible (e.g. \"{r.get('line')}\"), the handler ran {r.get('ran')} time(s), "
                           f"{r.get('elements')} payload element(s) in the DOM")
            return (head + f", {who}; every database read the page made - tables and rpc - was answered with its stored "
                    f"free text carrying the payload {results.get('payload')!r} (the reader's own name, hive and admin "
                    f"grant are poisoned only on the pages that draw them, index and hive, so every other page's start-up "
                    f"keeps working), and every table write held so the poison never reached the database): S4 on {page} - "
                    f"{reading}. Every value drawn into an inline handler goes through escJsAttr (gate "
                    f"handler-values-escaped). Teeth: {teeth.get('page')} served a utils.js whose escHtml returns its input "
                    f"unchanged - the payload ran {teeth.get('ran')} time(s) and became {teeth.get('elements')} "
                    f"element(s)." + tail)
        return (head + f", {who}): S5 on {page} - {r.get('responses')} response bodies ({r.get('kb')} KB: the HTML, every "
                f"script and stylesheet, every database and edge answer) and the page's localStorage / sessionStorage "
                f"scanned for the {len(results.get('secrets_checked') or [])} secret VALUE(s) .env holds (by name: "
                f"{', '.join(results.get('secrets_checked') or [])}), any JWT whose role is not anon or authenticated, "
                f"and {len(results.get('shapes') or [])} key shapes ({', '.join(results.get('shapes') or [])}): none "
                f"served. Teeth: {teeth.get('page')} served a planted service_role-shaped token and an .env secret value "
                f"- both caught (shape {teeth.get('caughtShape')}, value {teeth.get('caughtValue')})." + tail)
    if sublayer == "S3":
        r = per["chromium"][0]
        who = ("as the visitor it is for (signed out)" if t.get("persona") == "anon"
               else f"signed in as {t.get('persona')} through the product's own form")
        used = sum(len(v) for v in (r.get("used") or {}).values())
        why = "; ".join(f"{k} <- {v}" for k, v in (r.get("basis") or {}).items())
        teeth = results.get("teeth") or {}
        return (head + f", {who}, the document served the policy vercel.json resolves for its own path through "
                f"tools/serve_vercel_headers.py - the one matcher - with only the production Supabase origins mapped to "
                f"the local stack): S3 on {page} - {r.get('chars')} chars rendered, {used} origin(s) loaded across "
                f"{len(r.get('used') or {})} directive(s), 0 CSP violations, every origin it loaded named. NOTHING MORE: "
                f"the policy names {len(r.get('named') or [])} origin(s), each with its basis ({why or 'none - only self'}), "
                f"and no scheme wildcard. Teeth: under {teeth.get('commit')}'s site-wide policy {teeth.get('failed')} of "
                f"{teeth.get('pages')} page(s) named origins with no basis (e.g. {teeth.get('sample')})." + tail)
    chars = " and ".join(f"{rs[0].get('chars')} chars in {e.capitalize()}" for e, rs in per.items())
    return (head + f", signed in as {t.get('persona')} through the product's own sign-in form, every document served the "
            f"SHIPPED vercel.json CSP and Permissions-Policy with only the production Supabase origins mapped to the local "
            f"stack): {sublayer} on {page} as-served {chars}, 0 CSP violations, 0 uncaught client_errors inserts, 0 "
            f"pageerrors, no busy indicator left. What the page DOES on an action (a blob: image, a played audio) is held by "
            f"csp-covers-what-ships, extended 2026-10-14 (c1192af4) after this walk found img-src without blob: and no "
            f"media-src." + tail)


def _load_registry() -> dict:
    return json.load(io.open("trajectory_registry.json", encoding="utf-8"))


def _write_registry(reg: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(ROOT), suffix=".tmp")
    with io.open(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(reg, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, "trajectory_registry.json")


def _run_gate(script: str, *args: str) -> tuple[bool, str]:
    exe = ["node", script] if script.endswith(".mjs") else [sys.executable, script]
    r = subprocess.run(exe + list(args), capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    last = next((ln for ln in reversed(out.strip().splitlines()) if "PASS" in ln or "FAIL" in ln), out.strip()[-160:])
    return r.returncode == 0, last.strip()[:200]


def _readings(results: dict, page: str, condition: str | None, engine: str) -> list[dict]:
    return [r for r in results.get("results", []) if r.get("page") == page and r.get("engine") == engine
            and (condition is None or r.get("condition") == condition)]


def _bank(reg: dict, rid: str, basis: str, gates: list[str]) -> None:
    t = next(x for x in reg["trajectories"] if x["id"] == rid)
    locked = t.get("status") == "locked"
    st, pct = ("locked", 100) if locked else ("locking", 60)
    old = t.get("basis") or ""
    t["status"], t["pct"] = st, pct
    t["basis"] = basis.replace("{pct}", str(pct)) + (" || " + old if old else "")
    arts = t.setdefault("artifacts", {})
    arts["gates"] = sorted(set(arts.get("gates") or []) | set(gates))


def _closed(rids: list[str]) -> dict:
    import live_walk_manifest as lm
    bm = lm.build()
    rows = {x["id"]: x for x in (bm["rows"] if isinstance(bm, dict) else bm)}
    return {rid: lm.row_closed(rows[rid]) for rid in rids if rid in rows}


def bank_prover(results_path: str, sublayer: str, gates_only: bool) -> int:
    if sublayer not in PROVER_READS:
        print(f"no prover reading is defined for {sublayer} - nothing banked")
        return 1
    results = json.load(io.open(results_path, encoding="utf-8"))
    spec = PROVER_READS[sublayer]
    condition, engines = spec["condition"], spec["engines"]
    gate_lines = []
    for g in GATES[sublayer]:
        script = None if g == spec["gate"] else GATE_SCRIPTS.get(g)   # the prover's own run IS the results file
        if g in RECORD_GATES:
            run = (results.get("runs") or {}).get(RECORD_GATES[g])
            if not run:
                print(f"gate {g} has no run on file in the prover's record - nothing banked")
                return 1
            gate_lines.append(f"{g} RECORD (run {run})")
            continue
        if not script:
            continue
        ok, line = _run_gate(script, *GATE_ARGS.get(g, ()))
        gate_lines.append(f"{g} {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"gate {g} is not green ({line}) - nothing banked")
            return 1
    if not (results.get("teeth") or {}).get("bit"):
        print("the prover's teeth did not bite on this run - nothing banked")
        return 1
    if sublayer == "L1" and not all(x.get("rows_in_table", 0) >= 2 for x in (results.get("real") or [{}])):
        print("an anonymous error did not land through the policy on this run - nothing banked")
        return 1
    reg = _load_registry()
    today = time.strftime("%Y-%m-%d")
    banked, skipped = [], []
    for t in reg["trajectories"]:
        s = t.get("sl") or {}
        if s.get("sublayer") != sublayer or t.get("status") in ("locking", "locked", "descoped"):
            continue
        page = s.get("page")
        per = {e: _readings(results, page, condition, e) for e in engines}
        if not all(per.values()):
            continue                                 # the prover never read this page in every engine
        bad = [f"{e}: {'; '.join(r['problems'])}" for e, rs in per.items() for r in rs if not r.get("ok")]
        if bad:
            skipped.append(f"{t['id']} {page}: " + " | ".join(bad)[:200])
            continue
        basis = _basis(sublayer, t, page, per, gate_lines, results_path, results, today)
        if not gates_only:
            _bank(reg, t["id"], basis, GATES[sublayer])
        banked.append(t["id"])
    if not banked:
        print(f"nothing to bank for {sublayer}" + (f" - held: {skipped}" if skipped else ""))
        return 1 if skipped else 0
    if not gates_only:
        _write_registry(reg)
    closed = _closed(banked) if not gates_only else {}
    print(f"{sublayer}: banked {len(banked)} row(s) {banked}" + (f"; held {len(skipped)}: {skipped}" if skipped else ""))
    if closed:
        print(f"  CLOSED: {sum(closed.values())}/{len(closed)}" + ("" if all(closed.values()) else f" - open: {[k for k, v in closed.items() if not v]}"))
    return 0


def bank_refusal(sublayer: str, dry: bool) -> int:
    """S1 (read scope): every row's page through tools/prove_w4_layer_s.py's recipe - a foreign-hive member on the
    authenticated path, in a rolled-back transaction, must read zero of this hive's rows while the page's own member
    reads its own (the control). The gate w4-layer-entitlement runs the same recipe over every S row, SL S1 included."""
    if sublayer == "S2":
        return _bank_write_refusal(dry)
    if sublayer != "S1":
        print(f"no refusal recipe is defined for {sublayer} - nothing banked")
        return 1
    import prove_w4_layer_s as pw
    ok, line = _run_gate("tools/prove_w4_layer_s.py", "--check")
    if not ok:
        print(f"gate w4-layer-entitlement is not green ({line}) - nothing banked")
        return 1
    reg = _load_registry()
    rows = [t for t in reg["trajectories"] if (t.get("sl") or {}).get("sublayer") == "S1"
            and t.get("status") not in ("locking", "locked", "descoped")]
    pages = sorted({t["sl"]["page"] for t in rows})
    hive_tabs = pw.hive_id_tables(set().union(*(pw.tables_of(p) for p in pages)) if pages else set())
    verdict = {p: pw.check_page(p, hive_tabs) for p in pages}
    today = time.strftime("%Y-%m-%d")
    banked, held = [], []
    for t in rows:
        v, w = verdict[t["sl"]["page"]]
        if v == "BAD":
            held.append(f"{t['id']} {w[:160]}")
            continue
        how = ("refused a foreign hive" if v == "ok" else "nothing to refuse")
        basis = (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via tools/prove_w4_layer_s.py (gate w4-layer-entitlement, "
                 f"invoke + PostgREST as the caller: a member of ANOTHER hive, role authenticated + their JWT claims, in a "
                 f"rolled-back transaction, never the owner connection): S1 on {t['sl']['page']} - {how}. {w} Gate: "
                 f"{line[:160]}")
        if not dry:
            _bank(reg, t["id"], basis, ["w4-layer-entitlement", "rls-strict"])
        banked.append(t["id"])
    if not dry and banked:
        _write_registry(reg)
    print(f"S1: banked {len(banked)} row(s)" + (f"; HELD {len(held)} (a foreign hive read this hive's rows): {held}" if held else ""))
    return 1 if held else 0


def _bank_write_refusal(dry: bool) -> int:
    """S2 (write policies): tools/gen_write_authz_recipes.py --sl - for every table each S2 page WRITES (measured from
    its source), a member of ANOTHER hive on the authenticated path must touch 0 of this hive's rows on UPDATE and DELETE,
    and must not be able to MOVE their own row into a foreign hive (the WITH CHECK half); the page's own member is the
    control. Its recipes land in tools/psql_probes/, which the gate psql-probe-suite re-executes on every board."""
    import re as _re
    r = subprocess.run([sys.executable, "tools/gen_write_authz_recipes.py", "--sl"], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    verdict = {}
    for ln in (r.stdout or "").splitlines():
        m = _re.match(r"\s+(PASS|n/a|FAIL)\s+(\S+)\s+(.*)", ln)
        if m:
            verdict[m.group(2)] = (m.group(1), m.group(3))
    ok, line = _run_gate("tools/validate_psql_probe_suite.py")
    if not ok:
        print(f"gate psql-probe-suite is not green ({line}) - nothing banked")
        return 1
    reg = _load_registry()
    today = time.strftime("%Y-%m-%d")
    banked, held = [], []
    for t in reg["trajectories"]:
        sl = t.get("sl") or {}
        if sl.get("sublayer") != "S2" or t.get("status") in ("locking", "locked", "descoped"):
            continue
        page = sl.get("page")
        v, detail = verdict.get(page, ("missing", "the recipe run named no verdict for this page"))
        if v not in ("PASS", "n/a"):
            held.append(f"{t['id']} {page}: {v} {detail[:120]}")
            continue
        recipe = f"tools/psql_probes/{page.replace('.html', '')}__write_authz_depth.sql"
        what = (f"refused a foreign-hive request: on every hive-scoped table {page} writes, a member of ANOTHER hive "
                f"touched 0 of this hive's rows on UPDATE and DELETE and could not move their own row into a foreign hive "
                f"(the WITH CHECK half), the page's own member served as the control - {detail} - recipe {recipe}"
                if v == "PASS" else f"nothing to refuse: {page} {detail}")
        basis = (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via tools/gen_write_authz_recipes.py --sl (invoke + "
                 f"PostgREST as the caller: role authenticated + the member's JWT claims in a rolled-back transaction, never "
                 f"the owner connection): S2 on {page} - {what}. The WITH CHECK half found marketplace_sellers and "
                 f"resume_documents accepting a row moved into a foreign hive; fixed by migration 20261014000003. Gate: "
                 f"psql-probe-suite {line[:80]}")
        if not dry:
            _bank(reg, t["id"], basis, ["psql-probe-suite"])
        banked.append(t["id"])
    if not dry and banked:
        _write_registry(reg)
    print(f"S2: banked {len(banked)} row(s)" + (f"; HELD {len(held)}: {held}" if held else ""))
    return 1 if held else 0


def bank_walk(rid: str, steps: str, witness: str, note: str, webkit: str | None, unproven: str,
              check: bool = True, instrument: str = "chrome-devtools-mcp") -> int:
    reg = _load_registry()
    t = next((x for x in reg["trajectories"] if x["id"] == rid), None)
    # a BRH row (the bug-hunt wave) carries the same receipt contract - a named person at both viewports - and is
    # settled by the same walk as the SL sub-layer that met its defect class (BRH-F <- AU2, 2026-10-14)
    # ...and so does an ENH row (an enhancement built, then walked as the page's cast at both viewports): its key is
    # its class, ENH-<cls>, with its own gates and condition below (ENH-R first, 2026-10-19)
    if not t or not (t.get("sl") or t.get("brh") or t.get("enh")):
        print(f"{rid}: not an SL, BRH or ENH row")
        return 1
    s = t.get("sl") or t.get("brh") or t["enh"]
    key = (s.get("sublayer") if t.get("sl") else BRH_CLASS_SUBLAYER.get(s.get("cls"), "") if t.get("brh")
           else "ENH-" + str(s.get("cls") or ""))
    if t.get("enh") and key not in GATES:
        print(f"{rid}: no walk is defined for enhancement class {s.get('cls')} - nothing banked")
        return 1
    if t.get("brh") and not key:
        print(f"{rid}: no walk is defined for bug-hunt class {s.get('cls')} - nothing banked")
        return 1
    if str(s.get("instrument", "")).startswith("library"):
        print(f"{rid}: a contract row closes on its prover (--prover), not on a walk")
        return 1
    engine = "chromium"
    if s.get("engine") == "webkit":
        if not webkit:
            print(f"{rid}: an engine-sensitive row needs --webkit <the WebKit run's results> - nothing banked")
            return 1
        res = json.load(io.open(webkit, encoding="utf-8"))
        wk = [r for r in res.get("results", []) if r.get("page") == s.get("page") and r.get("engine") == "webkit"]
        if not wk or not all(r.get("ok") for r in wk):
            print(f"{rid}: the WebKit run holds no clean reading for {s.get('page')} - nothing banked")
            return 1
        engine = "webkit"
        witness = (f"WebKit half: {PROVER} ({webkit}, {res.get('generated')}): {s.get('page')} "
                   + "; ".join(f"{r['condition']} {r.get('chars')} chars, clean" for r in wk) + f". {witness}")
    cmd = [sys.executable, "tools/record_mcp_walk.py", "--id", rid, "--instrument", instrument,
           "--layer", s["layer"], "--as-persona", t.get("persona") or "",
           "--viewports", "phone-390,desktop-1280", "--engine", engine, "--steps", steps,
           "--witness", witness[:1900], "--note", note[:1500]]
    if t.get("sl"):
        cmd += ["--sublayer", s["sublayer"]]
    if unproven:
        cmd += ["--unproven", unproven[:400]]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = ((r.stdout or "") + (r.stderr or "")).strip()
    print(" ", out.splitlines()[-1][:220] if out else "(recorder said nothing)")
    if r.returncode != 0 or "refused" in out.lower() or "ok=True" not in out or unproven:
        print(f"{rid}: NOT banked")
        return 1
    today = time.strftime("%Y-%m-%d")
    how = (CONDITION.get("BRH-" + str(s.get("cls"))) if t.get("brh") else None) or CONDITION.get(key, CONDITION_DEFAULT)
    view = ("a TRUE 390 and 1280 through CDP" if instrument.startswith("chrome-devtools")
            else "390x844 and 1280x800 set through Playwright; every edge call carried x-wh-walk-no-model through a context "
                 "route, so no model was called")
    basis = (f"[{today}] pct -> {{pct}}. WALKED LIVE {today} via {instrument} ({view}, "
             f"signed in as {t.get('persona')} through the product's own sign-in form; {how}): {note} "
             f"Witness: {witness[:1200]} Receipt .tmp/mcp_walks/{rid}.json.")
    reg = _load_registry()
    _bank(reg, rid, basis, GATES.get(key, ["page-survives-optional-failures"]))
    _write_registry(reg)
    if not check:                       # a batch checks closure ONCE at its end (--check-closed): the ledger build is
        print(f"{rid}: banked")         # ~90 s, and per row it turned a 20-row bank into a 30-minute run (2026-10-14)
        return 0
    closed = _closed([rid])
    print(f"{rid}: CLOSED={closed.get(rid)}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prover", help="a prove_page_survives_optional_failures.mjs results file")
    ap.add_argument("--refusal", action="store_true", help="with --sublayer S1: bank through the foreign-hive refusal recipe")
    ap.add_argument("--sublayer", help="with --prover: the contract sub-layer to bank (H1)")
    ap.add_argument("--dry-run", action="store_true", help="with --prover: check gates and readings, write nothing")
    ap.add_argument("--walk", help="the SL id of a walk row")
    ap.add_argument("--steps")
    ap.add_argument("--witness", default="")
    ap.add_argument("--note", default="")
    ap.add_argument("--webkit", help="the WebKit run's results file, for an engine-sensitive row")
    ap.add_argument("--unproven", default="")
    ap.add_argument("--no-check", action="store_true", help="with --walk: skip the per-row ledger rebuild")
    ap.add_argument("--check-closed", nargs="+", help="report CLOSED for these ids (one ledger build)")
    a = ap.parse_args()
    if a.check_closed:
        c = _closed(a.check_closed)
        print(f"CLOSED {sum(c.values())}/{len(c)}" + ("" if all(c.values()) else f" - open: {[k for k, v in c.items() if not v]}"))
        return 0 if all(c.values()) else 1
    if a.refusal:
        return bank_refusal(a.sublayer or "", a.dry_run)
    if a.prover:
        return bank_prover(a.prover, a.sublayer or "", a.dry_run)
    if a.walk:
        return bank_walk(a.walk, a.steps, a.witness, a.note, a.webkit, a.unproven, check=not a.no_check)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
