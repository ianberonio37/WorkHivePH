"""Weibull MLE fitter (Phase R.5).

Wraps lifelines.WeibullFitter so the edge function gets a stable JSON
contract regardless of how lifelines evolves. Native censored-data
support is the reason we use lifelines here over a hand-rolled MLE.

Inputs:
  failures: list[float]   days-to-failure for each observed failure
  censored: list[float]   days-survived-without-failure for each right-censored asset

Output (matches weibull_fits + v_weibull_truth contract):
  beta:            float   Weibull shape parameter
  eta_days:        float   Weibull scale parameter (characteristic life)
  failure_pattern: 'infant'|'random'|'wearout'|'insufficient_data'
  n_failures:      int
  n_censored:      int
  log_likelihood:  float
  fit_method:      'mle_lifelines'
  diagnostic:      str     human-readable note (used by the UI)

Insufficient-data thresholds (skill: predictive-analytics):
  - fewer than 4 failure events   -> insufficient_data, no fit attempted
  - any duration <= 0             -> stripped before fitting
  - all durations identical       -> insufficient_data (degenerate likelihood)

beta classification (IEC 61649 / RCM bathtub curve):
  - beta < 0.95   -> infant   (decreasing hazard)
  - 0.95 <= beta <= 1.05 -> random  (constant hazard, exponential limit)
  - beta > 1.05   -> wearout  (increasing hazard)
"""
from __future__ import annotations

from typing import Any

# IEC 61649 minimum sample for a defensible Weibull fit. Below this we
# refuse to fit and return insufficient_data so the UI can warn the user.
MIN_FAILURES_FOR_FIT = 4

# Pattern thresholds — the +/- 0.05 band around 1.0 catches noisy fits that
# are practically random rather than mildly increasing/decreasing.
BETA_INFANT_MAX  = 0.95
BETA_WEAROUT_MIN = 1.05


def _classify_beta(beta: float) -> str:
    if beta is None or beta != beta:        # NaN guard
        return "insufficient_data"
    if beta < BETA_INFANT_MAX:
        return "infant"
    if beta > BETA_WEAROUT_MIN:
        return "wearout"
    return "random"


def fit_weibull(failures: list[float], censored: list[float] | None = None) -> dict[str, Any]:
    """Fit a 2-parameter Weibull via lifelines.WeibullFitter.

    Returns the JSON-safe contract above. Never raises for "not enough data";
    instead returns failure_pattern='insufficient_data' so the orchestrator
    can persist the row and the UI can show "need more failures".
    """
    failures = [float(x) for x in (failures or []) if x and float(x) > 0]
    censored = [float(x) for x in (censored or []) if x and float(x) > 0]

    n_failures = len(failures)
    n_censored = len(censored)

    if n_failures < MIN_FAILURES_FOR_FIT:
        return {
            "beta":            None,
            "eta_days":        None,
            "failure_pattern": "insufficient_data",
            "n_failures":      n_failures,
            "n_censored":      n_censored,
            "log_likelihood":  None,
            "fit_method":      "mle_lifelines",
            "diagnostic":      f"Need at least {MIN_FAILURES_FOR_FIT} failures (have {n_failures}). Log more corrective entries before refitting.",
        }

    # Degenerate case: all values identical -> Weibull MLE has no unique solution
    if len(set(failures)) == 1 and not censored:
        return {
            "beta":            None,
            "eta_days":        None,
            "failure_pattern": "insufficient_data",
            "n_failures":      n_failures,
            "n_censored":      n_censored,
            "log_likelihood":  None,
            "fit_method":      "mle_lifelines",
            "diagnostic":      "All time-between-failure values are identical. Degenerate likelihood; cannot fit.",
        }

    # Lazy import keeps the API cold-start light when no one is calling Weibull.
    try:
        from lifelines import WeibullFitter
    except Exception as e:        # pragma: no cover (deployment guard)
        return {
            "beta":            None,
            "eta_days":        None,
            "failure_pattern": "insufficient_data",
            "n_failures":      n_failures,
            "n_censored":      n_censored,
            "log_likelihood":  None,
            "fit_method":      "mle_lifelines",
            "diagnostic":      f"lifelines unavailable on this deployment: {e}",
        }

    durations = failures + censored
    # event_observed: 1 = failure, 0 = censored
    events = [1] * n_failures + [0] * n_censored

    wf = WeibullFitter()
    try:
        wf.fit(durations, event_observed=events)
    except Exception as e:
        return {
            "beta":            None,
            "eta_days":        None,
            "failure_pattern": "insufficient_data",
            "n_failures":      n_failures,
            "n_censored":      n_censored,
            "log_likelihood":  None,
            "fit_method":      "mle_lifelines",
            "diagnostic":      f"WeibullFitter convergence failed: {type(e).__name__}: {e}",
        }

    # lifelines parameterization:
    #   S(t) = exp(-(t / lambda_) ** rho_)
    #   rho_   = beta  (shape)
    #   lambda_= eta   (scale, characteristic life)
    beta = float(getattr(wf, "rho_", float("nan")))
    eta  = float(getattr(wf, "lambda_", float("nan")))
    try:
        ll = float(wf.log_likelihood_)
    except Exception:
        ll = None

    pattern = _classify_beta(beta)

    return {
        "beta":            beta,
        "eta_days":        eta,
        "failure_pattern": pattern,
        "n_failures":      n_failures,
        "n_censored":      n_censored,
        "log_likelihood":  ll,
        "fit_method":      "mle_lifelines",
        "diagnostic":      _human_diagnostic(pattern, beta, eta),
    }


def _human_diagnostic(pattern: str, beta: float | None, eta: float | None) -> str:
    if pattern == "insufficient_data":
        return "Insufficient or degenerate data."
    if beta is None or eta is None:
        return "Fit completed but parameters unstable. Treat with caution."
    if pattern == "infant":
        return (
            f"Infant mortality region (beta={beta:.2f} < 1). Hazard is highest just after "
            f"installation and drops with age. Look for installation defects, commissioning gaps, "
            f"or break-in failures rather than time-based replacement."
        )
    if pattern == "wearout":
        return (
            f"Wear-out region (beta={beta:.2f} > 1). Hazard rises with age. Time-based "
            f"replacement at a fraction of eta={eta:.0f}d is defensible; pick the "
            f"interval against your reliability target."
        )
    return (
        f"Random failures (beta={beta:.2f} ~ 1). Failures are memoryless; time-based "
        f"replacement is wasteful. Use condition-based monitoring or run-to-failure "
        f"depending on consequence."
    )
