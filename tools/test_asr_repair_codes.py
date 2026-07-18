import re
from collections import defaultdict

# Faithful copy of asr_server._EQUIP_WORDS + _repair_codes for logic verification.
_EQUIP_WORDS = {
    "PB": ("pump", "bomba", "bomba ng", "pamp"),
    "AC": ("compressor", "air compressor", "kompresor", "kompressor"),
    "CH": ("chiller",), "CT": ("cooling tower", "tower", "cooling"),
    "AHU": ("air handler", "air handling", "ahu"), "BLR": ("boiler", "boyler"),
    "BF": ("boiler feed", "feed pump", "belt feeder"), "BE": ("bucket elevator", "elevator", "elebeytor"),
    "FL": ("filter", "salaan"), "TX": ("transformer", "transpormer"), "FN": ("fan", "blower", "bentilador"),
    "MTR": ("motor",), "GB": ("gearbox", "gear box"), "CV": ("conveyor", "conveyor belt", "kombeyor"),
    "VP": ("vacuum pump", "vacuum"), "HX": ("heat exchanger", "exchanger"),
}


def _repair_codes(text, vocab):
    if not vocab:
        return text
    tags = [t.strip() for t in vocab if t.strip()]
    for tag in sorted(set(tags), key=len, reverse=True):
        m = re.match(r"^([A-Za-z]+)[-\s.]*(\d+)$", tag)
        if not m:
            continue
        pre, dig = m.group(1), m.group(2)
        prepat = r"[-\s.]*".join(re.escape(c) for c in pre)
        digpat = r"[-\s.]*".join(dig)
        pat = re.compile(r"\b" + prepat + r"[-\s.]*" + digpat + r"\b", re.IGNORECASE)
        text = pat.sub(tag, text)
    suffix_map = defaultdict(dict)
    for tag in set(tags):
        mm = re.match(r"^([A-Za-z]+)[-\s.]*(\d+)$", tag)
        if mm:
            suffix_map[mm.group(2)][mm.group(1).upper()] = tag
    src = text

    def _repair_bare(match):
        raw = match.start()
        before = src[max(0, raw - 4):raw]
        if re.search(r"[A-Za-z][-.]{0,2}$", before):
            return match.group(0)
        digits = re.sub(r"[^\d]", "", match.group(0))
        cands = suffix_map.get(digits)
        if not cands:
            return match.group(0)
        if len(cands) == 1:
            return next(iter(cands.values()))
        window = src[max(0, raw - 40):raw].lower()
        best_pre, best_pos = None, -1
        for pre in cands:
            for w in _EQUIP_WORDS.get(pre, ()):
                pos = window.rfind(w)
                if pos > best_pos:
                    best_pos, best_pre = pos, pre
        if best_pre is not None:
            return cands[best_pre]
        return match.group(0)

    text = re.sub(r"(?<![A-Za-z])\d(?:[-\s.]*\d){2,}", _repair_bare, text)
    return text


V3 = ["PB-001", "AC-001", "CH-001"]   # collided suffix 001
cases = [
    # (text, vocab, expected, label)
    ("check A C 002 please", ["AC-002"], "check AC-002 please", "primary: prefix survives + sep noise"),
    ("A C 001 and P B 001", ["AC-001", "PB-001"], "AC-001 and PB-001", "primary: collided suffix, both prefixes survive"),
    ("torque AC-003 done", ["AC-003"], "torque AC-003 done", "CORRUPTION GUARD: correct code untouched (no AC-AC-003)"),
    ("the pump 0-0-1 is leaking", V3, "the pump PB-001 is leaking", "lost-prefix + 'pump' -> PB"),
    ("ang bomba 0 0 1", V3, "ang bomba PB-001", "lost-prefix + Tagalog 'bomba' -> PB"),
    ("the compressor 001 tripped", V3, "the compressor AC-001 tripped", "lost-prefix + 'compressor' -> AC"),
    ("the chiller 001 alarm", V3, "the chiller CH-001 alarm", "lost-prefix + 'chiller' -> CH"),
    ("just 001 no context", V3, "just 001 no context", "ambiguous + NO equipment word -> leave alone (no guess)"),
    ("unit 0-0-7 down", ["PB-007"], "unit PB-007 down", "unambiguous lost-prefix -> fill directly"),
    ("PB-001 and PB-002 both", ["PB-001", "PB-002"], "PB-001 and PB-002 both", "correct codes untouched"),
    ("call 911 now", ["PB-001"], "call 911 now", "bare digits not in vocab -> untouched"),
    ("pump 001 and compressor 001", V3, "pump PB-001 and compressor AC-001", "two lost-prefix, each disambiguated"),
]
p = f = 0
for text, vocab, exp, label in cases:
    got = _repair_codes(text, vocab)
    ok = got == exp
    print(("PASS " if ok else "FAIL ") + label)
    if not ok:
        print("   in : " + text + "\n   exp: " + exp + "\n   got: " + got)
    p, f = (p + (1 if ok else 0), f + (0 if ok else 1))
print(f"\n{p}/{len(cases)} pass, {f} fail")
