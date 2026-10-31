---
name: change_external-llms-txt-complete-guide-2026-format-structure-wh_2026-10-31
type: source-change
chunk: external-llms-txt-complete-guide-2026-format-structure-wh
topic: llms.txt complete guide 2026 format structure what to include generator validator
source: https://llmpulse.ai/blog/llms-txt-guide/
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-llms-txt-complete-guide-2026-format-structure-wh changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-llms-txt-complete-guide-2026-format-structure-wh (before)
+++ external-llms-txt-complete-guide-2026-format-structure-wh (after)
@@ -1,24 +1,26 @@
-## reference · llms.txt
-* llms.txt is a proposed Markdown format for giving AI tools a curated map of important content.
-* The file should be served at the root path of a website, specifically at https://yourdomain.com/llms.txt.
-* The proposal requires an H1 and describes an optional structure for the elements that follow.
-* The H1 is the only required element and should be the site or project name.
-* A blockquote summary is optional and should be a short, one-sentence description of the site or project.
-* Free-form prose can provide context and should include information about the audience, topics, and what readers should expect.
-* H2 sections are optional and can group Markdown links under headings such as Docs, API, Examples, or Tutorials.
-* Link notes are optional and can add context to a link with a colon and description.
-* An "Optional" section can be used to list secondary content that can be skipped by the LLM if context is tight.
-* The file should be written in CommonMark Markdown and should not include XML, JSON, front-matter, or schema validation.
-* The simplicity of the format is intended to make it easy for LLMs to parse the file with a basic Markdown parser.
-* The file should be manually written, but generators can be used for a first pass.
-* When creating an llms.txt file, pick a clear H1 and one-line summary, write a context paragraph, enumerate important pages, group them under H2 sections, and write a one-line description per link.
-* The file should be validated, hosted at the root of the domain, and optionally referenced in the robots.txt file.
-* The file should not be used as a replacement for a sitemap.xml file, but rather as a complementary file to provide a curated index of key pages.
-* The following files serve different purposes: 
-  + robots.txt: allow/disallow rules for crawlers
-  + sitemap.xml: list of canonical URLs for search engines
-  + llms.txt: curated Markdown index for AI tools
-  + generated context bundle: implementation-specific context window for specific tools
-* Generators can be used to create an llms.txt file, but quality varies and some may produce bloated files.
-* Popular generators include Firecrawl, Mintlify, WordLift, and the llmstxt.org reference generator.
+## reference · llms.txt format and structure
+
+- **Definition**: `llms.txt` is a plain-text Markdown file served at the domain root (`https://yourdomain.com/llms.txt`) or subpath (e.g., `/docs/llms.txt`) to provide AI tools with a curated map of site content.
+- **Origin**: Proposed by Jeremy Howard (Answer.AI) in September 2024; updated to v2 in August 2026. Specification hosted at `llmstxt.org`.
+- **Required Elements**:
+  - **H1 Heading**: The only mandatory element. Must contain the site or project name.
+- **Optional Elements**:
+  - **Blockquote**: A short summary following the H1. No strict character limit (e.g., 200 chars) is enforced by the spec.
+  - **Free-form Prose**: Additional context paragraphs in Markdown.
+  - **H2 Sections**: Group links under headings (e.g., `## Docs`, `## API`, `## Examples`).
+  - **Link Descriptions**: Links can be followed by a colon and a one-line description (e.g., `- [Quickstart](https://example.com/docs): One-line description`).
+  - **"Optional" Section**: A convention for grouping secondary links that agents may skip if context is tight; has no special mechanical meaning.
+- **Format Rules**:
+  - Must be valid CommonMark Markdown.
+  - No XML, JSON, front-matter, or schema validation required.
+  - Designed for cheap parsing by LLMs using basic Markdown parsers.
+- **Distinctions from Other Files**:
+  - **vs. `robots.txt`**: `robots.txt` defines crawler access rules (allow/disallow); `llms.txt` provides content context.
+  - **vs. `sitemap.xml`**: `sitemap.xml` lists all URLs; `llms.txt` is a curated, human-written brief of important content.
+  - **vs. `llms-full.txt`**: `llms-full.txt` is **not** part of the official `llms.txt` proposal. It is a tool-specific convention for concatenating full page content.
+- **Strategic Notes**:
+  - **No Confirmed Ranking Signal**: Major search providers (including Google) have not confirmed `llms.txt` as a ranking input. Google states AI Overviews and AI Mode require no special AI file.
+  - **Purpose**: Reduces token waste by removing HTML noise (ads, nav, scripts) and providing clean, citable content for AI search engines (ChatGPT, Perplexity, Gemini).
+  - **Best For**: Documentation sites, knowledge bases, and content-heavy sites where clarity and curation are critical for AI ingestion.
+
 Sources: https://llmpulse.ai/blog/llms-txt-guide/
```

## Decision (2026-10-31)

No lever moves. The spec moved to v2 (August 2026) with only the H1 mandatory; the site's llms.txt has the H1, a blockquote and H2 link sections, so it conforms to both versions.
