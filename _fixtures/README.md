# _fixtures/ — negative fixtures, not product pages

Dev test copies and backups moved out of the served root (Trajectory T1 root hygiene,
2026-08-24). They are kept ON PURPOSE: T1.5's resurrection proofs run upgraded detectors
against pre-fix worlds, and these files are frozen pre-fix worlds (e.g. `index-*-test.html`
still carries the dead `#join` sticky CTA pattern the anchor-resolution gate must go RED on).

Rules:

* Nothing here is served: `netlify.toml` force-404s `/_fixtures/*` (publish is `.` so the
  directory would otherwise be public — `index.backup.html` was reachable on prod before this).
* Nothing here counts in any page roster, sweep denominator, or gate scope. Roster tools that
  previously excluded these files BY NAME at the root keep working (their exclusions now match
  nothing) — new tooling should exclude the `_fixtures/` directory, not filenames.
* Do not "fix" these files. A repaired fixture proves nothing; the whole point is that
  detectors fail on them.
