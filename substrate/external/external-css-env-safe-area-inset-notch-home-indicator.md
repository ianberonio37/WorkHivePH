---
name: external-css-env-safe-area-inset-notch-home-indicator
type: reference
source: https://developer.mozilla.org/en-US/docs/Web/CSS/env
source_sha: 0fb66b6ac99d46ca
fetched_at: 2026-07-18T10:48:36Z
last_verified: 2026-07-18
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: css env safe-area-inset notch home indicator
---

## reference · css env safe-area-inset notch home indicator
* The `env()` CSS function inserts the value of a user-agent defined environment variable into CSS.
* Environment variables include:
  + `safe-area-inset-top`, `safe-area-inset-right`, `safe-area-inset-bottom`, `safe-area-inset-left`: safe distance from the top, right, bottom, or left inset edge of the viewport.
  + `safe-area-max-inset-top`, `safe-area-max-inset-right`, `safe-area-max-inset-bottom`, `safe-area-max-inset-left`: static maximum values of their dynamic `safe-area-inset-*` variable counterparts.
  + `titlebar-area-x`, `titlebar-area-y`, `titlebar-area-width`, `titlebar-area-height`: dimensions of a visible `titlebar-area-*` area.
  + `keyboard-inset-top`, `keyboard-inset-right`, `keyboard-inset-bottom`, `keyboard-inset-left`, `keyboard-inset-width`, `keyboard-inset-height`: insets from the edge of the viewport and dimensions of the device's on-screen virtual keyboard.
  + `preferred-text-scale`: user's preferred font scaling factor.
  + `viewport-segment-width`, `viewport-segment-height`, `viewport-segment-top`, `viewport-segment-right`, `viewport-segment-bottom`, `viewport-segment-left`: dimensions and offset positions of specific viewport segments.
* The `env()` function accepts two parameters: `<environment-variable>` and an optional `<fallback>` value.
* The `<fallback>` value is used if the environment variable referenced in the first argument does not exist.
* The `env()` function can be used as a property value or in place of any part of a property value or descriptor.
Sources: https://developer.mozilla.org/en-US/docs/Web/CSS/env
