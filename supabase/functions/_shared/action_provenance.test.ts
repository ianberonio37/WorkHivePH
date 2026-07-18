// deno test _shared/action_provenance.test.ts
// CL10 action-faithfulness rail — regression contract. Run: deno test action_provenance.test.ts
import { assert, assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";
import { stripFalseActionClaims } from "./action_provenance.ts";

// ---- STRIP: fabricated COMPLETED system-write claims (the live-caught defect) ------------------
Deno.test("live-caught: 'Log entry added to CT-001 maintenance history' is stripped", () => {
  const r = stripFalseActionClaims("Acknowledged. Log entry added to CT-001 maintenance history.");
  assert(r.hit, "should strip the fabricated log-entry claim");
  assert(!/log entry added/i.test(r.clean), "clean must not claim a log entry was added");
  assert(/acknowledged/i.test(r.clean), "acknowledgement is preserved");
});

Deno.test("live-caught: 'Updated maintenance record for CT-001' header is stripped", () => {
  const r = stripFalseActionClaims("Updated maintenance record for CT-001: torque set to 137 Nm.");
  assert(r.hit);
  assert(!/updated maintenance record/i.test(r.clean));
});

Deno.test("first-person completed write with system target is stripped", () => {
  const r = stripFalseActionClaims("I've logged this to the maintenance history for you.");
  assert(r.hit);
  assert(!/i've logged/i.test(r.clean));
});

Deno.test("nominal passive 'the reminder was set' is stripped", () => {
  const r = stripFalseActionClaims("Done. The reminder was set for 48 hours from now.");
  assert(r.hit);
  assert(!/reminder was set/i.test(r.clean));
});

Deno.test("'added it to the logbook' is stripped", () => {
  const r = stripFalseActionClaims("I added it to the logbook and the CMMS.");
  assert(r.hit);
});

// ---- PRESERVE: legitimate recommendations, acknowledgements, and drafting offers ---------------
Deno.test("imperative advice 'Schedule a follow-up vibration check in 48h' is PRESERVED", () => {
  const r = stripFalseActionClaims("Schedule a follow-up vibration check in 48h to confirm installation.");
  assertEquals(r.hit, false);
  assert(/schedule a follow-up/i.test(r.clean));
});

Deno.test("imperative advice 'Notify the L1 technician' is PRESERVED", () => {
  const r = stripFalseActionClaims("Notify the L1 technician to verify torque with a calibrated wrench.");
  assertEquals(r.hit, false);
});

Deno.test("modal advice 'You should log this in the logbook' is PRESERVED", () => {
  const r = stripFalseActionClaims("You should log this in the logbook so it's on record.");
  assertEquals(r.hit, false);
});

Deno.test("drafting offer 'I can draft the purchase request' is PRESERVED", () => {
  const r = stripFalseActionClaims("I can draft the purchase request for you to send.");
  assertEquals(r.hit, false);
});

Deno.test("discourse marker 'I've added the following recommendations' is PRESERVED (no system target)", () => {
  const r = stripFalseActionClaims("I've added the following recommendations: check alignment, then re-torque.");
  assertEquals(r.hit, false);
});

Deno.test("plain grounded advice with a number is PRESERVED", () => {
  const r = stripFalseActionClaims("Your MTBF on PB-001 is 6.1 hours, which is below the class norm.");
  assertEquals(r.hit, false);
});

Deno.test("empty / no-claim answers are pass-through", () => {
  assertEquals(stripFalseActionClaims("").hit, false);
  assertEquals(stripFalseActionClaims("Acknowledged. No action needed beyond documentation.").hit, false);
});

// ---- Action-log LABEL fabrications (live-caught 2026-07-08 via direct ai-gateway invoke) --------
Deno.test("label: 'Logged: PB-002 pump bearing replaced' is stripped, sibling bullets kept", () => {
  const r = stripFalseActionClaims("**Action Items:**\n- Logged: PB-002 pump bearing replaced today, torque 142 Nm.\n- Assigned: Leandro to verify.\n- Note: stock low.");
  assert(r.hit);
  assert(!/logged: pb-002/i.test(r.clean), "the Logged: label fabrication is removed");
  assert(/assigned: leandro/i.test(r.clean) && /note: stock/i.test(r.clean), "sibling advice/notes kept");
});

Deno.test("label: 'Recorded: …' at sentence start is stripped, following advice kept", () => {
  const r = stripFalseActionClaims("Recorded: PB-003 bearing replaced today, torque 143 Nm. Assigned Leandro to verify within 24h. Note: stock low.");
  assert(r.hit);
  assert(!/recorded: pb-003/i.test(r.clean));
  assert(/assigned leandro/i.test(r.clean) && /note: stock/i.test(r.clean));
});

Deno.test("header: '… maintenance logged as follows:' is stripped, Details kept", () => {
  const r = stripFalseActionClaims("PB-001 pump maintenance logged as follows:\nDetails:\n- Task: Bearing replacement completed today.");
  assert(r.hit);
  assert(!/maintenance logged as follows/i.test(r.clean));
  assert(/task: bearing/i.test(r.clean));
});

Deno.test("grounded fact 'Your next PM is scheduled for Friday' is PRESERVED (not a fabrication)", () => {
  const r = stripFalseActionClaims("Your next PM is scheduled for Friday per your plan.");
  assertEquals(r.hit, false);
});

// ---- The full live-caught reply: fabrications gone, advice kept --------------------------------
Deno.test("full live reply: strips the two fabrications, keeps acknowledgement + both recommendations", () => {
  const live = "Acknowledged. Updated maintenance record for CT-001: Bearing replacement torque set to 137 Nm during today's overhaul. Log entry added to CT-001 maintenance history. Notify Leandro Marquez to verify torque with calibrated torque wrench. Schedule follow-up vibration check in 48h to confirm proper installation. No immediate action required beyond documentation.";
  const r = stripFalseActionClaims(live);
  assert(r.hit, "at least one fabrication stripped");
  assert(!/updated maintenance record/i.test(r.clean), "record-update fabrication removed");
  assert(!/log entry added/i.test(r.clean), "log-entry fabrication removed");
  assert(/notify leandro/i.test(r.clean), "the Notify recommendation is kept");
  assert(/schedule follow-up/i.test(r.clean), "the Schedule recommendation is kept");
  assert(/acknowledged/i.test(r.clean), "acknowledgement kept");
});
