"""Quick: list remaining unlabeled inputs in given files."""
import re, sys
for f in sys.argv[1:]:
    src = open(f, encoding="utf-8").read()
    label_for = set(re.findall(r'<label[^>]*\bfor\s*=\s*["\']([^"\']+)["\']', src, re.IGNORECASE))
    for m in re.finditer(r"<(input|textarea|select)\b([^>]*)>", src, re.IGNORECASE):
        attrs = m.group(2)
        t = re.search(r'\btype\s*=\s*["\']([^"\']*)["\']', attrs, re.IGNORECASE)
        if t and t.group(1).lower() in {"hidden", "submit", "button"}:
            continue
        if "aria-label" in attrs.lower():
            continue
        idm = re.search(r'\bid\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
        if not idm:
            continue
        if "${" in idm.group(1):
            continue
        if idm.group(1) in label_for:
            continue
        prefix = src[max(0, m.start()-250): m.start()]
        if "<label" in prefix.lower() and "</label" not in prefix.lower():
            continue
        line = src.count("\n", 0, m.start()) + 1
        print(f"{f}:{line}  id={idm.group(1)}  type={m.group(1)}  attrs={attrs.strip()[:80]}")
