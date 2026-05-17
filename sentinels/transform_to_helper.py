"""One-shot transform: rewrite sentinel tests to use pageSrcWithExternals.

Pattern targeted:
    const NAME = await whPage.evaluate(() => {
      const src = document.documentElement.outerHTML;
      return /REGEX/i.test(src);
    });

Rewritten as:
    const __srcN = await pageSrcWithExternals(whPage);
    const NAME = /REGEX/i.test(__srcN);

Also ensures `pageSrcWithExternals` is imported from './_helpers' in each file
that uses it.

Run once: `python sentinels/transform_to_helper.py`
"""

import re
import sys
from pathlib import Path

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

PAT = re.compile(
    r"const\s+(\w+)\s*=\s*await\s+whPage\.evaluate\(\(\)\s*=>\s*\{\s*"
    r"const\s+src\s*=\s*document\.documentElement\.outerHTML\s*;\s*"
    r"return\s+(/[\s\S]+?/i?)\.test\(\s*src\s*\)\s*;\s*"
    r"\}\s*\)\s*;",
    re.MULTILINE,
)


def transform_file(path: Path) -> int:
    src = path.read_text(encoding="utf-8")
    n = 0
    counter = [0]

    def repl(m):
        counter[0] += 1
        name = m.group(1)
        regex = m.group(2)
        suffix = f"_{counter[0]}" if counter[0] > 1 else ""
        return (
            f"const __sentSrc{suffix} = await pageSrcWithExternals(whPage);\n"
            f"    const {name} = {regex}.test(__sentSrc{suffix});"
        )

    new_src, n = PAT.subn(repl, src)

    if n > 0:
        if "pageSrcWithExternals" not in new_src.split("\n")[0:30].__str__():
            new_src = re.sub(
                r"(import\s+\{\s*[^}]*?)\bwaitForPageReady\b([^}]*?\}\s+from\s+['\"]\./_helpers['\"];)",
                r"\1waitForPageReady, pageSrcWithExternals\2",
                new_src,
                count=1,
            )
            if "pageSrcWithExternals" not in new_src:
                new_src = re.sub(
                    r"(import\s+\{\s*)([^}]*?)(\}\s+from\s+['\"]\./_helpers['\"];)",
                    r"\1\2, pageSrcWithExternals\3",
                    new_src,
                    count=1,
                )
            if "pageSrcWithExternals" not in new_src:
                new_src = re.sub(
                    r"(import\s+\{[^}]*\}\s+from\s+['\"]\./_fixtures['\"];)",
                    r"\1\nimport { pageSrcWithExternals, waitForPageReady } from './_helpers';",
                    new_src,
                    count=1,
                )
        path.write_text(new_src, encoding="utf-8")
    return n


def main():
    total = 0
    for spec in sorted(TESTS.glob("*.spec.ts")):
        if spec.name.startswith("_"):
            continue
        n = transform_file(spec)
        if n > 0:
            print(f"  {spec.name:<40}  {n} occurrences rewritten")
            total += n
    print(f"\nTotal: {total} sentinel patterns transformed.")


if __name__ == "__main__":
    main()
