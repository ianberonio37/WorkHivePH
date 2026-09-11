#!/usr/bin/env bash
# reload_and_rewalk_fn.sh — load the bounded provider calls, then re-ask every contract with the fixed lens.
#
# Two things changed since the first W3-FN walk and BOTH need a fresh run to mean anything:
#
#   the PRODUCT  — 10 provider calls that could hang forever are now bounded, so the failover written into
#                  _shared/embedding-chain.ts can finally run. ★THE LOCAL EDGE RUNTIME CACHES DENO MODULES
#                  AND WILL HAPPILY SERVE YESTERDAY'S FUNCTION: clear the cache and restart, or the walk
#                  measures the code that was already there and reports the fix as absent.
#   the LENS     — 59 of the 62 functions answer through _shared/envelope.ts, and the shape check was
#                  reading only each function's own file. It took a push-notification payload for a declared
#                  response and accused three functions of a shape they never claimed.
set -u
export PYTHONIOENCODING=utf-8

echo "== clearing the deno cache and restarting the edge runtime $(date +%H:%M:%S)"
docker exec supabase_edge_runtime_workhive sh -c 'rm -rf /root/.cache/deno' 2>&1 | tail -1
docker restart supabase_edge_runtime_workhive 2>&1 | tail -1

echo "== waiting for the stack to answer"
for i in $(seq 1 60); do
  n=$(timeout 25 docker exec supabase_db_workhive psql -U postgres -d postgres -Atc "select count(*) from hives" 2>/dev/null | tail -1)
  [ "$n" = "6" ] && break
  sleep 10
done
[ "${n:-}" = "6" ] || { echo "the database never came back - stopping rather than measuring a dead stack"; exit 1; }
sleep 20   # the runtime needs a moment after the DB is up

echo "== re-walking all 62 contracts $(date +%H:%M:%S)"
node tools/prove_fn_contracts.mjs > .tmp/fn_rewalk.log 2>&1
tail -2 .tmp/fn_rewalk.log

echo "== re-asking whatever still timed out, with a budget wider than the platform's own"
bash tools/repatient_fn_contracts.sh .tmp/fn_contracts.json 2>&1 | tail -12

echo "== banking"
python tools/bank_fn_contracts.py .tmp/fn_contracts.json 2>&1 | tail -6
echo "fn re-walk complete $(date +%H:%M:%S)"
