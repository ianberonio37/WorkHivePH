# persona_corpus/ — the persona-knowledge drop-folder (companion wiring W10)

Drop a file here → run `python tools/ingest_persona_knowledge.py --source drop-folder`
→ it becomes retrievable domain knowledge for the persona, contextually chunked,
embedded (Voyage 384-dim), and persona-scoped. Idempotent: editing a file just
refreshes its chunks (supersede-on-hash-change).

## The folder IS the scope (O15)

| Folder | persona_scope | Who retrieves it |
|---|---|---|
| `hezekiah/` | `technical` | Hezekiah (the technical expert) + (technical+shared) |
| `zaniah/`   | `strategic` | Zaniah (the strategist) + (strategic+shared) |
| `shared/`   | `shared`    | both personas |

Accepted file types: `.md`, `.txt`, `.pdf`. (PDFs are extracted with pdfplumber.)

## Two-planes guardrail — what may go in (locked 2026-06-12)

`persona_knowledge` has **no `hive_id`** → it is GLOBAL/cross-tenant. So ONLY the
persona's general **BRAIN** belongs here:

- ✅ **In:** your skills, platform **methodology/doctrine** (canonical OEE/MTBF/PM
  *definitions*, maturity-stairs), and **license-clean** external references.
- ❌ **Out:** ① **live tenant data** (any hive's logbook/assets/PM numbers — that is
  the per-tenant RLS plane served by L01–L07 + asset-brain; putting it in a global
  table is a multi-tenancy breach) · ② **raw code/architecture** (implementation,
  not expertise).

## License

Curate **license-clean** material only: public-domain, CC, Ian-licensed, or your own
words. Excerpt — never bulk-ingest copyrighted books. Quality over volume.

> An in-repo drop-folder is also what lets W12's GitHub Action reconcile + sweep the
> corpus automatically when content changes.
