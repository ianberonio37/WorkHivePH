---
name: external-llms-txt-complete-guide-2026-format-structure-wh
type: reference
source: https://llmpulse.ai/blog/llms-txt-guide/
source_sha: 0d5f0bc4635bfb51
fetched_at: 2026-08-05T02:46:57Z
last_verified: 2026-08-05
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: llms.txt complete guide 2026 format structure what to include generator validator
---

## reference · llms.txt
* llms.txt is a proposed Markdown format for giving AI tools a curated map of important content.
* The file should be served at the root path of a website, specifically at https://yourdomain.com/llms.txt.
* The proposal requires an H1 and describes an optional structure for the elements that follow.
* The H1 is the only required element and should be the site or project name.
* A blockquote summary is optional and should be a short, one-sentence description of the site or project.
* Free-form prose can provide context and should include information about the audience, topics, and what readers should expect.
* H2 sections are optional and can group Markdown links under headings such as Docs, API, Examples, or Tutorials.
* Link notes are optional and can add context to a link with a colon and description.
* An "Optional" section can be used to list secondary content that can be skipped by the LLM if context is tight.
* The file should be written in CommonMark Markdown and should not include XML, JSON, front-matter, or schema validation.
* The simplicity of the format is intended to make it easy for LLMs to parse the file with a basic Markdown parser.
* The file should be manually written, but generators can be used for a first pass.
* When creating an llms.txt file, pick a clear H1 and one-line summary, write a context paragraph, enumerate important pages, group them under H2 sections, and write a one-line description per link.
* The file should be validated, hosted at the root of the domain, and optionally referenced in the robots.txt file.
* The file should not be used as a replacement for a sitemap.xml file, but rather as a complementary file to provide a curated index of key pages.
* The following files serve different purposes: 
  + robots.txt: allow/disallow rules for crawlers
  + sitemap.xml: list of canonical URLs for search engines
  + llms.txt: curated Markdown index for AI tools
  + generated context bundle: implementation-specific context window for specific tools
* Generators can be used to create an llms.txt file, but quality varies and some may produce bloated files.
* Popular generators include Firecrawl, Mintlify, WordLift, and the llmstxt.org reference generator.
Sources: https://llmpulse.ai/blog/llms-txt-guide/
