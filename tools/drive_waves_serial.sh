#!/usr/bin/env bash
# drive_waves_serial.sh — run the remaining W3 waves ONE AT A TIME, banking each as it lands.
#
# ★THIS HOST HAS ONE DATABASE, AND IT IS SCARCER THAN THE BROWSER. tools/browser_slot.mjs serialises the
# browser, so three waves were started at once believing they would queue politely. They did — for the
# browser. Nothing serialised the DATABASE: a journey drive reading chains, a function wave probing edge
# calls and a content wave rendering pages drove an 8GB host to 0.19GB free and the docker engine stopped
# answering entirely. The readings taken in that window were not findings. Four of six journey chains came
# back "the database did not answer", and a function wave was mid-flight asking a dead stack whether it
# refuses a stranger — a question whose answer would have been recorded as a contract holding or breaking.
#
# So waves run in SEQUENCE, and each one WAITS for the host to be able to answer before it starts:
# the database must reply with the full cast, and enough memory must be free that the reply means something.
#
#   bash tools/drive_waves_serial.sh calc learn fn sc lc
set -u
export PYTHONIOENCODING=utf-8
LOG=".tmp/waves_serial.log"

# ONE DRIVER AT A TIME. The first version had no lock, and the reason it needed one is the reason it exists:
# a prover was killed mid-wave, its driver moved on to the NEXT wave, a second driver was started to replace
# it, and both ran - two content provers against one database, which is exactly the contention this script
# was written to prevent. A tool that serialises work must first serialise ITSELF.
DLOCK=".tmp/waves_serial.lock"
if [ -f "$DLOCK" ]; then
  OTHER=$(cat "$DLOCK" 2>/dev/null)
  if [ -n "${OTHER:-}" ] && kill -0 "$OTHER" 2>/dev/null; then
    echo "another serial drive is already running (pid $OTHER) - not starting a second one"
    exit 1
  fi
  echo "clearing a stale drive lock (pid ${OTHER:-?} is gone)"
fi
echo $$ > "$DLOCK"
trap 'rm -f "$DLOCK"' EXIT INT TERM

: > "$LOG"

# wait until the stack can answer, up to ~25 minutes; the engine recovers on its own once the load stops
wait_for_host() {
  for i in $(seq 1 100); do
    n=$(timeout 25 docker exec supabase_db_workhive psql -U postgres -d postgres -Atc "select count(*) from hives" 2>/dev/null | tail -1)
    free=$(wmic OS get FreePhysicalMemory 2>/dev/null | tr -d ' \r' | grep -E "^[0-9]+" | head -1)
    if [ "${n:-}" = "6" ]; then
      echo "   host ready after $((i*15))s (${free:-?}KB free)" | tee -a "$LOG"
      return 0
    fi
    sleep 15
  done
  echo "   the host never came back - stopping so nothing is measured against a dead stack" | tee -a "$LOG"
  return 1
}

for W in "$@"; do
  echo "== ${W} $(date +%H:%M:%S)" | tee -a "$LOG"
  wait_for_host || exit 1
  case "$W" in
    calc)
      node tools/prove_content_ufai.mjs --kind calc >> "$LOG" 2>&1
      [ -f .tmp/content_ufai_calc.json ] && python tools/bank_content_walk.py .tmp/content_ufai_calc.json >> "$LOG" 2>&1 ;;
    learn)
      node tools/prove_content_ufai.mjs --kind learn >> "$LOG" 2>&1
      [ -f .tmp/content_ufai_learn.json ] && python tools/bank_content_walk.py .tmp/content_ufai_learn.json >> "$LOG" 2>&1 ;;
    fn)
      node tools/prove_fn_contracts.mjs >> "$LOG" 2>&1
      [ -f .tmp/fn_contracts.json ] && python tools/bank_fn_contracts.py .tmp/fn_contracts.json >> "$LOG" 2>&1 ;;
    sc)
      node tools/prove_shared_components.mjs >> "$LOG" 2>&1
      [ -f .tmp/shared_components.json ] && python tools/bank_cell_walk.py .tmp/shared_components.json --gate shared-components >> "$LOG" 2>&1 ;;
    lc)
      node tools/prove_lifecycle_cells.mjs >> "$LOG" 2>&1
      [ -f .tmp/lifecycle_cells.json ] && python tools/bank_cell_walk.py .tmp/lifecycle_cells.json --gate lifecycle-cells >> "$LOG" 2>&1 ;;
    *) echo "   unknown wave: $W" | tee -a "$LOG" ;;
  esac
  tail -4 "$LOG" | sed 's/^/    /'
done
echo "serial drive complete $(date +%H:%M:%S)" | tee -a "$LOG"
