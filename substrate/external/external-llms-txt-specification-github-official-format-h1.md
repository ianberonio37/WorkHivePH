---
name: external-llms-txt-specification-github-official-format-h1
type: reference
source: https://github.com/AnswerDotAI/llms-txt
source_sha: baa67125f1b3f9cb
fetched_at: 2026-10-30T16:57:55Z
last_verified: 2026-10-31
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: llms.txt specification GitHub official format H1 blockquote sections Optional
---

## reference · llms.txt specification

- **File Location**: Must be served at the root of the domain (e.g., `https://example.com/llms.txt`).
- **MIME Type**: Should be served as `text/plain`.
- **Structure**:
  - **H1 Header**: The first line must be an H1 (`#`) containing the name of the website or project.
  - **Blockquote**: Immediately following the H1, include a blockquote (`>`) with a brief description of the site/project. This is optional but recommended.
  - **Sections**: Use H2 (`##`) headers to group related links (e.g., `## Documentation`, `## API Reference`).
- **Link Format**:
  - Each link must be a Markdown link: `[Title](URL)`.
  - Optional description: Append a colon and description after the link: `[Title](URL): Description`.
  - Descriptions should be concise (1-2 sentences).
- **Content Guidelines**:
  - Include links to key documentation, API references, and important pages.
  - Exclude navigation menus, footer links, and low-value pages.
  - Order links by importance (most important first).
- **Optional Fields**:
  - `llms-full.txt`: A separate file containing the full content of the site (concatenated Markdown) for LLM ingestion.
  - `llms.txt` can include a link to `llms-full.txt` if available.
- **Best Practices**:
  - Keep the file under 100KB for efficient loading.
  - Update regularly to reflect site changes.
  - Use clear, descriptive titles for links.
- **Example Structure**:
  ```markdown
  # Project Name
  > Brief description of the project.

  ## Documentation
  - [Getting Started](https://example.com/docs/getting-started): Quick start guide.
  - [API Reference](https://example.com/docs/api): Complete API documentation.

  ## Resources
  - [Blog](https://example.com/blog): News and updates.
  ```

Sources: https://github.com/AnswerDotAI/llms-txt
