# Phase 5: Measurement Setup for WorkHive

**Created:** 2026-05-17
**Owner:** Ian Beronio
**Status:** Playbook ready. Existing: GSC verification tag in `index.html` L7. Pending: GA4 wiring, Bing verification, prompt-audit ritual launch.

The Phase 3 off-site authority playbook activates the 24 `/learn/` articles. Phase 5 makes the activation **measurable**. Without measurement you cannot tell whether the LinkedIn newsletter is working, whether Reddit comments are converting, or whether ChatGPT and Perplexity are citing WorkHive yet.

---

## What measurement gives you

| Surface | What you measure | What it tells you |
|---|---|---|
| **Google Search Console** | Impressions, clicks, CTR, ranking position per query and per URL | What Google thinks WorkHive ranks for; which pages drive traffic |
| **Bing Webmaster Tools** | Same as GSC but for Bing index | Microsoft Copilot uses the Bing index, so Bing visibility = Copilot citation likelihood |
| **Google Analytics 4 (GA4)** | Sessions, conversions, traffic sources, user behaviour | Which platforms drive traffic; which articles convert to /#join signup |
| **Manual prompt audits** | Whether ChatGPT, Perplexity, Gemini, Claude cite WorkHive for target queries | The direct AI visibility metric; nothing else replaces it |
| **Meta Business Suite** | FB Page + Group analytics | Phase 3 platform effectiveness |
| **LinkedIn Analytics** | Company page + post engagement | Phase 3 platform effectiveness |
| **YouTube Studio** | Subscribers, watch time, traffic source | Phase 3 platform effectiveness |
| **Profound / Otterly / Peec.ai** (paid) | Automated AI visibility tracking | Defer 3 months; manual audits cover this until volume justifies subscription |

---

## Setup checklist (do these in order)

### 1. Google Search Console (GSC) — already partially done

You already have the GSC verification meta tag in `index.html` line 7:
```html
<meta name="google-site-verification" content="0R0cbzF4Ks6d28b_uWAH3kDotNTYQ64uQfdcuMNhb_c" />
```

This means you started GSC setup at some point. To complete:

