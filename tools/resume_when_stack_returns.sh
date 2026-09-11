#!/usr/bin/env bash
# resume_when_stack_returns.sh — wait for the docker engine to come back, then finish the blocked waves.
#
# ★WHAT THIS REPLACES. Four separate jobs were each waiting for the serial driver to print "serial drive
# complete" - a line it never prints when it gives up on a dead host, so all four would have waited for ever.
# A chain should key on the CONDITION it needs (can the stack answer?), never on another job's success
# message: the message is a proxy, and a proxy that can go permanently missing is a deadlock.
#
# The engine has been returning 500 on every API call for the best part of an hour. It has recovered on its
# own before, so this waits rather than restarting anything on Ian's machine.
set -u
export PYTHONIOENCODING=utf-8
LOG=".tmp/resume_chain.log"
: > "$LOG"
say() { echo "$(date +%H:%M:%S) $*" | tee -a "$LOG"; }

say "waiting for the docker engine (it has been returning 500 for ~1h; it recovers when idle)"
UP=0
for i in $(seq 1 240); do            # up to ~4 hours, cheaply
  n=$(timeout 20 docker exec supabase_db_workhive psql -U postgres -d postgres -Atc "select count(*) from hives" 2>/dev/null | tail -1)
  if [ "$n" = "6" ]; then UP=1; say "the stack answered after ~$((i*40))s"; break; fi
  sleep 20
done
[ "$UP" = "1" ] || { say "the stack never came back - nothing measured, nothing banked"; exit 1; }

say "== lifecycle cells (64 rows)"
node tools/prove_lifecycle_cells.mjs >> "$LOG" 2>&1
[ -f .tmp/lifecycle_cells.json ] && python tools/bank_cell_walk.py .tmp/lifecycle_cells.json --gate lifecycle-cells 2>&1 | tail -3 | tee -a "$LOG"

say "== shared components, this time with an identity so the walk reaches its pages"
node tools/prove_shared_components.mjs >> "$LOG" 2>&1
grep -c "bounced" "$LOG" | sed 's/^/    readings that still bounced: /' | tee -a "$LOG"

say "== edge functions: load the bounded provider calls, then re-ask every contract"
bash tools/reload_and_rewalk_fn.sh >> "$LOG" 2>&1
tail -4 "$LOG"

say "resume chain complete"
