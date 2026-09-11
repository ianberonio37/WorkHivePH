#!/usr/bin/env bash
# repatient_fn_contracts.sh — re-ask ONLY the contracts that ran out of the prober's patience.
#
# ★A TIMEOUT IS A FACT ABOUT THE INSTRUMENT, NOT THE FUNCTION. The platform bounds its provider calls at
# AbortSignal.timeout(60000) and allows one jittered retry, so a slow-but-correct answer can legitimately
# take about two minutes. The prober gives up at 35s, which is right for the ~55 functions that answer in
# under a second and wrong for the handful that do not: those read `n/a`, and the banker refuses to bank an
# n/a because an unanswered call is not a passed contract.
#
# So the fast budget stays the default and this re-asks the stragglers with a budget WIDER than the
# platform's own worst case, one function at a time, appending to the same results file.
set -u
export PYTHONIOENCODING=utf-8
RESULTS="${1:-.tmp/fn_contracts.json}"
[ -f "$RESULTS" ] || { echo "no results at $RESULTS - run the wave first"; exit 1; }

FNS=$(python -c "
import json, sys
d = json.load(open('$RESULTS', encoding='utf-8'))
fns = sorted({r['fn'] for r in d.get('results', []) if r.get('verdict') == 'n/a'})
print(' '.join(fns))
")
if [ -z "${FNS:-}" ]; then
  echo "no contract read n/a - the fast budget was enough for every function"
  exit 0
fi
echo "re-asking with a 135s budget (the platform's worst case is ~120s): $FNS"
for F in $FNS; do
  echo "== $F $(date +%H:%M:%S)"
  node tools/prove_fn_contracts.mjs --fn "$F" --patient 2>&1 | grep -E "^\s+(ok|BAD|n/a)" | sed 's/^/    /'
done
echo "patient re-probe complete $(date +%H:%M:%S)"
