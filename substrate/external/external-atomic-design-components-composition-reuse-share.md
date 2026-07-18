---
name: external-atomic-design-components-composition-reuse-share
type: reference
source: https://bradfrost.com/blog/post/atomic-web-design/
source_sha: c4ea01ea2adc7331
fetched_at: 2026-07-15T09:02:17Z
last_verified: 2026-07-15
ttl_days: 30
distilled_by: night-crawler-v1
supersedes: null
topic: atomic design components composition reuse shared primitives
---

## reference · atomic design components composition reuse shared primitives

* Atomic design is a methodology for creating design systems, consisting of five distinct levels: 
  * Atoms (basic HTML tags, e.g., form labels, inputs, buttons)
  * Molecules (groups of atoms, e.g., a form)
  * Organisms (groups of molecules, e.g., a masthead)
  * Templates (groups of organisms, e.g., a page layout)
  * Pages (specific instances of templates with real content)
* Atoms are abstract and not terribly useful on their own but serve as a reference in a pattern library.
* Molecules are relatively simple combinations of atoms, built for reuse, and encourage a "do one thing and do it well" mentality.
* Organisms are complex, distinct sections of an interface, composed of molecules, and promote creating standalone, portable, reusable components.
* Templates provide context to molecules and organisms, and clients can see the final design in place; they often start as HTML wireframes and increase in fidelity.
* Pages are specific instances of templates, with real content, and test the effectiveness of the design system.
* Atomic design provides a clear methodology for crafting design systems, promoting consistency, scalability, and the ability to traverse from abstract to concrete.

Sources: https://bradfrost.com/blog/post/atomic-web-design/
