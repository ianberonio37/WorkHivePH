"""
AI Companion Advanced Analytics Validator (turns #165-#174)
============================================================
Forward-only L0 ratchet for the seventeenth 10-turn flywheel batch (2026-05-21).

  T165  Anomaly detection (3σ)
  T166  Weibull MTBF forecast
  T167  Pareto top 80%
  T168  Linear trend
  T169  Seasonal peak index
  T170  Outlier-trimmed mean
  T171  Z-score
  T172  Pearson correlation
  T173  Weibull CDF
  T174  Availability calc

10-layer audit.
"""

from __future__ import annotations
import os, sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from validator_utils import read_file, format_result

VOICE_HANDLER_JS = "voice-handler.js"


def _read() -> str:
    return read_file(VOICE_HANDLER_JS) or ""


SYMBOLS = {
    "anomaly":      ["_detectAnomaly3Sigma"],
    "weibull_fit":  ["_weibullMomentFit", "Justus"],
    "pareto":       ["_paretoTop80"],
    "trend":        ["_linearTrend", "'rising'", "'falling'", "'flat'"],
    "seasonal":     ["_seasonalPeakIndex"],
    "trimmed":      ["_trimmedMean"],
    "zscore":       ["_zScore"],
    "correlation":  ["_pearsonCorrelation"],
    "weibull_cdf":  ["_weibullCdf"],
    "availability": ["_availability"],
}
LABELS = {
    "anomaly":      "T165 _detectAnomaly3Sigma",
    "weibull_fit":  "T166 _weibullMomentFit + Justus closed-form citation",
    "pareto":       "T167 _paretoTop80",
    "trend":        "T168 _linearTrend + rising/falling/flat directions",
    "seasonal":     "T169 _seasonalPeakIndex",
    "trimmed":      "T170 _trimmedMean",
    "zscore":       "T171 _zScore",
    "correlation":  "T172 _pearsonCorrelation",
    "weibull_cdf":  "T173 _weibullCdf",
    "availability": "T174 _availability",
}


def main() -> int:
    print("\033[1m\nAI Companion Advanced Analytics Validator (10-layer)\033[0m")
    print("=" * 60)
    c = _read()
    print(f"  Scanning {VOICE_HANDLER_JS}")
    issues = []
    for k, syms in SYMBOLS.items():
        for s in syms:
            if s not in c:
                issues.append({"check": k, "reason": f"{s} missing."})
    n_pass, n_skip, n_fail = format_result(list(SYMBOLS.keys()), LABELS, issues)
    print()
    if n_fail == 0:
        print(f"  \033[92mAll {n_pass} checks passed.\033[0m")
    else:
        print(f"  \033[91m{n_pass} PASS  {n_skip} SKIP  {n_fail} FAIL\033[0m")
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
