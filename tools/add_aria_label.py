"""
Phase-1 follow-up codemod: add aria-label to inputs that don't have a
visible <label for> AND aren't already aria-labelled.

Pairs with add_label_for.py. After that script paired every existing
<label> with its input, the remaining unlabeled inputs are typically
compact filter / search / inline inputs that don't get a visible label
by design (would clutter the UI). For those, aria-label derived from
the placeholder is the right tool: screen readers get a meaningful
name; layout stays unchanged.

Skipped:
  - inputs with type=hidden / submit / button
  - inputs that already have aria-label / aria-labelledby
  - inputs without an id (templated)
  - inputs without a placeholder (no name source available — would
    need manual triage)

Usage:
  python tools/add_aria_label.py --dry-run logbook.html
  python tools/add_aria_label.py logbook.html pm-scheduler.html
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


INPUT_RE = re.compile(
    r"""<(?P<tag>input|select|textarea)\b(?P<attrs>[^>]*)>""",
    re.IGNORECASE,
)


def _attr(attrs: str, name: str) -> str | None:
    m = re.search(rf'\b{name}\s*=\s*["\']([^"\']*)["\']', attrs, re.IGNORECASE)
    return m.group(1) if m else None


def _has_label_for(src: str, input_id: str) -> bool:
    return bool(re.search(rf'<label[^>]*\bfor\s*=\s*["\']{re.escape(input_id)}["\']', src, re.IGNORECASE))


def transform(src: str) -> tuple[str, int]:
    changes = 0
    out_parts: list[str] = []
    pos = 0

    for m in INPUT_RE.finditer(src):
        attrs = m.group("attrs")
        tag = m.group("tag").lower()
        input_type = (_attr(attrs, "type") or "").lower()
        if input_type in {"hidden", "submit", "button"}:
            continue
        if _attr(attrs, "aria-label") or _attr(attrs, "aria-labelledby"):
            continue
        input_id = _attr(attrs, "id")
        if not input_id or "${" in input_id or "{" in input_id:
            continue
        if _has_label_for(src, input_id):
            continue
        placeholder = _attr(attrs, "placeholder")
        if not placeholder:
            # No name source available — skip; manual triage needed for these.
            continue
        # Build new tag with aria-label inserted right after the opening
        # tag name (before other attrs).
        old_full = m.group(0)
        new_attrs = f' aria-label="{placeholder}"' + attrs
        new_full = f"<{tag}{new_attrs}>"
        # Emit text before this match, then the replacement.
        out_parts.append(src[pos:m.start()])
        out_parts.append(new_full)
        pos = m.end()
        changes += 1

    out_parts.append(src[pos:])
    return "".join(out_parts), changes


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)
    dry_run = False
    if "--dry-run" in args:
        dry_run = True
        args.remove("--dry-run")
    total = 0
    for arg in args:
        path = Path(arg)
        if not path.exists():
            print(f"  SKIP  {arg} — not found")
            continue
        src = path.read_text(encoding="utf-8")
        new_src, n = transform(src)
        total += n
        if dry_run:
            print(f"  {n:>4}  {arg}  (dry-run)")
        elif n:
            path.write_text(new_src, encoding="utf-8")
            print(f"  {n:>4}  {arg}  updated")
        else:
            print(f"  {n:>4}  {arg}  no changes")
    print(f"\n  Total: {total} aria-labels added")


if __name__ == "__main__":
    main()
