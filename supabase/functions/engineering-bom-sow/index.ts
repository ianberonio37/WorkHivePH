import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// ─── Groq LLM helper (OpenAI-compatible, free tier) ──────────────────────────

async function callGroq(prompt: string): Promise<string> {
  const GROQ_KEY = Deno.env.get("GROQ_API_KEY") || "";

  const res = await fetch("https://api.groq.com/openai/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${GROQ_KEY}`,
    },
    body: JSON.stringify({
      model: "llama-3.3-70b-versatile",
      messages: [{ role: "user", content: prompt }],
      temperature: 0.2,
      response_format: { type: "json_object" },
    }),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Groq API error ${res.status}: ${err}`);
  }

  const data = await res.json();
  return data?.choices?.[0]?.message?.content || "{}";
}

// ─── HVAC BOM + SOW Agent ─────────────────────────────────────────────────────

async function hvacBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project  = inputs.project_name  || "HVAC Project";
  const area     = inputs.floor_area    || "N/A";
  const totalKW  = results.recommended_kW  ?? results.q_design_kw ?? "N/A";
  const totalTR  = results.recommended_TR  ?? results.q_design_tr ?? "N/A";
  const nUnits   = results.recommended_units ?? Math.ceil(Number(totalKW) / 2.5);
  const unitKW   = results.ac_size_kw  ?? 2.5;
  const voltage  = inputs.voltage || "230V/1Ph/60Hz";
  const pipingM  = Number(nUnits) * 5;
  const wiringM  = Number(nUnits) * 7;

  const prompt = `You are a licensed Mechanical Engineer in the Philippines preparing official procurement and contracting documents for an HVAC split-type air-conditioning installation.

CALCULATION RESULT:
Project: ${project}
Floor Area: ${area} m²
Total Cooling Load: ${totalKW} kW (${totalTR} TR)
Recommended: ${nUnits} unit(s) × ${unitKW} kW split-type AC, R-410A, ${voltage}
Estimated piping run: ${pipingM} m total (≈5 m per unit)
Estimated wiring run: ${wiringM} m total (≈7 m per unit)

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1 — "bom_items": Standard Philippine HVAC contractor Bill of Materials.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items (use calculated quantities above):
1. Split-type Air Conditioning Unit, Indoor (wall-mounted) — qty: ${nUnits}
2. Outdoor Condensing Unit — qty: ${nUnits}
3. Refrigerant Piping Set (liquid + suction line, pre-insulated) — qty: ${pipingM} m
4. Pipe Insulation, closed-cell foam 13mm — qty: ${pipingM} m
5. Condensate Drain Line, PVC 3/4" — qty: ${pipingM} m
6. MCCB Circuit Breaker, 2-pole — qty: ${nUnits}
7. Electrical Wiring, THHN 3.5mm² Cu — qty: ${wiringM} m
8. Thermostat / Wired Remote Controller — qty: ${nUnits}
9. Outdoor Unit Mounting Bracket, heavy-duty galvanized — qty: ${nUnits} — checked: false (optional)
10. Refrigerant Charge, R-410A — qty: ${Number(nUnits) * 0.9} kg
11. Miscellaneous (anchors, cable ties, sealant, putty) — qty: 1 lot

Specifications must be specific: include kW capacity, voltage, refrigerant type, material grade, standard size. Match ${unitKW} kW per unit.

ARRAY 2 — "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope — checked: true
- "2.0" Applicable Standards and Codes — checked: true (list: PSME, ASHRAE, PEC 2017, DOLE OSH, manufacturer guidelines)
- "3.0" Materials — checked: true (reference BOM, state Philippine standards compliance)
- "4.1" Equipment Supply and Delivery — checked: true
- "4.2" Indoor Unit Installation — checked: true
- "4.3" Outdoor Unit Installation — checked: true
- "4.4" Refrigerant Piping Works — checked: true (include pressure test at 300 psi N2, 24-hour hold, evacuation, R-410A charge)
- "4.5" Electrical Connections — checked: true (reference PEC 2017, dedicated circuit per unit)
- "4.6" Condensate Drainage — checked: true
- "4.7" Thermal Insulation — checked: true
- "4.8" Testing and Commissioning — checked: true (verify ±10% of design capacity, measure supply air temp, submit commissioning report)
- "4.9" As-Built Documentation — checked: true
- "5.0" Inclusions — checked: false
- "6.0" Exclusions — checked: false (civil works, panel upgrade if required, duct fabrication)
- "7.0" Warranty — checked: false (1 year equipment per manufacturer, 1 year workmanship from acceptance)

Each content must be 3-5 sentences in professional Philippine engineering contractor style. Reference the specific equipment: ${nUnits} unit(s) of ${unitKW} kW split-type AC, R-410A refrigerant, for ${project}.

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Ventilation / ACH BOM + SOW Agent ───────────────────────────────────────

async function ventBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project    = inputs.project_name  || "Ventilation Project";
  const spaceType  = (results.inputs_used as Record<string, unknown>)?.space_label || inputs.room_function || "General Space";
  const ventType   = (results.inputs_used as Record<string, unknown>)?.vent_type   || inputs.vent_type    || "Supply and Exhaust";
  const floorArea  = inputs.floor_area    || "N/A";
  const persons    = inputs.persons       || 0;
  const reqACH     = results.required_ach || "N/A";
  const fanCMH     = results.recommended_fan_cmh || results.design_cmh || "N/A";
  const fanCFM     = results.recommended_fan_cfm || results.design_cfm || "N/A";
  const designCMH  = results.design_cmh   || fanCMH;
  const isExhaust  = String(ventType).toLowerCase().includes("exhaust");
  const isSupply   = String(ventType).toLowerCase().includes("supply");
  const isBoth     = isExhaust && isSupply;

  // Estimate quantities from floor area
  const area      = Number(floorArea) || 50;
  const ductM     = Math.round(area / 5);           // rough duct run
  const grilles   = Math.max(2, Math.round(area / 15)); // 1 grille per 15 m²
  const dampers   = Math.max(1, Math.round(area / 30));
  const nFans     = isBoth ? 2 : 1;

  const prompt = `You are a licensed Mechanical Engineer in the Philippines preparing official procurement and contracting documents for a ventilation system installation.

CALCULATION RESULT:
Project: ${project}
Space Type: ${spaceType}
Ventilation Type: ${ventType}
Floor Area: ${floorArea} m²
Occupancy: ${persons} persons
Required ACH: ${reqACH} ACH
Design Airflow: ${designCMH} m³/hr (${fanCFM} CFM)
Recommended Fan: ${fanCMH} m³/hr capacity
Estimated duct run: ${ductM} m (linear)
Estimated grille/diffuser count: ${grilles} pcs
Number of fans: ${nFans} (${isBoth ? 'supply fan + exhaust fan' : isExhaust ? 'exhaust fan only' : 'supply fan only'})

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1 — "bom_items": Standard Philippine mechanical contractor Bill of Materials for ventilation.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items (use calculated quantities above):
1. Inline/Centrifugal Fan (${isExhaust || isBoth ? 'Exhaust' : 'Supply'}) — qty: 1 unit — specify ${fanCMH} m³/hr, static pressure, voltage
2. ${isBoth ? 'Supply Fan — qty: 1 unit — specify capacity and motor spec' : 'Flexible Duct Connector — qty: 2 pcs — specify size to match fan outlet'}
3. Galvanized Steel Ductwork (Supply or Exhaust, as applicable) — qty: ${ductM} m — specify gauge, 1.0mm G.I. standard
4. Duct Insulation, pre-formed glass wool 25mm — qty: ${ductM} m — for supply air ducts only; skip if exhaust only
5. Supply Air Diffuser / Exhaust Grille — qty: ${grilles} pcs — specify size (e.g. 300×150mm or 600×600mm), aluminum
6. Volume Control Damper (manual) — qty: ${dampers} pcs — specify size, galvanized steel, opposed blade
7. Fire Damper (fusible link, 72°C) — qty: ${dampers} pcs — specify UL-listed, matching duct size — checked: false (optional per fire code)
8. Motorized Fresh Air Damper — qty: 1 pc — specify 24VAC actuator, normally closed — checked: ${isBoth ? 'true' : 'false'}
9. Electrical Wiring, THHN 2.0mm² Cu, 3-wire — qty: ${nFans * 10} m — specify color code per PEC 2017
10. On/Off Switch with pilot light — qty: ${nFans} pc — specify 15A, surface-mounted
11. Flexible Metal Duct, 150mm dia — qty: 4 m — for terminal connections
12. Miscellaneous (duct sealant, hangers, fasteners, damper clips) — qty: 1 lot

Specifications must be specific: include airflow in m³/hr, voltage (230V/1Ph or 460V/3Ph), material grade, duct gauge, grille size. Match ${fanCMH} m³/hr capacity.

ARRAY 2 — "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope — checked: true
- "2.0" Applicable Standards and Codes — checked: true (list: ASHRAE 62.1, PSME Code, PEC 2017, DOLE OSH Standards for workplace ventilation, National Building Code PD 1096, NFPA 90A for duct construction)
- "3.0" Materials — checked: true (reference BOM, state Philippine standards compliance, G.I. duct SMACNA standards)
- "4.1" Equipment Supply and Delivery — checked: true
- "4.2" Fan and Motor Installation — checked: true (specify vibration isolation mounts, flexible connectors, direction of rotation test)
- "4.3" Ductwork Fabrication and Installation — checked: true (specify SMACNA standards, gauge, sealing with UL-listed sealant, 25 Pa pressure test)
- "4.4" Grilles, Diffusers, and Dampers — checked: true (specify balancing procedure, airflow measurement at each terminal)
- "4.5" Electrical Connections — checked: true (reference PEC 2017, motor starter or direct-on-line starter, overload protection)
- "4.6" Fire Damper Installation — checked: false (where penetrating fire-rated partitions per BFP IRR)
- "4.7" Testing, Balancing, and Commissioning — checked: true (measure actual ACH, compare to design ${reqACH} ACH, submit TAB report, ASHRAE 111 method)
- "4.8" As-Built Documentation — checked: true
- "5.0" Inclusions — checked: false
- "6.0" Exclusions — checked: false (civil/building works, mechanical rooms, structural supports beyond scope)
- "7.0" Warranty — checked: false (1 year equipment per manufacturer, 1 year workmanship from acceptance)

Each content must be 3-5 sentences in professional Philippine engineering contractor style. Reference the specific system: ${ventType} ventilation for ${spaceType}, ${fanCMH} m³/hr design airflow, serving ${project}.

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Pump Sizing (TDH) BOM + SOW Agent ───────────────────────────────────────

async function pumpBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project     = inputs.project_name  || "Pump System Project";
  const fluidType   = inputs.fluid_type    || "Water";
  const flowLPM     = results.flow_lpm     || inputs.flow_rate   || "N/A";
  const flowM3hr    = results.flow_m3hr    || "N/A";
  const tdh         = results.TDH          || "N/A";
  const recHP       = results.recommended_hp || "N/A";
  const recKW       = results.recommended_kw || "N/A";
  const pipeDiaMM   = results.pipe_dia_mm  || (results.inputs_used as Record<string, unknown>)?.pipe_dia_mm || "N/A";
  const pipeMat     = (results.inputs_used as Record<string, unknown>)?.pipe_material || inputs.pipe_material || "PVC";
  const pipeLen     = inputs.pipe_length   || "N/A";
  const staticHead  = inputs.static_head   || "N/A";
  const pumpEff     = (results.inputs_used as Record<string, unknown>)?.pump_efficiency || inputs.pump_efficiency || 70;
  const motorEff    = (results.inputs_used as Record<string, unknown>)?.motor_efficiency || inputs.motor_efficiency || 90;
  const velocity    = results.pipe_velocity || "N/A";
  const npshA       = results.npsh_available || "N/A";

  const prompt = `You are a licensed Mechanical Engineer in the Philippines preparing official procurement and contracting documents for a pump system installation.

CALCULATION RESULT:
Project: ${project}
Fluid: ${fluidType}
Design Flow Rate: ${flowLPM} L/min (${flowM3hr} m³/hr)
Total Dynamic Head (TDH): ${tdh} m
Pipe Diameter: ${pipeDiaMM} mm (${pipeMat})
Pipe Length: ${pipeLen} m (total equivalent)
Static Head: ${staticHead} m
Pipe Velocity: ${velocity} m/s
NPSH Available: ${npshA} m
Pump Efficiency: ${pumpEff}%  |  Motor Efficiency: ${motorEff}%
Recommended Motor: ${recHP} hp (${recKW} kW)

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1 — "bom_items": Standard Philippine mechanical contractor Bill of Materials for pump system.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Centrifugal Pump — qty: 1 unit — specify ${recHP} hp, TDH ${tdh} m, ${flowM3hr} m³/hr, ${fluidType}, back-pull-out type, close-coupled or base-mounted
2. Electric Motor — qty: 1 unit — specify ${recHP} hp (${recKW} kW), TEFC, IE2/IE3 efficiency, 460V/3Ph/60Hz (or 230V if <1.5 kW)
3. Base Plate / Pump Base — qty: 1 set — specify epoxy-grouted, fabricated steel, drip rim
4. Gate Valve, flanged — qty: 2 pcs — specify PN16, ${pipeDiaMM} mm, cast iron or bronze, suction and discharge isolation
5. Check Valve (swing type), flanged — qty: 1 pc — specify PN16, ${pipeDiaMM} mm, cast iron, discharge side
6. Flexible Coupling / Vibration Isolator — qty: 2 pcs — specify flanged rubber expansion joint, ${pipeDiaMM} mm, rated PN16
7. Pressure Gauge with siphon — qty: 2 pcs — specify 0–${Math.ceil(Number(tdh) / 10) * 10 + 30} m (0–${Math.round((Number(tdh) + 30) * 0.0981)} bar), 100mm dial, glycerin-filled, suction and discharge
8. Pipe, ${pipeMat} — qty: ${pipeLen} m — specify ${pipeDiaMM} mm nominal dia, PN10 or PN16, including fittings
9. Pipe Fittings (elbows, tees, reducers) — qty: 1 lot — specify ${pipeDiaMM} mm, ${pipeMat}, match pipe class
10. Pipe Supports and Hangers — qty: 1 lot — specify adjustable clevis hanger, galvanized, spacing per PSME
11. Motor Control Center (MCC) / DOL Starter — qty: 1 unit — specify direct-on-line starter (DOL) if ≤7.5 hp or star-delta if >7.5 hp, MCCB, overload relay, ${recHP} hp rated
12. Electrical Wiring, THHN Cu — qty: ${Math.round(Number(pipeLen) * 1.2 + 10)} m — specify size per PEC 2017 motor branch circuit, THHN insulation
13. Pipe Insulation (for chilled water or hot water) — qty: ${pipeLen} m — specify closed-cell foam or pre-formed, 25mm thickness — checked: false (apply if chilled or hot water)
14. Miscellaneous (bolts, gaskets, pipe sealant, grout) — qty: 1 lot

Specifications must be specific: include HP, kW, flow, TDH, pipe size and class, valve PN rating. Match ${recHP} hp and ${pipeDiaMM} mm throughout.

ARRAY 2 — "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope — checked: true
- "2.0" Applicable Standards and Codes — checked: true (list: PSME Code, Hydraulic Institute Standards ANSI/HI, PEC 2017, Philippine Plumbing Code, DOLE OSH, manufacturer installation guidelines)
- "3.0" Materials — checked: true (reference BOM, all materials PN16 rated, PSME-compliant)
- "4.1" Equipment Supply and Delivery — checked: true (factory test certificates, performance curves to be submitted)
- "4.2" Pump and Motor Installation — checked: true (specify epoxy grouting, shaft alignment within 0.05mm TIR, vibration isolation mounts, direction of rotation check before coupling)
- "4.3" Piping Works — checked: true (specify ${pipeMat} pipe at ${pipeDiaMM} mm, support spacing, isolation valve locations, drain/vent points)
- "4.4" Valves and Instrumentation — checked: true (gate valves suction and discharge, swing check valve, pressure gauges both sides)
- "4.5" Electrical and Motor Starter — checked: true (reference PEC 2017, DOL or star-delta starter, overload relay set to motor FLA, dedicated circuit and MCCB)
- "4.6" Hydrostatic Pressure Test — checked: true (test piping at 1.5× working pressure for minimum 30 minutes, no leaks, document results)
- "4.7" Testing and Commissioning — checked: true (verify flow ${flowM3hr} m³/hr and TDH ${tdh} m at design point, measure motor current against nameplate, submit commissioning report)
- "4.8" As-Built Documentation — checked: true
- "5.0" Inclusions — checked: false
- "6.0" Exclusions — checked: false (civil / structural works, foundation design, building permits, electrical panel upgrade if required)
- "7.0" Warranty — checked: false (1 year equipment per manufacturer, 1 year workmanship from acceptance)

Each content must be 3-5 sentences in professional Philippine engineering contractor style. Reference the specific system: ${recHP} hp centrifugal pump, ${flowM3hr} m³/hr at TDH ${tdh} m, ${fluidType}, for ${project}.

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Pipe Sizing BOM + SOW Agent ─────────────────────────────────────────────

async function pipeSizingBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project     = inputs.project_name    || "Pipe System Project";
  const serviceType = (results.inputs_used as Record<string, unknown>)?.service_type || inputs.service_type || "General Water";
  const pipeMat     = (results.inputs_used as Record<string, unknown>)?.pipe_material || inputs.pipe_material || "PVC";
  const pipeDiaMM   = results.recommended_dia_mm || "N/A";
  const pipeLen     = inputs.pipe_length     || "N/A";
  const equivLen    = (results.inputs_used as Record<string, unknown>)?.equiv_length || "N/A";
  const flowLPM     = results.flow_lpm       || inputs.flow_rate || "N/A";
  const flowM3hr    = results.flow_m3hr      || "N/A";
  const velocity    = results.recommended_velocity || "N/A";
  const hfPerM      = results.hf_per_m       || "N/A";
  const hfTotal     = results.hf_total       || "N/A";
  const pressTotal  = results.press_drop_total || "N/A";
  const flowRegime  = results.flow_regime    || "Turbulent";
  const fittingsPct = (results.inputs_used as Record<string, unknown>)?.fittings_pct || inputs.fittings_allowance || 20;

  // Estimate accessory quantities from pipe length
  const pLen       = Number(pipeLen) || 30;
  const nIsolation = Math.max(2, Math.round(pLen / 15));  // isolation valves every ~15 m
  const nElbows    = Math.max(4, Math.round(pLen / 5));   // elbows every ~5 m
  const nSupports  = Math.max(3, Math.round(pLen / 2));   // supports every 2 m
  const nPressGauge= 2;
  const nDrain     = Math.max(1, Math.round(pLen / 20));

  const prompt = `You are a licensed Mechanical Engineer in the Philippines preparing official procurement and contracting documents for a piping system installation.

CALCULATION RESULT:
Project: ${project}
Service Type: ${serviceType}
Pipe Material: ${pipeMat}
Recommended Pipe Diameter: ${pipeDiaMM} mm (nominal)
Pipe Length: ${pipeLen} m (measured) / ${equivLen} m (equivalent, including ${fittingsPct}% fittings allowance)
Design Flow Rate: ${flowLPM} L/min (${flowM3hr} m³/hr)
Design Velocity: ${velocity} m/s
Friction Loss: ${hfPerM} m/m (total: ${hfTotal} m / ${pressTotal} kPa)
Flow Regime: ${flowRegime}

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1 — "bom_items": Standard Philippine mechanical contractor Bill of Materials for piping works.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Pipe, ${pipeMat} — qty: ${pLen} m — specify ${pipeDiaMM} mm nominal dia, include applicable pressure class (PN10/PN16/Schedule 40 depending on material), in 6-m lengths
2. Pipe Fittings — Elbows 90° — qty: ${nElbows} pcs — specify ${pipeDiaMM} mm, ${pipeMat}, same pressure class as pipe
3. Pipe Fittings — Tees (equal) — qty: ${Math.max(2, Math.round(nElbows / 3))} pcs — specify ${pipeDiaMM} mm, ${pipeMat}
4. Pipe Fittings — Reducers / Couplings — qty: ${Math.max(2, Math.round(nElbows / 4))} pcs — specify ${pipeDiaMM} mm, ${pipeMat}
5. Isolation Valve (gate or ball type) — qty: ${nIsolation} pcs — specify ${pipeDiaMM} mm, PN16, bronze or cast iron, sectional isolation
6. Check Valve (swing type) — qty: ${nDrain} pc — specify ${pipeDiaMM} mm, PN16, at pump discharge or riser base — checked: false (if no pump in scope)
7. Drain Valve / Blow-off Valve — qty: ${nDrain} pcs — specify 20 mm, bronze ball valve with hose bib
8. Pressure Gauge with siphon — qty: ${nPressGauge} pcs — specify 0–${Math.ceil((Number(hfTotal) + 30) * 0.1) * 100} kPa, 100mm dial, glycerin-filled
9. Pipe Supports and Hangers — qty: ${nSupports} sets — specify adjustable clevis hanger, galvanized, PSME-compliant spacing for ${pipeMat} at ${pipeDiaMM} mm
10. Pipe Insulation (if chilled water or hot water service) — qty: ${pLen} m — specify pre-formed glass wool or closed-cell foam 25mm, with aluminum jacket — checked: false (apply if chilled or hot water)
11. Flanges and Gaskets — qty: 1 lot — specify ${pipeDiaMM} mm, PN16, flat face or raised face, with spiral wound or rubber gaskets, for equipment connections
12. Welding Consumables / Jointing Materials — qty: 1 lot — specify per pipe material: solvent cement for PVC, Teflon tape + pipe compound for threaded, argon + filler rod for SS/Cu
13. Miscellaneous (anchors, pipe labels, supports, testing plugs) — qty: 1 lot

Specifications must be specific: include pipe diameter, pressure class, material grade, and Philippine standards compliance (PSME, PNS). All sizes must match ${pipeDiaMM} mm throughout.

ARRAY 2 — "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope — checked: true
- "2.0" Applicable Standards and Codes — checked: true (list: PSME Code, Philippine Plumbing Code (based on UPC/IPC), ASTM material standards for ${pipeMat}, Hydraulic Institute Standards, PEC 2017 for any electrical components, DOLE OSH)
- "3.0" Materials — checked: true (reference BOM, state ${pipeMat} pipe at ${pipeDiaMM} mm nominal, specify ASTM or PNS standard, all valves PN16 minimum)
- "4.1" Equipment and Material Delivery — checked: true (include inspection on delivery, material test certificates for ${pipeMat} pipe and fittings)
- "4.2" Pipe Fabrication and Installation — checked: true (specify cutting, jointing method for ${pipeMat}, support spacing per PSME, slope requirements for drainage if applicable, alignment and grading)
- "4.3" Valve and Instrument Installation — checked: true (specify orientation, isolation valve placement, pressure gauge siphon requirement, access provision for maintenance)
- "4.4" Pipe Supports and Anchors — checked: true (specify hanger type, PSME maximum spacing for ${pipeDiaMM} mm ${pipeMat} pipe, seismic provision if applicable)
- "4.5" Insulation Works — checked: false (if chilled water or hot water: closed-cell foam or glass wool 25mm, aluminum jacket, all joints sealed with vapor barrier tape)
- "4.6" Pressure Testing — checked: true (hydrostatic test at 1.5× working pressure, minimum 30 minutes, zero pressure drop, document and submit test records)
- "4.7" Flushing and Cleaning — checked: true (flush at minimum 1.5× design velocity before commissioning, water quality test for potable or process systems, chemical cleaning for chilled water per ASHRAE guideline)
- "4.8" Commissioning and Handover — checked: true (verify flow ${flowM3hr} m³/hr and velocity ${velocity} m/s at design point, submit as-built drawings and commissioning report)
- "4.9" As-Built Documentation — checked: true
- "5.0" Inclusions — checked: false
- "6.0" Exclusions — checked: false (civil / structural works, equipment foundations, electrical connections unless specified, building permits)
- "7.0" Warranty — checked: false (1 year workmanship from acceptance; material warranty per manufacturer)

Each content must be 3-5 sentences in professional Philippine engineering contractor style. Reference the specific system: ${pipeDiaMM} mm ${pipeMat} pipe, ${serviceType}, ${flowM3hr} m³/hr design flow, for ${project}.

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Compressed Air BOM + SOW Agent ──────────────────────────────────────────

async function compressedAirBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project       = inputs.project_name         || "Compressed Air System Project";
  const recHP         = results.recommended_hp       || "N/A";
  const recCFM        = results.recommended_cfm      || "N/A";
  const designCFM     = results.design_cfm           || "N/A";
  const designLPS     = results.design_lps           || "N/A";
  const designM3min   = results.design_m3min         || "N/A";
  const recReceiverL  = results.recommended_receiver_L || "N/A";
  const recPipeMM     = results.recommended_pipe_mm  || "N/A";
  const workingBar    = (results.inputs_used as Record<string, unknown>)?.working_pressure || inputs.working_pressure || 7;
  const pipeLen       = inputs.pipe_length           || "N/A";
  const leakagePct    = (results.inputs_used as Record<string, unknown>)?.leakage_pct || inputs.leakage_allowance || 10;

  // Quantity estimates
  const pLen        = Number(pipeLen) || 30;
  const nDropLegs   = Math.max(2, Math.round(pLen / 10)); // drop legs every ~10 m
  const nIsolation  = Math.max(2, Math.round(pLen / 15));
  const nSupports   = Math.max(4, Math.round(pLen / 2));
  const nFil        = 1; // filter-regulator-lubricator sets

  const prompt = `You are a licensed Mechanical Engineer in the Philippines preparing official procurement and contracting documents for a compressed air system installation.

CALCULATION RESULT:
Project: ${project}
Working Pressure: ${workingBar} bar(g)
Design FAD Required: ${designCFM} CFM (${designLPS} L/s / ${designM3min} m³/min)
Recommended Compressor: ${recHP} hp / ${recCFM} CFM FAD
Recommended Air Receiver: ${recReceiverL} litres
Recommended Distribution Pipe: ${recPipeMM} mm
Distribution Pipe Length: ${pipeLen} m
Leakage Allowance: ${leakagePct}%

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1 — "bom_items": Standard Philippine mechanical contractor Bill of Materials for compressed air system.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Air Compressor, Rotary Screw — qty: 1 unit — specify ${recHP} hp, ${recCFM} CFM FAD, ${workingBar} bar working pressure, air-cooled, direct drive, CAGI-certified
2. Air Receiver Tank — qty: 1 unit — specify ${recReceiverL} litres, working pressure ${workingBar} bar(g), ASME-coded or PNS pressure vessel, complete with safety relief valve, drain valve, pressure gauge, and sight glass
3. Air Dryer (Refrigerated Type) — qty: 1 unit — specify ${recCFM} CFM capacity, pressure dew point -3°C to +3°C, ISO 8573-1 Class 4 moisture, matched to compressor FAD
4. Pre-filter (Coalescing), 1 micron — qty: 1 unit — specify ${recCFM} CFM, ISO 8573-1 Class 3 oil, at compressor outlet
5. After-filter (Particulate), 0.01 micron — qty: 1 unit — specify ${recCFM} CFM, ISO 8573-1 Class 1, downstream of dryer
6. Distribution Pipe, Black Steel Schedule 40 — qty: ${pLen} m — specify ${recPipeMM} mm nominal bore, threaded or flanged connections, in 6-m lengths
7. Pipe Fittings (elbows, tees, unions) — qty: 1 lot — specify ${recPipeMM} mm, black steel, Class 150, PSME-compliant
8. Drop Leg Assembly with Auto Drain — qty: ${nDropLegs} sets — specify ${recPipeMM} mm tee, 25 mm drop leg, ball valve, automatic condensate drain
9. Ball Valve, full bore — qty: ${nIsolation} pcs — specify ${recPipeMM} mm, PN16, chrome-plated brass or cast iron, for sectional isolation
10. Safety Relief Valve (distribution header) — qty: 1 pc — specify set pressure ${Math.ceil(Number(workingBar) * 1.1 * 10) / 10} bar(g), ASME-certified, at header inlet
11. Pressure Gauge (distribution) — qty: ${Math.max(2, nDropLegs)} pcs — specify 0–${Math.ceil(Number(workingBar) * 2)} bar, 100mm dial, glycerin-filled, at key points
12. Filter-Regulator-Lubricator (FRL) Unit — qty: ${nFil} set — specify ${recPipeMM} mm port, 0–${workingBar} bar range, at point-of-use headers — checked: false (supply if process requires lubrication)
13. Pipe Supports and Hangers — qty: ${nSupports} sets — specify galvanized clevis hanger, PSME spacing, slope 1:200 toward drop legs
14. Condensate Drain System — qty: 1 lot — specify automatic electronic timer drain at compressor, receiver, dryer, and each filter; PVC condensate collection line to drain
15. Miscellaneous (Teflon tape, pipe compound, hose connectors, labels) — qty: 1 lot

Specifications must be specific: include HP, CFM, bar pressure, pipe size and schedule, filter micron rating, ISO 8573-1 class. All rated for ${workingBar} bar(g) minimum.

ARRAY 2 — "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope — checked: true
- "2.0" Applicable Standards and Codes — checked: true (list: PSME Code, ISO 8573-1 Compressed Air Purity, ISO 1217 Compressor Performance, CAGI Standards, ASME Section VIII pressure vessels, PEC 2017, DOLE OSH Compressed Gas Safety)
- "3.0" Materials — checked: true (reference BOM, black steel Schedule 40 for distribution, all equipment rated ${workingBar} bar(g) minimum, ASME pressure vessel code for receiver)
- "4.1" Equipment Supply and Delivery — checked: true (CAGI performance data sheets, pressure vessel certificates, factory test reports to be submitted prior to delivery)
- "4.2" Compressor and Receiver Installation — checked: true (specify concrete pad, vibration isolation mounts, levelling, minimum 1-metre clearance for maintenance access, compressor room ventilation)
- "4.3" Air Treatment Equipment — checked: true (dryer inlet/outlet isolation valves, bypass line for dryer maintenance, filter differential pressure gauges, auto-drain connections)
- "4.4" Distribution Piping Works — checked: true (black steel Schedule 40 at ${recPipeMM} mm, slope 1:200 toward drop legs for condensate drainage, all joints threaded or flanged with PTFE, pressure test before insulation)
- "4.5" Drop Legs and Point-of-Use Connections — checked: true (drop legs at low points and at each use point, automatic condensate drains at all low points, FRL sets at process connections if required)
- "4.6" Electrical Connections and Control — checked: true (dedicated circuit per PEC 2017, motor starter or VFD for compressor, pressure switch for automatic start/stop, overload protection)
- "4.7" Pressure Testing — checked: true (pneumatic leak test at 1.1× working pressure with soapy water, all joints checked, zero leakage acceptable, document and submit records)
- "4.8" System Commissioning — checked: true (verify compressor FAD ${recCFM} CFM at ${workingBar} bar, check dryer dew point, verify auto-start/stop, measure system leakage — must be < ${leakagePct}% of FAD, submit commissioning report)
- "4.9" As-Built Documentation — checked: true
- "5.0" Inclusions — checked: false
- "6.0" Exclusions — checked: false (civil works, compressor room construction, utility connections unless specified, piping beyond drop leg outlets)
- "7.0" Warranty — checked: false (1 year equipment per manufacturer, 1 year workmanship from acceptance; compressor extended warranty if available)

Each content must be 3-5 sentences in professional Philippine engineering contractor style. Reference the specific system: ${recHP} hp rotary screw compressor, ${recCFM} CFM at ${workingBar} bar, ${recReceiverL}L receiver, for ${project}.

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Water Supply Pipe Sizing BOM + SOW Agent ────────────────────────────────

async function waterSupplyBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project      = inputs.project_name    || "Water Supply Project";
  const supplyType   = inputs.supply_type     || "Cold and Hot";
  const pipeMat      = (results.inputs_used as Record<string, unknown>)?.pipe_material || inputs.pipe_material || "PVC";
  const pipeDiaMM    = results.recommended_dia_mm || "N/A";
  const pipeLen      = inputs.pipe_length     || "N/A";
  const equivLen     = results.equiv_length   || "N/A";
  const totalWFU     = results.total_wfu      || "N/A";
  const peakLPS      = results.peak_lps       || "N/A";
  const peakLPM      = results.peak_lpm       || "N/A";
  const velocity     = results.pipe_velocity  || "N/A";
  const hfTotal      = results.hf_total_m     || "N/A";
  const pressAvail   = results.pressure_available || "N/A";
  const minPress     = results.min_pressure   || inputs.min_pressure || 70;
  const supplyPress  = inputs.supply_pressure || 350;
  const fittingsPct  = (results.inputs_used as Record<string, unknown>)?.fittings_pct || inputs.fittings_allowance || 20;
  const hasHot       = String(supplyType).includes("Hot");

  const pLen         = Number(pipeLen) || 30;
  const nIsolation   = Math.max(2, Math.round(pLen / 15));
  const nSupports    = Math.max(4, Math.round(pLen / 2));
  const nFixtures    = (() => {
    const fx = inputs.fixtures as Array<{ quantity: number }> || [];
    return fx.reduce((s, f) => s + (Number(f.quantity) || 1), 0);
  })();
  const nAngle       = Math.max(nFixtures, 4);

  const prompt = `You are a licensed Mechanical/Sanitary Engineer in the Philippines preparing official procurement and contracting documents for a domestic water supply piping system installation.

CALCULATION RESULT:
Project: ${project}
Supply Type: ${supplyType}
Pipe Material: ${pipeMat}
Recommended Pipe Diameter: ${pipeDiaMM} mm (nominal, main line)
Pipe Length: ${pipeLen} m (measured) / ${equivLen} m (equivalent, incl. ${fittingsPct}% fittings)
Total Fixture Units (WFU): ${totalWFU} WFU (Hunter's Method, Philippine Plumbing Code)
Peak Design Flow: ${peakLPS} L/s (${peakLPM} L/min)
Pipe Velocity: ${velocity} m/s
Friction Head Loss: ${hfTotal} m total
Supply Pressure: ${supplyPress} kPa available at meter / Minimum residual: ${minPress} kPa
Residual Pressure at Furthest Fixture: ${pressAvail} kPa

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1 — "bom_items": Standard Philippine sanitary/plumbing contractor Bill of Materials for domestic water supply system.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Water Supply Pipe, ${pipeMat} — qty: ${pLen} m — specify ${pipeDiaMM} mm nominal dia, PN10 pressure class (or Schedule 40 if CPVC), NSF/PNS 65 potable water rated, in 6-m lengths
2. Pipe Fittings — Elbows 90° — qty: ${Math.max(4, Math.round(pLen / 5))} pcs — specify ${pipeDiaMM} mm, ${pipeMat}, same pressure class, potable water grade
3. Pipe Fittings — Tees (equal and reducing) — qty: ${Math.max(2, Math.round(pLen / 8))} pcs — specify ${pipeDiaMM} mm, ${pipeMat}, per Philippine Plumbing Code
4. Pipe Fittings — Reducers / Couplings — qty: ${Math.max(2, Math.round(pLen / 10))} pcs — specify ${pipeDiaMM} mm, ${pipeMat}
5. Gate Valve / Ball Valve (isolation), full bore — qty: ${nIsolation} pcs — specify ${pipeDiaMM} mm, PN16, bronze, for sectional isolation and at each riser base
6. Angle Valve (fixture stop valve) — qty: ${nAngle} pcs — specify 15 mm (1/2 in), chrome-plated brass, 1 per fixture connection
7. Pressure Reducing Valve (PRV) — qty: 1 pc — specify inlet: ${supplyPress} kPa, outlet: ${Math.min(Number(supplyPress) - 50, 250)} kPa, bronze body, spring-loaded, per Philippine Plumbing Code — checked: ${Number(supplyPress) > 300 ? 'true' : 'false'} (required if supply pressure > 300 kPa)
8. Water Meter — qty: 1 pc — specify ${pipeDiaMM} mm, multi-jet type, MWSS/LWUA approved, flanged or threaded connections
9. Backflow Preventer / Check Valve — qty: 1 pc — specify ${pipeDiaMM} mm, double-check assembly type, PN16, at meter outlet per Philippine Plumbing Code
10. ${hasHot ? 'Hot Water Supply Pipe, CPVC or Cu' : 'Cold Water Branch Pipe, PVC'} — qty: ${Math.round(pLen * 0.5)} m — specify 20 mm or 15 mm as required for branch lines to fixtures
11. Pipe Insulation (for hot water lines) — qty: ${hasHot ? Math.round(pLen * 0.5) : 0} m — specify closed-cell foam 13mm, aluminum foil jacket, for all hot water pipes — checked: ${hasHot ? 'true' : 'false'}
12. Pipe Supports and Hangers — qty: ${nSupports} sets — specify galvanized pipe clamp or clevis hanger, spacing per Philippine Plumbing Code (${pipeMat} at ${pipeDiaMM} mm)
13. Pressure Gauge (at PRV outlet and riser base) — qty: 2 pcs — specify 0–700 kPa, 100mm dial, glycerin-filled
14. Pipe Labelling and Colour Banding — qty: 1 lot — specify per Philippine Plumbing Code: cold water = blue, hot water = red/orange
15. Miscellaneous (Teflon tape, pipe cement for PVC, hangers, anchors, cleanouts) — qty: 1 lot

Specifications must reference PNS/NSF potable water standards, ${pipeDiaMM} mm throughout main line. All valves and fittings rated for potable water contact.

ARRAY 2 — "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope — checked: true
- "2.0" Applicable Standards and Codes — checked: true (list: Philippine Plumbing Code (PPC) — based on UPC/IPC, NSF/PNS 65 potable water piping, PSME Code, LWUA/MWSS connection standards, PEC 2017 for any electrical components, DOLE OSH)
- "3.0" Materials — checked: true (reference BOM, all pipes and fittings potable water rated NSF/PNS 65, ${pipeMat} at ${pipeDiaMM} mm nominal, all valves bronze or NSF-approved material)
- "4.1" Equipment and Material Delivery — checked: true (material test certificates and NSF/PNS compliance certificates to be submitted; all materials inspected on delivery before installation)
- "4.2" Pipe Installation — checked: true (specify jointing method for ${pipeMat}, support spacing per Philippine Plumbing Code, 25mm clearance from structural elements, grading toward drain points, sleeve through walls)
- "4.3" Valve and Meter Installation — checked: true (isolation valves at each riser base and branch takeoff, water meter accessible for reading, PRV accessible for adjustment)
- "4.4" Pipe Supports and Sleeves — checked: true (hanger spacing per PPC, all pipe penetrations through slabs/walls with galvanized sleeves sealed with fire-rated sealant at fire-rated assemblies)
- "4.5" Hot Water Piping Works — checked: ${hasHot ? 'true' : 'false'} (CPVC or copper for hot water lines, all hot water pipes insulated with closed-cell foam 13mm, slope toward drain for system draining)
- "4.6" Pressure Testing — checked: true (hydrostatic test at 2× working pressure (${Math.round(Number(supplyPress) * 2)} kPa) or minimum 1,000 kPa for 30 minutes, all joints and valves checked for leaks, document and submit test records)
- "4.7" Disinfection and Flushing — checked: true (flush system at 1.5× design velocity, disinfect with chlorine solution 50 ppm for 24 hours per Philippine Plumbing Code, flush until residual chlorine < 0.5 ppm before connection to fixtures)
- "4.8" Commissioning and Handover — checked: true (verify flow at furthest fixture, measure residual pressure (must be ≥ ${minPress} kPa), check all fixture stop valves, submit commissioning report and water quality test results)
- "4.9" As-Built Documentation — checked: true
- "5.0" Inclusions — checked: false
- "6.0" Exclusions — checked: false (civil / structural works, plumbing fixtures and fittings beyond stop valves, MWSS/LWUA service connection fees, water treatment equipment)
- "7.0" Warranty — checked: false (1 year workmanship from acceptance; material warranty per manufacturer; leaks discovered within warranty period repaired at Contractor's cost)

Each content must be 3-5 sentences in professional Philippine engineering contractor style. Reference: ${pipeDiaMM} mm ${pipeMat} pipe, ${supplyType} supply, ${peakLPS} L/s peak flow (${totalWFU} WFU), for ${project}.

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Hot Water Demand BOM + SOW Agent ────────────────────────────────────────

async function hotWaterBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name          || "Hot Water System Project";
  const tSupply        = inputs.supply_temp            || 28;
  const tHot           = inputs.hot_temp               || 60;
  const deltaT         = results.delta_T               || (Number(tHot) - Number(tSupply));
  const totalDailyL    = results.total_daily_L         || "N/A";
  const peakHourL      = results.peak_hour_L           || "N/A";
  const recStorageL    = results.recommended_storage_L || "N/A";
  const recHeaterKW    = results.recommended_heater_kW || "N/A";
  const recoveryLPH    = results.recovery_rate_lph     || "N/A";
  const recoveryHrs    = inputs.recovery_hours         || 2;
  const heatKWh        = results.heat_energy_kWh       || "N/A";
  const pipeLossPct    = inputs.pipe_loss_pct          || 10;

  // Estimate pipe quantities from storage size and likely building scale
  const storageL       = Number(recStorageL) || 200;
  const pipeLen        = storageL > 500 ? 40 : storageL > 200 ? 25 : 15; // rough distribution run
  const nFixtures      = (() => {
    const us = inputs.uses as Array<{ quantity: number }> || [];
    return Math.max(4, us.reduce((s, u) => s + (Number(u.quantity) || 1), 0));
  })();
  const nIsolation     = Math.max(2, Math.round(pipeLen / 15));
  const nSupports      = Math.max(4, Math.round(pipeLen / 2));
  const isElectric     = Number(recHeaterKW) <= 36;  // >36 kW typically gas/heat pump
  const heaterVoltage  = Number(recHeaterKW) > 6 ? "400V/3Ph/60Hz" : "230V/1Ph/60Hz";

  const prompt = `You are a licensed Mechanical/Sanitary Engineer in the Philippines preparing official procurement and contracting documents for a domestic hot water system installation.

CALCULATION RESULT:
Project: ${project}
Cold Water Inlet Temperature: ${tSupply}°C (Philippine tropical default)
Hot Water Supply Temperature: ${tHot}°C
Temperature Rise (ΔT): ${deltaT}°C
Total Daily Hot Water Demand: ${totalDailyL} L/day (incl. ${pipeLossPct}% pipe heat loss)
Peak Hour Demand: ${peakHourL} L/hr
Recommended Storage Tank: ${recStorageL} litres
Recommended Heater Capacity: ${recHeaterKW} kW
Recovery Rate: ${recoveryLPH} L/hr
Recovery Time: ${recoveryHrs} hours
Daily Heat Energy: ${heatKWh} kWh/day
Estimated Hot Water Pipe Run: ${pipeLen} m

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1 — "bom_items": Standard Philippine plumbing contractor Bill of Materials for hot water system.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Hot Water Storage Tank — qty: 1 unit — specify ${recStorageL} litres, ${tHot}°C rated, glass-lined or stainless steel inner tank, polyurethane foam insulation, working pressure 600 kPa, complete with anode rod, temperature-pressure relief valve, drain valve, and inspection port
2. Water Heater / Heating Element — qty: 1 unit — specify ${recHeaterKW} kW${isElectric ? `, ${heaterVoltage}, immersion-type electric heating element, thermostat-controlled, CHED/BPS approved` : `, gas-fired or heat pump type, rated at ${recHeaterKW} kW input, thermostat with high-limit safety cutout`}, recovery rate ${recoveryLPH} L/hr at ΔT ${deltaT}°C
3. Temperature-Pressure Relief Valve (T&P Valve) — qty: 1 pc — specify set at 700 kPa / 99°C, ANSI/ASME rated, 3/4 in discharge, with full-size drain to floor drain — checked: true (mandatory per Philippine Plumbing Code)
4. Expansion Tank (thermal expansion) — qty: 1 unit — specify pre-charged diaphragm type, sized for ${recStorageL}L system, 350–700 kPa operating range, ASME-rated — checked: true (required in closed systems)
5. Mixing Valve / Thermostatic Mixing Valve (TMV) — qty: 1 unit — specify ASSE 1017 listed, set at ${Math.min(Number(tHot) - 5, 55)}°C delivery temperature, to prevent scalding at fixtures, ${Math.max(nFixtures * 2, 15)} L/min capacity
6. Hot Water Supply Pipe, CPVC — qty: ${pipeLen} m — specify 20 mm or 25 mm nominal, ASTM D2846, rated 82°C / 600 kPa, in 6-m lengths
7. Cold Water Feed Pipe, PVC PN10 — qty: ${Math.round(pipeLen * 0.4)} m — specify 20 mm or 25 mm nominal, potable water rated NSF/PNS 65, for heater inlet
8. Pipe Insulation, pre-formed closed-cell foam — qty: ${pipeLen} m — specify 19mm wall thickness, aluminum foil jacket, for all hot water supply pipes to minimise heat loss
9. Isolation Ball Valve (hot water rated) — qty: ${nIsolation + 2} pcs — specify 20–25 mm, full bore, PTFE-seated, rated 120°C / PN16, at heater inlet/outlet and branch takeoffs
10. Check Valve (anti-siphon) — qty: 1 pc — specify 20–25 mm, spring-loaded, PN16, at cold water inlet to heater
11. Angle Valve (fixture stop valve, chrome) — qty: ${nFixtures} pcs — specify 15 mm (1/2 in), chrome-plated brass, 1 per hot water fixture connection
12. Pipe Supports and Hangers — qty: ${nSupports} sets — specify galvanized pipe clamp, CPVC-compatible cushion liner, spacing per Philippine Plumbing Code (max 1.2 m for CPVC)
13. ${isElectric ? 'Electrical Wiring, THHN Cu' : 'Gas Supply Piping, Schedule 40 Black Steel'} — qty: ${isElectric ? Math.round(pipeLen * 1.5) : Math.round(pipeLen * 0.5)} m — specify ${isElectric ? `size per PEC 2017 for ${recHeaterKW} kW load at ${heaterVoltage}, dedicated circuit, GFCI-protected` : `25 mm nominal, threaded fittings, leak tested at 1.5x working pressure, per PSME gas code`}
14. Floor Drain (near heater and T&P relief discharge) — qty: 1 pc — specify 100 mm dia, chrome strainer, for T&P valve discharge line termination
15. Miscellaneous (Teflon tape, pipe cement, hangers, labels, access panel) — qty: 1 lot — specify hot water pipe labels in red/orange per Philippine Plumbing Code

ARRAY 2 — "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope — checked: true
- "2.0" Applicable Standards and Codes — checked: true (list: Philippine Plumbing Code (PPC), ASHRAE HVAC Applications Handbook Chapter 50 (Service Water Heating), NSF/PNS 65 potable water materials, ANSI/ASME for relief valves, ASSE 1017 thermostatic mixing valve, PEC 2017 for electrical connections, DOLE OSH, BPS/CHED equipment approval)
- "3.0" Materials — checked: true (glass-lined or SS storage tank rated ${tHot}°C, CPVC hot water pipe ASTM D2846, all valves PN16 and 120°C rated, insulation 19mm closed-cell foam with foil jacket)
- "4.1" Equipment Supply and Delivery — checked: true (submit heater performance data sheet, BPS/CHED approval certificate, tank warranty card, T&P valve certification before delivery)
- "4.2" Heater and Tank Installation — checked: true (specify floor-mounted or wall-mounted per equipment type, vibration isolation pad, minimum 600 mm clearance on service side, drip pan under tank connected to floor drain)
- "4.3" Hot Water Piping Works — checked: true (CPVC pipe at 20–25 mm nominal, all joints solvent-cemented per ASTM D2846, slope toward drain point, all pipes insulated 19mm closed-cell foam, pipe labelled red/orange per PPC)
- "4.4" Safety Devices — checked: true (T&P relief valve mandatory at heater, full-size 3/4 in discharge pipe to floor drain, no valves on discharge line, thermostatic mixing valve at distribution header set at ${Math.min(Number(tHot) - 5, 55)}°C, expansion tank on cold water feed in closed system)
- "4.5" Electrical Connections — checked: ${isElectric ? 'true' : 'false'} (dedicated circuit per PEC 2017, GFCI protection, disconnect within sight of heater, wire sized for ${recHeaterKW} kW at ${heaterVoltage})
- "4.6" Pressure Testing — checked: true (hydrostatic test at 2× working pressure (1,200 kPa) for 30 minutes, all joints and connections leak-free, document and submit test records before insulation)
- "4.7" Disinfection and Commissioning — checked: true (flush system, set thermostat to ${tHot}°C, verify recovery rate ${recoveryLPH} L/hr within ${recoveryHrs} hours, check T&P valve operation, verify TMV outlet temperature, submit commissioning report)
- "4.8" As-Built Documentation — checked: true
- "5.0" Inclusions — checked: false
- "6.0" Exclusions — checked: false (civil / structural works, plumbing fixtures beyond stop valves, electrical panel upgrade if required, gas meter or utility connection fees)
- "7.0" Warranty — checked: false (tank: 5-year manufacturer warranty on inner tank, 1-year on components; 1 year workmanship from acceptance)

Each content must be 3-5 sentences in professional Philippine engineering contractor style. Reference: ${recHeaterKW} kW heater, ${recStorageL}L storage, ${tHot}°C supply at ${recoveryLPH} L/hr recovery, for ${project}.

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Drainage Pipe Sizing BOM + SOW Agent ────────────────────────────────────

async function drainageBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project      = inputs.project_name       || "Drainage System Project";
  const systemType   = results.system_type       || inputs.system_type  || "Horizontal Branch";
  const pipeMat      = results.pipe_material     || inputs.pipe_material || "PVC";
  const pipeDiaMM    = results.recommended_dia_mm || "N/A";
  const totalDFU     = results.total_dfu         || "N/A";
  const slopePct     = results.slope_pct         || "2";
  const slopeMmPerM  = results.slope_mm_per_m    || "20";
  const velocity     = results.design_velocity   || "N/A";
  const capacityLS   = results.capacity_q_ls     || "N/A";
  const isStack      = String(systemType).includes("Stack");

  const nFixtures    = (() => {
    const fx = inputs.fixtures as Array<{ quantity: number }> || [];
    return Math.max(4, fx.reduce((s, f) => s + (Number(f.quantity) || 1), 0));
  })();
  const pipeLen      = isStack ? 20 : 30;  // rough estimate: stacks ~20m vertical, branches ~30m
  const nCleanouts   = Math.max(2, Math.round(pipeLen / 15));
  const nSupports    = Math.max(4, Math.round(pipeLen / 2));
  const nBranches    = Math.max(2, Math.round(nFixtures / 3));
  const nVents       = Math.max(2, Math.round(nFixtures / 4));

  const prompt = `You are a licensed Sanitary/Mechanical Engineer in the Philippines preparing official procurement and contracting documents for a building drainage and sanitary piping system installation.

CALCULATION RESULT:
Project: ${project}
System Type: ${systemType}
Pipe Material: ${pipeMat}
Recommended Pipe Diameter: ${pipeDiaMM} mm (nominal)
Total Drainage Fixture Units (DFU): ${totalDFU} DFU (Philippine Plumbing Code Table)
${isStack ? 'Drain Stack — vertical riser' : `Pipe Slope: ${slopePct}% (${slopeMmPerM} mm/m fall)`}
Design Flow Capacity: ${capacityLS} L/s (Manning's equation, ${isStack ? 'full-bore' : 'half-full'})
Design Velocity: ${velocity} m/s (minimum 0.6 m/s for self-cleansing)

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1 — "bom_items": Standard Philippine sanitary contractor Bill of Materials for drainage and sanitary piping system.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Drainage Pipe, ${pipeMat} — qty: ${pipeLen} m — specify ${pipeDiaMM} mm nominal dia, ASTM D3034 (PVC sewer) or PNS equivalent, in 3-m or 6-m lengths, for ${systemType}
2. Drainage Fittings — 45° Wye / Long-sweep 90° Elbows — qty: ${Math.max(4, Math.round(pipeLen / 5))} pcs — specify ${pipeDiaMM} mm, ${pipeMat}, sanitary drainage type (no T-fittings on horizontal drains), per Philippine Plumbing Code
3. Drainage Fittings — Sanitary Tee / Combination Wye — qty: ${nBranches} pcs — specify ${pipeDiaMM} mm, ${pipeMat}, for branch connections
4. Pipe Reducers / Couplings — qty: ${Math.max(2, Math.round(pipeLen / 10))} pcs — specify ${pipeDiaMM} mm, ${pipeMat}
5. Cleanout Plugs with Access Frame — qty: ${nCleanouts} sets — specify ${pipeDiaMM} mm, ${pipeMat}, at every change of direction, at base of each stack, and every 15 m of horizontal run per Philippine Plumbing Code
6. Floor Drain with P-Trap — qty: ${Math.max(2, Math.round(nFixtures / 4))} pcs — specify 100 mm or 150 mm dia, chrome ABS or cast iron strainer, integral P-trap, deep-seal 76 mm minimum water seal
7. P-Trap for Fixtures — qty: ${nFixtures} pcs — specify 32–50 mm dia as required per fixture, PVC, 76 mm minimum water seal, one per fixture without integral trap
8. Vent Pipe, ${pipeMat} — qty: ${Math.round(pipeLen * 0.6)} m — specify 50 mm or 75 mm nominal, ${pipeMat}, individual vents to each fixture or loop vent per Philippine Plumbing Code
9. Vent Fittings — 45° Elbows, Tees — qty: ${nVents * 2} pcs — specify 50–75 mm, ${pipeMat}, for vent stack connections
10. Stack Base Fitting (sanitary tee with 45° inlet) — qty: ${isStack ? Math.max(1, Math.round(nFixtures / 10)) : 0} pc — specify ${pipeDiaMM} mm, for drain stack base to building drain — checked: ${isStack ? 'true' : 'false'}
11. Pipe Hangers and Supports — qty: ${nSupports} sets — specify perforated metal strap or clevis hanger, galvanized, spacing per Philippine Plumbing Code (max 1.2 m for PVC, 3 m for cast iron)
12. Pipe Sleeves through Slabs/Walls — qty: ${Math.max(4, nFixtures)} pcs — specify 25 mm oversize galvanized steel sleeve with fire-rated annular sealant at fire-rated assemblies
13. Roof Vent Flashing / Vent Terminal — qty: ${Math.max(1, Math.round(nVents / 2))} pc — specify lead or PVC flashing, for vent stack termination 150 mm minimum above roof, with bird screen
14. Grease Trap (if kitchen/canteen drainage) — qty: 1 unit — specify flow-rated to match kitchen fixture DFU, pre-cast concrete or prefab HDPE, with access covers and basket strainer — checked: false (include if scope covers kitchen/canteen drainage)
15. Miscellaneous (solvent cement, pipe primer, anchors, pipe labels) — qty: 1 lot — specify per ${pipeMat} jointing requirements; drainage pipes labelled per Philippine Plumbing Code

ARRAY 2 — "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope — checked: true
- "2.0" Applicable Standards and Codes — checked: true (list: Philippine Plumbing Code (PPC) — based on UPC/IPC, ASTM D3034 for PVC sewer pipe, PSME Code, National Building Code of the Philippines PD 1096, DOLE OSH Standards, DOH requirements for sanitary works)
- "3.0" Materials — checked: true (${pipeMat} pipe ASTM D3034 or PNS equivalent at ${pipeDiaMM} mm, all fittings sanitary drainage type — no sharp-turn tees on horizontal runs, all traps minimum 76 mm water seal)
- "4.1" Material Delivery and Inspection — checked: true (pipe and fittings inspected on delivery, ASTM/PNS compliance markings verified, damaged pipe rejected and replaced)
- "4.2" Pipe Installation — checked: true (specify jointing method for ${pipeMat} — solvent cement per ASTM D2564, pipe slope at ${slopePct}% (${slopeMmPerM} mm/m), all horizontal runs sloped continuously toward outlet, no back-grading, support at max 1.2 m spacing)
- "4.3" Trap and Cleanout Installation — checked: true (one trap per fixture, 76 mm minimum water seal, cleanouts at every direction change and stack base, accessible and within 600 mm of finished floor or wall per PPC, accessible cleanout cover flush with finished surface)
- "4.4" Vent System Installation — checked: true (individual or loop vents per PPC, vent stack terminated 150 mm minimum above roof and 300 mm from any window or opening, no vent connection within 300 mm below flood level rim of fixture)
- "4.5" Drain Stack and Building Drain" — checked: ${isStack ? 'true' : 'false'} (drain stack plumb within 1:100, supported at each floor with riser clamp, base fitting at stack foot, stack extends as vent above highest branch)
- "4.6" Pipe Supports and Sleeves — checked: true (PVC hangers every 1.2 m, sleeves at all slab and wall penetrations, fire-rated annular sealant at fire-rated assemblies, no pipe resting on structural elements without proper saddle support)
- "4.7" Water Test (Air or Water Tightness Test) — checked: true (water test: fill system to flood-level rim of highest fixture and hold 15 minutes, zero leaks, OR air test at 35 kPa for 15 minutes, document and submit test records)
- "4.8" Commissioning and Handover — checked: true (flush all lines, verify trap water seals, verify cleanout accessibility, check slope with spirit level at representative locations, submit as-built drawings)
- "4.9" As-Built Documentation — checked: true
- "5.0" Inclusions — checked: false
- "6.0" Exclusions — checked: false (civil / structural works including trenching for underground drainage, sewage treatment plant, septic tank unless specified, building permits and sanitary engineer PRC fees)
- "7.0" Warranty — checked: false (1 year workmanship from acceptance; leaks or blockages within warranty period remedied at Contractor's cost)

Each content must be 3-5 sentences in professional Philippine engineering contractor style. Reference: ${pipeDiaMM} mm ${pipeMat} ${systemType} drainage, ${totalDFU} DFU, ${isStack ? 'vertical stack' : `slope ${slopePct}%`}, for ${project}.

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Septic Tank Sizing BOM + SOW Agent ──────────────────────────────────────

async function septicBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project     = inputs.project_name   || "Septic Tank Project";
  const occType     = results.occupancy_type || inputs.occupancy_type || "Residential";
  const occupants   = results.occupants      || inputs.occupants      || "N/A";
  const designVolL  = results.design_volume_L  ?? "N/A";
  const designVolM3 = results.design_volume_m3 ?? "N/A";
  const widthM      = results.tank_width_m     ?? "N/A";
  const lengthM     = results.tank_length_m    ?? "N/A";
  const totalDepthM = results.total_depth_m    ?? "N/A";
  const compartments= results.compartments     ?? inputs.compartments ?? 2;
  const desludgeYrs = results.desludge_years   ?? inputs.desludge_years ?? 3;
  const comp1L      = results.comp1_L          ?? "N/A";
  const comp2L      = results.comp2_L          ?? "N/A";
  const comp1Lm     = results.comp1_L_m        ?? "N/A";
  const comp2Lm     = results.comp2_L_m        ?? "N/A";
  const dailyFlowL  = results.daily_flow_L     ?? "N/A";

  const prompt = `You are a Philippine sanitary engineering expert. Generate a professional BOM and SOW for a SEPTIC TANK construction project.

PROJECT: ${project}
OCCUPANCY TYPE: ${occType}
OCCUPANTS: ${occupants} persons
DAILY WASTEWATER FLOW: ${dailyFlowL} L/day
DESIGN VOLUME: ${designVolL} L (${designVolM3} m³)
TANK DIMENSIONS: ${lengthM} m L × ${widthM} m W × ${totalDepthM} m total depth (incl. 300mm freeboard)
COMPARTMENTS: ${compartments} (Compartment 1: ${comp1L}L / ${comp1Lm}; Compartment 2: ${comp2L}L / ${comp2Lm})
DESLUDGING INTERVAL: ${desludgeYrs} years
STANDARDS: Philippine Plumbing Code (PPC), DOH Sanitation Code (P.D. 856), DENR DAO 2016-08, DPWH Blue Book

Generate a JSON object with:
1. "bom_items": array of 16 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Reinforced concrete works (formwork, rebars 10mm dia, concrete CHB 150mm hollow blocks alternative), Tank excavation (add 0.5m working space each side), waterproofing membrane (crystalline or epoxy), inlet tee (100mm uPVC sanitary tee with 150mm submerged drop), outlet tee (100mm uPVC sanitary tee with 150mm submerged drop), baffles/dividing wall with transfer port, inspection covers (precast RC or HDPE 600mm dia), vent pipe (75mm uPVC, min 2m above grade), inlet pipe from building (100mm uPVC), distribution box or leachfield inspection box (if leachfield required), gravel/crushed rock (leachfield bed), perforated drain pipe 100mm for leachfield, backfill and compaction, bioactivator/seeding compound (for startup), desludging access port/sump, warning sign/marker post
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (PPC occupancy method, P.D. 856), Tank Construction (RC or CHB, watertight), Inlet/Outlet/Baffle/Vent Configuration (PPC-compliant), Leachfield or Soakpit (DENR DAO 2016-08 effluent disposal), Testing and Commissioning (water tightness test — fill to overflow and hold 24 hours, zero visible leakage), Desludging and Maintenance Schedule (every ${desludgeYrs} years by licensed operator), Regulatory Compliance (DENR, LGU sanitary permit, DOH)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical Load Estimation BOM + SOW Agent ───────────────────────────────

async function loadEstBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project       = inputs.project_name        || "Electrical Project";
  const phaseConfig   = results.phase_config        || inputs.phase_config   || "3-Phase 4-Wire (400V)";
  const voltage       = results.voltage             || 400;
  const connKVA       = results.total_connected_kva ?? "N/A";
  const demandKVA     = results.total_demand_kva    ?? "N/A";
  const demandKW      = results.total_demand_kw     ?? "N/A";
  const computedA     = results.computed_ampacity   ?? "N/A";
  const spareA        = results.ampacity_with_spare ?? "N/A";
  const breakerA      = results.recommended_breaker_A ?? "N/A";
  const breakdown     = results.load_breakdown as Array<{ load_type: string; qty: number; watts_each: number; demand_va: number }> || [];
  const loadSummary   = breakdown.slice(0, 12).map(l =>
    `${l.load_type} x${l.qty} @ ${l.watts_each}W (${Math.round(l.demand_va / 1000 * 100) / 100} kVA demand)`
  ).join("; ");

  const prompt = `You are a Philippine electrical engineering expert (PEC 2017). Generate a professional BOM and SOW for an ELECTRICAL LOAD ESTIMATION and distribution board installation project.

PROJECT: ${project}
PHASE CONFIGURATION: ${phaseConfig} — ${voltage}V
TOTAL CONNECTED LOAD: ${connKVA} kVA
TOTAL DEMAND LOAD: ${demandKVA} kVA (${demandKW} kW)
COMPUTED AMPACITY: ${computedA} A
WITH 25% SPARE CAPACITY: ${spareA} A
RECOMMENDED MAIN BREAKER: ${breakerA} A
LOAD BREAKDOWN SUMMARY: ${loadSummary}
STANDARDS: PEC 2017 (Philippine Electrical Code), PEC Article 2.10 / 2.20, DOE/ERC regulations, DOLE OSH Electrical Safety, NEC parallel reference

Generate a JSON object with:
1. "bom_items": array of 16 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Main distribution board/panelboard (NEMA 1 surface/flush-mount, number of poles sized to load count), main MCCB/ACB circuit breaker (${breakerA}A, interrupt capacity ≥ 10 kA), phase bus bars (copper, properly rated), neutral/ground bus bars, equipment grounding conductor (EGC), individual branch circuit breakers (MCB, sized per load group — qty derived from load breakdown), THHN/THWN copper conductors (main feeder, sized for ${spareA}A), conduit (EMT or RSC, properly sized), load schedule nameplate (laminated or engraved), energy meter (kWh, class 1.0, utility-grade), surge protective device (SPD, Type 2, properly rated), cable lugs and terminal connectors, conduit fittings and accessories, panel enclosure padlock, warning labels (PEC-compliant arc flash / voltage warning), wire markers and cable ties
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (PEC 2017 Art. 2.10/2.20, demand factor method, 25% spare), Distribution Board Installation (mounting, clearances, labeling), Main and Branch Circuit Breaker Installation (sizing, discrimination/coordination, interrupt rating), Wiring and Conduit Works (conductor sizing, conduit fill, color coding per PEC), Grounding and Bonding System (EGC, ground rod, bonding), Testing and Commissioning (insulation resistance test ≥ 1 MΩ at 500V DC, continuity test, load test at 80% capacity, thermal scanning), Regulatory Compliance and Handover (PEC 2017, ERC/DOE, DOLE OSH, as-built load schedule submission)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical Voltage Drop BOM + SOW Agent ─────────────────────────────────

async function voltageDropBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project       = inputs.project_name     || "Electrical Project";
  const circuitType   = results.circuit_type     || inputs.circuit_type   || "Branch Circuit";
  const phase         = results.phase            || inputs.phase          || "Single-phase";
  const voltage       = results.voltage          || inputs.voltage        || 230;
  const current       = results.current          || inputs.current        || "N/A";
  const wireLength    = results.wire_length      || inputs.wire_length    || "N/A";
  const conductorMM2  = results.conductor_mm2    || inputs.conductor_mm2  || "N/A";
  const conductorMat  = results.conductor_mat    || inputs.conductor_mat  || "Copper";
  const vdPct         = results.vd_pct           ?? "N/A";
  const vdVolts       = results.vd_volts         ?? "N/A";
  const vdLimit       = results.vd_limit         ?? 3;
  const pass          = results.pass             ?? false;
  const maxLengthM    = results.max_length_m     ?? "N/A";
  const passStr       = pass ? "PASS" : "FAIL — conductor size increase required";

  // Find next larger passing conductor from size_comparison if failing
  const comparison = results.size_comparison as Array<{ size_mm2: number; vd_pct: number; pass: boolean }> || [];
  const nextPassSize = comparison.find(s => s.pass && s.size_mm2 > Number(conductorMM2));
  const recommendedMM2 = pass ? conductorMM2 : (nextPassSize?.size_mm2 ?? conductorMM2);

  const prompt = `You are a Philippine electrical engineering expert (PEC 2017). Generate a professional BOM and SOW for a VOLTAGE DROP COMPLIANCE wiring project.

PROJECT: ${project}
CIRCUIT TYPE: ${circuitType}
PHASE: ${phase} — ${voltage}V
DESIGN CURRENT: ${current} A
CIRCUIT LENGTH: ${wireLength} m (one-way)
SELECTED CONDUCTOR: ${conductorMM2} mm² ${conductorMat} THHN/THWN
VOLTAGE DROP RESULT: ${vdVolts}V (${vdPct}%) — ${passStr}
VOLTAGE DROP LIMIT: ${vdLimit}%
MAXIMUM ALLOWABLE LENGTH @ selected size: ${maxLengthM} m
RECOMMENDED CONDUCTOR SIZE (PEC-compliant): ${recommendedMM2} mm² ${conductorMat}
STANDARDS: PEC 2017 Article 2.10.19 / 2.20, Philippine Electrical Code, DOLE OSH

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Phase conductor (${recommendedMM2} mm² ${conductorMat} THHN/THWN, rated for ${voltage}V, length ${wireLength}m + 10% allowance for terminations), neutral conductor (same size as phase for single-phase; 50% of phase for three-phase balanced), equipment grounding conductor (EGC, green/green-yellow, sized per PEC Table 2.50.95), conduit (EMT for indoors, RSC for exposed/outdoor, sized per PEC conduit fill), conduit fittings and couplings, pull boxes (if circuit exceeds 30m or has more than 4 bends), circuit breaker (sized for design current with 125% for continuous loads), cable tray or cable support clips (if surface-mounted), wire markers/circuit labels (origin panel, circuit number, load description), terminal lugs (for terminations at both ends), junction box with cover (rated for conductor count), conduit strap/saddle anchors (every 1.5m on exposed conduit), wire pulling lubricant (for conduit runs over 15m), cable ties
2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (PEC 2017 Art. 2.10.19, voltage drop ≤ ${vdLimit}% = ${Number(vdLimit)/100 * Number(voltage)} V max, conductor selection criteria), Conductor and Conduit Installation (pulling, bending radius, fill ratio per PEC, no sharp bends), Termination and Splicing (compression lugs, no taped splices in conduit — junction box only), Grounding and Continuity (EGC continuity, bonding at all metal conduit terminations), Testing and Verification (insulation resistance test ≥ 1 MΩ at 500V DC, continuity test, voltage drop field measurement under load — confirm ≤ ${vdLimit}%), Regulatory Compliance (PEC 2017, Electrical Permit, DOLE OSH, qualified licensed master electrician)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical Wire Sizing BOM + SOW Agent ───────────────────────────────────

async function wireSizingBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project       = inputs.project_name           || "Electrical Project";
  const loadType      = results.load_type              || inputs.load_type      || "General Load";
  const phase         = results.phase                  || inputs.phase          || "Single-phase";
  const voltage       = results.voltage                || inputs.voltage        || 230;
  const powerW        = results.power_w                || inputs.power_w        || "N/A";
  const pf            = results.power_factor           || inputs.power_factor   || 0.85;
  const loadCurrentA  = results.load_current           ?? "N/A";
  const demandMult    = results.demand_multiplier      ?? 1.0;
  const designCurrentA= results.design_current         ?? "N/A";
  const ambientTemp   = results.ambient_temp           || inputs.ambient_temp   || 30;
  const conduitFill   = results.conduit_fill           || inputs.conduit_fill   || "1-3";
  const tempFactor    = results.temp_factor            ?? "N/A";
  const fillFactor    = results.fill_factor            ?? "N/A";
  const recSizeMM2    = results.recommended_size_mm2   ?? "N/A";
  const recAmpacity   = results.recommended_ampacity   ?? "N/A";
  const recBreakerA   = results.recommended_breaker_A  ?? "N/A";
  const isMotor       = String(loadType).toLowerCase().includes("motor");

  const prompt = `You are a Philippine electrical engineering expert (PEC 2017). Generate a professional BOM and SOW for a WIRE SIZING and circuit installation project.

PROJECT: ${project}
LOAD TYPE: ${loadType}
PHASE: ${phase} — ${voltage}V
LOAD POWER: ${powerW} W @ PF ${pf}
LOAD CURRENT: ${loadCurrentA} A
DEMAND MULTIPLIER: ${demandMult}x (${isMotor ? "motor/continuous load — PEC 125% rule" : "standard load"})
DESIGN CURRENT: ${designCurrentA} A
AMBIENT TEMPERATURE: ${ambientTemp}°C (correction factor: ${tempFactor})
CONDUIT FILL: ${conduitFill} conductors (fill factor: ${fillFactor})
RECOMMENDED CONDUCTOR SIZE: ${recSizeMM2} mm² Copper THHN/THWN
CORRECTED AMPACITY: ${recAmpacity} A
RECOMMENDED BREAKER: ${recBreakerA} A
STANDARDS: PEC 2017 Table 3.10.1, PEC Article 2.10 / 2.30, DOLE OSH Electrical Safety

Generate a JSON object with:
1. "bom_items": array of 15 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Phase conductor (${recSizeMM2} mm² Copper THHN/THWN 75°C, ${voltage}V rated), neutral conductor (same size as phase for single-phase; may be reduced for balanced 3-phase), equipment grounding conductor (EGC, green/green-yellow, sized per PEC Table 2.50.95 based on breaker ${recBreakerA}A), circuit breaker (${recBreakerA}A, interrupt capacity ≥ available fault current${isMotor ? ', thermal-magnetic or motor circuit protector' : ''}), conduit (EMT for concealed/indoor, RSC for exposed/outdoor — sized per PEC conduit fill table for ${recSizeMM2} mm² conductors), conduit fittings, locknuts, and bushings, pull boxes or junction boxes (at every 30m or 4 bends), wire markers and circuit labels (origin panel, circuit no., load description), terminal compression lugs (for all terminations — no bare wire twist connections), cable ties and conduit saddle/strap anchors (every 1.5m on exposed runs), panel knockout seal/reducer (if conduit enters existing panelboard), wire pulling lubricant, flexible conduit and connector (last 600mm to motor — if motor load), warning labels (voltage level, circuit identification), spare conduit cap/plugs (for unused knockouts)
2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (PEC 2017 Table 3.10.1 ampacity with ${tempFactor} temperature correction and ${fillFactor} conduit fill correction, ${demandMult}x demand multiplier per PEC${isMotor ? ' Art. 2.30 motor branch circuit rules' : ' Art. 2.10 branch circuit rules'}), Conductor and Conduit Installation (no conductor smaller than minimum branch circuit size, bending radius ≥ 6× OD, maximum conduit fill per PEC, support intervals), Termination Works (compression lugs at all terminations, no splices inside conduit — use junction box, tighten to manufacturer torque spec), ${isMotor ? 'Motor Branch Circuit Requirements (locked-rotor current withstand, overload protection sizing, flexible conduit to motor terminal box),' : 'Circuit Protection (breaker sizing, coordination with upstream protective device,)'} Testing and Commissioning (insulation resistance ≥ 1 MΩ at 500V DC megger, continuity check on EGC, polarity verification, breaker trip test), Regulatory Compliance (PEC 2017, Electrical Permit, DOLE OSH, licensed master electrician, as-built drawings)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical Short Circuit BOM + SOW Agent ────────────────────────────────

async function shortCircuitBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project       = inputs.project_name       || "Electrical Project";
  const xfmrKVA       = inputs.xfmr_kva           ?? "N/A";
  const zPct          = inputs.z_pct              ?? "N/A";
  const voltageLLV    = inputs.voltage_ll          ?? 400;
  const cableMM2      = inputs.cable_mm2           ?? "N/A";
  const cableLenM     = inputs.cable_len_m         ?? "N/A";
  const breakerIC     = inputs.breaker_ic_kA       ?? "N/A";
  const IscKA         = results.Isc_kA             ?? "N/A";
  const IpeakKA       = results.Ipeak_kA           ?? "N/A";
  const icCheck       = results.ic_check           ?? "N/A";
  const icMargin      = results.ic_margin          ?? "N/A";
  const icMinRec      = results.ic_min_recommended ?? "N/A";
  const ZtotalOhm     = results.Z_total_ohm        ?? "N/A";
  const icFail        = String(icCheck) === "FAIL";

  const prompt = `You are a Philippine electrical engineering expert (PEC 2017). Generate a professional BOM and SOW for a SHORT CIRCUIT ANALYSIS and breaker interrupting capacity compliance project.

PROJECT: ${project}
TRANSFORMER: ${xfmrKVA} kVA, Z = ${zPct}%, ${voltageLLV}V line-to-line
CABLE TO PANEL: ${cableMM2} mm² × ${cableLenM} m
TOTAL IMPEDANCE: ${ZtotalOhm} Ω
3-PHASE FAULT CURRENT (Isc): ${IscKA} kA symmetrical
ASYMMETRICAL PEAK (Ipeak): ${IpeakKA} kA
INSTALLED BREAKER IC: ${breakerIC} kA — ${icCheck}${icFail ? ` (INSUFFICIENT — must be upgraded to minimum ${icMinRec} kA)` : ` (margin: +${icMargin} kA)`}
MINIMUM RECOMMENDED IC: ${icMinRec} kA
STANDARDS: PEC 2017 Article 1.30, PEC Article 2.40, IEEE Std 141 (Red Book), IEC 60909

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Main circuit breaker (MCCB or ACB — minimum IC ${icMinRec} kA at ${voltageLLV}V${icFail ? `, REPLACEMENT REQUIRED — installed unit undersized` : ``}), branch circuit breakers (MCCBs — IC ≥ ${icMinRec} kA, sized per branch loads), current transformer (CT) for metering (if panel > 100A), arc flash warning labels (NFPA 70E / PEC-compliant, incident energy and PPE level), arc flash boundary markers, short circuit study report holder/binder (for panel schedule record), bus bar shorting link (for fault current test, 1 set per panel), personal protective equipment (PPE) — arc-rated FR clothing and face shield (for commissioning work near energized bus), insulated tools (1000V rated), ground fault indicator light or relay (per PEC 2017), panel enclosure padlock set, cable bus duct or switchgear cubicle (if fault level requires metal-enclosed gear), thermal imaging window port (installed on panel door for ongoing maintenance), insulating mat (IEC 61111 Class 1 minimum, for work area protection)
2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (PEC 2017 Art. 1.30, IEC 60909 transformer impedance method, 3-phase symmetrical fault ${IscKA} kA, asymmetrical peak ${IpeakKA} kA), ${icFail ? `Breaker Upgrade Requirement (installed ${breakerIC} kA IC is INSUFFICIENT for ${IscKA} kA fault level — replace with minimum ${icMinRec} kA IC-rated breaker before energization — PEC Art. 1.30 non-negotiable)` : `Breaker IC Verification (installed ${breakerIC} kA IC confirmed adequate for ${IscKA} kA fault level with ${icMargin} kA safety margin)`}, Arc Flash Hazard Assessment and Labeling (incident energy analysis, PPE levels, arc flash boundary marking per NFPA 70E / PEC), Panel Schedule and Single-Line Diagram Update (as-built SLD showing transformer, feeder cable, fault current level at each panel), Testing and Commissioning (insulation resistance test, breaker contact resistance test, trip test, IR thermal scan of bus connections under load), Regulatory Compliance (PEC 2017 Art. 1.30 and 2.40, Electrical Permit, DOLE OSH, short circuit study report filed with as-built documents)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical Lighting Design BOM + SOW Agent ───────────────────────────────

async function lightingDesignBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project      = inputs.project_name      || "Lighting Project";
  const spaceType    = inputs.space_type        || "Office";
  const roomLenM     = inputs.room_len_m        ?? "N/A";
  const roomWidM     = inputs.room_wid_m        ?? "N/A";
  const ceilingHtM   = inputs.ceiling_ht_m      ?? "N/A";
  const targetLux    = inputs.target_lux        ?? "N/A";
  const lumensPerFix = inputs.lumens_per_fix     ?? "N/A";
  const wattsPerFix  = inputs.watts_per_fix      ?? "N/A";
  const llf          = inputs.llf               ?? 0.80;
  const floorAreaM2  = results.floor_area_m2    ?? "N/A";
  const rcr          = results.RCR              ?? "N/A";
  const cu           = results.CU               ?? "N/A";
  const nFixtures    = results.N_fixtures        ?? "N/A";
  const eActualLux   = results.E_actual_lux     ?? "N/A";
  const totalWatts   = results.total_watts      ?? "N/A";
  const totalKW      = results.total_kW         ?? "N/A";
  const lpdWm2       = results.lpd_W_m2         ?? "N/A";

  const prompt = `You are a Philippine electrical engineering expert (PEC 2017, IES). Generate a professional BOM and SOW for a LIGHTING DESIGN and installation project.

PROJECT: ${project}
SPACE TYPE: ${spaceType}
ROOM DIMENSIONS: ${roomLenM} m × ${roomWidM} m, ceiling height ${ceilingHtM} m
FLOOR AREA: ${floorAreaM2} m²
TARGET ILLUMINANCE: ${targetLux} lux
FIXTURE: ${lumensPerFix} lm per fixture, ${wattsPerFix} W per fixture
LIGHT LOSS FACTOR (LLF): ${llf}
ROOM CAVITY RATIO (RCR): ${rcr}
COEFFICIENT OF UTILIZATION (CU): ${cu}
REQUIRED FIXTURES: ${nFixtures} units
ACHIEVED ILLUMINANCE: ${eActualLux} lux
TOTAL CONNECTED LOAD: ${totalWatts} W (${totalKW} kW)
LIGHTING POWER DENSITY (LPD): ${lpdWm2} W/m²
STANDARDS: PEC 2017, IES Lighting Handbook (Lumen Method), ASHRAE 90.1 LPD limits, PEC Article 2.10

Generate a JSON object with:
1. "bom_items": array of 15 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: LED luminaire fixtures (${nFixtures} units — ${lumensPerFix} lm, ${wattsPerFix}W, CRI ≥ 80, color temperature per space type: office/corridor 4000K neutral white, warehouse/industrial 5000K daylight, restaurant/hotel 3000K warm white), emergency luminaire with battery backup (minimum 1 per room exit route, 90-min backup, 10 lux minimum on exit path), lighting circuit wiring (THHN/THWN copper, sized per ${totalWatts}W load + 25% continuous load factor), lighting circuit breaker (MCB, sized for circuit), lighting conduit (EMT, properly sized), conduit fittings and accessories, junction boxes (one per fixture cluster), lighting switches (per circuit zone, flush-mounted, rated 10A minimum), occupancy sensor or daylight sensor (if applicable to space type — offices, corridors), lighting panel/sub-panel (if dedicated lighting load), wire markers and circuit labels, ceiling grid or mounting hardware (for recessed or surface mount per ceiling type), fixture hangers and safety cables (per fixture weight), dimmer module or lighting control relay (if dimming specified), laminated lighting layout drawing (as-installed record)
2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (IES Lumen Method, RCR ${rcr}, CU ${cu}, LLF ${llf}, target ${targetLux} lux, achieved ${eActualLux} lux, LPD ${lpdWm2} W/m² vs ASHRAE 90.1 limit for ${spaceType}), Fixture Installation (mounting height, aiming, spacing, uniformity ratio ≥ 0.7), Circuit Wiring and Conduit Works (conductor sizing for continuous lighting load × 125%, conduit fill, color coding per PEC), Emergency Lighting and Exit Signs (PEC Art. 2.10, minimum 10 lux on exit path, 90-min backup, monthly test procedure), Testing and Commissioning (illuminance measurement grid test with calibrated lux meter at work plane height — verify ≥ ${targetLux} lux at all measurement points, uniformity check, circuit continuity and insulation resistance test), Regulatory Compliance (PEC 2017, DOLE OSH lighting requirements for ${spaceType}, Electrical Permit, as-built lighting layout drawing submission)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Fire Protection: Fire Sprinkler Hydraulic BOM + SOW Agent ───────────────

async function fireSprinklerBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name       || "Fire Protection Project";
  const hazard         = results.hazard             || inputs.occupancy_hazard  || "Ordinary Group 1";
  const kFactor        = inputs.k_factor            ?? 80;
  const pipeMat        = results.pipe_material      || inputs.pipe_material     || "Black Steel";
  const pipeLength     = inputs.pipe_length         ?? 30;
  const nSprinklers    = results.N_sprinklers        ?? "N/A";
  const qPerHead       = results.Q_per_head          ?? "N/A";
  const pDesign        = results.P_design            ?? "N/A";
  const qSprinklers    = results.Q_sprinklers_total  ?? "N/A";
  const qHose          = results.Q_hose              ?? "N/A";
  const qTotal         = results.Q_total             ?? "N/A";
  const pipeDiaMM      = results.pipe_dia            ?? "N/A";
  const velocity       = results.velocity            ?? "N/A";
  const pSource        = results.P_source            ?? "N/A";
  const pSourceKPa     = results.P_source_kPa        ?? "N/A";
  const duration       = results.duration            ?? 60;
  const waterVolL      = results.water_volume_L      ?? "N/A";
  const waterVolM3     = results.water_volume_m3     ?? "N/A";
  const density        = results.density             ?? "N/A";
  const designArea     = results.design_area         ?? "N/A";
  const coverageHead   = results.coverage_per_head   ?? "N/A";

  const prompt = `You are a Philippine fire protection engineering expert (NFPA 13, BFP Philippines). Generate a professional BOM and SOW for a FIRE SPRINKLER SYSTEM installation project.

PROJECT: ${project}
OCCUPANCY HAZARD: ${hazard}
DESIGN DENSITY: ${density} mm/min
DESIGN AREA: ${designArea} m²
COVERAGE PER HEAD: ${coverageHead} m²/sprinkler
K-FACTOR: ${kFactor} (L/min / bar^0.5)
SPRINKLERS IN DESIGN AREA: ${nSprinklers} heads
FLOW PER SPRINKLER: ${qPerHead} L/min @ ${pDesign} bar
TOTAL SPRINKLER FLOW: ${qSprinklers} L/min
HOSE STREAM ALLOWANCE: ${qHose} L/min
TOTAL SYSTEM DEMAND: ${qTotal} L/min @ ${pSource} bar (${pSourceKPa} kPa) at source
PIPE: ${pipeDiaMM} mm ${pipeMat}, ${pipeLength} m riser to remote head, velocity ${velocity} m/s
DURATION: ${duration} minutes
WATER STORAGE REQUIRED: ${waterVolL} L (${waterVolM3} m³)
STANDARDS: NFPA 13 (Sprinkler Systems), NFPA 25 (Inspection/Testing), BFP Philippines Fire Code (RA 9514), Philippine Fire Code IRR, Local BFP Authority Having Jurisdiction (AHJ)

Generate a JSON object with:
1. "bom_items": array of 18 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Upright/pendant sprinkler heads (${nSprinklers} heads minimum in design area — K=${kFactor}, rated temperature 68°C standard or 79°C intermediate, UL/FM listed), additional spare sprinkler heads (minimum 6 spare heads per NFPA 13 + wrench), sprinkler head escutcheon plates (for ceiling-recessed pendant type), main distribution pipe — riser (${pipeDiaMM} mm ${pipeMat} Schedule 40, ${pipeLength} m), branch line pipe (25–40 mm ${pipeMat} Schedule 40 — sized per NFPA 13 pipe schedule or hydraulic), cross main pipe (50–65 mm ${pipeMat} Schedule 40), pipe fittings and grooved couplings (tees, elbows, reducers — UL/FM listed, grooved or threaded), pipe hangers and supports (per NFPA 13 hanger spacing — max 3.7 m for branch lines), flow control valve / OS&Y gate valve (full-bore, UL/FM listed, with tamper switch), alarm check valve with waterflow alarm switch (UL listed, with retard chamber), alarm bell / water motor gong (outdoor audible alarm), alarm pressure gauge set (one above and one below alarm check valve), inspector's test and drain valve (2-piece ball valve, minimum 25 mm), fire department connection / siamese connection (65×65 mm twin inlet, chrome-plated, BFP-compliant), water storage tank (${waterVolL}L minimum — ${waterVolM3} m³ reinforced concrete or GRP/HDPE), pressure gauge at system riser (0–21 bar glycerin-filled), anti-freeze or dry-pipe valve (if required for exposed/outdoor areas — specify for Philippines climate — usually not required in tropical settings), pipe identification labels and directional arrows (per NFPA 13 color coding)
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (NFPA 13 Design Area Method, ${hazard} classification, density ${density} mm/min over ${designArea} m², K-factor ${kFactor}, total demand ${qTotal} L/min @ ${pSource} bar), Sprinkler Head Layout and Coverage (maximum spacing ${coverageHead} m² per head, minimum clearance requirements, obstruction rules per NFPA 13), Pipe Installation (pipe sizing per NFPA 13 hydraulic calculation, hanger spacing, flushing before connection), Valves Alarm Devices and FDC (OS&Y valve locations, alarm check valve, waterflow alarm switch, fire department connection per BFP), Water Supply and Storage Tank (${waterVolM3} m³ dedicated fire water storage, fill rate, isolation from domestic supply), Inspection Testing and Commissioning (hydrostatic test at 200 kPa above working pressure or 1,380 kPa minimum for 2 hours — NFPA 13 Section 29, flush test, alarm test, BFP acceptance inspection), Regulatory Compliance (RA 9514 Philippine Fire Code, BFP permit, Authority Having Jurisdiction sign-off, NFPA 13 / NFPA 25 maintenance schedule)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Fire Protection: Fire Pump Sizing BOM + SOW Agent ───────────────────────

async function firePumpBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name      || "Fire Pump System Project";
  const requiredFlow   = inputs.required_flow     ?? results.flow_lpm    ?? "N/A";
  const requiredPressBar = Number(inputs.required_pressure ?? 0);
  const requiredPressKPa = (requiredPressBar * 100).toFixed(0);
  const elevation      = inputs.elevation         ?? 0;
  const suctionType    = inputs.suction_type      || "Flooded Suction";
  const suctionHead    = inputs.suction_head      ?? 1.5;
  const pipeDia        = results.pipe_dia_mm      ?? inputs.pipe_diameter ?? "N/A";
  const pipeMat        = inputs.pipe_material     || "Steel";
  const driveType      = inputs.drive_type        || "Electric Motor";
  const pumpEff        = inputs.pump_efficiency   ?? 70;
  const motorEff       = inputs.motor_efficiency  ?? 90;

  const TDH            = results.TDH              ?? "N/A";
  const flowLpm        = results.flow_lpm         ?? requiredFlow;
  const hydraulicKw    = results.hydraulic_kw     ?? "N/A";
  const brakeKw        = results.brake_kw         ?? "N/A";
  const motorKw        = results.motor_kw         ?? "N/A";
  const motorHp        = results.motor_hp         ?? "N/A";
  const recommendedHp  = results.recommended_hp   ?? "N/A";
  const recommendedKw  = results.recommended_kw   ?? "N/A";
  const pipeVelocity   = results.pipe_velocity    ?? "N/A";
  const npshAvail      = results.npsh_available   ?? "N/A";
  const staticHead     = results.static_head      ?? elevation;
  const frictionHead   = results.friction_head    ?? "N/A";

  // NFPA 20 motor rating: 115% for electric, 120% for diesel
  const isDiesel       = String(driveType).toLowerCase().includes("diesel");
  const nfpa20Pct      = isDiesel ? 120 : 115;
  const nfpa20Note     = isDiesel
    ? `Diesel drive selected — NFPA 20 requires motor rated at minimum 120% of pump BHP. Diesel backup is MANDATORY per BFP IRR for high-rise buildings and critical occupancies.`
    : `Electric motor drive — NFPA 20 requires motor rated at minimum 115% of pump BHP. A diesel backup pump is required in high-rise or critical occupancies per BFP IRR.`;

  const prompt = `You are a Philippine fire protection engineering expert (NFPA 20, BFP Philippines). Generate a professional BOM and SOW for a FIRE PUMP SYSTEM installation project.

PROJECT: ${project}
DESIGN FLOW RATE: ${flowLpm} L/min
REQUIRED PRESSURE AT PUMP DISCHARGE: ${requiredPressBar} bar (${requiredPressKPa} kPa)
TOTAL DYNAMIC HEAD (TDH): ${TDH} m
  - Static Head: ${staticHead} m
  - Friction Head: ${frictionHead} m
ELEVATION (pump CL to highest sprinkler): ${elevation} m
SUCTION TYPE: ${suctionType} (suction head: ${suctionHead} m)
PIPE: ${pipeDia} mm ${pipeMat} Schedule 40, velocity ${pipeVelocity} m/s
PUMP EFFICIENCY: ${pumpEff}%
MOTOR EFFICIENCY: ${motorEff}%
HYDRAULIC POWER: ${hydraulicKw} kW
BRAKE POWER (BHP): ${brakeKw} kW
MOTOR INPUT POWER: ${motorKw} kW (${motorHp} HP)
RECOMMENDED MOTOR RATING (NFPA 20 at ${nfpa20Pct}%): ${recommendedHp} HP (${recommendedKw} kW)
DRIVE TYPE: ${driveType}
NPSHa (available): ${npshAvail} m
NFPA 20 NOTE: ${nfpa20Note}
STANDARDS: NFPA 20 (Stationary Fire Pumps), NFPA 13 (Sprinkler Systems — source of flow/pressure), BFP Philippines Fire Code (RA 9514), Philippine Fire Code IRR, National Building Code PD 1096

Generate a JSON object with:
1. "bom_items": array of 16 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Fire pump unit — end suction centrifugal (${flowLpm} L/min @ ${TDH} m TDH, ${recommendedHp} HP ${driveType}, UL/FM listed — NFPA 20 Section 4), pump baseplate and coupling guard (common baseplate, flexible coupling, stainless guard), electric motor — TEFC (${recommendedHp} HP, ${nfpa20Pct}% of BHP per NFPA 20, IP55 enclosure, IE3 efficiency class), diesel engine driver (if applicable — ${isDiesel ? `backup required per BFP IRR, engine HP = ${nfpa20Pct}% x BHP` : "not required for this installation — electric primary selected"}), jockey (pressure maintenance) pump (small centrifugal, approx. 10% of main pump flow, maintains system pressure to prevent false alarms), jockey pump motor (fractional HP, DOL starter), main pump suction pipe — ${pipeDia}mm ${pipeMat} Sch.40 with eccentric reducer and isolation valve (flooded suction configuration per NFPA 20), main pump discharge pipe — ${pipeDia}mm ${pipeMat} Sch.40 with concentric reducer to system main, pump discharge check valve (swing type, UL/FM listed — prevents backflow on pump shutdown), pump discharge gate valve / butterfly valve (OS&Y or LI type with tamper switch, UL/FM listed), pressure relief valve (set at 10% above churn pressure — NFPA 20 requirement), pressure gauges — suction and discharge (glycerin-filled, 0–21 bar, per NFPA 20), flow meter / test header with sight glass or ultrasonic flow meter (for periodic flow testing per NFPA 25), fire pump controller — automatic pressure-sensing type (UL listed per NFPA 20, auto-start on pressure drop, manual stop only, alarm panel with remote signal), automatic transfer switch / ATS (if diesel backup is provided — transfers power on utility failure), vibration isolation pads and anchor bolts (per pump manufacturer specification, seismic restraint if required)
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (NFPA 20 design criteria, ${flowLpm} L/min @ ${requiredPressBar} bar, TDH=${TDH}m, ${driveType} drive, ${nfpa20Note}), Pump and Driver Installation (alignment, baseplate grouting, coupling guard, vibration isolation, NFPA 20 Section 4 clearance requirements), Piping Connections (suction eccentric reducer, discharge concentric reducer, pipe sizing per NFPA 20 velocity limits, hanger spacing, flanged connections to pump nozzles), Valves Instrumentation and Controller (OS&Y isolation valves with tamper switches, check valve, pressure gauges on suction and discharge, automatic fire pump controller per UL 218 / NFPA 20 — auto-start, manual-stop-only, alarm outputs), Jockey Pump (sizing and installation, pressure setting to maintain system at ${(requiredPressBar * 100).toFixed(0)} kPa ± 35 kPa, prevent nuisance starts), Inspection Testing and Commissioning (churn/no-flow test, 100% flow test, 150% flow test at 65% pressure per NFPA 20 Section 12, pressure relief valve test, controller and ATS test, BFP acceptance inspection), Regulatory Compliance (RA 9514 Philippine Fire Code, NFPA 20 acceptance test witnessed by BFP AHJ, PRC-licensed Mechanical Engineer sign-off, O&M manual submission)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Main handler ─────────────────────────────────────────────────────────────

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const body = await req.json();

    // Diagnostic endpoint
    if (body.action === "list_models") {
      const models = await listModels();
      return new Response(JSON.stringify({ models }), {
        headers: { ...corsHeaders, "Content-Type": "application/json" },
      });
    }

    const { discipline, calc_type, calc_inputs, calc_results } = body;

    if (!discipline || !calc_type || !calc_results) {
      return new Response(
        JSON.stringify({ error: "Missing required fields: discipline, calc_type, calc_results" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    let result: { bom_items: unknown[]; sow_sections: unknown[] };

    // Discipline router — add branches here for Pump Sizing, Electrical, etc.
    if (discipline === "Mechanical" && calc_type === "HVAC Cooling Load") {
      result = await hvacBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Mechanical" && calc_type === "Ventilation / ACH") {
      result = await ventBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Mechanical" && calc_type === "Pump Sizing (TDH)") {
      result = await pumpBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Mechanical" && calc_type === "Pipe Sizing") {
      result = await pipeSizingBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Mechanical" && calc_type === "Compressed Air") {
      result = await compressedAirBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Water Supply Pipe Sizing") {
      result = await waterSupplyBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Hot Water Demand") {
      result = await hotWaterBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Drainage Pipe Sizing") {
      result = await drainageBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Septic Tank Sizing") {
      result = await septicBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Load Estimation") {
      result = await loadEstBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Voltage Drop") {
      result = await voltageDropBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Wire Sizing") {
      result = await wireSizingBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Short Circuit") {
      result = await shortCircuitBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Lighting Design") {
      result = await lightingDesignBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Fire Protection" && calc_type === "Fire Sprinkler Hydraulic") {
      result = await fireSprinklerBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Fire Protection" && calc_type === "Fire Pump Sizing") {
      result = await firePumpBomSowAgent(calc_inputs || {}, calc_results);
    } else {
      return new Response(
        JSON.stringify({ error: `BOM+SOW not yet available for ${discipline} / ${calc_type}` }),
        { status: 422, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    return new Response(JSON.stringify(result), {
      headers: { ...corsHeaders, "Content-Type": "application/json" },
    });

  } catch (err) {
    console.error("engineering-bom-sow error:", err);
    return new Response(
      JSON.stringify({ error: err instanceof Error ? err.message : "Internal error" }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});

// Diagnostic: POST { "action": "list_models" } to see available models
async function listModels(): Promise<string[]> {
  const key = Deno.env.get("GEMINI_API_KEY") || "";
  const res = await fetch(`https://generativelanguage.googleapis.com/v1beta/models?key=${key}`);
  const data = await res.json();
  return (data.models || []).map((m: { name: string }) => m.name);
}