1. Sign in to [search.google.com/search-console](https://search.google.com/search-console)
2. Confirm property is verified for `workhiveph.com` (or `https://workhiveph.com/` if you set it up as URL prefix)
3. Submit the sitemap: paste `https://workhiveph.com/sitemap.xml` into Sitemaps section
4. Wait 7-14 days for first impression data to populate
5. Add Domain property variant if you haven't (verifies via DNS TXT record; covers all subdomains)

**Once active, check weekly:**
- Performance tab: top queries you rank for, top pages by clicks
- Coverage tab: any indexing errors
- Enhancements > Sitelinks searchbox: appears once you have organic brand traffic

### 2. Bing Webmaster Tools (BWT)

Critical because Microsoft Copilot indexes Bing data, not Google. Many AI engines also pull from Bing.

1. Sign in to [bing.com/webmasters](https://www.bing.com/webmasters) with a Microsoft account
2. Add site `https://workhiveph.com/`
3. Choose Import from Google Search Console (one-click; reuses your GSC verification, no need for a new tag)
4. Submit sitemap `https://workhiveph.com/sitemap.xml`
5. Use the URL Inspection tool to manually submit the 25 most important pages for faster indexing

If GSC import does not work, you can verify Bing with:
- A `msvalidate.01` meta tag (Bing gives you the code)
- A `BingSiteAuth.xml` file at root
- A DNS CNAME record

Once verified, give me the meta tag code and I'll wire it into all public pages in one batch.

### 3. Google Analytics 4 (GA4)

GA4 is free and the de facto standard for web traffic measurement.

1. Sign in to [analytics.google.com](https://analytics.google.com) with the Google account that owns workhiveph.com
2. Create a new GA4 property called "WorkHive Platform"
3. Set up a Web data stream for `https://workhiveph.com/`
4. Copy the Measurement ID (format: `G-XXXXXXXXXX`)
5. Give me the Measurement ID — I will wire the GA4 snippet into all 26 public pages in one pass (with consent-mode for GDPR/DPA compliance)

Recommended GA4 events to track (I will set these up when you give me the Measurement ID):
- `signup_form_view` (when someone scrolls to the #join CTA)
- `signup_form_submit` (when someone submits the form)
- `learn_article_read_80pct` (when someone scrolls past 80% of a /learn/ article)
- `cta_tool_click` (when someone clicks the "Open the [Tool]" CTA in a learn article)
- `faq_open` (which FAQs get most expanded)
- `external_link_click` (clicks to Chronicle citation, Wikipedia, etc.)

### 4. UTM tagging for Phase 3 platforms

So you can see in GA4 which platform drove which visit. Use this naming convention for all links you post:

```
utm_source   = facebook | linkedin | reddit | youtube | tiktok | wikipedia | newsletter
utm_medium   = social | organic | newsletter
utm_campaign = phase3-launch | phase3-amaq3 | phase3-newsletter-may | phase3-pscme-newsletter
```

Example links to post:
```
https://workhiveph.com/learn/what-is-oee-how-to-calculate/?utm_source=linkedin&utm_medium=social&utm_campaign=phase3-launch
https://workhiveph.com/?utm_source=facebook&utm_medium=social&utm_campaign=phase3-launch
```

Save these patterns in the prompt audit tool (next section) so you do not have to re-derive them each time.

### 5. Manual prompt-audit ritual (the only metric that actually matters for AEO/GEO)

GSC, Bing, and GA4 measure traditional SEO. They do not measure whether ChatGPT cites you. The only way to measure AI visibility right now is to manually run the target queries against each AI engine weekly and log the result.

Run [prompt_audit.py](prompt_audit.py) at the project root once a week. It opens the [prompt_audit_queries.json](prompt_audit_queries.json) file, walks you through each query, and lets you tap whether WorkHive was cited. Results land in `prompt_audit_results/<YYYY-MM-DD>.csv` for trend tracking.

Initial 20 target queries are seeded. Add or remove as your strategy evolves.

### 6. Meta + LinkedIn + YouTube + TikTok native analytics

These are built into each platform; nothing for me to wire in. Check weekly:
- **Meta Business Suite** (`business.facebook.com`): Page reach, Group activity, Reels views
- **LinkedIn Analytics** (`linkedin.com/company/.../admin/analytics/`): Page follower growth, post impressions
- **YouTube Studio** (`studio.youtube.com`): Subscribers, watch time, traffic source
- **TikTok Analytics** (`tiktok.com/business/`): Video views, profile views, completion rate

### 7. Optional: Microsoft Clarity (free session recording)

Microsoft Clarity is a free product that shows you actual session recordings of how visitors use the site. Lower priority than the basics above; consider adding in month 4 once you have meaningful traffic to record.

### 8. AI visibility SaaS (defer 3 months)

Profound, Otterly, Peec.ai, LLMrefs — these tools automate the manual prompt audit at scale. Each costs PHP 2,500-10,000/month. Defer until you have:
- At least 3 months of manual audit data showing some traction
- A confirmed need to track 100+ queries (manual audit covers up to ~30 efficiently)
- Budget headroom (these are nice-to-have, not need-to-have)

---

## What I need from you to finish the wiring

| Item | Where to find it | What I do with it |
|---|---|---|
| **GA4 Measurement ID** | `G-XXXXXXXXXX` from analytics.google.com property settings | Wire GA4 snippet into all 26 public pages (index.html + hub + 24 articles) + set up the 6 recommended custom events |
| **Bing verification meta tag** (if GSC import did not work) | bing.com/webmasters site verification screen | Add to `<head>` of index.html (alongside the existing GSC tag) |
| **Microsoft Clarity Project ID** (optional) | clarity.microsoft.com after creating project | Wire snippet to all 26 public pages |

Paste any of these into chat and I will batch-update all pages in one pass.

---

## Realistic expectation timeline

- **Week 1-2:** GSC + Bing + GA4 setup complete. Data trickles in within 7 days.
- **Month 1:** First search query impressions appear in GSC. Probably zero clicks yet (you have not been off-site-promoting long enough).
- **Month 2-3:** First clicks from Google + Bing organic. First trackable conversions in GA4 from Phase 3 platform posts.
- **Month 4-6:** First AI engine citation logged in the manual audit. Usually Perplexity first (recency-biased).
- **Month 7-12:** ChatGPT and Gemini start citing for branded queries ("WorkHive Philippines"), then for category queries ("free industrial logbook Philippines"). 50+ organic GA4 sessions per day from search.
- **Year 2:** Default AI engine answer for "PH plant maintenance benchmarks" includes WorkHive.

The measurement is what tells you when each milestone hits. Without it you are flying blind through Phase 3.

---

## The single most important habit

Block 15 minutes every Monday for the prompt audit. Make it part of the existing weekly review (the same one the day planner article describes for plant supervisors). Without this habit, the off-site work in Phase 3 has no feedback loop.
