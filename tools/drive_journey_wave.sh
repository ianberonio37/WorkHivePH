#!/usr/bin/env bash
# drive_journey_wave.sh — walk the W3-JN archetypes one at a time, banking each as it lands.
#
# This 8GB host wedges its docker engine after roughly twenty minutes of sustained browser work and
# recovers on its own once the load stops, so the wave cannot be driven as one long run: it has to be
# driven as many short ones that WAIT for the stack rather than reporting its absence as a finding.
# Before every archetype the database is asked a trivial question until it answers; a walk that starts
# without a cast would report six bounced pages instead of "the stack is down".
#
#   bash tools/drive_journey_wave.sh A J2 J3 J13        # tier A, these archetypes
#   bash tools/drive_journey_wave.sh A                  # tier A, every archetype in the registry order
set -u
TIER="${1:-A}"; shift || true
LOG=".tmp/jn_drive_${TIER}.log"

# ★ONE DRIVE AT A TIME, and the reason is a mistake already made tonight with the serial driver: two waiting
# jobs keyed on the same signal both fired, and two walks ran against one database. This drive is hours long
# and banks as it goes, so a second copy would interleave banks from two different walks of the same
# archetype. A tool that serialises work must first serialise ITSELF.
DLOCK=".tmp/jn_drive_self.lock"
if [ -f "$DLOCK" ]; then
  OTHER=$(cat "$DLOCK" 2>/dev/null)
  if [ -n "${OTHER:-}" ] && kill -0 "$OTHER" 2>/dev/null; then
    echo "another journey drive is already running (pid $OTHER) - not starting a second one"
    exit 1
  fi
  echo "clearing a stale journey-drive lock (pid ${OTHER:-?} is gone)"
fi
echo $$ > "$DLOCK"
trap 'rm -f "$DLOCK"' EXIT INT TERM

if [ "$#" -gt 0 ]; then
  ARCHES="$*"
else
  ARCHES=$(python -c "
import json
reg = json.load(open('trajectory_registry.json', encoding='utf-8'))
seen = []
for t in reg['trajectories']:
    if t.get('wave') != 'W3-JN':
        continue
    a = str((t.get('journey') or {}).get('archetype') or '')
    if '+' in a or not a or a in seen:
        continue
    seen.append(a)
print(' '.join(seen))
")
fi

# ★ONE WALK AT A TIME ON THIS HOST. Two drives overlapping (an old shell that outlived its task plus a new
# one) put two browsers on an 8GB box and turned clean pages into "wait ran out" for both. A lock file makes
# that impossible: a second drive says so and exits rather than quietly halving the first one's evidence.
LOCK=".tmp/jn_drive.lock"
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "a journey drive is already running (pid $(cat "$LOCK")) - not starting a second one" | tee -a "$LOG"
  exit 1
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT
echo "driving tier ${TIER}: ${ARCHES}" | tee -a "$LOG"
for A in $ARCHES; do
  # wait for the stack, up to ~10 minutes, before asking the browser to do anything
  for i in $(seq 1 40); do
    n=$(timeout 25 docker exec supabase_db_workhive psql -U postgres -d postgres -Atc "select count(*) from hives" 2>/dev/null | tail -1)
    [ "$n" = "6" ] && break
  done
  if [ "${n:-}" != "6" ]; then
    echo "  ${A}: the database never answered - stopping so nothing is measured without a cast" | tee -a "$LOG"
    exit 1
  fi
  echo "== ${A} $(date +%H:%M:%S)" | tee -a "$LOG"
  node tools/prove_full_journeys.mjs --archetype "$A" --tier "$TIER" >> "$LOG" 2>&1
  # ★A RUN THAT LOST THE DATABASE IS NOT A RESULT. The engine wedges under browser load and recovers on its
  # own; two archetypes were spent on "the database did not answer" before this retry existed. Wait for the
  # stack again and walk it once more rather than banking a run that never had a cast.
  if grep -q "the database did not answer" "$LOG" 2>/dev/null && ! [ -f ".tmp/full_journeys_${A}_tier${TIER}.json" ]; then
    for i in $(seq 1 40); do
      n=$(timeout 25 docker exec supabase_db_workhive psql -U postgres -d postgres -Atc "select count(*) from hives" 2>/dev/null | tail -1)
      [ "$n" = "6" ] && break
    done
    echo "   ${A}: the stack came back - walking it again" | tee -a "$LOG"
    node tools/prove_full_journeys.mjs --archetype "$A" --tier "$TIER" >> "$LOG" 2>&1
  fi
  RESULT=".tmp/full_journeys_${A}_tier${TIER}.json"
  if [ -f "$RESULT" ]; then
    python tools/bank_journey_walk.py "$RESULT" >> "$LOG" 2>&1
    tail -3 "$LOG" | sed 's/^/    /'
  fi
done
echo "drive complete $(date +%H:%M:%S)" | tee -a "$LOG"
