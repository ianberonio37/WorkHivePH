---
name: change_external-llms-txt-specification-github-official-format-h1_2026-10-31
type: source-change
chunk: external-llms-txt-specification-github-official-format-h1
topic: llms.txt specification GitHub official format H1 blockquote sections Optional
source: https://github.com/AnswerDotAI/llms-txt
detected: 2026-10-31
age_days: 86
ttl_days: 30
---

# external-llms-txt-specification-github-official-format-h1 changed on re-fetch (2026-10-31)

The distilled facts moved. DECIDE: which lever (gate threshold, roadmap claim, robots.txt line, copy) rests on this source, and whether it moves with it - the KA-E row for this chunk is re-opened to hold that decision.

```diff
--- external-llms-txt-specification-github-official-format-h1 (before)
+++ external-llms-txt-specification-github-official-format-h1 (after)
@@ -1,10 +1,37 @@
 ## reference · llms.txt specification
-* The `/llms.txt` file is a proposed standard for providing information to help LLMs use a website at inference time.
-* The file should be in markdown format and contain brief background information, guidance, and links to detailed markdown files.
-* Pages on websites that have information useful for LLMs should provide a clean markdown version of those pages at the same URL as the original page, but with `.md` appended.
-* URLs without file names should append `index.html.md` instead.
-* The `/llms.txt` file can be processed using classical programming techniques such as parsers and regex.
-* The file can serve many purposes, including helping developers find their way around software documentation, outlining business structure, or breaking down complex legislation.
-* All `nbdev` projects now create `.md` versions of all pages by default.
-* The `llms.txt` file can be used to create two markdown files with the contents of the linked URLs: `llms-ctx.txt` and `llms-ctx-full.txt`.
+
+- **File Location**: Must be served at the root of the domain (e.g., `https://example.com/llms.txt`).
+- **MIME Type**: Should be served as `text/plain`.
+- **Structure**:
+  - **H1 Header**: The first line must be an H1 (`#`) containing the name of the website or project.
+  - **Blockquote**: Immediately following the H1, include a blockquote (`>`) with a brief description of the site/project. This is optional but recommended.
+  - **Sections**: Use H2 (`##`) headers to group related links (e.g., `## Documentation`, `## API Reference`).
+- **Link Format**:
+  - Each link must be a Markdown link: `[Title](URL)`.
+  - Optional description: Append a colon and description after the link: `[Title](URL): Description`.
+  - Descriptions should be concise (1-2 sentences).
+- **Content Guidelines**:
+  - Include links to key documentation, API references, and important pages.
+  - Exclude navigation menus, footer links, and low-value pages.
+  - Order links by importance (most important first).
+- **Optional Fields**:
+  - `llms-full.txt`: A separate file containing the full content of the site (concatenated Markdown) for LLM ingestion.
+  - `llms.txt` can include a link to `llms-full.txt` if available.
+- **Best Practices**:
+  - Keep the file under 100KB for efficient loading.
+  - Update regularly to reflect site changes.
+  - Use clear, descriptive titles for links.
+- **Example Structure**:
+  ```markdown
+  # Project Name
+  > Brief description of the project.
+
+  ## Documentation
+  - [Getting Started](https://example.com/docs/getting-started): Quick start guide.
+  - [API Reference](https://example.com/docs/api): Complete API documentation.
+
+  ## Resources
+  - [Blog](https://example.com/blog): News and updates.
+  ```
+
 Sources: https://github.com/AnswerDotAI/llms-txt
```

## Decision (2026-10-31)

No lever moves. The site's llms.txt already follows the re-fetched spec: H1 'WorkHive' first, a blockquote description, then H2 sections (9) of Markdown links, served at the root (local 200, read 2026-10-31). build_md_twins, which it anchors, needs no change.
