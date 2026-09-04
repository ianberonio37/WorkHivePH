# Degradation Precedence — the game-day's chosen design (T200)

When the platform degrades under compound failure (multiple subsystems failing at once), it must shed
capability in a **deliberate order**, so the game-day (T200) asserts a *chosen* design rather than
whatever falls out. This is the sensible default for a maintenance CMMS whose job is keeping a plant
safe and its work recorded; adjust if the business decides otherwise.

**Precedence — preserved LONGEST (top) to shed FIRST (bottom):**

1. **Safety-critical alerts** — anomaly / incident / risk signals. A plant safety signal must survive
   almost everything; losing it silently is the worst failure. (lane: `cc_failure_injection` — a failed
   read renders a *failure*, never a false "all clear".)
2. **Active work capture** — a worker mid-job must be able to record it even offline; the write queues
   and survives. (lanes: `offline-queued`, and the queue survives a reload.)
3. **Read access, legibly degraded** — reads retry, and when they cannot resolve they refuse *out loud*
   (never a blank that reads as "nothing here"). (lanes: `auto-read-retry`, `cg_offline_views`.)
4. **Attachments / media** — media failures degrade *alone*; a storage outage never takes the parent
   write down with it. (lane: `media-fails-alone`.)
5. **Background sync / analytics / cosmetic** — embeddings, analytics compute, XP animations. Shed
   FIRST; none of it is load-bearing for a shift completing.

**North star:** under compound degradation, *the shift's work still completes* — a worker can record
what they did and a supervisor can still see safety signals — and on recovery the subsystems restore in
**reverse** order (safety first back to full, cosmetic last).

**How the game-day proves it:** the five degradation lanes above are each a registered prover; the
game-day is their UNION under simultaneous stress. `validate_game_day_capstone` holds that every lane
is present and green and that this precedence is declared, so "the program's proof" composes.
