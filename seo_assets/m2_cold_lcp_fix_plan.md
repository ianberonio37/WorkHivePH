# M2 — cold-LCP fix plan (kill the render-blocking Tailwind Play CDN)

**Problem (measured):** warm-cache CWV is all green, but **first-visit (cold) LCP is 3-5s**. Root cause confirmed: every page loads `<script src="https://cdn.tailwindcss.com"></script>` — the Tailwind **Play CDN**, a ~400KB JavaScript runtime that generates CSS in the browser at load. Tailwind documents this as **development-only, not for production**. It is the "synchronous JS + non-critical CSS on the initial view" anti-pattern named in `external-core-web-vitals-2026-lcp-inp-cls-thresholds` (Digivate). It blocks 16+ public pages.

**This is a genuine fork (needs Ian's OK)** because the site deliberately has **no build step**, and every fix changes how all pages load CSS. Approaches:

| Approach | What it is | Build step? | Risk | Recommend |
|---|---|---|---|---|
| **A. Self-host a prebuilt Tailwind CSS** | Run Tailwind CLI ONCE to emit a static `assets/tailwind.css` scoped to the classes actually used; replace the CDN `<script>` with `<link rel="stylesheet">`. Regenerate only when classes change (not per deploy). | One-time / occasional, NOT an ongoing pipeline | Low-medium (visual diff needed) | ★ **YES** |
| B. Inline critical CSS per page | Extract above-the-fold CSS into a `<style>` in each `<head>`, defer the rest. | None | High (per-page, brittle) | No |
| C. Keep the Play CDN | Stays dev-mode; cold-LCP unfixed. | None | Perf debt persists | No |

## Approach A — the steps (execute later, after Ian's OK)
1. `npx tailwindcss -i input.css -o assets/tailwind.css --minify` with a `tailwind.config.js` whose `content` globs all `*.html` + `learn/**/*.html` (so every used class is emitted). Carry over the existing inline `tailwind.config` (theme extend, fonts) into the config file.
2. Replace on every page: `<script src="https://cdn.tailwindcss.com"></script>` + the inline `tailwind.config = {...}` block → `<link rel="stylesheet" href="/assets/tailwind.css">`.
3. Keep `tokens.css` + the Poppins `@font-face` (already `display=optional`, good).
4. Add `fetchpriority="high"` to the LCP element (usually the hero logo/heading) per the CWV chunk.
5. **Verify the WHOLE page, every page** (whole-artifact discipline): full-page screenshot diff before/after on index + 2-3 tool pages + a learn article, at both viewports, to catch any missing utility class.
6. Re-run `cwv_probe.mjs` / `cwv_gate.py` — confirm `lcp_cold_ms` drops under 2.5s and nothing regressed warm.
7. Registration: this is a new committed asset (`assets/tailwind.css`) + a regeneration note in the DevOps skill so a future class addition remembers to rebuild.

**Blast radius:** 16 public pages + the app pages that use the CDN. The regeneration-forgetting risk (add a class, forget to rebuild → unstyled element) is the main ongoing cost — mitigate with a gate that greps for classes not present in the built CSS, or a pre-commit rebuild.

**Status:** SKELETON / awaiting Ian's approach decision. Do NOT execute blind — it touches the live public render path.
