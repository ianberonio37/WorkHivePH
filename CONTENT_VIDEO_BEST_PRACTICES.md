# Short-Form Marketing / Explainer Video — Best-Practice Reference (cited)

**Purpose:** Ground the "WorkHive Explains" product-overview video (74s, 9:16, James Filipino-accented TTS, pure-Python Pillow+ffmpeg engine) in reputable, numeric best practices for **pacing, scene design, and script**, plus everything a first-timer misses.

**Our current spec (baseline):** 74 seconds · 9:16 vertical · Filipino-accented TTS · phone-frame screenshots with Ken Burns + spring-in · 8-screen montage · kinetic word-by-word captions · real logo · value-first script (3AM breakdown → why → product → tool tour → takeaway → CTA) · low music bed.

---

## TOP SUMMARY — the numbers that matter most

| Lever | Reputable target | Our baseline | Gap |
|---|---|---|---|
| Hook window | Win seconds **0–3**; brand + product in first **5s**; 2+ shots in first 5s | 3AM stakes cold-open | Verify product/logo visible ≤5s |
| Scene length | Something new every **3–5s**; pattern-interrupt every **5–8s** | Ken Burns per screen | Ensure no shot >5s static |
| VO pace | **130–150 wpm** (conversational) | TTS — check wpm | ~150 wpm ceiling |
| Total length | Educational sweet spot **15–60s**; <60s = ~52% avg engagement | **74s** | Trim toward ≤60s if possible |
| Captions | 85–92% watch **muted**; captions +40% watch time; <32 chars/line | Kinetic captions present | Confirm size/safe-zone |
| Caption safe zone | Keep text between **top 14%** and **bottom 20–35%**; ≥48–60px bold | Word-by-word | Verify px + safe margins |
| Contrast | **4.5:1** (AA) min; white text + dark outline | — | Add outline if missing |
| CTA | **One** CTA; verbal + on-screen together; end-card last 5–20s | CTA present | Ensure single, dual-coded |
| Hook rate to beat | **≥30%** (TikTok) / **≥25%** (Meta) | — | Measure |

---

## 1. HOOK & FIRST FRAME

