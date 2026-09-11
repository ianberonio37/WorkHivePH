#!/usr/bin/env bash
# run_under_drive_lock.sh — run any prover under the SAME lock the journey drive takes.
#
# This 8GB host has one usable browser slot. The journey drive already refuses to start a second copy of
# itself, but nothing stopped a DIFFERENT prover from opening a second browser beside it - and that is
# exactly what turned clean pages into "wait ran out" for both, twice in one night. Every browser-driven
# wave now queues behind the same lock instead of racing the drive for the same memory.
#
#   bash tools/run_under_drive_lock.sh node tools/prove_content_ufai.mjs --kind calc
#   bash tools/run_under_drive_lock.sh node tools/prove_lifecycle_cells.mjs --wave PG
set -u
LOCK=".tmp/jn_drive.lock"
LABEL="${*:1:3}"

# wait for whatever holds the slot, up to ~40 minutes, checking twice so a lock released between two
# archetypes of a running drive is not mistaken for a free host
for i in $(seq 1 80); do
  if [ ! -f "$LOCK" ] || ! kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
    sleep 20
    if [ ! -f "$LOCK" ] || ! kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
      break
    fi
  fi
  sleep 30
done
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "the browser slot never freed (held by pid $(cat "$LOCK")) - not starting: ${LABEL}"
  exit 1
fi

# ★THE WRAPPER MUST NOT HOLD THE LOCK THE COMMAND ITSELF TAKES. Once every browser prover began taking the
# slot in tools/browser_slot.mjs, a wrapper that grabbed it first left the prover waiting 45 minutes for a
# lock its own parent was holding - a deadlock built out of two correct halves. The wrapper now only WAITS
# for the host to be free and hands over; the prover takes the slot itself and releases it on exit.
echo "== $(date +%H:%M:%S) host is free, handing over to: $*"
"$@"
rc=$?
echo "== $(date +%H:%M:%S) finished (exit ${rc}): ${LABEL}"
exit $rc
