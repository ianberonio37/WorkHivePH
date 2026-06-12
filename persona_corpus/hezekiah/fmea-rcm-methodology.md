# FMEA and RCM — failure analysis methodology (technical reference)

*Paraphrased reference notes (license-clean). Standards cited for the reader to consult
the originals: IEC 60812 (FMEA), SAE J1739, SAE JA1011/JA1012 (RCM), MIL-STD-1629A.*

## FMEA — Failure Mode and Effects Analysis

FMEA is a structured, bottom-up method to identify how each component of a system can
fail, what the effects of each failure are, and how to prioritise action before failures
happen. The workflow:

1. **Break the system into functions and items** (asset → subsystem → component).
2. **List failure modes** for each item — the specific ways it can fail to perform its
   function (e.g. a bearing: seizure, excessive clearance, contamination, fatigue spall).
3. **Trace effects** — local effect, next-level effect, and end effect on the system.
4. **Identify causes** — the underlying mechanisms (misalignment, over-lubrication,
   ingress, fatigue).
5. **Score and rank with the RPN** — Risk Priority Number = Severity × Occurrence ×
   Detection, each rated 1–10. A high RPN flags where to act first. Modern practice
   (AIAG-VDA) replaces the single RPN with Action Priority (High/Medium/Low) bands.
6. **Define controls and actions** — detection controls (inspection, monitoring) and
   prevention controls (design change, PM task), then re-score.

FMEA feeds the PM program: every credible failure mode should map to a task that
detects or prevents it, or a conscious decision to run-to-failure.

## RCM — Reliability-Centered Maintenance

RCM decides the *right* maintenance strategy for each failure mode by answering the
seven SAE JA1011 questions: functions, functional failures, failure modes, failure
effects, failure consequences, proactive tasks, and default actions. The core logic:

- **Classify the consequence** of each failure mode: hidden, safety/environmental,
  operational, or non-operational. Consequence drives how hard you work to prevent it.
- **Choose a task by applicability and effectiveness**, in this preference order:
  on-condition (condition monitoring) → scheduled restoration → scheduled discard →
  failure-finding (for hidden failures) → run-to-failure (only when acceptable).
- **A safety or environmental failure mode** must have a task that reduces risk to a
  tolerable level; if none exists, the design must change. You may never "run to failure"
  a hazard.

RCM's discipline is that a PM task earns its place only if it is both *applicable* (it
can detect or prevent the mode) and *worth doing* (its cost is justified by the
consequence avoided). This is how you prune a bloated, calendar-driven PM list.

## Practical link

Run an FMEA to enumerate and rank failure modes; apply RCM logic to assign each ranked
mode the right task. The output is a defensible, consequence-driven maintenance program
rather than an inherited checklist.
