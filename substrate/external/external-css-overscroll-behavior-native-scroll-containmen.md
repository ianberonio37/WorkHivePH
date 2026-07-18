---
name: external-css-overscroll-behavior-native-scroll-containmen
type: reference
source: https://developer.mozilla.org/en-US/docs/Web/CSS/overscroll-behavior
source_sha: 9b2bed1c45ca825f
fetched_at: 2026-07-18T10:48:24Z
last_verified: 2026-07-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: css overscroll-behavior native scroll containment
---

## reference · css overscroll-behavior native scroll containment

- `overscroll-behavior` is a shorthand for `overscroll-behavior-x` and `overscroll-behavior-y`.  
- Syntax: one or two keywords (`auto`, `contain`, `none`).  
  - One keyword applies to both the x‑ and y‑axes.  
  - Two keywords set the x‑axis first, then the y‑axis.  
- Initial value: `auto`.  
- Not inherited.  
- Applies to non‑replaced block‑level and non‑replaced inline‑block elements that are scroll containers.  
- **`auto`** – default scroll overflow behavior (normal scrolling, bounce, pull‑to‑refresh).  
- **`contain`** – allows normal scrolling inside the element but blocks scroll chaining to parent containers; disables native navigation gestures such as pull‑to‑refresh and horizontal swipe navigation.  
- **`none`** – prevents scroll chaining and suppresses default scroll overflow behavior (no bounce, no pull‑to‑refresh).  
- A scroll container with `overflow: hidden` is always at its scroll boundary; applying `contain` or `none` to it stops ancestor scrolling (useful for modal dialogs or overlays).  
- The property does **not** apply to `<iframe>` elements. To control scroll chaining from an iframe, set `overscroll-behavior` on the `<html>` and `<body>` of the iframe’s document.  
- Use `overscroll-behavior` to eliminate unwanted scroll chaining and browser‑specific “bounce” or “pull‑to‑refresh” effects on mobile devices.  
- Supported in all modern browsers except for some older or less‑common ones; it is not considered baseline compatibility.  

Sources: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/overscroll-behavior
