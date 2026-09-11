#!/usr/bin/env python3
"""derive_fil_guidance_vocab.py — derive X1's FILIPINO guidance vocabulary from the platform's own
parallel corpus, instead of hand-adding one verb at a time.

★WHY THIS EXISTS. X1 asks whether an empty/error state offers a way onward. It answers by looking for
guidance vocabulary, and its English list is broad ("add", "create", "start", "tap", "register"...).
Its Filipino list was hand-extended twice and still failed a third time: `inventory` graded X1 75% on
"Walang nakarehistrong asset. Irehistro muna ang mga asset sa Logbook." — which NAMES its recovery path —
while the SAME panel in English ("No assets registered. Register assets in the Logbook first.") graded
X1 100%. Same page, same panel, one difference: the language. Filipino builds imperatives by PREFIX
(i-, mag-, ma-) and SUFFIX (-in, -an), so a list holding `i-save` and `simulan` will keep missing
`irehistro` and `magsimula` forever. Enumerating verbs is the wrong shape of solution.

★THE STRUCTURE. `i18n/*.json` maps each ENGLISH string to its shipped FILIPINO — a parallel corpus.
If the English side of a pair contains a guidance verb, then the Filipino side IS guidance, by
construction. So the Filipino vocabulary can be DERIVED from the English one rather than guessed: this
tool finds every pair whose English matches X1's English guidance regex, extracts the Filipino tokens
that carry imperative morphology, and ranks them. The output is a measured word list with provenance —
each token traceable to the sentence pair that produced it — which is pasted into survey_ufai_rubric.js.

Re-run it whenever the dictionaries grow; a vocabulary derived from the corpus stays true to the corpus.

    python tools/derive_fil_guidance_vocab.py            # ranked tokens + the pair each came from
    python tools/derive_fil_guidance_vocab.py --regex    # emit the regex fragment for the rubric
"""
from __future__ import annotations

import argparse
import glob
import io
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# X1's ENGLISH guidance vocabulary, kept in step with survey_ufai_rubric.js `_guide`.
EN_GUIDE = re.compile(
    r"\badd\b|\bcreate\b|\bnew\b|\bstart\b|\btap\b|\bclick\b|\bgenerate\b|\bupload\b|\bimport\b"
    r"|\binvite\b|\bbrowse\b|\blog\b|\bpost\b|\btry\b|\badjust\b|\bfilter|\bmatch|\bclear\b|\breset\b"
    r"|\brefresh\b|\bsearch\b|\bfill\b|\bregister\b|\bopen\b|\brun\b|\bwire\b|\bwiden\b|\bconnect\b"
    r"|\bselect\b|\benable\b|\bgo to\b|check back|lands? here|surface[sd]? here|appears? here"
    r"|will (appear|show|surface)|use the\b|\bvia\b", re.I)

# Filipino imperative / instruction morphology. A token is a CANDIDATE only if it carries one of these
# shapes — this is what keeps ordinary nouns and function words out of a vocabulary meant for verbs.
FIL_SHAPE = re.compile(
    r"^(?:i-[a-z]{2,}"          # i-save, i-upload, i-click       (i- prefix, hyphenated loanword)
    r"|i[a-z]{4,}"              # idagdag, irehistro               (i- prefix, native root)
    r"|mag-?[a-z]{3,}"          # magdagdag, magsimula, mag-log
    r"|[a-z]{3,}(?:in|an)"      # piliin, simulan, buksan, hanapin (-in / -an imperative suffix)
    r"|ma[a-z]{4,})$",          # makikita, magpapakita
    re.I)

# Words that pass the morphology test but are not guidance — measured stop-list, kept explicit so a
# reader can see exactly what was excluded and why.
STOP = {
    "iyong", "ilan", "ito", "iba", "isang", "itong", "ibang", "iyon", "ikaw",
    "marami", "maliit", "malaki", "mabilis", "maayos", "maaari", "maaaring", "matapos",
    "walan", "wala", "naman", "lamang", "kailan", "paanan", "kahit",
    "makita", "makuha",           # bare potentials, not instructions
    "asignatura",
}


def pairs() -> list[tuple[str, str, str]]:
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "i18n", "*.json"))):
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        for en, fil in d.items():
            if not isinstance(en, str) or not isinstance(fil, str) or not fil.strip():
                continue
            if en.startswith("_"):
                continue
            out.append((os.path.basename(p), en, fil))
    return out


def derive():
    tok = Counter()
    prov = defaultdict(list)
    for src, en, fil in pairs():
        if not EN_GUIDE.search(en):
            continue
        for w in re.findall(r"[A-Za-zÀ-ÿ-]+", fil):
            lw = w.lower()
            if lw in STOP or len(lw) < 4:
                continue
            if FIL_SHAPE.match(lw):
                tok[lw] += 1
                if len(prov[lw]) < 2:
                    prov[lw].append((src, en[:52], fil[:52]))
    return tok, prov


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--regex", action="store_true", help="emit the regex fragment for survey_ufai_rubric.js")
    ap.add_argument("--min", type=int, default=2, help="minimum occurrences to include (default 2)")
    a = ap.parse_args()
    tok, prov = derive()
    keep = [w for w, n in tok.most_common() if n >= a.min]
    if a.regex:
        print("|".join(rf"\b{re.escape(w)}\b" for w in sorted(keep)))
        return 0
    print(f"parallel pairs whose ENGLISH carries a guidance verb: "
          f"{sum(1 for s, e, f in pairs() if EN_GUIDE.search(e))}")
    print(f"Filipino tokens with imperative morphology (>= {a.min} occurrences): {len(keep)}\n")
    for w in sorted(keep, key=lambda x: -tok[x]):
        s, e, f = prov[w][0]
        print(f"  {w:18s} x{tok[w]:<3d}  {s:24s} EN {e!r}")
        print(f"  {'':18s}      {'':24s} FIL {f!r}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
