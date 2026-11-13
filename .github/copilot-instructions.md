# Copilot instructions for WorkHive

You are the coding agent. Claude is the orchestrator: it writes one brief per unit of work in `.tmp/copilot/`, and
after you finish it reads your diff and runs the gates again. Do what the brief asks, in the files it names, and
nothing more. If the brief looks wrong, or a check disagrees with it, stop and say so in your report. Do not widen
the scope to make something pass.

## The project

- **WorkHive** is a maintenance platform for Filipino industrial workers. The pages are plain HTML, CSS and vanilla
  JS, served as static files with no build step. `learn/` holds the public guides, and the app pages sit at the repo
  root.
- The backend is Supabase: Postgres with row-level security, migrations in `supabase/migrations/`, and Deno edge
  functions in `supabase/functions/`. Development runs against the LOCAL stack (Docker, `supabase_db_workhive`).
- `tools/` holds the Python and Node scripts. The checks ("gates") are registered in `run_platform_checks.py`.
  Run one with `python run_platform_checks.py --only <id>[,<id>...]`, or run its script directly as the brief says.

## Never do these

- Never run git write commands: no commit, push, stash, reset or checkout of files. Claude commits.
  Never stage `.vscode/settings.json`.
- Never touch production. Do not run `supabase db push` or `supabase functions deploy`, and do not use the
  production project `hzyvnjtisfgbksicrouu`.
- Never make a paid or model API call (Claude, Gemini, Voyage, OpenAI), and never run the full gate board.
- Never lower a ratchet to make a gate pass. Do not run `--rebase` and do not hand-edit `*_baseline.json`. Fix the
  cause instead.
- Never hand-edit generated files: `trajectory_registry.json`, the scoreboard at the top of
  `UFAI_TRAJECTORY_ROADMAP.md`, `live_walk_manifest.json`, `public_page_stamps.json`, or the `*.html.md` twins of
  learn guides. Claude regenerates them.
- Never skip a git hook or a check with a flag.

## Rules for public copy (learn guides, landing pages)

- English only. No em dash (the long dash) anywhere in visible copy.
- Sentences of 20 words or fewer, in the active voice. A sentence of 12 or more words must read at Flesch-Kincaid
  grade 8 or below, so use short words. A paragraph or list block stays under 60 words.
- Write full sentences with a subject and a verb. Do not stack short fragments or "No X." sentences for rhythm. The
  design detector counts that as "aphoristic cadence" and fails the page.
- Explain every acronym at its first use on the page, like "MTBF (mean time between failures)".
- Say only what the product really does. Before you describe a feature, check it in the code or the database. Do not
  invent case studies, plant names, dates or figures. Keep every fact a sentence already states, and do not add new
  ones.
- A FAQ answer appears twice: in the visible `<details>` and in the JSON-LD `FAQPage`. Change both the same way, and
  keep the JSON-LD valid JSON.
- The `<div class="answer-first">` opener must keep a number, a unit (hours, days, %, peso sign, degrees...) and a
  proper noun.

## Rules for code

- Escape user content before it goes into HTML (`escHtml`).
- Use the design tokens (`var(--wh-...)`) for colors, font sizes and spacing. Do not hard-code them.
- Touch targets are at least 44 px. Respect `prefers-reduced-motion`.
- When Python writes a text file on Windows, use `open(path, 'w', encoding='utf-8', newline='')` so no CR characters
  reach the file. Do not build file content in a shell heredoc if it holds backslashes or quotes.
- A migration is a new file in `supabase/migrations/`. Never edit an applied one.

## Your report

When you finish, list:
1. every file you changed, and what changed in each;
2. each acceptance command from the brief, with its last lines of output (PASS or FAIL);
3. anything the brief asked for that you could not do, and why.
