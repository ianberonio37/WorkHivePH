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
