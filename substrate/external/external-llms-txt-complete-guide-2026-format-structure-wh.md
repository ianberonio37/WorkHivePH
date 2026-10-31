---
name: external-llms-txt-complete-guide-2026-format-structure-wh
type: reference
source: https://llmpulse.ai/blog/llms-txt-guide/
source_sha: b4187b3d5da5a44a
fetched_at: 2026-10-30T17:18:29Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: llms.txt complete guide 2026 format structure what to include generator validator
---

## reference · llms.txt format and structure

- **Definition**: `llms.txt` is a plain-text Markdown file served at the domain root (`https://yourdomain.com/llms.txt`) or subpath (e.g., `/docs/llms.txt`) to provide AI tools with a curated map of site content.
- **Origin**: Proposed by Jeremy Howard (Answer.AI) in September 2024; updated to v2 in August 2026. Specification hosted at `llmstxt.org`.
- **Required Elements**:
  - **H1 Heading**: The only mandatory element. Must contain the site or project name.
- **Optional Elements**:
  - **Blockquote**: A short summary following the H1. No strict character limit (e.g., 200 chars) is enforced by the spec.
  - **Free-form Prose**: Additional context paragraphs in Markdown.
  - **H2 Sections**: Group links under headings (e.g., `## Docs`, `## API`, `## Examples`).
  - **Link Descriptions**: Links can be followed by a colon and a one-line description (e.g., `- [Quickstart](https://example.com/docs): One-line description`).
  - **"Optional" Section**: A convention for grouping secondary links that agents may skip if context is tight; has no special mechanical meaning.
- **Format Rules**:
  - Must be valid CommonMark Markdown.
  - No XML, JSON, front-matter, or schema validation required.
  - Designed for cheap parsing by LLMs using basic Markdown parsers.
- **Distinctions from Other Files**:
  - **vs. `robots.txt`**: `robots.txt` defines crawler access rules (allow/disallow); `llms.txt` provides content context.
  - **vs. `sitemap.xml`**: `sitemap.xml` lists all URLs; `llms.txt` is a curated, human-written brief of important content.
  - **vs. `llms-full.txt`**: `llms-full.txt` is **not** part of the official `llms.txt` proposal. It is a tool-specific convention for concatenating full page content.
- **Strategic Notes**:
  - **No Confirmed Ranking Signal**: Major search providers (including Google) have not confirmed `llms.txt` as a ranking input. Google states AI Overviews and AI Mode require no special AI file.
  - **Purpose**: Reduces token waste by removing HTML noise (ads, nav, scripts) and providing clean, citable content for AI search engines (ChatGPT, Perplexity, Gemini).
  - **Best For**: Documentation sites, knowledge bases, and content-heavy sites where clarity and curation are critical for AI ingestion.

Sources: https://llmpulse.ai/blog/llms-txt-guide/
