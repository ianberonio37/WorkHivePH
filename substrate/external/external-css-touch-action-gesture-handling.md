---
name: external-css-touch-action-gesture-handling
type: reference
source: https://developer.mozilla.org/en-US/docs/Web/CSS/touch-action
source_sha: 7c2a719f3c5b25bc
fetched_at: 2026-07-18T10:48:31Z
last_verified: 2026-07-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: css touch-action gesture handling
---

## reference · css touch-action gesture handling

- **Default**: `touch-action: auto` – browser handles all panning and pinch‑zoom gestures.  
- **Disable all gestures**: `touch-action: none` – blocks browser scrolling, zooming, and double‑tap‑to‑zoom; may hinder accessibility for low‑vision users.  
- **Enable only panning**:  
  - `pan-x` – allow single‑finger horizontal panning.  
  - `pan-y` – allow single‑finger vertical panning.  
  - Combine (`pan-x pan-y`) to permit both axes.  
- **Directional shortcuts**: `pan-left`, `pan-right`, `pan-up`, `pan-down` enable scrolling that *starts* in the named direction (e.g., `pan-up` means the finger moves **down** on the screen).  
  - Invalid combo: `pan-left pan-right` → use `pan-x` instead.  
  - Valid combo: `pan-left pan-down`.  
- **Pinch‑zoom**: add `pinch-zoom` to any `pan‑*` set to allow multi‑finger zooming.  
- **Manipulation**: alias for `pan-x pan-y pinch-zoom`; also disables non‑standard gestures like double‑tap‑to‑zoom, removing the click‑event delay.  
- **Value syntax**: one keyword (`auto`, `none`, `manipulation`) **or** any combination of `pan-x|pan-left|pan-right`, `pan-y|pan-up|pan-down`, and optional `pinch-zoom`.  
- **Interaction with Pointer Events**: when the browser takes over a gesture, a `pointercancel` event is dispatched to the element.  
- **Interaction with Touch Events**: calling `event.preventDefault()` disables browser handling, but `touch-action` should still be set to convey intent before listeners run.  
- **Inheritance rule**: the effective `touch-action` for a gesture is the intersection of the touched element’s value and all its ancestors up to the first scrolling container. Usually set on the top‑level interactive element only.  
- **Runtime limitation**: changing `touch-action` **after** a gesture has started does **not** affect that ongoing gesture.  
- **Accessibility caution**: avoid `touch-action: none` unless you provide an alternative zoom mechanism; it can prevent users with low vision from enlarging content.  
- **Browser support**: baseline support across major browsers since **September 2019**; widely available with no known major gaps.  

Sources: https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/touch-action