| Finding | Number | Source |
|---|---|---|
| Most drop-off happens in seconds **0–3**; winning that window is critical | 0–3s | [OpusClip](https://www.opus.pro/blog/ideal-youtube-shorts-length-format-retention) |
| The decision to keep watching happens in the **first 3 seconds** | 3s | [OpusClip Reels](https://www.opus.pro/blog/ideal-instagram-reels-length) |
| Aim for **2+ shots in the first 5 seconds**; introduce brand/product in first **5s**; start "in the middle of the action" or on a close-up; use bold color/contrast | 2 shots / 5s | [Think with Google — ABCDs](https://business.google.com/us/think/future-of-marketing/youtube-video-ad-creative/) |
| "Start big — earn engagement right from the get-go"; brand **early, often, richly** | — | [Think with Google — ABCDs](https://business.google.com/us/think/future-of-marketing/youtube-video-ad-creative/) |
| Pattern-interrupt in the **first second** (hard cut, snap-zoom, visual mismatch) to trigger curiosity | 1s | [Automateed](https://www.automateed.com/content-hooks-for-short-form-videos) |
| The ABCDs deliver **+30%** short-term sales lift, **+17%** long-term brand contribution | +30% / +17% | [Think with Google — ABCDs](https://business.google.com/us/think/future-of-marketing/youtube-video-ad-creative/) |

**→ Apply to WorkHive explainer**
- First frame must be a **stop-scroll visual** (bold color, big text, or a striking screenshot) — not a slow logo fade. Put the strongest word ("3AM. The line just stopped.") on screen at frame 1.
- Ensure the **WorkHive logo + a product screenshot both appear by 5s** (currently the stakes cold-open may hold product back too long).
- Add a hard cut or snap-zoom in the **first second** (a fast Ken Burns punch-in on the phone frame counts as a pattern-interrupt in our engine).
- Get **2 distinct visuals in the first 5s** (e.g., dark alarm shot → app screenshot), not one long Ken Burns pan.

---

## 2. PACING & SCENE DURATION

| Finding | Number | Source |
|---|---|---|
| Viewers absorb a shot in ~**3s**; attention fades past **5s** — change something visually every **3–5s** (angle, b-roll, transition) | 3–5s/shot | [Vidpros](https://vidpros.com/video-clip-length/) |
| Add a **pattern-interrupt every 5–8s** | 5–8s | [Automateed](https://www.automateed.com/content-hooks-for-short-form-videos) |
| Tighter cuts in the intro with a small visual reset every **10–20s**; widen to **25–40s** once hooked; **vary** clip lengths (mix short rapid cuts with longer shots) — uniform pacing loses viewers | varies | [Automateed](https://www.automateed.com/content-hooks-for-short-form-videos) |
| 15–30s shorts hit the highest retention (often **>80%**) — enough for one complete idea without dragging | 15–30s | [OpusClip](https://www.opus.pro/blog/ideal-youtube-shorts-length-format-retention) |
| Editors control rhythm by matching cut cadence to content energy | — | [StudioBinder](https://www.studiobinder.com/blog/how-does-an-editor-control-the-rhythm-of-a-film/) |

**→ Apply to WorkHive explainer**
- **Cap every scene at 5s** of static; if a screen must stay longer, add a second motion beat (a callout push-in, a caption flip, a second Ken Burns move) so "something changes every 3–5s."
- Our **8-screen montage** should run **~3–4s per screen** (24–32s total) — fast enough to keep momentum, slow enough to read one caption each.
- **Vary the cadence**: fast 2–3s cuts through the hook + montage, then a slightly longer (4–5s) beat on the takeaway so it lands.
- Schedule a deliberate **pattern-interrupt every 5–8s** (transition style change, zoom, color shift) — trivial to script in a Python timeline.

---

## 3. LENGTH PER PLATFORM

| Platform | Ideal length | Source |
|---|---|---|
| Instagram Reels | **15–30s** highest engagement; 7–15s for entertainment; educational/tutorial 15–30s; >90s not promoted for discovery | [OpusClip](https://www.opus.pro/blog/ideal-instagram-reels-length) |
| TikTok | Viral sweet spot **30–60s** (~45s ideal); hook in first 3s | [ShortsNinja](https://shortsninja.com/blog/best-video-lengths-for-tiktok-youtube-instagram/) |
| YouTube Shorts | **15–30s** to hold attention | [OpusClip](https://www.opus.pro/blog/ideal-youtube-shorts-length-format-retention) |
| Any | Videos **<1 min** average **~52%** engagement (viewers watch half); little difference 1–5 min; big drop past 5 min | [Wistia State of Video](https://wistia.com/learn/marketing/optimal-video-length) |
| Any | Completion ~**66%** for <1 min vs ~**56%** for 1–2 min | [Wistia](https://wistia.com/learn/marketing/video-marketing-statistics) |
| Retention math | A 30s Reel @50% retention = **15s watch time** > a 10s Reel @80% = **8s**; algorithms weight both retention **and** total watch time | [OpusClip](https://www.opus.pro/blog/ideal-instagram-reels-length) |

**→ Apply to WorkHive explainer**
- **74s is above every short-form sweet spot.** Target a **≤60s cut** for Reels/Shorts/TikTok; a 45–60s version will get far wider algorithmic distribution than 74s.
- Consider **two exports**: a **≤30s** "hook + 3 best tools + CTA" cut for Reels/Shorts discovery, and the **60–74s** full version for the site/landing page (where longer is fine).
- Because completion matters, **cutting 74→55s** likely raises completion rate meaningfully (66% vs 56% band).

---

## 4. SCRIPT & STORY FRAMEWORKS

| Finding | Number | Source |
|---|---|---|
| VO pace **130–150 wpm** (125–150 conversational; pros read 130–140) | 130–150 wpm | [Gisteo](https://gisteo.com/blogs/scriptwriting-editing/explainer-video-scriptwriting-101-how-to-tell-a-compelling-story-in-90-seconds/) |
| ~**150 words per minute** of video; 90s ≈ 225 words; 30s ≈ 75 words | 150 wpm | [MyPromoVideos](https://mypromovideos.com/blog/explainer-video-script/) |
| Use **contractions**, **short sentences (10–15 words max)**, conversational tone — not corporate speak | ≤15 words | [Gisteo](https://gisteo.com/blogs/scriptwriting-editing/explainer-video-scriptwriting-101-how-to-tell-a-compelling-story-in-90-seconds/) |
| Explainer rhythm: **Hook (0–15s)** presents the daily pain → problem-solution structure (open on pain, product = solution) | 0–15s hook | [Vidico](https://vidico.com/news/explainer-video-script-examples/) |
| **StoryBrand:** customer is the **hero**, brand is the **guide** with a **3-step plan**, one clear **CTA**, and explicit **stakes** (what happens if they fail) | 7 parts | [StoryBrand](https://storybrand.com/downloads/your-brand-is-not-the-hero.pdf) |
| **AIDA:** Attention → Interest → Desire → Action | 4 stages | [Swarmify](https://swarmify.com/blog/script-writing/) |
| **PAS:** Problem → Agitate → Solve (open on pain, twist the knife, resolve) | — | [Vidico](https://vidico.com/news/explainer-video-script-examples/) |

**→ Apply to WorkHive explainer**
- Our value-first script already maps to **PAS + StoryBrand**. Tighten the roles: the **maintenance worker is the hero**, **WorkHive is the guide** (not the hero) — phrase benefits as "you'll…" not "WorkHive does…".
- Enforce **one idea per line, ≤15 words**, contractions on. Read the script aloud; anything over 15 words gets split.
- **Word budget:** at 150 wpm, 60s ≈ **150 words**, 74s ≈ **185 words**. Count the current script — if it's over, the TTS is rushing (a common "not contented" symptom). Cut to the budget rather than speeding James up.
- Make the **stakes explicit and quantified** in the hook (e.g., "every hour down costs ₱___") — StoryBrand says name the failure state.
- **3-step plan** framing for the tool tour ("Log it → Assign it → Track it") reads cleaner than 8 disconnected screens.

---

## 5. CAPTIONS / SUBTITLES

| Finding | Number | Source |
|---|---|---|
| **85–92%** of social/mobile video watched **without sound**; 80% of Reels muted | 85–92% | [OpusClip](https://www.opus.pro/blog/facebook-reels-caption-subtitle-best-practices), [Bluetext](https://bluetext.com/blog/closed-captions-silent-video/) |
| Captions raise avg watch time **+40–60%**; completion **91% vs 66%** without | +40–60% | [Scenith](https://scenith.in/blogs/silent-engagement-crisis), [Subtitlesfast](https://subtitlesfast.com/blog/social-media-subtitle-best-practices/) |
| Keep lines **<32 characters**; position in safe zone **20%–70% from top**; test mobile-first | <32 chars | [Subtitlesfast](https://subtitlesfast.com/blog/social-media-subtitle-best-practices/) |
| **White text + black outline**; start ~**22pt** and scale up; each caption on screen ≥**1.2s**; reading speed 160–180 wpm (~2.5–3s per 10-word line) | ≥1.2s | [Videotap](https://videotap.com/blog/subtitle-formatting-best-practices-and-standards) |
| On mobile, text should be **48–60px bold** minimum to read in the first second | 48–60px | [Kreatli](https://kreatli.com/guides/youtube-shorts-safe-zone) |

**→ Apply to WorkHive explainer**
- Silent-first is **the** design constraint: the video must **fully make sense muted**. Verify the caption track carries the whole narrative on its own.
- Set kinetic caption font to **≥48px bold** (our engine renders at 1080×1920 — 48px is small there; go **56–72px**), **white with a 3–5px dark stroke/shadow** for the 4.5:1 contrast (see §6).
- Keep any single on-screen phrase **<32 characters** and on screen **≥1.2s** — word-by-word is fine, but don't flash words faster than ~3 per second or they're unreadable.
- Anchor captions in the **20–70% vertical band** (avoid the top-14% and bottom-20–35% platform-UI zones, §9).

---

## 6. VISUAL / MOTION

| Finding | Number | Source |
|---|---|---|
| **Ease-in/ease-out** looks natural; **linear feels mechanical**; a zoom should **settle before** the viewer needs to read | — | [SmoothCapture](https://www.smoothcapture.app/blog/product-demonstration-video) |
| Use **5–10% push-ins** to emphasize an element; **don't exceed ~15%** zoom unless showing tiny UI | 5–15% | [SmoothCapture](https://www.smoothcapture.app/blog/product-demonstration-video) |
| **Move cursor slower than natural**, pause before/after clicks, use a **bigger cursor**; add click ripples so motion feels motivated | — | [SmoothCapture](https://www.smoothcapture.app/blog/product-demonstration-video) |
| Add **callouts** (circles, arrows, annotations) to highlight the clickable element | — | [SmoothCapture](https://www.smoothcapture.app/blog/product-demonstration-video) |
| Mobile text needs **high contrast**: WCAG AA **4.5:1** (normal), **3:1** (large ≥18pt/14pt-bold); AAA **7:1** | 4.5:1 | [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) |
| Bold color/contrast in the opening grabs attention | — | [Think with Google](https://business.google.com/us/think/future-of-marketing/youtube-video-ad-creative/) |

**→ Apply to WorkHive explainer**
- Our spring-in easing is on-brief (ease-out). **Audit every Ken Burns move**: it should **settle ~0.3–0.5s before** the caption needs reading, not still be moving.
- Keep Ken Burns push-ins in the **5–15% range** — big enough to feel alive, small enough to keep the UI legible. Reserve >15% zoom only for tiny-UI moments (a specific button/number).
- Add **callout overlays** (a soft circle/arrow rendered in Pillow) on the exact tool/button each screen is about — this is "show, not just tell."
- Enforce **4.5:1 contrast** on every caption and label. White text over bright screenshots needs a **scrim/gradient panel** behind it (a semi-opaque dark bar) — trivial in Pillow.
- If simulating cursor/taps, **slow the motion and pause on clicks**; add a tap-ripple.

---

## 7. CTA

| Finding | Number | Source |
|---|---|---|
| **One primary CTA** per video; everything else supports it or it's noise | 1 | [Gumlet](https://www.gumlet.com/learn/video-cta/) |
| **Reinforce CTA verbally + on-screen at the same time** — the combo sticks | — | [Gumlet](https://www.gumlet.com/learn/video-cta/) |
| End-of-content CTAs can lift conversion **+20–30%**; end screens live in the **last 5–20s** | +20–30% | [Automateed](https://www.automateed.com/how-to-add-ctas-in-youtube-videos) |
| Video CTAs average **~16%** conversion (Wistia platform) | ~16% | [Wistia](https://wistia.com/learn/marketing/using-video-ctas) |
| Place the CTA **right after delivering value** (after solving the pain) | — | [Gumlet](https://www.gumlet.com/learn/video-cta/) |

**→ Apply to WorkHive explainer**
- Ship **exactly one** CTA (e.g., "Start free at workhive.ph"). Don't split attention with a second ask.
- **Dual-code it**: James says it *and* it's on-screen as a bold end-card simultaneously in the **last 5–8s**.
- End card should hold the CTA **long enough to read + act** (≥3–5s static end frame with logo + URL).
- Place it immediately **after the takeaway** ("no more 3AM guesswork") so the CTA rides the emotional peak.

---

## 8. MEASUREMENT

| Metric | Benchmark to beat | Source |
|---|---|---|
| **Hook rate** (3s views / impressions) | TikTok **≥30%** healthy, **40%+** elite; Meta **≥25%** table-stakes, **30%+** best-in-class | [Billo](https://billo.app/blog/hook-rate-to-hold-rate/), [AdLibrary](https://adlibrary.com/posts/hold-rate) |
| **Hold rate** (past 15s / 75% complete) | <15s ads: **35–50%** solid; 15–30s ads: **25–40%** solid, 40–60% strong; TikTok runs higher | [AdLibrary](https://adlibrary.com/posts/hold-rate) |
| **Retention curve** (per-second % still watching) | Chart drop-off second-by-second to find the exact cut that kills the video | [AdLibrary](https://adlibrary.com/posts/hold-rate) |
| **Avg completion** | <1 min ≈ **66%**; 1–2 min ≈ **56%** | [Wistia](https://wistia.com/learn/marketing/video-marketing-statistics) |
| **Fix order** | Fix **hook rate first** (nothing matters if no one watches), then retention/hold | [Imagine](https://www.imagine.art/blogs/hook-rate-vs-hold-rate) |

**→ Apply to WorkHive explainer**
- Instrument the landing-page embed to log **3s-view rate (hook), 25/50/75/100% completion, and CTA clicks**. Target hook ≥30%, hold ≥40%.
- **A/B two hooks** (stakes cold-open vs. product-first) — hook rate first; nothing else moves the needle until it's ≥30%.
- Pull the **per-second retention curve** and find the exact scene where drop-off spikes; that's the scene to re-cut.

---

## 9. EXTEND — what first-timers miss

| Finding | Number | Source |
|---|---|---|
| **Cover/first frame is a thumbnail** — the still someone sees before pressing play must sell the click (bold text + strong image) | — | [Kreatli](https://kreatli.com/guides/youtube-shorts-safe-zone) |
| **9:16 safe zones:** keep text/faces out of **top 14%** and **bottom 20–35%**; on Reels, ≥**108px from top**, ≥**320px from bottom**, side buffer; right **10%** = engagement buttons | 1080×1920 | [Billo](https://billo.app/blog/meta-ads-safe-zones/), [Kreatli](https://kreatli.com/guides/youtube-shorts-safe-zone) |
| **Show, don't tell** — bold imagery/demo beats narration of features | — | [Think with Google](https://business.google.com/us/think/future-of-marketing/youtube-video-ad-creative/) |
| **Brand consistency:** logo + colors early, often, and richly | — | [Think with Google](https://business.google.com/us/think/future-of-marketing/youtube-video-ad-creative/) |
| **Accessibility:** captions legible on light **and** dark UIs; test in-device before launch | 4.5:1 | [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/) |
| **Pace edits to reading speed / music beats** — story, like music, is formulaic; cut on the beat | — | [Vidico](https://vidico.com/news/explainer-video-script-examples/), [StoryBrand](https://storybrand.com/) |
| **Hook-then-reward:** open a loop in the hook, pay it off later ("here's how →") | — | [Automateed](https://www.automateed.com/content-hooks-for-short-form-videos) |

**→ Apply to WorkHive explainer**
- **Design the cover frame** deliberately (bold "STOP the 3AM breakdowns" + a screenshot) — it's the thumbnail that decides the click.
- Bring caption/logo anchoring **inside the 1080×1920 safe zone** (≥108px top, ≥320px bottom) so platform UI never covers our text.
- Our music bed is right; go further and **align key cuts/caption reveals to the beat** — deterministic to do in a Python timeline (snap scene boundaries to beat timestamps).
- Add a **hook-then-reward loop**: hook poses "What if the fix was already in your pocket?" → tool tour pays it off.
- **Show, don't tell:** each claim should be backed by the matching screenshot on screen at that moment (already our model — verify sync).

---

## TOP 12 CHANGES, RANKED (highest leverage first)

1. **Trim 74s → ≤60s** (ideally a 45–55s cut) to hit short-form distribution + higher completion. Two exports: ≤30s discovery cut + ~55s full cut. *(§3)*
2. **Get product screenshot + logo on screen by 5s**, and a **stop-scroll first frame** (bold text, not a slow logo fade). *(§1, §9)*
3. **Cap every scene at 5s of static motion**; put a fresh visual/beat every **3–5s**; pattern-interrupt every **5–8s**. *(§2)*
4. **Enforce the word budget:** 150 wpm → ≤150 words for 60s. If the script is over, cut words — don't speed up James. *(§4)*
5. **Bump caption size to 56–72px bold, white + 3–5px dark stroke/scrim**, ≥1.2s on screen, <32 chars/line — verify it reads **muted**. *(§5)*
6. **Move all text into the 9:16 safe zone** (≥108px top, ≥320px bottom); design a deliberate cover/thumbnail frame. *(§9)*
7. **One dual-coded CTA** (spoken + on-screen, last 5–8s, ≥3–5s static end-card with logo+URL). *(§7)*
8. **StoryBrand the script:** worker = hero, WorkHive = guide, quantified stakes in the hook, 3-step plan for the tool tour. *(§4)*
9. **Add callout overlays** (circle/arrow) on the exact button/tool each screen shows — show, don't just narrate. *(§6)*
10. **Audit Ken Burns easing/zoom:** ease-out, 5–15% push-in, and **settle ~0.4s before** the caption needs reading. *(§6)*
11. **Snap scene/caption cuts to the music beat** for perceived polish. *(§9)*
12. **Instrument + A/B the hook:** measure 3s hook rate (target ≥30%) and per-second retention; re-cut the scene where drop-off spikes. *(§8)*

---

*Compiled 2026-07-01. All figures carry inline sources. Primary references: Think with Google (ABCDs), Wistia State of Video, OpusClip, StoryBrand (Donald Miller), W3C WCAG 2.2, plus industry retention/caption studies.*
