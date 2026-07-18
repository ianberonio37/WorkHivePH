"""validate_no_client_counter_write.py — STATIC P6 lost-update regression gate.

Locks the class fixed by mig 20260713000008 (inventory qty_on_hand) + closed platform-wide:
a client that reads a shared counter, computes a new ABSOLUTE value, and writes it back via
`.update({counter: x})` / `.upsert({counter: x})` races every concurrent writer — the classic
lost-update. The platform's discipline is that EVERY counter/value-integrity mutation goes through
an atomic server RPC (inventory_deduct/inventory_restock FOR-UPDATE, increment_*, grade_*, award_*),
which serialises the read-modify-write under a row lock.

This gate greps all page HTML for a client `.update(...)`/`.upsert(...)` whose object literal SETS
one of the value-integrity counter fields, and FAILs on any hit (they must be RPC-mediated instead).
The live sweep on 2026-07-14 found ZERO such writes; this gate keeps it at zero. It is static (no DB),
so it runs in --fast and can never flake on infra.

If a legitimate client counter-write is ever needed (it should not be), add it to ALLOW with a reason.
"""
import sys, re
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; RESET = "\033[0m"; BOLD = "\033[1m"
ROOT = Path(__file__).resolve().parent.parent

# value-integrity counters: a lost-update on any of these silently corrupts stock / XP / trust / votes.
COUNTERS = [
    "qty_on_hand", "xp_total", "current_level", "total_sales", "rating_avg",
    "helpful_count", "vote_count", "reaction_count", "view_count", "reputation_score",
    "points", "balance", "likes", "exam_score", "current_stock",
]
# a client `.update({ ... counter: <expr> ... })` or `.upsert({ ... counter: <expr> ... })`.
# We match a write call whose argument object contains a COUNTER key. RPC calls (db.rpc(...)) never
# match because they are `.rpc('name', {...})`, not `.update(`/`.upsert(`.
WRITE = re.compile(
    r"\.(update|upsert)\(\s*\{[^}]*\b(" + "|".join(COUNTERS) + r")\b\s*:", re.DOTALL
)

# {file: [line-substrings]} — explicit, reasoned exceptions. Empty by design.
ALLOW: dict[str, list[str]] = {}


def main():
    print(f"\n{BOLD}NO CLIENT COUNTER-WRITE (P6 lost-update regression gate · static){RESET}")
    print("-" * 44)
    hits = []
    for html in sorted(ROOT.glob("*.html")):
        text = html.read_text(encoding="utf-8", errors="replace")
        for m in WRITE.finditer(text):
            line_no = text[: m.start()].count("\n") + 1
            field = m.group(2)
            snippet = text[m.start(): m.start() + 80].replace("\n", " ")
            allowed = any(a in snippet for a in ALLOW.get(html.name, []))
            if not allowed:
                hits.append((html.name, line_no, field, snippet))

    if not hits:
        print(f"  {GREEN}PASS{RESET}  0 client counter-writes — every value-integrity counter is RPC-mediated")
        print(f"        (guarded fields: {', '.join(COUNTERS)})")
        return 0

    print(f"  {RED}FAIL{RESET}  {len(hits)} client counter-write(s) — lost-update-prone, route through an atomic RPC:")
    for fname, ln, field, snip in hits:
        print(f"    {RED}·{RESET} {fname}:{ln}  sets '{field}'  →  {snip[:70]}…")
    return 1


if __name__ == "__main__":
    sys.exit(main())
