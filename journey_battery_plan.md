# Journey Battery Plan — ③ Journey altitude (executable continuity)

> Each journey drives a job-to-be-done across pages with `window.__JOURNEY` (journey_battery.js) and asserts **state + number continuity**. Anchored to a Phase-3 finding + the `sweep:ia:*` candidate it corroborates. SURFACE-only.

> **Install per page:** `browser_evaluate(fn = <journey_battery.js>)` then the step() call below. Run the page kernel (`__UFAI.run`) too — journey COMPOSES the page battery.

## Find what maintenance is due/overdue (does the count agree across the pages a worker sees?)

- **Persona:** field/novice  ·  **Expect:** `agree`
- **Tests:** Phase-3 'due/overdue' AMBIGUITY OF SOURCE — the overdue count is derived two ways (per-asset v_pm_compliance_truth vs per-scope-item v_pm_scope_items_truth).
- **Corroborates:** `sweep:ia:theme:late-overdue`, `sweep:ia:theme:due-soon-upcoming`

```js
window.__JOURNEY.reset();
// navigate → pm-scheduler.html, re-install journey_battery.js, then:
window.__JOURNEY.step("pm-scheduler", { overdue: '[data-rag-tile="pm-scheduler:overdue"] .sc-hero' });
// navigate → dayplanner.html, re-install journey_battery.js, then:
window.__JOURNEY.step("dayplanner", { overdue: '[data-rag-tile="dayplanner:overdue_count"] .sc-hero' });
window.__JOURNEY.verdict({ tol: 0.5 });
```
> **Interpretation:** a `journey-number-drift` here is a real finding — the same KPI disagrees across pages (verify same-derivation first, then it is a drift bug that can show users a stale value). Feed the result onto the cited candidate.

## Find the highest-risk asset (do the risk lenses agree?)

- **Persona:** supervisor/novice  ·  **Expect:** `agree`
- **Tests:** Phase-3 'top risk' AMBIGUITY + CANONICAL UNREACHABLE (predictive is hidden). Risk is shown as hot assets / critical assets / high-severity alerts — confirm whether these are one number or three legitimately different lenses.
- **Corroborates:** `sweep:ia:theme:risk-hot-critical`

```js
window.__JOURNEY.reset();
// navigate → predictive.html, re-install journey_battery.js, then:
window.__JOURNEY.step("predictive", { at_risk: '[data-rag-tile="predictive:hot_assets"] .sc-hero' });
// navigate → asset-hub.html, re-install journey_battery.js, then:
window.__JOURNEY.step("asset-hub", { at_risk: '[data-rag-tile="asset-hub:critical_assets"] .sc-hero' });
// navigate → alert-hub.html, re-install journey_battery.js, then:
window.__JOURNEY.step("alert-hub", { at_risk: '[data-rag-tile="alert-hub:high_severity_alerts"] .sc-hero' });
window.__JOURNEY.verdict({ tol: 0.5 });
```
> **Interpretation:** a `journey-number-drift` here is a real finding — the same KPI disagrees across pages (verify same-derivation first, then it is a drift bug that can show users a stale value). Feed the result onto the cited candidate.

## See what's waiting for my approval (assets vs parts — SHOULD these differ?)

- **Persona:** supervisor/novice  ·  **Expect:** `drift-confirms-distinct`
- **Tests:** Phase-2 RELABEL — same label 'Pending approval' on two pages with DIFFERENT subjects (assets vs parts). A drift here is the EXPECTED proof they are distinct units (relabel, don't consolidate); agreement would be a coincidence, not a contract.
- **Corroborates:** `sweep:ia:relabel:pending-approval`

```js
window.__JOURNEY.reset();
// navigate → asset-hub.html, re-install journey_battery.js, then:
window.__JOURNEY.step("asset-hub", { pending_approval: '[data-rag-tile="asset-hub:pending_approval"] .sc-hero' });
// navigate → inventory.html, re-install journey_battery.js, then:
window.__JOURNEY.step("inventory", { pending_approval: '[data-rag-tile="inventory:pending_approval"] .sc-hero' });
window.__JOURNEY.verdict({ tol: 0.5 });
```
> **Interpretation:** a `journey-number-drift` here is EXPECTED and CONFIRMS the two units are different subjects (relabel, do not consolidate). Agreement would be coincidence.

---
_State continuity (identity/role/hive constant) is asserted automatically by `verdict()` across all steps — no per-step config needed._
