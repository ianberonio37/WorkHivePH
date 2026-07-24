---
name: external-apca-perceptual-contrast-wcag3-successor
type: reference
source: https://git.apcacontrast.com/documentation/APCAeasyIntro
source_sha: b0ab375172a74e22
fetched_at: 2026-07-24T03:50:56Z
last_verified: 2026-07-24
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: apca-perceptual-contrast-wcag3-successor
---

## reference · apca-perceptual-contrast-wcag3-successor
* Visual readability is a key part of web content, affecting 99% of internet users.
* WCAG 2.x contrast guidelines are outdated and need a replacement.
* The Accessible Perceptual Contrast Algorithm (APCA) is a new method for calculating and predicting readability contrast.
* APCA generates a lightness contrast value (Lc) for a minimum font weight, size, and color pair.
* Lc values range from 0 to ±106, with Lc 15 being the point of invisibility for many users.
* Minimum Lc values for different use cases:
  + Lc 90: preferred level for fluent text and columns of body text (font no smaller than 14px/weight 400).
  + Lc 75: minimum level for columns of body text (font no smaller than 18px/400).
  + Lc 60: minimum level for content text that is not body, column, or block text (font no smaller than 24px/400 or 16px/700).
  + Lc 45: minimum for larger, heavier text (36px normal weight or 24px bold).
  + Lc 30: absolute minimum for any text not listed above.
  + Lc 15: absolute minimum for any non-text that needs to be discernible and differentiable (no less than 5px in smallest dimension).
* For AAA, increase contrast values by Lc 15.
* Dark Mode Maximum: Lc -90 for large fonts (preliminary).
* APCA considers many factors, including font size, weight, and color, to provide a range-based conformance system.
* APCA does not rely on an arbitrary pass/fail binary scoring, nor brute-forced thresholds.
Sources: https://git.apcacontrast.com/documentation/APCAeasyIntro
