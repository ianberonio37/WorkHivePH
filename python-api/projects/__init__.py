# Project Manager Backend — Phase 2 of WorkHive Project Manager
# Standards: PMBOK 7th ed., AACE 17R-97, ISO 21500, IDCON 6-Phase, SMRP
#
# Mirrors python-api/analytics/ structure. Each module exposes a
# `calculate(inputs: dict) -> dict` function called by the /project/progress
# endpoint in main.py.
#
# Phases (parallel to the analytics 4-phase model):
#   descriptive  — current state: rollup, status mix, hours, days elapsed
#   diagnostic   — variance decomposition: SV, CV by phase; blocker frequency
#   predictive   — forecast: EAC, ETC, finish-date trend, P50/P80 windows
#   prescriptive — recommendations: critical path (networkx), slack, fast-track
