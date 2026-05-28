import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

// contract-allow: deterministic BOM/SOW generation; not a brain output
import { callAI } from "../_shared/ai-chain.ts";
import { logAICost, estimateTokens } from "../_shared/cost-log.ts";
import { getCorsHeaders } from "../_shared/cors.ts";
// P1 roadmap 2026-05-26: envelope adoption (helper imported; success-path migration follows).
import { beginRequest, ok, fail, recordModelHop } from "../_shared/envelope.ts";

// ─── BOM unit sanitizer ───────────────────────────────────────────────────────
// LLMs sometimes put descriptive text in the `unit` field.
// Clamp any value longer than 12 characters or containing spaces back to "unit".
const VALID_UNITS = new Set([
  'unit','set','pc','pcs','lot','m','m²','m³','kg','L','roll','pair',
  'panel','breaker','tank','battery','length','run','assembly','bag',
  'sheet','drum','box','can','tube','bar','bundle',
]);
function sanitizeBomItems(items: unknown[]): unknown[] {
  return items.map((item: unknown) => {
    const it = item as Record<string, unknown>;
    const raw = String(it.unit || 'unit').trim();
    const clean = VALID_UNITS.has(raw.toLowerCase()) ? raw : (raw.length > 12 || raw.includes(' ') ? 'unit' : raw);
    // Strip non-ASCII characters from text fields (guards against LLM Unicode garbling)
    const stripNonAscii = (s: unknown) => String(s || '').replace(/[^\x20-\x7E]/g, '');
    return {
      ...it,
      unit:        clean,
      description: stripNonAscii(it.description),
      specification: stripNonAscii(it.specification),
      remarks:     stripNonAscii(it.remarks),
    };
  });
}

async function callGroq(prompt: string): Promise<string> {
  const result = await callAI(prompt, { temperature: 0.2, maxTokens: 8000, jsonMode: true });
  if (result === "{}") throw new Error("All AI providers are at capacity. Try again in a few minutes.");
  return result;
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

ARRAY 1: "bom_items": Standard Philippine HVAC contractor Bill of Materials.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items (use calculated quantities above):
1. Split-type Air Conditioning Unit, Indoor (wall-mounted): qty: ${nUnits}
2. Outdoor Condensing Unit: qty: ${nUnits}
3. Refrigerant Piping Set (liquid + suction line, pre-insulated): qty: ${pipingM} m
4. Pipe Insulation, closed-cell foam 13mm: qty: ${pipingM} m
5. Condensate Drain Line, PVC 3/4": qty: ${pipingM} m
6. MCCB Circuit Breaker, 2-pole: qty: ${nUnits}
7. Electrical Wiring, THHN 3.5mm² Cu: qty: ${wiringM} m
8. Thermostat / Wired Remote Controller: qty: ${nUnits}
9. Outdoor Unit Mounting Bracket, heavy-duty galvanized: qty: ${nUnits}: checked: false (optional)
10. Refrigerant Charge, R-410A: qty: ${Number(nUnits) * 0.9} kg
11. Miscellaneous (anchors, cable ties, sealant, putty): qty: 1 lot

Specifications must be specific: include kW capacity, voltage, refrigerant type, material grade, standard size. Match ${unitKW} kW per unit.

ARRAY 2: "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope: checked: true
- "2.0" Applicable Standards and Codes: checked: true (list: PSME, ASHRAE, PEC 2017, DOLE OSH, manufacturer guidelines)
- "3.0" Materials: checked: true (reference BOM, state Philippine standards compliance)
- "4.1" Equipment Supply and Delivery: checked: true
- "4.2" Indoor Unit Installation: checked: true
- "4.3" Outdoor Unit Installation: checked: true
- "4.4" Refrigerant Piping Works: checked: true (include pressure test at 300 psi N2, 24-hour hold, evacuation, R-410A charge)
- "4.5" Electrical Connections: checked: true (reference PEC 2017, dedicated circuit per unit)
- "4.6" Condensate Drainage: checked: true
- "4.7" Thermal Insulation: checked: true
- "4.8" Testing and Commissioning: checked: true (verify ±10% of design capacity, measure supply air temp, submit commissioning report)
- "4.9" As-Built Documentation: checked: true
- "5.0" Inclusions: checked: false
- "6.0" Exclusions: checked: false (civil works, panel upgrade if required, duct fabrication)
- "7.0" Warranty: checked: false (1 year equipment per manufacturer, 1 year workmanship from acceptance)

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

ARRAY 1: "bom_items": Standard Philippine mechanical contractor Bill of Materials for ventilation.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items (use calculated quantities above):
1. Inline/Centrifugal Fan (${isExhaust || isBoth ? 'Exhaust' : 'Supply'}): qty: 1 unit: specify ${fanCMH} m³/hr, static pressure, voltage
2. ${isBoth ? 'Supply Fan: qty: 1 unit: specify capacity and motor spec' : 'Flexible Duct Connector: qty: 2 pcs: specify size to match fan outlet'}
3. Galvanized Steel Ductwork (Supply or Exhaust, as applicable): qty: ${ductM} m: specify gauge, 1.0mm G.I. standard
4. Duct Insulation, pre-formed glass wool 25mm: qty: ${ductM} m: for supply air ducts only; skip if exhaust only
5. Supply Air Diffuser / Exhaust Grille: qty: ${grilles} pcs: specify size (e.g. 300×150mm or 600×600mm), aluminum
6. Volume Control Damper (manual): qty: ${dampers} pcs: specify size, galvanized steel, opposed blade
7. Fire Damper (fusible link, 72°C): qty: ${dampers} pcs: specify UL-listed, matching duct size: checked: false (optional per fire code)
8. Motorized Fresh Air Damper: qty: 1 pc: specify 24VAC actuator, normally closed: checked: ${isBoth ? 'true' : 'false'}
9. Electrical Wiring, THHN 2.0mm² Cu, 3-wire: qty: ${nFans * 10} m: specify color code per PEC 2017
10. On/Off Switch with pilot light: qty: ${nFans} pc: specify 15A, surface-mounted
11. Flexible Metal Duct, 150mm dia: qty: 4 m: for terminal connections
12. Miscellaneous (duct sealant, hangers, fasteners, damper clips): qty: 1 lot

Specifications must be specific: include airflow in m³/hr, voltage (230V/1Ph or 460V/3Ph), material grade, duct gauge, grille size. Match ${fanCMH} m³/hr capacity.

ARRAY 2: "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope: checked: true
- "2.0" Applicable Standards and Codes: checked: true (list: ASHRAE 62.1, PSME Code, PEC 2017, DOLE OSH Standards for workplace ventilation, National Building Code PD 1096, NFPA 90A for duct construction)
- "3.0" Materials: checked: true (reference BOM, state Philippine standards compliance, G.I. duct SMACNA standards)
- "4.1" Equipment Supply and Delivery: checked: true
- "4.2" Fan and Motor Installation: checked: true (specify vibration isolation mounts, flexible connectors, direction of rotation test)
- "4.3" Ductwork Fabrication and Installation: checked: true (specify SMACNA standards, gauge, sealing with UL-listed sealant, 25 Pa pressure test)
- "4.4" Grilles, Diffusers, and Dampers: checked: true (specify balancing procedure, airflow measurement at each terminal)
- "4.5" Electrical Connections: checked: true (reference PEC 2017, motor starter or direct-on-line starter, overload protection)
- "4.6" Fire Damper Installation: checked: false (where penetrating fire-rated partitions per BFP IRR)
- "4.7" Testing, Balancing, and Commissioning: checked: true (measure actual ACH, compare to design ${reqACH} ACH, submit TAB report, ASHRAE 111 method)
- "4.8" As-Built Documentation: checked: true
- "5.0" Inclusions: checked: false
- "6.0" Exclusions: checked: false (civil/building works, mechanical rooms, structural supports beyond scope)
- "7.0" Warranty: checked: false (1 year equipment per manufacturer, 1 year workmanship from acceptance)

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

ARRAY 1: "bom_items": Standard Philippine mechanical contractor Bill of Materials for pump system.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Centrifugal Pump: qty: 1 unit: specify ${recHP} hp, TDH ${tdh} m, ${flowM3hr} m³/hr, ${fluidType}, back-pull-out type, close-coupled or base-mounted
2. Electric Motor: qty: 1 unit: specify ${recHP} hp (${recKW} kW), TEFC, IE2/IE3 efficiency, 460V/3Ph/60Hz (or 230V if <1.5 kW)
3. Base Plate / Pump Base: qty: 1 set: specify epoxy-grouted, fabricated steel, drip rim
4. Gate Valve, flanged: qty: 2 pcs: specify PN16, ${pipeDiaMM} mm, cast iron or bronze, suction and discharge isolation
5. Check Valve (swing type), flanged: qty: 1 pc: specify PN16, ${pipeDiaMM} mm, cast iron, discharge side
6. Flexible Coupling / Vibration Isolator: qty: 2 pcs: specify flanged rubber expansion joint, ${pipeDiaMM} mm, rated PN16
7. Pressure Gauge with siphon: qty: 2 pcs: specify 0–${Math.ceil(Number(tdh) / 10) * 10 + 30} m (0–${Math.round((Number(tdh) + 30) * 0.0981)} bar), 100mm dial, glycerin-filled, suction and discharge
8. Pipe, ${pipeMat}: qty: ${pipeLen} m: specify ${pipeDiaMM} mm nominal dia, PN10 or PN16, including fittings
9. Pipe Fittings (elbows, tees, reducers): qty: 1 lot: specify ${pipeDiaMM} mm, ${pipeMat}, match pipe class
10. Pipe Supports and Hangers: qty: 1 lot: specify adjustable clevis hanger, galvanized, spacing per PSME
11. Motor Control Center (MCC) / DOL Starter: qty: 1 unit: specify direct-on-line starter (DOL) if ≤7.5 hp or star-delta if >7.5 hp, MCCB, overload relay, ${recHP} hp rated
12. Electrical Wiring, THHN Cu: qty: ${Math.round(Number(pipeLen) * 1.2 + 10)} m: specify size per PEC 2017 motor branch circuit, THHN insulation
13. Pipe Insulation (for chilled water or hot water): qty: ${pipeLen} m: specify closed-cell foam or pre-formed, 25mm thickness: checked: false (apply if chilled or hot water)
14. Miscellaneous (bolts, gaskets, pipe sealant, grout): qty: 1 lot

Specifications must be specific: include HP, kW, flow, TDH, pipe size and class, valve PN rating. Match ${recHP} hp and ${pipeDiaMM} mm throughout.

ARRAY 2: "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope: checked: true
- "2.0" Applicable Standards and Codes: checked: true (list: PSME Code, Hydraulic Institute Standards ANSI/HI, PEC 2017, Philippine Plumbing Code, DOLE OSH, manufacturer installation guidelines)
- "3.0" Materials: checked: true (reference BOM, all materials PN16 rated, PSME-compliant)
- "4.1" Equipment Supply and Delivery: checked: true (factory test certificates, performance curves to be submitted)
- "4.2" Pump and Motor Installation: checked: true (specify epoxy grouting, shaft alignment within 0.05mm TIR, vibration isolation mounts, direction of rotation check before coupling)
- "4.3" Piping Works: checked: true (specify ${pipeMat} pipe at ${pipeDiaMM} mm, support spacing, isolation valve locations, drain/vent points)
- "4.4" Valves and Instrumentation: checked: true (gate valves suction and discharge, swing check valve, pressure gauges both sides)
- "4.5" Electrical and Motor Starter: checked: true (reference PEC 2017, DOL or star-delta starter, overload relay set to motor FLA, dedicated circuit and MCCB)
- "4.6" Hydrostatic Pressure Test: checked: true (test piping at 1.5× working pressure for minimum 30 minutes, no leaks, document results)
- "4.7" Testing and Commissioning: checked: true (verify flow ${flowM3hr} m³/hr and TDH ${tdh} m at design point, measure motor current against nameplate, submit commissioning report)
- "4.8" As-Built Documentation: checked: true
- "5.0" Inclusions: checked: false
- "6.0" Exclusions: checked: false (civil / structural works, foundation design, building permits, electrical panel upgrade if required)
- "7.0" Warranty: checked: false (1 year equipment per manufacturer, 1 year workmanship from acceptance)

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

ARRAY 1: "bom_items": Standard Philippine mechanical contractor Bill of Materials for piping works.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Pipe, ${pipeMat}: qty: ${pLen} m: specify ${pipeDiaMM} mm nominal dia, include applicable pressure class (PN10/PN16/Schedule 40 depending on material), in 6-m lengths
2. Pipe Fittings: Elbows 90°: qty: ${nElbows} pcs: specify ${pipeDiaMM} mm, ${pipeMat}, same pressure class as pipe
3. Pipe Fittings: Tees (equal): qty: ${Math.max(2, Math.round(nElbows / 3))} pcs: specify ${pipeDiaMM} mm, ${pipeMat}
4. Pipe Fittings: Reducers / Couplings: qty: ${Math.max(2, Math.round(nElbows / 4))} pcs: specify ${pipeDiaMM} mm, ${pipeMat}
5. Isolation Valve (gate or ball type): qty: ${nIsolation} pcs: specify ${pipeDiaMM} mm, PN16, bronze or cast iron, sectional isolation
6. Check Valve (swing type): qty: ${nDrain} pc: specify ${pipeDiaMM} mm, PN16, at pump discharge or riser base: checked: false (if no pump in scope)
7. Drain Valve / Blow-off Valve: qty: ${nDrain} pcs: specify 20 mm, bronze ball valve with hose bib
8. Pressure Gauge with siphon: qty: ${nPressGauge} pcs: specify 0–${Math.ceil((Number(hfTotal) + 30) * 0.1) * 100} kPa, 100mm dial, glycerin-filled
9. Pipe Supports and Hangers: qty: ${nSupports} sets: specify adjustable clevis hanger, galvanized, PSME-compliant spacing for ${pipeMat} at ${pipeDiaMM} mm
10. Pipe Insulation (if chilled water or hot water service): qty: ${pLen} m: specify pre-formed glass wool or closed-cell foam 25mm, with aluminum jacket: checked: false (apply if chilled or hot water)
11. Flanges and Gaskets: qty: 1 lot: specify ${pipeDiaMM} mm, PN16, flat face or raised face, with spiral wound or rubber gaskets, for equipment connections
12. Welding Consumables / Jointing Materials: qty: 1 lot: specify per pipe material: solvent cement for PVC, Teflon tape + pipe compound for threaded, argon + filler rod for SS/Cu
13. Miscellaneous (anchors, pipe labels, supports, testing plugs): qty: 1 lot

Specifications must be specific: include pipe diameter, pressure class, material grade, and Philippine standards compliance (PSME, PNS). All sizes must match ${pipeDiaMM} mm throughout.

ARRAY 2: "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope: checked: true
- "2.0" Applicable Standards and Codes: checked: true (list: PSME Code, Philippine Plumbing Code (based on UPC/IPC), ASTM material standards for ${pipeMat}, Hydraulic Institute Standards, PEC 2017 for any electrical components, DOLE OSH)
- "3.0" Materials: checked: true (reference BOM, state ${pipeMat} pipe at ${pipeDiaMM} mm nominal, specify ASTM or PNS standard, all valves PN16 minimum)
- "4.1" Equipment and Material Delivery: checked: true (include inspection on delivery, material test certificates for ${pipeMat} pipe and fittings)
- "4.2" Pipe Fabrication and Installation: checked: true (specify cutting, jointing method for ${pipeMat}, support spacing per PSME, slope requirements for drainage if applicable, alignment and grading)
- "4.3" Valve and Instrument Installation: checked: true (specify orientation, isolation valve placement, pressure gauge siphon requirement, access provision for maintenance)
- "4.4" Pipe Supports and Anchors: checked: true (specify hanger type, PSME maximum spacing for ${pipeDiaMM} mm ${pipeMat} pipe, seismic provision if applicable)
- "4.5" Insulation Works: checked: false (if chilled water or hot water: closed-cell foam or glass wool 25mm, aluminum jacket, all joints sealed with vapor barrier tape)
- "4.6" Pressure Testing: checked: true (hydrostatic test at 1.5× working pressure, minimum 30 minutes, zero pressure drop, document and submit test records)
- "4.7" Flushing and Cleaning: checked: true (flush at minimum 1.5× design velocity before commissioning, water quality test for potable or process systems, chemical cleaning for chilled water per ASHRAE guideline)
- "4.8" Commissioning and Handover: checked: true (verify flow ${flowM3hr} m³/hr and velocity ${velocity} m/s at design point, submit as-built drawings and commissioning report)
- "4.9" As-Built Documentation: checked: true
- "5.0" Inclusions: checked: false
- "6.0" Exclusions: checked: false (civil / structural works, equipment foundations, electrical connections unless specified, building permits)
- "7.0" Warranty: checked: false (1 year workmanship from acceptance; material warranty per manufacturer)

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

ARRAY 1: "bom_items": Standard Philippine mechanical contractor Bill of Materials for compressed air system.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Air Compressor, Rotary Screw: qty: 1 unit: specify ${recHP} hp, ${recCFM} CFM FAD, ${workingBar} bar working pressure, air-cooled, direct drive, CAGI-certified
2. Air Receiver Tank: qty: 1 unit: specify ${recReceiverL} litres, working pressure ${workingBar} bar(g), ASME-coded or PNS pressure vessel, complete with safety relief valve, drain valve, pressure gauge, and sight glass
3. Air Dryer (Refrigerated Type): qty: 1 unit: specify ${recCFM} CFM capacity, pressure dew point -3°C to +3°C, ISO 8573-1 Class 4 moisture, matched to compressor FAD
4. Pre-filter (Coalescing), 1 micron: qty: 1 unit: specify ${recCFM} CFM, ISO 8573-1 Class 3 oil, at compressor outlet
5. After-filter (Particulate), 0.01 micron: qty: 1 unit: specify ${recCFM} CFM, ISO 8573-1 Class 1, downstream of dryer
6. Distribution Pipe, Black Steel Schedule 40: qty: ${pLen} m: specify ${recPipeMM} mm nominal bore, threaded or flanged connections, in 6-m lengths
7. Pipe Fittings (elbows, tees, unions): qty: 1 lot: specify ${recPipeMM} mm, black steel, Class 150, PSME-compliant
8. Drop Leg Assembly with Auto Drain: qty: ${nDropLegs} sets: specify ${recPipeMM} mm tee, 25 mm drop leg, ball valve, automatic condensate drain
9. Ball Valve, full bore: qty: ${nIsolation} pcs: specify ${recPipeMM} mm, PN16, chrome-plated brass or cast iron, for sectional isolation
10. Safety Relief Valve (distribution header): qty: 1 pc: specify set pressure ${Math.ceil(Number(workingBar) * 1.1 * 10) / 10} bar(g), ASME-certified, at header inlet
11. Pressure Gauge (distribution): qty: ${Math.max(2, nDropLegs)} pcs: specify 0–${Math.ceil(Number(workingBar) * 2)} bar, 100mm dial, glycerin-filled, at key points
12. Filter-Regulator-Lubricator (FRL) Unit: qty: ${nFil} set: specify ${recPipeMM} mm port, 0–${workingBar} bar range, at point-of-use headers: checked: false (supply if process requires lubrication)
13. Pipe Supports and Hangers: qty: ${nSupports} sets: specify galvanized clevis hanger, PSME spacing, slope 1:200 toward drop legs
14. Condensate Drain System: qty: 1 lot: specify automatic electronic timer drain at compressor, receiver, dryer, and each filter; PVC condensate collection line to drain
15. Miscellaneous (Teflon tape, pipe compound, hose connectors, labels): qty: 1 lot

Specifications must be specific: include HP, CFM, bar pressure, pipe size and schedule, filter micron rating, ISO 8573-1 class. All rated for ${workingBar} bar(g) minimum.

ARRAY 2: "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope: checked: true
- "2.0" Applicable Standards and Codes: checked: true (list: PSME Code, ISO 8573-1 Compressed Air Purity, ISO 1217 Compressor Performance, CAGI Standards, ASME Section VIII pressure vessels, PEC 2017, DOLE OSH Compressed Gas Safety)
- "3.0" Materials: checked: true (reference BOM, black steel Schedule 40 for distribution, all equipment rated ${workingBar} bar(g) minimum, ASME pressure vessel code for receiver)
- "4.1" Equipment Supply and Delivery: checked: true (CAGI performance data sheets, pressure vessel certificates, factory test reports to be submitted prior to delivery)
- "4.2" Compressor and Receiver Installation: checked: true (specify concrete pad, vibration isolation mounts, levelling, minimum 1-metre clearance for maintenance access, compressor room ventilation)
- "4.3" Air Treatment Equipment: checked: true (dryer inlet/outlet isolation valves, bypass line for dryer maintenance, filter differential pressure gauges, auto-drain connections)
- "4.4" Distribution Piping Works: checked: true (black steel Schedule 40 at ${recPipeMM} mm, slope 1:200 toward drop legs for condensate drainage, all joints threaded or flanged with PTFE, pressure test before insulation)
- "4.5" Drop Legs and Point-of-Use Connections: checked: true (drop legs at low points and at each use point, automatic condensate drains at all low points, FRL sets at process connections if required)
- "4.6" Electrical Connections and Control: checked: true (dedicated circuit per PEC 2017, motor starter or VFD for compressor, pressure switch for automatic start/stop, overload protection)
- "4.7" Pressure Testing: checked: true (pneumatic leak test at 1.1× working pressure with soapy water, all joints checked, zero leakage acceptable, document and submit records)
- "4.8" System Commissioning: checked: true (verify compressor FAD ${recCFM} CFM at ${workingBar} bar, check dryer dew point, verify auto-start/stop, measure system leakage: must be < ${leakagePct}% of FAD, submit commissioning report)
- "4.9" As-Built Documentation: checked: true
- "5.0" Inclusions: checked: false
- "6.0" Exclusions: checked: false (civil works, compressor room construction, utility connections unless specified, piping beyond drop leg outlets)
- "7.0" Warranty: checked: false (1 year equipment per manufacturer, 1 year workmanship from acceptance; compressor extended warranty if available)

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

ARRAY 1: "bom_items": Standard Philippine sanitary/plumbing contractor Bill of Materials for domestic water supply system.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Water Supply Pipe, ${pipeMat}: qty: ${pLen} m: specify ${pipeDiaMM} mm nominal dia, PN10 pressure class (or Schedule 40 if CPVC), NSF/PNS 65 potable water rated, in 6-m lengths
2. Pipe Fittings: Elbows 90°: qty: ${Math.max(4, Math.round(pLen / 5))} pcs: specify ${pipeDiaMM} mm, ${pipeMat}, same pressure class, potable water grade
3. Pipe Fittings: Tees (equal and reducing): qty: ${Math.max(2, Math.round(pLen / 8))} pcs: specify ${pipeDiaMM} mm, ${pipeMat}, per Philippine Plumbing Code
4. Pipe Fittings: Reducers / Couplings: qty: ${Math.max(2, Math.round(pLen / 10))} pcs: specify ${pipeDiaMM} mm, ${pipeMat}
5. Gate Valve / Ball Valve (isolation), full bore: qty: ${nIsolation} pcs: specify ${pipeDiaMM} mm, PN16, bronze, for sectional isolation and at each riser base
6. Angle Valve (fixture stop valve): qty: ${nAngle} pcs: specify 15 mm (1/2 in), chrome-plated brass, 1 per fixture connection
7. Pressure Reducing Valve (PRV): qty: 1 pc: specify inlet: ${supplyPress} kPa, outlet: ${Math.min(Number(supplyPress) - 50, 250)} kPa, bronze body, spring-loaded, per Philippine Plumbing Code: checked: ${Number(supplyPress) > 300 ? 'true' : 'false'} (required if supply pressure > 300 kPa)
8. Water Meter: qty: 1 pc: specify ${pipeDiaMM} mm, multi-jet type, MWSS/LWUA approved, flanged or threaded connections
9. Backflow Preventer / Check Valve: qty: 1 pc: specify ${pipeDiaMM} mm, double-check assembly type, PN16, at meter outlet per Philippine Plumbing Code
10. ${hasHot ? 'Hot Water Supply Pipe, CPVC or Cu' : 'Cold Water Branch Pipe, PVC'}: qty: ${Math.round(pLen * 0.5)} m: specify 20 mm or 15 mm as required for branch lines to fixtures
11. Pipe Insulation (for hot water lines): qty: ${hasHot ? Math.round(pLen * 0.5) : 0} m: specify closed-cell foam 13mm, aluminum foil jacket, for all hot water pipes: checked: ${hasHot ? 'true' : 'false'}
12. Pipe Supports and Hangers: qty: ${nSupports} sets: specify galvanized pipe clamp or clevis hanger, spacing per Philippine Plumbing Code (${pipeMat} at ${pipeDiaMM} mm)
13. Pressure Gauge (at PRV outlet and riser base): qty: 2 pcs: specify 0–700 kPa, 100mm dial, glycerin-filled
14. Pipe Labelling and Colour Banding: qty: 1 lot: specify per Philippine Plumbing Code: cold water = blue, hot water = red/orange
15. Miscellaneous (Teflon tape, pipe cement for PVC, hangers, anchors, cleanouts): qty: 1 lot

Specifications must reference PNS/NSF potable water standards, ${pipeDiaMM} mm throughout main line. All valves and fittings rated for potable water contact.

ARRAY 2: "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope: checked: true
- "2.0" Applicable Standards and Codes: checked: true (list: Philippine Plumbing Code (PPC): based on UPC/IPC, NSF/PNS 65 potable water piping, PSME Code, LWUA/MWSS connection standards, PEC 2017 for any electrical components, DOLE OSH)
- "3.0" Materials: checked: true (reference BOM, all pipes and fittings potable water rated NSF/PNS 65, ${pipeMat} at ${pipeDiaMM} mm nominal, all valves bronze or NSF-approved material)
- "4.1" Equipment and Material Delivery: checked: true (material test certificates and NSF/PNS compliance certificates to be submitted; all materials inspected on delivery before installation)
- "4.2" Pipe Installation: checked: true (specify jointing method for ${pipeMat}, support spacing per Philippine Plumbing Code, 25mm clearance from structural elements, grading toward drain points, sleeve through walls)
- "4.3" Valve and Meter Installation: checked: true (isolation valves at each riser base and branch takeoff, water meter accessible for reading, PRV accessible for adjustment)
- "4.4" Pipe Supports and Sleeves: checked: true (hanger spacing per PPC, all pipe penetrations through slabs/walls with galvanized sleeves sealed with fire-rated sealant at fire-rated assemblies)
- "4.5" Hot Water Piping Works: checked: ${hasHot ? 'true' : 'false'} (CPVC or copper for hot water lines, all hot water pipes insulated with closed-cell foam 13mm, slope toward drain for system draining)
- "4.6" Pressure Testing: checked: true (hydrostatic test at 2× working pressure (${Math.round(Number(supplyPress) * 2)} kPa) or minimum 1,000 kPa for 30 minutes, all joints and valves checked for leaks, document and submit test records)
- "4.7" Disinfection and Flushing: checked: true (flush system at 1.5× design velocity, disinfect with chlorine solution 50 ppm for 24 hours per Philippine Plumbing Code, flush until residual chlorine < 0.5 ppm before connection to fixtures)
- "4.8" Commissioning and Handover: checked: true (verify flow at furthest fixture, measure residual pressure (must be ≥ ${minPress} kPa), check all fixture stop valves, submit commissioning report and water quality test results)
- "4.9" As-Built Documentation: checked: true
- "5.0" Inclusions: checked: false
- "6.0" Exclusions: checked: false (civil / structural works, plumbing fixtures and fittings beyond stop valves, MWSS/LWUA service connection fees, water treatment equipment)
- "7.0" Warranty: checked: false (1 year workmanship from acceptance; material warranty per manufacturer; leaks discovered within warranty period repaired at Contractor's cost)

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

ARRAY 1: "bom_items": Standard Philippine plumbing contractor Bill of Materials for hot water system.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Hot Water Storage Tank: qty: 1 unit: specify ${recStorageL} litres, ${tHot}°C rated, glass-lined or stainless steel inner tank, polyurethane foam insulation, working pressure 600 kPa, complete with anode rod, temperature-pressure relief valve, drain valve, and inspection port
2. Water Heater / Heating Element: qty: 1 unit: specify ${recHeaterKW} kW${isElectric ? `, ${heaterVoltage}, immersion-type electric heating element, thermostat-controlled, CHED/BPS approved` : `, gas-fired or heat pump type, rated at ${recHeaterKW} kW input, thermostat with high-limit safety cutout`}, recovery rate ${recoveryLPH} L/hr at ΔT ${deltaT}°C
3. Temperature-Pressure Relief Valve (T&P Valve): qty: 1 pc: specify set at 700 kPa / 99°C, ANSI/ASME rated, 3/4 in discharge, with full-size drain to floor drain: checked: true (mandatory per Philippine Plumbing Code)
4. Expansion Tank (thermal expansion): qty: 1 unit: specify pre-charged diaphragm type, sized for ${recStorageL}L system, 350–700 kPa operating range, ASME-rated: checked: true (required in closed systems)
5. Mixing Valve / Thermostatic Mixing Valve (TMV): qty: 1 unit: specify ASSE 1017 listed, set at ${Math.min(Number(tHot) - 5, 55)}°C delivery temperature, to prevent scalding at fixtures, ${Math.max(nFixtures * 2, 15)} L/min capacity
6. Hot Water Supply Pipe, CPVC: qty: ${pipeLen} m: specify 20 mm or 25 mm nominal, ASTM D2846, rated 82°C / 600 kPa, in 6-m lengths
7. Cold Water Feed Pipe, PVC PN10: qty: ${Math.round(pipeLen * 0.4)} m: specify 20 mm or 25 mm nominal, potable water rated NSF/PNS 65, for heater inlet
8. Pipe Insulation, pre-formed closed-cell foam: qty: ${pipeLen} m: specify 19mm wall thickness, aluminum foil jacket, for all hot water supply pipes to minimise heat loss
9. Isolation Ball Valve (hot water rated): qty: ${nIsolation + 2} pcs: specify 20–25 mm, full bore, PTFE-seated, rated 120°C / PN16, at heater inlet/outlet and branch takeoffs
10. Check Valve (anti-siphon): qty: 1 pc: specify 20–25 mm, spring-loaded, PN16, at cold water inlet to heater
11. Angle Valve (fixture stop valve, chrome): qty: ${nFixtures} pcs: specify 15 mm (1/2 in), chrome-plated brass, 1 per hot water fixture connection
12. Pipe Supports and Hangers: qty: ${nSupports} sets: specify galvanized pipe clamp, CPVC-compatible cushion liner, spacing per Philippine Plumbing Code (max 1.2 m for CPVC)
13. ${isElectric ? 'Electrical Wiring, THHN Cu' : 'Gas Supply Piping, Schedule 40 Black Steel'}: qty: ${isElectric ? Math.round(pipeLen * 1.5) : Math.round(pipeLen * 0.5)} m: specify ${isElectric ? `size per PEC 2017 for ${recHeaterKW} kW load at ${heaterVoltage}, dedicated circuit, GFCI-protected` : `25 mm nominal, threaded fittings, leak tested at 1.5x working pressure, per PSME gas code`}
14. Floor Drain (near heater and T&P relief discharge): qty: 1 pc: specify 100 mm dia, chrome strainer, for T&P valve discharge line termination
15. Miscellaneous (Teflon tape, pipe cement, hangers, labels, access panel): qty: 1 lot: specify hot water pipe labels in red/orange per Philippine Plumbing Code

ARRAY 2: "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope: checked: true
- "2.0" Applicable Standards and Codes: checked: true (list: Philippine Plumbing Code (PPC), ASHRAE HVAC Applications Handbook Chapter 50 (Service Water Heating), NSF/PNS 65 potable water materials, ANSI/ASME for relief valves, ASSE 1017 thermostatic mixing valve, PEC 2017 for electrical connections, DOLE OSH, BPS/CHED equipment approval)
- "3.0" Materials: checked: true (glass-lined or SS storage tank rated ${tHot}°C, CPVC hot water pipe ASTM D2846, all valves PN16 and 120°C rated, insulation 19mm closed-cell foam with foil jacket)
- "4.1" Equipment Supply and Delivery: checked: true (submit heater performance data sheet, BPS/CHED approval certificate, tank warranty card, T&P valve certification before delivery)
- "4.2" Heater and Tank Installation: checked: true (specify floor-mounted or wall-mounted per equipment type, vibration isolation pad, minimum 600 mm clearance on service side, drip pan under tank connected to floor drain)
- "4.3" Hot Water Piping Works: checked: true (CPVC pipe at 20–25 mm nominal, all joints solvent-cemented per ASTM D2846, slope toward drain point, all pipes insulated 19mm closed-cell foam, pipe labelled red/orange per PPC)
- "4.4" Safety Devices: checked: true (T&P relief valve mandatory at heater, full-size 3/4 in discharge pipe to floor drain, no valves on discharge line, thermostatic mixing valve at distribution header set at ${Math.min(Number(tHot) - 5, 55)}°C, expansion tank on cold water feed in closed system)
- "4.5" Electrical Connections: checked: ${isElectric ? 'true' : 'false'} (dedicated circuit per PEC 2017, GFCI protection, disconnect within sight of heater, wire sized for ${recHeaterKW} kW at ${heaterVoltage})
- "4.6" Pressure Testing: checked: true (hydrostatic test at 2× working pressure (1,200 kPa) for 30 minutes, all joints and connections leak-free, document and submit test records before insulation)
- "4.7" Disinfection and Commissioning: checked: true (flush system, set thermostat to ${tHot}°C, verify recovery rate ${recoveryLPH} L/hr within ${recoveryHrs} hours, check T&P valve operation, verify TMV outlet temperature, submit commissioning report)
- "4.8" As-Built Documentation: checked: true
- "5.0" Inclusions: checked: false
- "6.0" Exclusions: checked: false (civil / structural works, plumbing fixtures beyond stop valves, electrical panel upgrade if required, gas meter or utility connection fees)
- "7.0" Warranty: checked: false (tank: 5-year manufacturer warranty on inner tank, 1-year on components; 1 year workmanship from acceptance)

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
${isStack ? 'Drain Stack: vertical riser' : `Pipe Slope: ${slopePct}% (${slopeMmPerM} mm/m fall)`}
Design Flow Capacity: ${capacityLS} L/s (Manning's equation, ${isStack ? 'full-bore' : 'half-full'})
Design Velocity: ${velocity} m/s (minimum 0.6 m/s for self-cleansing)

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1: "bom_items": Standard Philippine sanitary contractor Bill of Materials for drainage and sanitary piping system.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Drainage Pipe, ${pipeMat}: qty: ${pipeLen} m: specify ${pipeDiaMM} mm nominal dia, ASTM D3034 (PVC sewer) or PNS equivalent, in 3-m or 6-m lengths, for ${systemType}
2. Drainage Fittings: 45° Wye / Long-sweep 90° Elbows: qty: ${Math.max(4, Math.round(pipeLen / 5))} pcs: specify ${pipeDiaMM} mm, ${pipeMat}, sanitary drainage type (no T-fittings on horizontal drains), per Philippine Plumbing Code
3. Drainage Fittings: Sanitary Tee / Combination Wye: qty: ${nBranches} pcs: specify ${pipeDiaMM} mm, ${pipeMat}, for branch connections
4. Pipe Reducers / Couplings: qty: ${Math.max(2, Math.round(pipeLen / 10))} pcs: specify ${pipeDiaMM} mm, ${pipeMat}
5. Cleanout Plugs with Access Frame: qty: ${nCleanouts} sets: specify ${pipeDiaMM} mm, ${pipeMat}, at every change of direction, at base of each stack, and every 15 m of horizontal run per Philippine Plumbing Code
6. Floor Drain with P-Trap: qty: ${Math.max(2, Math.round(nFixtures / 4))} pcs: specify 100 mm or 150 mm dia, chrome ABS or cast iron strainer, integral P-trap, deep-seal 76 mm minimum water seal
7. P-Trap for Fixtures: qty: ${nFixtures} pcs: specify 32–50 mm dia as required per fixture, PVC, 76 mm minimum water seal, one per fixture without integral trap
8. Vent Pipe, ${pipeMat}: qty: ${Math.round(pipeLen * 0.6)} m: specify 50 mm or 75 mm nominal, ${pipeMat}, individual vents to each fixture or loop vent per Philippine Plumbing Code
9. Vent Fittings: 45° Elbows, Tees: qty: ${nVents * 2} pcs: specify 50–75 mm, ${pipeMat}, for vent stack connections
10. Stack Base Fitting (sanitary tee with 45° inlet): qty: ${isStack ? Math.max(1, Math.round(nFixtures / 10)) : 0} pc: specify ${pipeDiaMM} mm, for drain stack base to building drain: checked: ${isStack ? 'true' : 'false'}
11. Pipe Hangers and Supports: qty: ${nSupports} sets: specify perforated metal strap or clevis hanger, galvanized, spacing per Philippine Plumbing Code (max 1.2 m for PVC, 3 m for cast iron)
12. Pipe Sleeves through Slabs/Walls: qty: ${Math.max(4, nFixtures)} pcs: specify 25 mm oversize galvanized steel sleeve with fire-rated annular sealant at fire-rated assemblies
13. Roof Vent Flashing / Vent Terminal: qty: ${Math.max(1, Math.round(nVents / 2))} pc: specify lead or PVC flashing, for vent stack termination 150 mm minimum above roof, with bird screen
14. Grease Trap (if kitchen/canteen drainage): qty: 1 unit: specify flow-rated to match kitchen fixture DFU, pre-cast concrete or prefab HDPE, with access covers and basket strainer: checked: false (include if scope covers kitchen/canteen drainage)
15. Miscellaneous (solvent cement, pipe primer, anchors, pipe labels): qty: 1 lot: specify per ${pipeMat} jointing requirements; drainage pipes labelled per Philippine Plumbing Code

ARRAY 2: "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope: checked: true
- "2.0" Applicable Standards and Codes: checked: true (list: Philippine Plumbing Code (PPC): based on UPC/IPC, ASTM D3034 for PVC sewer pipe, PSME Code, National Building Code of the Philippines PD 1096, DOLE OSH Standards, DOH requirements for sanitary works)
- "3.0" Materials: checked: true (${pipeMat} pipe ASTM D3034 or PNS equivalent at ${pipeDiaMM} mm, all fittings sanitary drainage type: no sharp-turn tees on horizontal runs, all traps minimum 76 mm water seal)
- "4.1" Material Delivery and Inspection: checked: true (pipe and fittings inspected on delivery, ASTM/PNS compliance markings verified, damaged pipe rejected and replaced)
- "4.2" Pipe Installation: checked: true (specify jointing method for ${pipeMat}: solvent cement per ASTM D2564, pipe slope at ${slopePct}% (${slopeMmPerM} mm/m), all horizontal runs sloped continuously toward outlet, no back-grading, support at max 1.2 m spacing)
- "4.3" Trap and Cleanout Installation: checked: true (one trap per fixture, 76 mm minimum water seal, cleanouts at every direction change and stack base, accessible and within 600 mm of finished floor or wall per PPC, accessible cleanout cover flush with finished surface)
- "4.4" Vent System Installation: checked: true (individual or loop vents per PPC, vent stack terminated 150 mm minimum above roof and 300 mm from any window or opening, no vent connection within 300 mm below flood level rim of fixture)
- "4.5" Drain Stack and Building Drain": checked: ${isStack ? 'true' : 'false'} (drain stack plumb within 1:100, supported at each floor with riser clamp, base fitting at stack foot, stack extends as vent above highest branch)
- "4.6" Pipe Supports and Sleeves: checked: true (PVC hangers every 1.2 m, sleeves at all slab and wall penetrations, fire-rated annular sealant at fire-rated assemblies, no pipe resting on structural elements without proper saddle support)
- "4.7" Water Test (Air or Water Tightness Test): checked: true (water test: fill system to flood-level rim of highest fixture and hold 15 minutes, zero leaks, OR air test at 35 kPa for 15 minutes, document and submit test records)
- "4.8" Commissioning and Handover: checked: true (flush all lines, verify trap water seals, verify cleanout accessibility, check slope with spirit level at representative locations, submit as-built drawings)
- "4.9" As-Built Documentation: checked: true
- "5.0" Inclusions: checked: false
- "6.0" Exclusions: checked: false (civil / structural works including trenching for underground drainage, sewage treatment plant, septic tank unless specified, building permits and sanitary engineer PRC fees)
- "7.0" Warranty: checked: false (1 year workmanship from acceptance; leaks or blockages within warranty period remedied at Contractor's cost)

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
   Cover: Scope of Works, Design Basis (PPC occupancy method, P.D. 856), Tank Construction (RC or CHB, watertight), Inlet/Outlet/Baffle/Vent Configuration (PPC-compliant), Leachfield or Soakpit (DENR DAO 2016-08 effluent disposal), Testing and Commissioning (water tightness test: fill to overflow and hold 24 hours, zero visible leakage), Desludging and Maintenance Schedule (every ${desludgeYrs} years by licensed operator), Regulatory Compliance (DENR, LGU sanitary permit, DOH)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Water Softener Sizing BOM + SOW Agent ───────────────────────────────────

async function waterSoftenerBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name       || "Water Softener Project";
  const demandLpd      = inputs.demand_lpd          || results.demand_lpd          || "N/A";
  const inletHardness  = inputs.inlet_hardness_mg   || results.inlet_hardness_mg   || "N/A";
  const targetHardness = inputs.target_hardness     || results.target_hardness     || "50";
  const resinVolumeL   = results.resin_volume_L     ?? "N/A";
  const mineralTank    = results.mineral_tank_size  ?? "N/A";
  const brineTankL     = results.brine_tank_size_L  ?? "N/A";
  const saltKgRegen    = results.salt_kg_per_regen  ?? "N/A";
  const regenFreqDays  = results.regen_freq_days    ?? "N/A";
  const saltType       = results.salt_type          || inputs.salt_type || "NaCl";
  const resinType      = results.resin_type         || "Na-form strong acid cation exchange";
  const flowCheckLabel = results.flow_check_label   || results.flow_check || "N/A";
  const designFlowLpm  = results.design_flow_Lpm    ?? "N/A";
  const minFlowLpm     = results.min_flow_Lpm       ?? "N/A";
  const regenSystem    = results.regen_system       || inputs.regen_type || "Timer-initiated";

  const prompt = `You are a Philippine water treatment engineering expert. Generate a professional BOM and SOW for a WATER SOFTENER SYSTEM installation project.

PROJECT: ${project}
DAILY WATER DEMAND: ${demandLpd} L/day
INLET HARDNESS: ${inletHardness} mg/L as CaCO3
TARGET OUTLET HARDNESS: ≤ ${targetHardness} mg/L as CaCO3 (per PNS 1998 limit)
RESIN VOLUME: ${resinVolumeL} L (${resinType} resin)
MINERAL TANK SIZE: ${mineralTank}
BRINE TANK CAPACITY: ${brineTankL} L
SALT CONSUMPTION: ${saltKgRegen} kg ${saltType} per regeneration
REGENERATION FREQUENCY: every ${regenFreqDays} days
REGENERATION SYSTEM: ${regenSystem}
DESIGN FLOW: ${designFlowLpm} L/min: Flow Check: ${flowCheckLabel} (min service flow: ${minFlowLpm} L/min)
STANDARDS: NSF/ANSI 44 (Residential/Commercial Cation Exchange Softeners), WQA (Water Quality Association) Commercial Sizing Guidelines, PNS 1998 (Philippine National Standard for Drinking Water: hardness limit), Philippine Plumbing Code (PPC), DOH Drinking Water Regulations

Generate a JSON object with:
1. "bom_items": array of 15 items (each: description, specification, qty, unit, remarks, checked: true)
   Include:
   1. Water Softener Unit (mineral tank + resin + distributor assembly): qty: 1 unit: specify ${mineralTank} fiberglass mineral tank, ${resinVolumeL}L of NSF/ANSI 61 certified ${resinType} resin, internal distributor basket, top and bottom screen assemblies, NSF/ANSI 44 certified, rated for ${designFlowLpm} L/min service flow
   2. Automatic Control Valve (timer or meter-initiated): qty: 1 unit: specify ${regenSystem} regeneration controller, NSF/ANSI 61 certified, digital timer/meter-head, selectable regen cycles, compatible with mineral tank outlet
   3. Brine Tank with Salt Grid: qty: 1 unit: specify ${brineTankL}L polyethylene brine tank, safety float valve, brine line with flow control, salt storage platform/grid to prevent salt bridging, overflow connection, NSF/ANSI 61 rated
   4. Ion Exchange Resin (spare stock: 1st fill included in unit): qty: 25 kg: specify NSF/ANSI 61 certified ${resinType} resin, grain capacity per manufacturer spec, for first-year replenishment stock
   5. Salt (${saltType}, water softener grade): qty: ${Math.max(20, Math.round(Number(saltKgRegen) * 4))} kg: specify water softener grade (not road salt or rock salt), 99.5% purity minimum, in 10 or 25 kg bags
   6. Bypass Valve Assembly (3-valve bypass): qty: 1 set: specify inlet ball valve, outlet ball valve, bypass ball valve: 25mm or 32mm full-bore, PN16, food-grade safe, allows service without interrupting water supply
   7. Inlet/Outlet Pipe Connection Kit: qty: 1 lot: specify 25mm or 32mm PVC PN10, NSF/PNS 65 potable water rated, fittings for connection to existing supply line and distribution header
   8. Brine Line Tubing: qty: 3 m: specify 9.5mm (3/8") polyethylene tubing, food-grade, UV-stabilized, with compression fittings from brine tank to control valve
   9. Drain Line Tubing: qty: 5 m: specify 12mm or 16mm polyethylene or PVC drain tubing, from control valve to nearest floor drain, slope to drain per Philippine Plumbing Code
   10. Pressure Gauge (inlet and outlet): qty: 2 pcs: specify 0–700 kPa, 63mm dial, glycerin-filled, with 1/4" BSP connection: for monitoring pressure drop across resin bed
   11. Sediment Pre-Filter (5 micron): qty: 1 unit: specify 10" clear housing, 5-micron polypropylene sediment cartridge, 25mm inlet/outlet, wrench included, NSF/ANSI 42 rated: install upstream of softener to protect resin from particulate fouling
   12. Backwash Filter (if sediment > 5 NTU): qty: 1 unit: specify automatic backwash sediment filter, sized for system flow, multimedia or sand media: checked: ${Number(inletHardness) > 300 ? 'true' : 'false'} (include if inlet total suspended solids is high)
   13. Water Quality Test Kit (hardness, TDS): qty: 1 set: specify digital TDS meter + titration hardness test kit (as CaCO3), for pre-commissioning and periodic post-regeneration hardness verification
   14. Pipe Supports, Hangers, Anchors: qty: 1 lot: specify galvanized pipe clamps, wall anchors for inlet/outlet piping and bypass assembly
   15. Miscellaneous (Teflon tape, PVC pipe cement, pipe labels for SOFTENED WATER and HARD WATER BYPASS lines, warning signs): qty: 1 lot

2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover:
   - "1.0" General Scope (supply, install, commission water softener system for ${demandLpd} L/day demand at ${inletHardness} mg/L inlet hardness, outlet ≤ ${targetHardness} mg/L as CaCO3)
   - "2.0" Applicable Standards and Codes (NSF/ANSI 44, NSF/ANSI 61, WQA, PNS 1998 hardness limit, Philippine Plumbing Code, DOH drinking water regulations, DOLE OSH)
   - "3.0" Equipment Supply and Delivery (NSF/ANSI 44 certified unit, factory-tested, manufacturer data sheets and resin specification to be submitted for Engineer's approval before procurement)
   - "4.1" Softener Unit Installation (positioning on level concrete pad, inlet/outlet orientation, minimum clearances for salt loading and service access: 600mm minimum side clearance, bracing for earthquake zone)
   - "4.2" Bypass Valve and Plumbing Connections (3-valve bypass loop installation, pre-filter installation upstream, drain line routing to floor drain with air gap, brine line connection)
   - "4.3" Control Valve Programming (timer/meter setting for ${regenFreqDays}-day regen cycle, brine draw time, backwash time, salt dose at ${saltKgRegen} kg per regen, delayed regen during off-peak hours: typically 2:00-4:00 AM)
   - "5.0" Testing and Commissioning (pre-commissioning hardness test of inlet water, resin bed conditioning procedure: first 3 regen cycles to fully exchange resin, post-commissioning hardness test of outlet water: must read ≤ ${targetHardness} mg/L, pressure drop measurement across resin bed, water quality report to be submitted)
   - "6.0" Maintenance and Handover (salt replenishment schedule every ${regenFreqDays} days × number of regen cycles per refill period, annual resin inspection, quarterly pre-filter cartridge change, 1-year warranty documentation, O&M manual handover, operator training for salt loading and bypass procedure)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Water Treatment System BOM + SOW Agent ──────────────────────────────────

async function waterTreatmentBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name      || "Water Treatment System Project";
  const demandLpd      = inputs.demand_lpd         || results.demand_lpd         || "N/A";
  const rawSource      = inputs.raw_source         || "Unknown";
  const turbidityNtu   = inputs.turbidity_ntu      ?? "N/A";
  const ironMg         = inputs.iron_mg            ?? "N/A";
  const bacteriaConcern = inputs.bacteria_concern  || "Yes";
  const intendedUse    = inputs.intended_use       || "Potable Water";
  const peakFactor     = inputs.peak_factor        || 1.5;
  const peakFlowLpm    = results.peak_flow_Lpm     ?? "N/A";
  const filterDiaMm    = results.filter_vessel_dia_mm ?? "N/A";
  const filterAreaM2   = results.filter_area_m2    ?? "N/A";
  const filterType     = results.filter_type       || "Multimedia";
  const needsCoag      = results.needs_coag_floc   ?? false;
  const needsIron      = results.needs_iron_removal ?? false;
  const needsDisinf    = results.needs_disinfection ?? true;
  const disinfMethod   = results.disinfection_method || "Chlorination";
  const cl2DoseMg      = results.cl2_dose_mg_L     ?? "N/A";
  const naoclLpd       = results.naocl_daily_L     ?? "N/A";
  const alumDoseMg     = results.alum_dose_mg_L    ?? "N/A";
  const storageTankL   = results.storage_tank_L    ?? "N/A";
  const pnsStatus      = results.pns_compliance_status || "REVIEW";
  const trainSteps     = (results.train_steps as string[]) || [];

  const trainSummary = trainSteps.map((s, i) => `Step ${i+1}: ${s}`).join('; ');

  const prompt = `You are a Philippine water treatment engineering expert. Generate a professional BOM and SOW for a WATER TREATMENT SYSTEM installation project.

PROJECT: ${project}
RAW WATER SOURCE: ${rawSource}
DAILY DEMAND: ${demandLpd} L/day
PEAK FLOW: ${peakFlowLpm} L/min
INLET TURBIDITY: ${turbidityNtu} NTU
INLET IRON: ${ironMg} mg/L
BACTERIA CONCERN: ${bacteriaConcern}
INTENDED USE: ${intendedUse}
PEAK FACTOR: ${peakFactor}
TREATMENT TRAIN: ${trainSummary}
FILTER: ${filterType} filter, ${filterDiaMm}mm vessel, ${filterAreaM2} m² bed area
COAGULATION/FLOCCULATION REQUIRED: ${needsCoag}
IRON REMOVAL REQUIRED: ${needsIron}
DISINFECTION REQUIRED: ${needsDisinf}, Method: ${disinfMethod}
CHLORINE DOSE: ${cl2DoseMg} mg/L, NaOCl consumption: ${naoclLpd} L/day (10% solution)
ALUM DOSE (if coag): ${alumDoseMg} mg/L
STORAGE TANK: ${storageTankL} L
PNS 1998 COMPLIANCE STATUS: ${pnsStatus}
STANDARDS: PNS 1998 (Philippine National Standard for Drinking Water), DOH Drinking Water Regulations, WHO Guidelines 4th Edition, AWWA Design of Water Treatment Facilities, NSF/ANSI 61, Philippine Plumbing Code (PPC), DOLE OSH

Generate a JSON object with:
1. "bom_items": array of 18 items (each: description, specification, qty, unit, remarks, checked: true)
   Include these items in order:
   1. Raw Water Pump (if source is borehole/deep well): centrifugal submersible pump, capacity ${peakFlowLpm} L/min, head per site survey, SS 304 impeller, NSF/ANSI 61 wetted parts: qty: 1 unit (mark as conditional if source is municipal/surface)
   2. Raw Water Storage/Break Tank: ${Math.round(Number(storageTankL) * 0.5 || 500)}L polyethylene or RC tank, NSF/ANSI 61 rated, inlet float valve, overflow and drain outlets: qty: 1 unit
   3. ${filterType} Filter Vessel: ${filterDiaMm}mm FRP pressure vessel, rated 6 bar, top distributor, bottom collector lateral assembly, ${filterType === 'Greensand' ? 'greensand media 900mm bed depth, silica underbedding 300mm' : 'multimedia (anthracite, sand, gravel) 750mm bed depth'}, automatic backwash valve: qty: 1 unit
   4. ${needsIron ? 'Greensand Iron Removal Filter: ' + filterDiaMm + 'mm FRP vessel, greensand media, KMnO4 regenerant feed system, 900mm bed depth: qty: 1 unit' : 'Sediment Pre-Filter (5 micron cartridge): 20" housing, polypropylene sediment cartridge, NSF/ANSI 42, 25–50mm inlet/outlet: qty: 1 unit'}
   5. ${needsCoag ? 'Coagulation/Flocculation Tank: GRP or HDPE tank, alum dosing point at inlet, mechanical stirrer/paddle flocculator, sized for 20-minute retention time at peak flow: qty: 1 unit' : 'Backwash Controller and Automatic Valve Assembly: timer-controlled automatic backwash valve, digital controller, compatible with filter vessel: qty: 1 set'}
   6. ${needsDisinf ? (disinfMethod.includes('UV') ? 'UV Disinfection Unit: 40 mJ/cm² minimum dose, SS 316L chamber, quartz sleeve, electronic ballast, flow-proportional control, NSF/ANSI 55 Class A certified: qty: 1 unit' : 'Chemical Dosing Pump (Chlorine): diaphragm-type metering pump, output ' + peakFlowLpm + ' L/min at rated pressure, PVDF wetted parts, NSF/ANSI 61 rated, adjustable stroke: qty: 1 unit') : 'Flow Meter: electromagnetic or paddle-wheel type, 25–50mm, pulse output for dosing control: qty: 1 unit'}
   7. Chemical Dosing Tank (NaOCl): ${Math.max(50, Math.round(Number(naoclLpd) * 7 || 100))}L HDPE chemical-grade tank, vent cap, level indicator, lockable lid, for 7-day NaOCl storage at ${naoclLpd} L/day: qty: 1 unit
   8. ${needsCoag ? 'Alum (Aluminum Sulfate) Solution Tank: HDPE 100L tank, mechanical agitator, dosing pump connection, spill containment tray: qty: 1 unit' : 'Chemical Injection Quill and Static Mixer: SS 316L injection quill, pipe mixer for rapid chlorine dispersion: qty: 1 set'}
   9. Activated Carbon Filter (post-treatment): ${filterDiaMm}mm FRP vessel, granular activated carbon (GAC) 600mm bed depth, EBCT 10 min, NSF/ANSI 61, automatic backwash: qty: ${Number(turbidityNtu || 0) > 5 ? '1 unit (turbidity > 5 NTU: required)' : '1 unit (optional: recommended for taste/odor control)'}
   10. Treated Water Storage Tank: ${storageTankL}L capacity (1-day demand), polyethylene or RC construction, covered, NSF/ANSI 61 rated, inlet float valve, overflow, drain, man-way for cleaning: qty: 1 unit
   11. Transfer/Booster Pump (treated water to distribution): centrifugal pump, capacity ${peakFlowLpm} L/min at distribution pressure, SS 304 impeller, NSF/ANSI 61, with pressure tank 24L minimum: qty: 1 set
   12. Pressure Gauges (inlet, interstage, outlet): 0–700 kPa, 63mm glycerin-filled, 1/4" BSP: qty: 4 pcs
   13. Water Quality Test Kit: digital turbidity meter (NTU), colorimetric iron test kit, free chlorine DPD test kit (0–5 mg/L), pH meter: qty: 1 set (for commissioning and routine monitoring)
   14. Interconnecting Pipework: 32–50mm uPVC PN10 or SS 304 piping between treatment stages, NSF/PNS 65 rated, ball valves at each unit inlet/outlet for isolation, union fittings for easy service: qty: 1 lot
   15. Chemical Room Equipment: spill containment bund (GRP or HDPE), eyewash station, PPE hooks, chemical warning labels, ventilation louver: qty: 1 lot (DOLE OSH compliance)
   16. Electrical and Control Panel: IP55 enclosure, ON/OFF controls for all pumps, alarm for high/low level, hour meters, properly rated MCBs per PEC 2017: qty: 1 lot
   17. Pipe Supports, Anchors, and Fittings: galvanized pipe clamps, wall anchors, reducers, couplings for complete installation: qty: 1 lot
   18. Miscellaneous (Teflon tape, PVC cement, pipe labels per PNS 65 color code, safety signs, cable ties): qty: 1 lot

2. "sow_sections": array of 9 sections (each: section_no, title, content)
   Cover:
   - "1.0" General Scope (design, supply, install, test, and commission complete Water Treatment System for ${demandLpd} L/day from ${rawSource} source, producing outlet water compliant with PNS 1998 / DOH standards: turbidity ≤ 1 NTU potable, iron ≤ 0.3 mg/L, free chlorine 0.2–0.5 mg/L at point of use)
   - "2.0" Applicable Standards (PNS 1998, DOH Administrative Order on Water Quality, WHO 4th Edition Guidelines, AWWA design standards, NSF/ANSI 61, Philippine Plumbing Code, DOLE OSH chemical safety, PEC 2017 for electrical)
   - "3.0" Equipment Supply and Submittal Requirements (all wetted equipment NSF/ANSI 61 certified; submit manufacturer data sheets, pressure vessel certificates, media gradation analysis, and NSF certificates for Engineer's approval before procurement; raw water quality analysis report from DOH-accredited laboratory required before design finalization)
   - "4.1" Civil and Structural Works (concrete pad for filter vessels and tanks: minimum 150mm thick RC slab; chemical room with 300mm bunded floor, drain to sump, forced ventilation minimum 10 ACH; all anchor bolts per NSCP seismic zone)
   - "4.2" Treatment Equipment Installation (filter vessel installation on level pad, minimum 1.0m service clearance on all sides; backwash drain to be piped to waste/drainage; chemical dosing lines labeled; injection points upstream of static mixer; storage tanks to be covered and vented through insect screen)
   - "4.3" Disinfection and Chemical Dosing System (${needsDisinf ? `chlorine dosing set at ${cl2DoseMg} mg/L to achieve CT ≥ 30 mg·min/L; free chlorine residual target 0.5 mg/L post-contact tank; NaOCl stored in locked chemical room; dose to be verified by daily grab sample using DPD test kit` : 'disinfection not required: install sampling tap at treated water outlet for periodic water quality verification'})
   - "5.0" Testing and Commissioning (pre-commissioning raw water quality test by DOH-accredited laboratory; 72-hour continuous operation test; daily grab samples for turbidity, iron, pH, free chlorine during commissioning; final treated water quality report to be submitted confirming PNS 1998 compliance before handover)
   - "6.0" Safety and Environmental Compliance (DOLE OSH requirements for chemical handling: chlorine/alum/KMnO4 SDS to be posted in chemical room; spill containment capacity ≥ 110% of largest chemical container; backwash wastewater to be discharged to DENR-compliant disposal point: not directly to drainage without settlement; operator must hold TESDA or DOH water treatment certificate)
   - "7.0" Maintenance, Training, and Handover (media replacement schedule per manufacturer spec; monthly backwash frequency check; weekly water quality monitoring log; quarterly chemical stock inspection; annual pressure vessel inspection; 1-year warranty on all equipment; O&M manual; operator training minimum 8 hours covering backwash procedure, chemical dosing, daily water quality testing, and emergency shutdown)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Wastewater Treatment (STP) BOM + SOW Agent ──────────────────────────────

async function wastewaterSTPBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name      || "Wastewater Treatment Plant (STP)";
  const flowM3Day      = results.flow_m3_day       ?? inputs.flow_direct_m3d ?? "N/A";
  const population     = inputs.population         || "N/A";
  const bodIn          = inputs.bod_influent        ?? "N/A";
  const bodOut         = inputs.bod_effluent        ?? "N/A";
  const bodRemPct      = results.bod_removal_pct    ?? "N/A";
  const aerVolM3       = results.aeration_vol_m3    ?? "N/A";
  const aerHrtHr       = results.aeration_hrt_hr    ?? "N/A";
  const aerDims        = results.aeration_dims      ?? "N/A";
  const srtDays        = inputs.srt_days            ?? "N/A";
  const mlssMgL        = inputs.mlss_mg_l           ?? "N/A";
  const blowerM3Min    = results.blower_recommended_m3_min ?? "N/A";
  const blowerKw       = results.blower_kw          ?? "N/A";
  const primDiaM       = results.prim_dia_m         ?? "N/A";
  const primAreaM2     = results.prim_area_m2       ?? "N/A";
  const secDiaM        = results.sec_dia_m          ?? "N/A";
  const secAreaM2      = results.sec_area_m2        ?? "N/A";
  const sludgeKgDay    = results.sludge_kg_day      ?? "N/A";
  const sludgeM3Day    = results.sludge_m3_day      ?? "N/A";
  const disinfection   = String(inputs.disinfection || "Chlorination");
  const cl2DoseMgL     = results.cl2_dose_mg_l      ?? "N/A";
  const naoclLpd       = results.naocl_lpd          ?? "N/A";
  const contactTankM3  = results.contact_tank_m3    ?? "N/A";
  const peakFlowLps    = results.peak_flow_lps      ?? "N/A";
  const denrStatus     = results.denr_status        || "REVIEW";
  const o2TotalKgDay   = results.o2_total_kg_day    ?? "N/A";

  const prompt = `You are a Philippine sanitary and mechanical engineering expert. Generate a professional BOM and SOW for a WASTEWATER TREATMENT PLANT (STP) construction project.

PROJECT: ${project}
DESIGN POPULATION: ${population} persons
AVERAGE DAILY FLOW (ADF): ${flowM3Day} m³/day
PEAK FLOW: ${peakFlowLps} L/s (1.5× ADF)
BOD INFLUENT / EFFLUENT: ${bodIn} mg/L → ${bodOut} mg/L (${bodRemPct}% removal)
PROCESS: Conventional Activated Sludge
SRT / MLSS: ${srtDays} days / ${mlssMgL} mg/L
PRIMARY CLARIFIER: ${primDiaM} m diameter, ${primAreaM2} m² surface area
AERATION TANK: ${aerVolM3} m³ (HRT ${aerHrtHr} hr), Dimensions ${aerDims}
TOTAL O₂ DEMAND: ${o2TotalKgDay} kg O₂/day
BLOWER: ${blowerM3Min} m³/min @ ${blowerKw} kW (with 20% safety factor)
SECONDARY CLARIFIER: ${secDiaM} m diameter, ${secAreaM2} m² surface area
SLUDGE PRODUCTION: ${sludgeKgDay} kg dry solids/day (${sludgeM3Day} m³/day at 1% DS)
DISINFECTION: ${disinfection}${disinfection === 'Chlorination' ? `: Cl₂ dose ${cl2DoseMgL} mg/L, NaOCl (10%) ${naoclLpd} L/day, contact tank ${contactTankM3} m³` : ': UV 40 mJ/cm²'}
DENR DAO 2016-08 STATUS: ${denrStatus}
STANDARDS: DENR DAO 2016-08 (BOD ≤ 30 mg/L, TSS ≤ 50 mg/L, pH 6–9), DOH PD 856, Metcalf & Eddy (5th Ed.), PSME Code, DOLE OSH

Generate a JSON object with:
1. "bom_items": array of 20 items (each: description, specification, qty, unit, remarks, checked: true)
   Include these items in order:
   1. Influent Pump/Lift Station: submersible sewage pump, capacity ${peakFlowLps} L/s, 15mm solids handling, SS 316 impeller, duplex (duty+standby), IP68, with level float controls and auto-alternating panel: qty: 2 units (duty+standby)
   2. Bar Screen / Fine Screen: manual or mechanical bar screen, 25mm spacing, SS 316, with scum/screenings basket, removable for cleaning: qty: 1 unit
   3. Grit Chamber / Grit Trap: horizontal flow grit chamber, sized for peak flow ${peakFlowLps} L/s, SS 316L weir plate, manual cleanout: qty: 1 unit
   4. Primary Clarifier Tank (RC): ${primDiaM} m diameter circular RC settling tank, ${primAreaM2} m² surface area, 3.5 m SWD, hopper bottom, scum baffle, effluent weir, sludge drain valve: qty: 1 unit
   5. Aeration Tank (RC): ${aerDims} RC aeration basin, volume ${aerVolM3} m³, internal baffles for plug flow, concrete lined with epoxy, overflow weir to secondary clarifier: qty: 1 unit
   6. Fine Bubble Diffuser System: EPDM membrane disc diffusers, OTE ≥ 8% (standard conditions), grid layout at tank floor, SS 316 air distribution headers, HDPE drop pipes: qty: 1 lot (sized for ${aerVolM3} m³ tank)
   7. Blower Unit (Duty+Standby): rotary lobe or screw blower, capacity ${blowerM3Min} m³/min each at 50 kPa discharge pressure, ${blowerKw} kW motor with VFD, IP55, silencer, check valve, pressure gauge: qty: 2 units (duty+standby)
   8. Blower Control Panel: IP55 enclosure, auto-alternating duty/standby, DO sensor input for blower modulation, hour meters, fault alarm: qty: 1 lot
   9. Secondary Clarifier Tank (RC): ${secDiaM} m diameter circular RC clarifier, ${secAreaM2} m² surface area, 4.0 m SWD, peripheral weir, sludge hopper, RAS sump: qty: 1 unit
   10. Return Activated Sludge (RAS) Pump: submersible or dry-pit centrifugal, capacity 50–100% of ADF (${Math.round(Number(flowM3Day) * 0.75 / 24 * 1000 / 60 || 5)} L/min nominal), SS 316 wetted parts, duplex: qty: 2 units (duty+standby)
   11. Waste Activated Sludge (WAS) Pump: progressive cavity or peristaltic pump, capacity ${sludgeM3Day} m³/day (${Math.round(Number(sludgeM3Day) / 24 * 1000 / 60 || 2)} L/min), SS 316: qty: 1 unit
   12. Sludge Holding Tank (RC): min 20 m³ capacity RC tank, covered, dewatering drain, overflow, level indicator: qty: 1 unit
   13. ${disinfection === 'Chlorination' ? `Chlorination Contact Tank (RC): ${contactTankM3} m³ RC baffled contact tank (30-min HRT at peak flow), SS 316 baffles: qty: 1 unit` : 'UV Disinfection Channel: stainless steel UV channel, 40 mJ/cm² dose at peak flow, NSF/ANSI 55 Class A, electronic ballast, quartz sleeves, flow-proportional control: qty: 1 unit'}
   14. ${disinfection === 'Chlorination' ? `Chemical Dosing System (NaOCl): peristaltic metering pump ${naoclLpd} L/day capacity, HDPE dosing tank ${Math.max(50, Math.round(Number(naoclLpd) * 7 || 100))}L (7-day storage), injection quill, flow meter: qty: 1 set` : 'Post-Chlorination Residual Dosing (backup): small NaOCl dosing pump for residual maintenance, 20L HDPE tank: qty: 1 set'}
   15. Effluent Flow Meter: electromagnetic flow meter, flanged, sized for peak flow, 4–20mA output for SCADA, SS 316 electrodes: qty: 1 unit
   16. Interconnecting Pipework: uPVC or DI pipe PN10, all process lines between tanks, sewage-grade fittings, isolation gate/ball valves at each unit inlet/outlet, air release valves on force mains: qty: 1 lot
   17. Electrical and SCADA Panel: MCC panel IP55, auto/manual controls for all pumps and blowers, alarm annunciator (high level, pump fault, blower fault, DO alarm), hour meters, energy meter: qty: 1 lot (PEC 2017 compliant)
   18. Civil and Structural Works: all RC tank construction per structural drawings, epoxy lining of all wet surfaces, access ladders, grating covers, pipe supports, earthworks, site drainage, perimeter fencing: qty: 1 lot
   19. Online Water Quality Monitor: DO meter (in aeration tank), pH/ORP meter (in effluent), with continuous display and alarm outputs: qty: 1 set
   20. Miscellaneous: pipe labels, valve tags, safety signs (confined space, chemical hazard), PPE hooks, eyewash station, O&M tool kit: qty: 1 lot

2. "sow_sections": array of 10 sections (each: section_no, title, content)
   Cover:
   - "1.0" General Scope (design, supply, construct, install, test, and commission complete Wastewater Treatment Plant for ${flowM3Day} m³/day ADF: achieving DENR DAO 2016-08 Class D effluent: BOD ≤ ${bodOut} mg/L, TSS ≤ 50 mg/L, pH 6–9)
   - "2.0" Applicable Standards and Permits (DENR DAO 2016-08: ECC and Sewage Discharge Permit required before commissioning; DOH PD 856: Sanitary Permit from LGU; PSME Code for mechanical equipment; DOLE OSH for confined space and chemical safety; DENR-accredited laboratory for effluent testing)
   - "3.0" Civil and Structural Works (all RC tanks watertight: water-fill test required; epoxy lining of all wet surfaces; minimum 150 mm RC slab for all equipment pads; confined space access provisions: hatches, ventilation, safety ladders; seismic zone design per NSCP; perimeter fencing)
   - "4.1" Preliminary Treatment Installation (bar screen, grit chamber, and lift station installation; screenings collection and disposal; grit washout drainage)
   - "4.2" Primary Treatment: Clarifier (primary clarifier construction and installation; sludge draw-off piping to sludge holding tank; scum removal connection; effluent weir leveling: must be within ±3mm horizontal)
   - "4.3" Biological Treatment: Aeration Tank and Blowers (aeration tank construction; diffuser grid installation: all EPDM membrane discs at uniform spacing; blower installation on vibration-isolated base; blower discharge piping sized for ${blowerM3Min} m³/min; VFD commissioning and DO setpoint configuration at 2.0 mg/L)
   - "4.4" Secondary Clarifier and Sludge Return (secondary clarifier construction; RAS pump installation and commissioning: initial RAS/Q ratio 0.5; WAS pump connection to sludge holding tank; sludge wasting schedule per ${srtDays}-day SRT)
   - "4.5" Disinfection and Effluent Discharge (${disinfection === 'Chlorination' ? `contact tank construction; NaOCl dosing pump commissioning at ${cl2DoseMgL} mg/L dose; target effluent residual 0.2–0.5 mg/L free chlorine; chlorine contact time minimum 30 min` : `UV unit installation; minimum 40 mJ/cm² dose verification at peak flow; quartz sleeve cleaning schedule: monthly`}; effluent flow meter calibration; effluent discharge to approved receiving water body with DENR Sewage Discharge Permit)
   - "5.0" Testing and Commissioning (civil watertightness test before backfill: all RC tanks; mechanical run test for all pumps and blowers: 4-hour continuous; biological start-up: seed sludge from existing STP or commercial MLSS activator; 72-hour continuous STP operation test with daily effluent sampling; DENR-accredited lab analysis for BOD, TSS, pH, DO: results to be submitted as commissioning report; blower DO control calibration)
   - "6.0" Regulatory Compliance, Training, and Handover (DENR ECC compliance documentation; DOH Sanitation Permit renewal support; operator training minimum 16 hours: covering daily operations, DO control, sludge wasting, chemical handling, confined space entry, DENR sampling procedures; O&M manual including maintenance schedules for diffusers, RAS pumps, blowers, and UV/chlorination system; sludge disposal agreement with DOH/DENR-licensed hauler; 1-year warranty on all mechanical equipment; monthly effluent water quality monitoring log for DENR compliance)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Storm Drain / Stormwater BOM + SOW Agent ────────────────────────────────

async function stormDrainBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project       = inputs.project_name    || "Storm Drain / Stormwater";
  const areaMode      = inputs.area_mode       || "single";
  const totalAreaHa   = results.total_area_ha  ?? inputs.area_ha ?? "N/A";
  const compositeC    = results.composite_c    ?? inputs.c_value ?? "N/A";
  const returnPeriod  = results.return_period_yr ?? inputs.return_period ?? 10;
  const intensityMmhr = results.intensity_mmhr ?? inputs.intensity_mmhr ?? 75;
  const tcMin         = results.tc_min         ?? inputs.tc_min ?? 15;
  const slopePct      = results.slope_pct      ?? inputs.slope_pct ?? 0.5;
  const pipeMaterial  = results.pipe_material  ?? inputs.pipe_material ?? "uPVC";
  const manningN      = results.manning_n      ?? inputs.manning_n ?? 0.011;
  const dRequiredMm   = results.d_required_mm  ?? "N/A";
  const dSelectedMm   = results.d_selected_mm  ?? "N/A";
  const designFlowLps = results.design_flow_lps ?? "N/A";
  const designFlowM3s = results.design_flow_m3s ?? "N/A";
  const qCapLps       = results.q_capacity_lps  ?? "N/A";
  const fullPipeVel   = results.full_pipe_vel_ms ?? "N/A";
  const maxVel        = results.max_velocity_ms  ?? "N/A";
  const velCheck      = results.velocity_check   || "REVIEW";
  const flowRatioPct  = results.flow_ratio_pct   ?? "N/A";

  const prompt = `You are a Philippine civil and sanitary engineering expert. Generate a professional BOM and SOW for a STORM DRAIN / STORMWATER DRAINAGE construction project.

PROJECT: ${project}
CATCHMENT AREA: ${totalAreaHa} ha (${areaMode === 'composite' ? 'composite multi-zone' : 'single zone'})
COMPOSITE RUNOFF COEFFICIENT (C): ${compositeC}
RETURN PERIOD: ${returnPeriod}-year storm event
RAINFALL INTENSITY: ${intensityMmhr} mm/hr at tc = ${tcMin} min (PAGASA IDF)
METHOD: Rational Method: Q = C×i×A/360
DESIGN FLOW: ${designFlowM3s} m³/s (${designFlowLps} L/s)
REQUIRED PIPE DIAMETER: ${dRequiredMm} mm (calculated)
SELECTED PIPE DIAMETER: ${dSelectedMm} mm (DPWH standard, minimum 300 mm)
PIPE MATERIAL: ${pipeMaterial} (Manning's n = ${manningN})
PIPE SLOPE: ${slopePct}%
PIPE CAPACITY (full-flow): ${qCapLps} L/s
FLOW VELOCITY: ${fullPipeVel} m/s (DPWH limit: 0.6–${maxVel} m/s): ${velCheck}
FLOW RATIO: ${flowRatioPct}% of full capacity
STANDARDS: DPWH Flood Control Design Manual, PAGASA IDF, DPWH Blue Book, NSCP, PNS/ISO pipe standards

Generate a JSON object with:
1. "bom_items": array of 16 items (each: description, specification, qty, unit, remarks, checked: true)
   Include these items in order:
   1. Storm Drain Pipe: ${dSelectedMm} mm nominal diameter ${pipeMaterial} pipe, PN6 or PN10 (pressure rating per site conditions), DPWH-approved, socket and spigot jointing with rubber ring: qty: per linear meter of drain run (Contractor to quantify from layout drawing)
   2. Catch Basin / Storm Inlet: precast RC catch basin, 600×600 mm (minimum), 150 mm RC walls, haunched base, mortar-bedded to pipe invert, kerb inlet or grated top: qty: as per layout (typically 1 per 20–30 m spacing in paved areas)
   3. Grated Cover / CI Grating: cast iron heavy-duty grating, 600×600 mm, HS20 traffic-rated where in vehicular areas, anti-theft bolted frame: qty: matching catch basin count
   4. Manhole (RC Type): 1200 mm diameter RC manhole, 150 mm wall, benched invert, step irons, min 1.2 m depth, precast or in-situ RC construction per DPWH Standard Drawing: qty: at all junctions and max 50 m spacing along drain run
   5. Manhole Frame and Cover (CI/DI): cast iron or ductile iron frame and lid, 600 mm clear opening, HS20-rated where in road, anti-theft bolt: qty: matching manhole count
   6. Concrete Pipe Bedding and Surround: Class B granular bedding (25mm crushed gravel), 150 mm bed below pipe, 300 mm surround to pipe springline, compacted in 150 mm layers: qty: per linear meter
   7. Pipe Jointing Material: rubber ring push-fit gaskets (factory-supplied with pipe), joint lubricant, HDPE or uPVC coupler fittings at bends and branches: qty: 1 lot
   8. Concrete Headwall / Outfall Structure: RC headwall at pipe outfall, 200 mm RC, weep holes, toe slab, riprap energy dissipation pad (0.5 m × pipe dia.) at downstream end: qty: 1 unit per outfall
   9. Riprap / Erosion Protection: 150–300 mm hand-placed riprap at outfall and along open channel transitions, geotextile filter fabric underlayer: qty: as required at outfall
   10. Excavation and Trenching: machine excavation in suitable ground, trench width = pipe OD + 600 mm, shoring if > 1.5 m deep, stockpile and haul spoil: qty: per linear meter (volume per trench dimensions)
   11. Dewatering: submersible pump, wellpoint or sump dewatering during pipe laying in wet ground, continuous monitoring: qty: 1 lot (provisional: per actual site conditions)
   12. Trench Backfill and Compaction: selected fill (CBR ≥ 15%), compacted in 200 mm layers at 95% Standard Proctor Density, proctor tests at 50 m intervals: qty: per linear meter
   13. Road / Pavement Reinstatement: reinstatement of existing road pavement (asphalt or concrete) over trench zone per DPWH standard repair detail, matching existing pavement thickness: qty: per linear meter in paved areas
   14. Inlet Protection / Trash Guard: 50 mm SS 304 bar grating trash guard at pipe inlet, bolted to headwall or catch basin to prevent debris blockage: qty: 1 unit per inlet structure
   15. CCTV Pipe Inspection (post-construction): CCTV survey of completed drain run after backfill to verify line, level, and joint integrity before final acceptance: qty: per linear meter of drain installed
   16. Miscellaneous: pipe markers (every 20 m), manhole numbering plaques, as-built survey, temporary diversion drain during construction, site safety signage, spoil disposal: qty: 1 lot

2. "sow_sections": array of 9 sections (each: section_no, title, content)
   Cover:
   - "1.0" General Scope (design, supply, and construct a complete storm drain system to convey the ${returnPeriod}-year design storm runoff of ${designFlowLps} L/s from a ${totalAreaHa} ha catchment; all work in accordance with DPWH Flood Control Design Manual and DPWH Blue Book Standard Specifications; contractor shall verify all quantities from final layout drawings: BOM is for planning purposes only)
   - "2.0" Applicable Standards and Permits (DPWH Drainage Design Manual; DPWH Blue Book Standard Specifications for Highways, Bridges and Airports; PAGASA IDF data; NSCP; PNS/ISO 4435 for uPVC sewer pipes; LGU Building Permit and DPWH permit where crossing national road; environmental compliance for discharge to receiving water body per RA 9275 Clean Water Act)
   - "3.0" Site Investigation and Setting Out (topographic survey and as-built check; hydraulic grade line confirmation: invert levels to be set to achieve minimum ${slopePct}% slope throughout; confirm soil classification and groundwater level before finalsing trench and shoring design; all manholes to be surveyed and referenced to benchmark)
   - "4.1" Pipe Laying and Jointing (trench excavation to designed invert levels; Class B granular bedding compacted to 95% SPD before pipe laying; ${dSelectedMm} mm ${pipeMaterial} pipe laid true to line and grade: maximum 5 mm horizontal deviation per 3 m rod; rubber ring joints lubricated per manufacturer instructions; no open-cut joints permitted; post-laying alignment check by laser or string line before backfill)
   - "4.2" Catch Basins and Manholes (precast or in-situ RC catch basins and manholes constructed per DPWH standard drawings; invert benching mortar-finished to direct flow; all lid frames grouted level; CI grating and manhole covers to be HS20-rated in vehicular areas; step irons in all manholes at 300 mm vertical spacing; joint between precast sections to be bituminous-sealed watertight)
   - "4.3" Outfall and Erosion Protection (RC headwall constructed at all outfall locations; riprap energy dissipation pad min 1.5× pipe diameter length on receiving channel bed; geotextile filter fabric under all riprap; outfall invert to be at or above ordinary high-water level of receiving watercourse; if below HWL, provide flap gate to prevent backflow)
   - "4.4" Backfill, Compaction, and Pavement Reinstatement (selected fill backfill in 200 mm compacted layers; 95% SPD throughout; field density test every 50 m minimum; road pavement reinstatement to match existing layer-by-layer: subbase, base course, and wearing course; asphalt to be hot-mix ACI, concrete to be minimum 3000 psi; line-marking reinstated where applicable)
   - "5.0" Testing and Inspection (CCTV survey of all completed drain runs after backfill: contractor to provide CCTV report with video and defect log; any misaligned joints, displaced pipes, or infiltration to be repaired before acceptance; water-test all manhole benching and catch basin bases: no visible seepage after 30 min; as-built survey of all inverts and manhole rim levels to be submitted within 5 days of final section completion)
   - "6.0" Regulatory Compliance, Safety, and Handover (trench safety per DOLE OSH Standards: shoring mandatory for depths > 1.2 m; traffic management plan for works on or near roads: DPWH and LGU traffic permit required; confined space entry permit for manhole works; CCTV inspection report and as-built drawings submitted with handover package; O&M guide covering manhole cleaning schedule (annual), catch basin desludging (semi-annual), outfall inspection after each major storm event; 1-year defects liability period: contractor responsible for any settlement or drainage failure)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Grease Trap Sizing BOM + SOW Agent ──────────────────────────────────────

async function greaseTrapBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project         = inputs.project_name    || "Grease Trap Project";
  const facilityType    = inputs.facility_type   || "Restaurant / Commercial Kitchen";
  const mealsPerDay     = inputs.meals_per_day   ?? "N/A";
  const suf             = results.suf_used       ?? inputs.suf ?? 0.75;
  const totalFlowLpm    = results.total_flow_lpm ?? "N/A";
  const qDesignLpm      = results.q_design_lpm   ?? "N/A";
  const qDesignGpm      = results.q_design_gpm   ?? "N/A";
  const pdiGpm          = results.pdi_gpm        ?? "N/A";
  const liquidCapL      = results.liquid_cap_l   ?? "N/A";
  const greaseRetKg     = results.grease_ret_kg  ?? "N/A";
  const cleanIntervalDays = results.clean_interval_days ?? 30;

  const prompt = `You are a Philippine sanitary engineering expert. Generate a professional BOM and SOW for a GREASE TRAP / GREASE INTERCEPTOR installation project.

PROJECT: ${project}
FACILITY TYPE: ${facilityType}
MEALS PER DAY: ${mealsPerDay}
SIMULTANEOUS USE FACTOR (SUF): ${suf}
TOTAL FIXTURE FLOW: ${totalFlowLpm} LPM
DESIGN FLOW (Q_design): ${qDesignLpm} LPM (${qDesignGpm} GPM)
PDI STANDARD SIZE SELECTED: ${pdiGpm} GPM
LIQUID HOLDING CAPACITY: ${liquidCapL} L (PDI: ${pdiGpm} GPM × 2 gal × 3.785 L/gal)
GREASE RETENTION CAPACITY: ${greaseRetKg} kg
RECOMMENDED CLEANOUT INTERVAL: every ${cleanIntervalDays} days
STANDARDS: PDI BH-201 (Flow Rate Method), Philippine Plumbing Code (PPC), DENR DAO 2016-08 (Wastewater Effluent), PNS/ICS

Generate a JSON object with:
1. "bom_items": array of 15 items (each: description, specification, qty, unit, remarks, checked: true)
   Include these items in order:
   1. Grease Interceptor Unit (PDI-rated): PDI BH-201 certified grease interceptor, ${pdiGpm} GPM rated capacity, ${liquidCapL} L liquid holding, ${greaseRetKg} kg grease retention; cast iron, steel, or HDPE body; inlet baffle and outlet T-pipe; gastight bolted cover; PPC and DENR DAO 2016-08 compliant: qty: 1 unit
   2. Inlet Pipe Connection: 100 mm (4-inch) PVC Schedule 40 inlet pipe from kitchen fixture drain header to grease interceptor inlet; includes 45° elbow, short nipple, and union for maintenance access: qty: 1 lot (per site layout)
   3. Outlet Pipe Connection: 100 mm (4-inch) PVC Schedule 40 outlet pipe from grease interceptor outlet to building drain or septic tank connection; P-trap on outlet side; cleanout plug at low point: qty: 1 lot (per site layout)
   4. Vent Pipe Assembly: 50 mm (2-inch) PVC Schedule 40 vent pipe from grease interceptor body to open air above roof line; anti-siphon vent valve if direct roof vent is not possible; all joints solvent-welded per PPC: qty: 1 lot
   5. Grease Trap Cover and Access Lid: factory-supplied gastight bolted lid (matching interceptor unit); if installed in floor slab: 600 mm x 600 mm cast iron traffic-rated access cover, HS20-rated where in vehicular area, frame set in concrete haunch: qty: 1 set
   6. Inlet and Outlet Fittings: 100 mm tee (for inlet drop pipe baffle), 100 mm 90° elbows (min 2), cleanout plugs (min 2), reducing bushings (if fixture piping is 75 mm), PVC solvent cement and primer: qty: 1 lot
   7. Inlet Strainer / Basket: stainless steel SS 304 perforated basket strainer at interceptor inlet to capture food solids before grease chamber; removable for cleaning; mesh opening 5–10 mm: qty: 1 unit
   8. Grease Waste Drum / Collection Container: 200 L HDPE closed-head drum with tight-lid, labelled "GREASE WASTE: HAZARDOUS" per DENR DAO 2013-22; used for collected grease during pump-out service; quantity per cleaning cycle: qty: 2 units (initial supply)
   9. Interceptor Mounting / Concrete Pad: 150 mm thick reinforced concrete pad under interceptor; 3000 psi (20 MPa) concrete; 12 mm RSB mesh reinforcement; anti-vibration neoprene pads if interceptor is above ground: qty: 1 unit (dimensions per interceptor footprint + 150 mm edge clearance)
   10. Trench / Slab Opening Works: breaking of existing floor tile and concrete slab (if unit is below-grade); excavation to design invert level; formwork and backfill; floor tile reinstatement in matching material and grout: qty: 1 lot (provisional per actual site condition)
   11. Drain Piping: Branch lines to fixtures: 75 mm PVC Schedule 40 kitchen drain branch piping from individual fixtures (sinks, dishwasher, floor drains) to the common drain header feeding the interceptor; all slopes minimum 1:50 per PPC; cleanout plugs at each change of direction: qty: per linear meter (contractor to quantify from kitchen layout drawing)
   12. Pressure Test Fittings and Test Plugs: rubber test plugs (100 mm and 50 mm); hand pump for air pressure test; all drain and vent lines tested at 0.3 bar (5 PSI) air pressure for 15 minutes with no pressure drop before covering: qty: 1 lot
   13. Support Brackets and Pipe Hangers: galvanized steel pipe hangers at max 1.2 m spacing for horizontal runs; wall clamps for vertical stacks; all supports sized for pipe OD and weight when full: qty: 1 lot (per layout)
   14. Inspection and Sampling Port: 100 mm PVC inspection tee with cleanout cap at outlet side of interceptor; provides access for sampling effluent per DENR DAO 2016-08 discharge monitoring requirements: qty: 1 unit
   15. Miscellaneous: pipe labels ("GREASE WASTE DRAIN"), as-built drawing, cleaning log book, Contractor's Grease Management Plan per DENR DAO 2016-08, DENR discharge permit assistance, temporary plumbing covers during construction: qty: 1 lot

2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover:
   - "1.0" General Scope (supply, install, and commission a PDI BH-201-rated grease interceptor system for the ${facilityType}; design flow ${qDesignGpm} GPM: PDI selected unit: ${pdiGpm} GPM; liquid holding capacity ${liquidCapL} L; grease retention ${greaseRetKg} kg; all work in accordance with PDI BH-201, Philippine Plumbing Code (PPC), and DENR DAO 2016-08; BOM quantities are for planning purposes only: contractor shall verify all quantities against approved kitchen layout and as-built plans)
   - "2.0" Applicable Standards and Permits (PDI BH-201: Grease Interceptors (Flow Rate Method); Philippine Plumbing Code (PPC): drain, waste, and vent requirements; DENR DAO 2016-08: Revised Effluent Standards for Wastewater Discharge; DENR DAO 2013-22: Grease Waste as Scheduled Waste; PNS/ICS 15:2003: sanitary drainage; DOLE OSH Standards for confined space work; LGU Building Permit with plumbing permit; obtain DENR Discharge Permit if interceptor outlet discharges to public drain or water body)
   - "3.0" Site Preparation and Slab Works (mark out interceptor location in coordination with kitchen layout and existing drain invert levels; confirm sufficient fall from kitchen fixtures to interceptor inlet (min 1:50 slope) and from interceptor outlet to building drain connection; core drill or break slab only where necessary for below-grade installation; all temporary openings to be barricaded and covered at end of each shift; reinstate slab and floor tiles in matching material after interceptor installation is complete and inspected)
   - "4.0" Grease Interceptor Installation (install PDI-rated interceptor unit on 150 mm reinforced concrete pad at design invert; connect inlet and outlet piping using PVC Schedule 40 solvent-welded joints; install inlet drop baffle tee and outlet T-pipe per PDI BH-201 requirements; install vent pipe to open air above roof; ensure gastight lid is correctly seated and bolted; provide minimum 600 mm clear maintenance access around unit; install SS304 basket strainer at inlet; install DENR-compliant sampling port at outlet)
   - "4.1" Drain and Vent Piping (route kitchen drain branch lines at minimum 1:50 fall to common header; common header to interceptor inlet at 1:50 minimum slope; all changes of direction via 45° bends: no 90° sweep below floor slab; cleanout plugs at each change of direction and at foot of each stack; vent piping to be independent of soil vent stack if discharging >0.6 m³/day; all solvent-welded joints cured 24 hours before pressure test)
   - "5.0" Testing and Inspection (air pressure test all drain and vent lines at 0.3 bar for 15 minutes with no pressure drop before concealing; flow test: pour 10 L of water into each connected fixture and observe free drainage with no gurgling at fixtures: confirms correct venting; after commissioning, sample interceptor effluent and test for Oil and Grease (O&G): must meet DENR DAO 2016-08 limit of 5 mg/L for Class SB/SC receiving waters; submit test results to building owner and LGU sanitary inspector; DENR inspection required before final occupancy clearance if facility serves >50 meals/day)
   - "6.0" Maintenance and Cleanout Schedule (establish Grease Management Plan (GMP): interceptor to be cleaned every ${cleanIntervalDays} days based on ${mealsPerDay} meals/day and ${greaseRetKg} kg retention capacity; cleaning procedure: remove lid, pump out grease and liquid waste into sealed 200 L drums labelled per DENR DAO 2013-22, scrape baffle walls, rinse with hot water (not caustic chemicals), replace basket strainer, re-seat lid; engaged licensed environmental services contractor (LLDA/EMB-accredited) for grease waste hauling and disposal; maintain cleaning log book on-site for DENR inspection; if O&G in effluent exceeds 5 mg/L on any sampling event, reduce cleanout interval immediately)
   - "7.0" Regulatory Compliance and Handover (submit as-built plumbing drawings showing grease interceptor location, pipe sizes, invert levels, and connection to building drain; provide manufacturer's data sheet and PDI certification for interceptor unit; submit Grease Management Plan (GMP) to LGU and DENR as required; provide owner training on daily pre-cleaning of basket strainer, visual grease level check, and emergency spill procedure; 1-year defects liability: contractor responsible for any joint failure, blockage attributable to incorrect installation, or interceptor unit defect within warranty period)
   - "8.0" Health, Safety, and Environment (all confined space entry (below-grade interceptor pit) under confined space entry permit per DOLE OSH Rule 1977; PPE: chemical-resistant gloves, safety goggles, chemical apron, and respiratory protection during cleanout; no smoking or open flame near interceptor: methane/H2S gas hazard; grease waste is scheduled waste per DENR DAO 2013-22: manifest required for every haul; do not discharge grease waste to floor drain, sewer, or storm drain: fine and penalty under RA 9275 Clean Water Act)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Roof Drain Sizing BOM + SOW Agent ────────────────────────────────────────

async function roofDrainBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name       || "Roof Drain Sizing";
  const nDrains        = results.n_drains          ?? inputs.n_drains          ?? 2;
  const drainSizeMm    = results.drain_size_mm     ?? "N/A";
  const leaderSizeMm   = results.leader_size_mm    ?? drainSizeMm;
  const horizLeaderMm  = results.horiz_leader_mm   ?? "N/A";
  const overflowMm     = results.overflow_drain_mm ?? null;
  const qTotalLs       = results.q_total_ls        ?? "N/A";
  const qEachLs        = results.q_each_ls         ?? "N/A";
  const intensityMmhr  = results.intensity_mmhr    ?? inputs.intensity_mmhr    ?? 100;
  const slopePct       = results.leader_slope_pct  ?? inputs.leader_slope_pct  ?? 1.0;
  const pipeMaterial   = results.pipe_material     ?? inputs.pipe_material     ?? "uPVC";
  const manningN       = results.manning_n         ?? 0.011;
  const hasParapet     = results.has_parapet        ?? (inputs.has_parapet === "Yes");
  const roofAreaM2     = results.roof_area_m2      ?? inputs.roof_area         ?? "N/A";
  const overallStatus  = results.overall_status    || "PASS";

  const astmPipe  = pipeMaterial === "uPVC" ? "ASTM D2665 (uPVC DWV)" : "ASTM A74 (cast iron)";
  const overflowLine = overflowMm
    ? `OVERFLOW DRAINS: ${nDrains} × ${overflowMm} mm overflow drain bodies, invert set at +50 mm above primary drain invert per IPC §1101.7`
    : "OVERFLOW DRAINS: Not required: no parapet walls present";

  const prompt = `You are a Philippine licensed sanitary / plumbing engineer. Generate a professional BOM and SOW for a ROOF DRAIN SYSTEM construction project.

PROJECT: ${project}
ROOF DRAINAGE AREA: ${roofAreaM2} m²
DESIGN RAINFALL INTENSITY: ${intensityMmhr} mm/hr (PAGASA 10-yr, 60-min IDF)
DESIGN METHOD: Rational Method: Q = I × A / 3600 (C = 1.0, impervious roof)
TOTAL DESIGN FLOW: ${qTotalLs} L/s
FLOW PER DRAIN: ${qEachLs} L/s
NUMBER OF PRIMARY DRAINS: ${nDrains} (IPC §1106.3 minimum 2 drains)
PRIMARY DRAIN BODY SIZE: ${drainSizeMm} mm nominal (ASME A112.21.2M)
VERTICAL LEADER SIZE: ${leaderSizeMm} mm nominal
HORIZONTAL LEADER SIZE: ${horizLeaderMm} mm ${pipeMaterial} at ${slopePct}% slope (Manning n = ${manningN})
${overflowLine}
PIPE MATERIAL: ${pipeMaterial} (${astmPipe})
COMPLIANCE STATUS: ${overallStatus}
STANDARDS: IPC 2018 Chapter 11 (§1106 Roof Drain Sizing, §1101.7 Overflow Drains), Philippine Plumbing Code (PPC), ASPE Plumbing Engineering Design Handbook Vol. 2, ASME A112.21.2M, PAGASA IDF Curves, DOLE OSH Standards

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include these items in order:
   1. Primary Roof Drain Body: ${drainSizeMm} mm nominal cast iron or ABS roof drain body per ASME A112.21.2M, flat or low-profile strainer dome, integral membrane clamp and gravel stop, sediment bucket: qty: ${nDrains} units
   2. Strainer Dome: heavy-duty cast iron or ABS strainer dome for ${drainSizeMm} mm drain body, domed profile to prevent debris bridging, removable for cleaning: qty: ${nDrains} units (included with drain body as standard accessory)
   3. Vertical Roof Leader (Conductor) Pipe: ${leaderSizeMm} mm nominal ${pipeMaterial} pipe (${astmPipe}), Schedule 40 minimum wall, plain end with couplings: qty: per vertical height (m) of each leader: Contractor to quantify from drawings
   4. Horizontal Leader Pipe: ${horizLeaderMm} mm nominal ${pipeMaterial} pipe (${astmPipe}), minimum ${slopePct}% slope, plain end with solvent-weld or mechanical couplings: qty: per linear meter of horizontal run: Contractor to quantify from drainage layout drawing
   5. 90° Long-Radius Elbow: ${leaderSizeMm} mm ${pipeMaterial} long-radius elbow at base of each vertical leader to transition to horizontal run, sweep radius minimum 1.5× pipe diameter to minimise turbulence: qty: ${nDrains} units (minimum)
   6. ${overflowMm ? `Overflow Roof Drain Body: ${overflowMm} mm nominal overflow drain body per ASME A112.21.2M, set at invert +50 mm above primary drain per IPC §1101.7; must discharge independently or through a separate leader: qty: ${nDrains} units` : `Pipe Coupling / Jointing Materials: solvent-weld couplings, primer and cement (ASTM D2564 for uPVC) or lead and oakum for cast iron; joint compound, Teflon tape for threaded fittings: qty: 1 lot`}
   7. Cleanout Fitting: ${horizLeaderMm} mm cleanout plug with access cover at all changes of direction on horizontal leader and at maximum 10 m spacing per IPC §708; flush-mounted cover plate at finished ceiling: qty: as required from layout
   8. Pipe Hanger / Support: heavy-duty clevis hanger for vertical leader at each floor penetration and at maximum 1.5 m spacing; adjustable iron ring hanger for horizontal leader at maximum 1.2 m spacing: qty: as required per layout (Contractor to quantify)
   9. Roof Membrane Flashing: pre-formed ${drainSizeMm} mm lead or stainless steel clamping ring flashing, lapped minimum 150 mm over waterproof membrane, sealed with polyurethane sealant: qty: ${nDrains} units (plus ${overflowMm ? nDrains : 0} overflow units)
   10. Roof Penetration Sleeve: galvanised steel or HDPE pipe sleeve through roof slab at each drain location, minimum 50 mm annular clearance, non-shrink grout seal, fire-rated where required by code: qty: ${nDrains} units (plus overflow units if any)
   11. Test Plugs (Inflatable or Mechanical): inflatable test plugs for flood test per IPC §1109; capable of holding 150 mm head of water for minimum 15 minutes without seepage: qty: ${nDrains} units
   12. Waterproofing Sealant: polyurethane or silicone-based waterproofing sealant at all drain-to-membrane interfaces, UV-stable, compatible with roofing membrane material: qty: 1 lot
   13. Pipe Insulation (Cold Lines): 25 mm elastomeric foam insulation on horizontal leaders in conditioned spaces to prevent condensation; vapour barrier jacket where exposed: qty: per linear meter in conditioned areas
   14. Miscellaneous: pipe markers at 3 m spacing, drain body identification tags, as-built drainage layout drawing, temporary covers during construction, site safety signage, commissioning test report: qty: 1 lot

2. "sow_sections": array of 7 sections (each: section_no, title, content: full "The Contractor shall..." paragraphs, not bullets)
   Cover:
   - "1.0" General Scope: The Contractor shall design, supply, install, test, and commission a complete roof drainage system for a ${roofAreaM2} m² roof area, designed to convey the 10-year design storm runoff of ${qTotalLs} L/s at ${intensityMmhr} mm/hr rainfall intensity (PAGASA IDF data) to the building storm drainage system or approved point of discharge. The system shall comprise ${nDrains} primary roof drain bodies (${drainSizeMm} mm nominal), ${leaderSizeMm} mm vertical leaders, and ${horizLeaderMm} mm horizontal leaders at ${slopePct}% minimum slope${overflowMm ? `, plus ${nDrains} overflow drain bodies (${overflowMm} mm nominal) set at invert +50 mm above primary drain invert per IPC §1101.7` : ""}. All work shall comply with the Philippine Plumbing Code (PPC), IPC 2018 Chapter 11, ASPE Plumbing Engineering Design Handbook Vol. 2, and all applicable local government requirements. The Contractor shall verify all quantities from final architectural and structural drawings: the BOM is for planning purposes only.
   - "2.0" Applicable Standards and Permits: The Contractor shall comply with all of the following: IPC 2018 Chapter 11 (Storm Drainage: §1106 Roof Drain Sizing, §1101.7 Overflow Drains, §1109 Roof Drain Testing); Philippine Plumbing Code (PPC): adopts IPC with local amendments; ASPE Plumbing Engineering Design Handbook, Volume 2: Plumbing Systems; ASME A112.21.2M: Roof Drain Standard; ASTM D2665 (uPVC DWV pipe) or ASTM A74 (cast iron pipe) as applicable; PAGASA IDF Curves for design rainfall intensity; DOLE OSH Standards for construction safety. The Contractor shall secure all required building permits, plumbing permits, and inspections from the Local Government Unit (LGU) before commencing installation.
   - "3.0" Roof Drain Body Installation: The Contractor shall install ${nDrains} primary roof drain bodies (${drainSizeMm} mm nominal, ASME A112.21.2M) at locations shown on the drainage layout drawing, coordinating with the structural and waterproofing works. Each drain body shall be set flush with the finished roof surface with positive drainage fall towards the drain of minimum 1:100 on the roof deck. The membrane clamping ring shall be installed prior to application of the waterproofing membrane, and the upper clamping ring applied over the completed membrane with polyurethane sealant at all interfaces. Pre-formed lead or stainless steel flashing shall be lapped minimum 150 mm over the membrane and sealed continuously. The Contractor shall install strainer domes on all drain bodies and verify free rotation and positive seating before handover.${hasParapet ? ` Overflow drain bodies (${overflowMm} mm nominal) shall be installed at each primary drain location with the invert set at +50 mm above the primary drain invert per IPC §1101.7; overflow drains shall discharge independently through separate leaders or through a dedicated connection to the storm drain system: they shall NOT share a common trap or p-trap with primary drains.` : ""}
   - "4.0" Vertical Leaders and Horizontal Piping: The Contractor shall install ${leaderSizeMm} mm nominal ${pipeMaterial} vertical leaders (conductors) from each roof drain body to the horizontal collector, supported with riser clamps at each floor penetration and at maximum 1.5 m vertical spacing. All penetrations through roof slabs and beams shall be sleeved with a galvanised steel pipe sleeve with 50 mm annular clearance, grouted solid with non-shrink mortar and fire-stopped where required. Horizontal leaders shall be installed at ${horizLeaderMm} mm nominal ${pipeMaterial}, pitched at minimum ${slopePct}% (${slopePct === 1 ? "1/8 in/ft" : slopePct + "%"}) throughout: no reverse-fall, no flat sections. All changes of direction shall use long-radius (sweep) fittings; no short-radius elbows on horizontal runs. Pipe hangers shall be installed at maximum 1.2 m spacing on horizontal runs. Cleanouts with flush access covers shall be provided at all changes of direction and at maximum 10 m spacing per IPC §708.
   - "5.0" Testing: Roof Flood Test (IPC §1109): The Contractor shall conduct a roof flood test on the completed drainage system prior to installation of any finish materials and before final acceptance. The test shall be conducted as follows: (1) plug all drain bodies at the roof level using inflatable or mechanical test plugs rated for the test head; (2) flood the roof to a minimum 150 mm head of water (measured at the drain body); (3) maintain the test head for a minimum of 15 minutes without any visible seepage through the roof membrane, flashings, or deck penetrations; (4) record the test date, water level, and result in the commissioning test report; (5) any seepage or weeping at drain body flanges, sleeves, or membrane laps shall be repaired and the flood test repeated before acceptance. The Contractor shall submit the flood test report, signed by the responsible licensed plumber, to the Engineer within 3 days of the test.
   - "6.0" Regulatory Compliance and Safety: The Contractor shall comply with all DOLE OSH Standards for construction safety, including proper scaffolding and fall protection for all roof-level works. A confined space entry permit shall be required for any work inside enclosed chases or ceiling spaces containing drain leaders. The Contractor shall maintain a clean and dry work area at all roofing penetrations to prevent water infiltration into the building during construction. All hot-works (welding, cutting) near waterproofing membrane shall require a hot-work permit from the fire safety officer. The Contractor shall not backfill or conceal any piping until it has been inspected and approved by the licensed plumber-in-charge and, where required, by the LGU plumbing inspector.
   - "7.0" Handover and As-Built Documentation: Upon completion of all works and successful flood test, the Contractor shall submit the following to the Engineer and Owner: (1) as-built roof drainage layout drawing showing drain body locations, leader routes, invert levels, and cleanout positions; (2) flood test report per IPC §1109 signed by the licensed plumber; (3) manufacturer's data sheets for all drain bodies, pipe, and fittings installed; (4) material test reports or mill certificates for structural components; (5) O&M guide covering: drain body strainer dome cleaning (monthly), cleanout rodding (annual), flood-test repeat (every 5 years or after any roof membrane repair); (6) recommended spare strainer domes (minimum 2 units) handed over to the Owner. A 1-year defects liability period applies from the date of handover acceptance: the Contractor shall rectify any drainage failure, leak, or blockage attributable to defective materials or workmanship at no additional cost.

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
PHASE CONFIGURATION: ${phaseConfig}: ${voltage}V
TOTAL CONNECTED LOAD: ${connKVA} kVA
TOTAL DEMAND LOAD: ${demandKVA} kVA (${demandKW} kW)
COMPUTED AMPACITY: ${computedA} A
WITH 25% SPARE CAPACITY: ${spareA} A
RECOMMENDED MAIN BREAKER: ${breakerA} A
LOAD BREAKDOWN SUMMARY: ${loadSummary}
STANDARDS: PEC 2017 (Philippine Electrical Code), PEC Article 2.10 / 2.20, DOE/ERC regulations, DOLE OSH Electrical Safety, NEC parallel reference

Generate a JSON object with:
1. "bom_items": array of 16 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Main distribution board/panelboard (NEMA 1 surface/flush-mount, number of poles sized to load count), main MCCB/ACB circuit breaker (${breakerA}A, interrupt capacity ≥ 10 kA), phase bus bars (copper, properly rated), neutral/ground bus bars, equipment grounding conductor (EGC), individual branch circuit breakers (MCB, sized per load group: qty derived from load breakdown), THHN/THWN copper conductors (main feeder, sized for ${spareA}A), conduit (EMT or RSC, properly sized), load schedule nameplate (laminated or engraved), energy meter (kWh, class 1.0, utility-grade), surge protective device (SPD, Type 2, properly rated), cable lugs and terminal connectors, conduit fittings and accessories, panel enclosure padlock, warning labels (PEC-compliant arc flash / voltage warning), wire markers and cable ties
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
  const passStr       = pass ? "PASS" : "FAIL: conductor size increase required";

  // Find next larger passing conductor from size_comparison if failing
  const comparison = results.size_comparison as Array<{ size_mm2: number; vd_pct: number; pass: boolean }> || [];
  const nextPassSize = comparison.find(s => s.pass && s.size_mm2 > Number(conductorMM2));
  const recommendedMM2 = pass ? conductorMM2 : (nextPassSize?.size_mm2 ?? conductorMM2);

  const prompt = `You are a Philippine electrical engineering expert (PEC 2017). Generate a professional BOM and SOW for a VOLTAGE DROP COMPLIANCE wiring project.

PROJECT: ${project}
CIRCUIT TYPE: ${circuitType}
PHASE: ${phase}: ${voltage}V
DESIGN CURRENT: ${current} A
CIRCUIT LENGTH: ${wireLength} m (one-way)
SELECTED CONDUCTOR: ${conductorMM2} mm² ${conductorMat} THHN/THWN
VOLTAGE DROP RESULT: ${vdVolts}V (${vdPct}%): ${passStr}
VOLTAGE DROP LIMIT: ${vdLimit}%
MAXIMUM ALLOWABLE LENGTH @ selected size: ${maxLengthM} m
RECOMMENDED CONDUCTOR SIZE (PEC-compliant): ${recommendedMM2} mm² ${conductorMat}
STANDARDS: PEC 2017 Article 2.10.19 / 2.20, Philippine Electrical Code, DOLE OSH

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Phase conductor (${recommendedMM2} mm² ${conductorMat} THHN/THWN, rated for ${voltage}V, length ${wireLength}m + 10% allowance for terminations), neutral conductor (same size as phase for single-phase; 50% of phase for three-phase balanced), equipment grounding conductor (EGC, green/green-yellow, sized per PEC Table 2.50.95), conduit (EMT for indoors, RSC for exposed/outdoor, sized per PEC conduit fill), conduit fittings and couplings, pull boxes (if circuit exceeds 30m or has more than 4 bends), circuit breaker (sized for design current with 125% for continuous loads), cable tray or cable support clips (if surface-mounted), wire markers/circuit labels (origin panel, circuit number, load description), terminal lugs (for terminations at both ends), junction box with cover (rated for conductor count), conduit strap/saddle anchors (every 1.5m on exposed conduit), wire pulling lubricant (for conduit runs over 15m), cable ties
2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (PEC 2017 Art. 2.10.19, voltage drop ≤ ${vdLimit}% = ${Number(vdLimit)/100 * Number(voltage)} V max, conductor selection criteria), Conductor and Conduit Installation (pulling, bending radius, fill ratio per PEC, no sharp bends), Termination and Splicing (compression lugs, no taped splices in conduit: junction box only), Grounding and Continuity (EGC continuity, bonding at all metal conduit terminations), Testing and Verification (insulation resistance test ≥ 1 MΩ at 500V DC, continuity test, voltage drop field measurement under load: confirm ≤ ${vdLimit}%), Regulatory Compliance (PEC 2017, Electrical Permit, DOLE OSH, qualified licensed master electrician)

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
PHASE: ${phase}: ${voltage}V
LOAD POWER: ${powerW} W @ PF ${pf}
LOAD CURRENT: ${loadCurrentA} A
DEMAND MULTIPLIER: ${demandMult}x (${isMotor ? "motor/continuous load: PEC 125% rule" : "standard load"})
DESIGN CURRENT: ${designCurrentA} A
AMBIENT TEMPERATURE: ${ambientTemp}°C (correction factor: ${tempFactor})
CONDUIT FILL: ${conduitFill} conductors (fill factor: ${fillFactor})
RECOMMENDED CONDUCTOR SIZE: ${recSizeMM2} mm² Copper THHN/THWN
CORRECTED AMPACITY: ${recAmpacity} A
RECOMMENDED BREAKER: ${recBreakerA} A
STANDARDS: PEC 2017 Table 3.10.1, PEC Article 2.10 / 2.30, DOLE OSH Electrical Safety

Generate a JSON object with:
1. "bom_items": array of 15 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Phase conductor (${recSizeMM2} mm² Copper THHN/THWN 75°C, ${voltage}V rated), neutral conductor (same size as phase for single-phase; may be reduced for balanced 3-phase), equipment grounding conductor (EGC, green/green-yellow, sized per PEC Table 2.50.95 based on breaker ${recBreakerA}A), circuit breaker (${recBreakerA}A, interrupt capacity ≥ available fault current${isMotor ? ', thermal-magnetic or motor circuit protector' : ''}), conduit (EMT for concealed/indoor, RSC for exposed/outdoor: sized per PEC conduit fill table for ${recSizeMM2} mm² conductors), conduit fittings, locknuts, and bushings, pull boxes or junction boxes (at every 30m or 4 bends), wire markers and circuit labels (origin panel, circuit no., load description), terminal compression lugs (for all terminations: no bare wire twist connections), cable ties and conduit saddle/strap anchors (every 1.5m on exposed runs), panel knockout seal/reducer (if conduit enters existing panelboard), wire pulling lubricant, flexible conduit and connector (last 600mm to motor: if motor load), warning labels (voltage level, circuit identification), spare conduit cap/plugs (for unused knockouts)
2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (PEC 2017 Table 3.10.1 ampacity with ${tempFactor} temperature correction and ${fillFactor} conduit fill correction, ${demandMult}x demand multiplier per PEC${isMotor ? ' Art. 2.30 motor branch circuit rules' : ' Art. 2.10 branch circuit rules'}), Conductor and Conduit Installation (no conductor smaller than minimum branch circuit size, bending radius ≥ 6× OD, maximum conduit fill per PEC, support intervals), Termination Works (compression lugs at all terminations, no splices inside conduit: use junction box, tighten to manufacturer torque spec), ${isMotor ? 'Motor Branch Circuit Requirements (locked-rotor current withstand, overload protection sizing, flexible conduit to motor terminal box),' : 'Circuit Protection (breaker sizing, coordination with upstream protective device,)'} Testing and Commissioning (insulation resistance ≥ 1 MΩ at 500V DC megger, continuity check on EGC, polarity verification, breaker trip test), Regulatory Compliance (PEC 2017, Electrical Permit, DOLE OSH, licensed master electrician, as-built drawings)

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
INSTALLED BREAKER IC: ${breakerIC} kA: ${icCheck}${icFail ? ` (INSUFFICIENT: must be upgraded to minimum ${icMinRec} kA)` : ` (margin: +${icMargin} kA)`}
MINIMUM RECOMMENDED IC: ${icMinRec} kA
STANDARDS: PEC 2017 Article 1.30, PEC Article 2.40, IEEE Std 141 (Red Book), IEC 60909

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Main circuit breaker (MCCB or ACB: minimum IC ${icMinRec} kA at ${voltageLLV}V${icFail ? `, REPLACEMENT REQUIRED: installed unit undersized` : ``}), branch circuit breakers (MCCBs: IC ≥ ${icMinRec} kA, sized per branch loads), current transformer (CT) for metering (if panel > 100A), arc flash warning labels (NFPA 70E / PEC-compliant, incident energy and PPE level), arc flash boundary markers, short circuit study report holder/binder (for panel schedule record), bus bar shorting link (for fault current test, 1 set per panel), personal protective equipment (PPE): arc-rated FR clothing and face shield (for commissioning work near energized bus), insulated tools (1000V rated), ground fault indicator light or relay (per PEC 2017), panel enclosure padlock set, cable bus duct or switchgear cubicle (if fault level requires metal-enclosed gear), thermal imaging window port (installed on panel door for ongoing maintenance), insulating mat (IEC 61111 Class 1 minimum, for work area protection)
2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (PEC 2017 Art. 1.30, IEC 60909 transformer impedance method, 3-phase symmetrical fault ${IscKA} kA, asymmetrical peak ${IpeakKA} kA), ${icFail ? `Breaker Upgrade Requirement (installed ${breakerIC} kA IC is INSUFFICIENT for ${IscKA} kA fault level: replace with minimum ${icMinRec} kA IC-rated breaker before energization: PEC Art. 1.30 non-negotiable)` : `Breaker IC Verification (installed ${breakerIC} kA IC confirmed adequate for ${IscKA} kA fault level with ${icMargin} kA safety margin)`}, Arc Flash Hazard Assessment and Labeling (incident energy analysis, PPE levels, arc flash boundary marking per NFPA 70E / PEC), Panel Schedule and Single-Line Diagram Update (as-built SLD showing transformer, feeder cable, fault current level at each panel), Testing and Commissioning (insulation resistance test, breaker contact resistance test, trip test, IR thermal scan of bus connections under load), Regulatory Compliance (PEC 2017 Art. 1.30 and 2.40, Electrical Permit, DOLE OSH, short circuit study report filed with as-built documents)

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
   Include: LED luminaire fixtures (${nFixtures} units: ${lumensPerFix} lm, ${wattsPerFix}W, CRI ≥ 80, color temperature per space type: office/corridor 4000K neutral white, warehouse/industrial 5000K daylight, restaurant/hotel 3000K warm white), emergency luminaire with battery backup (minimum 1 per room exit route, 90-min backup, 10 lux minimum on exit path), lighting circuit wiring (THHN/THWN copper, sized per ${totalWatts}W load + 25% continuous load factor), lighting circuit breaker (MCB, sized for circuit), lighting conduit (EMT, properly sized), conduit fittings and accessories, junction boxes (one per fixture cluster), lighting switches (per circuit zone, flush-mounted, rated 10A minimum), occupancy sensor or daylight sensor (if applicable to space type: offices, corridors), lighting panel/sub-panel (if dedicated lighting load), wire markers and circuit labels, ceiling grid or mounting hardware (for recessed or surface mount per ceiling type), fixture hangers and safety cables (per fixture weight), dimmer module or lighting control relay (if dimming specified), laminated lighting layout drawing (as-installed record)
2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (IES Lumen Method, RCR ${rcr}, CU ${cu}, LLF ${llf}, target ${targetLux} lux, achieved ${eActualLux} lux, LPD ${lpdWm2} W/m² vs ASHRAE 90.1 limit for ${spaceType}), Fixture Installation (mounting height, aiming, spacing, uniformity ratio ≥ 0.7), Circuit Wiring and Conduit Works (conductor sizing for continuous lighting load × 125%, conduit fill, color coding per PEC), Emergency Lighting and Exit Signs (PEC Art. 2.10, minimum 10 lux on exit path, 90-min backup, monthly test procedure), Testing and Commissioning (illuminance measurement grid test with calibrated lux meter at work plane height: verify ≥ ${targetLux} lux at all measurement points, uniformity check, circuit continuity and insulation resistance test), Regulatory Compliance (PEC 2017, DOLE OSH lighting requirements for ${spaceType}, Electrical Permit, as-built lighting layout drawing submission)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical: Solar PV System BOM + SOW Agent ─────────────────────────────

async function solarPVBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project       = inputs.project_name     || "Solar PV Project";
  const systemType    = results.system_type     || inputs.system_type     || "Grid-Tied";
  const location      = results.location        || inputs.location        || "Metro Manila";
  const pshHr         = results.psh_hr          ?? inputs.psh_hr          ?? 4.5;
  const panelQty      = results.panel_qty       ?? "N/A";
  const panelWp       = inputs.panel_wp         ?? results.panel_wp       ?? 450;
  const actualKWp     = results.actual_array_kwp ?? "N/A";
  const panelsPerStr  = results.panels_per_string ?? "N/A";
  const numStrings    = results.num_strings     ?? "N/A";
  const inverterKW    = results.inverter_kw     ?? "N/A";
  const roofAreaM2    = results.total_roof_area_m2 ?? "N/A";
  const annualYield   = results.annual_yield_kwh ?? "N/A";
  const co2Kg         = results.co2_reduction_kg ?? "N/A";
  const isOffGrid     = String(systemType).includes("Off-Grid") || String(systemType).includes("Hybrid");
  const battKWh       = results.battery_kwh     ?? 0;
  const battAh        = results.battery_ah      ?? 0;
  const battV         = inputs.battery_voltage  ?? results.battery_voltage ?? 48;

  const prompt = `You are a senior electrical engineer in the Philippines preparing a Bill of Materials and Scope of Works for a Solar PV System.

PROJECT: ${project}
SYSTEM TYPE: ${systemType}
LOCATION: ${location} (PSH: ${pshHr} h/day)
ARRAY: ${actualKWp} kWp: ${panelQty} panels × ${panelWp} Wp each
STRING CONFIG: ${panelsPerStr} panels/string × ${numStrings} strings (1000V DC IEC 62548)
INVERTER: ${inverterKW} kW (grid-tie / hybrid inverter)
ROOF AREA: ${roofAreaM2} m²
ANNUAL YIELD: ${annualYield} kWh/yr | CO₂ REDUCTION: ${co2Kg} kg/yr
${isOffGrid ? `BATTERY BANK: ${battKWh} kWh / ${battAh} Ah @ ${battV}V DC (Off-Grid/Hybrid)` : "NET METERING: Grid-Tied: DOE DC2015-07-0012 net metering application required"}

Generate a professional BOM and SOW for this project.

RETURN JSON ONLY in this exact format:
{
  "bom_items": [
    { "description": "...", "specification": "...", "qty": 1, "unit": "unit", "remarks": "..." }
  ],
  "sow_sections": [
    { "section_no": "1.0", "title": "...", "content": "The Contractor shall..." }
  ]
}

BOM REQUIREMENTS (minimum 18 items):
1. Solar PV Modules: ${panelWp} Wp monocrystalline PERC/TOPCon, IEC 61215 / IEC 61730 certified; Qty: ${panelQty} pcs
2. Solar Mounting Structure: Aluminum anodized roof-mount rail system; Qty: for ${panelQty} panels set
3. String Inverter: ${inverterKW} kW grid-tie inverter, IEC 61727, DOE-approved, anti-islanding protection; Qty: 1 unit
4. DC Combiner Box: ${numStrings}-string, with fuses, surge arrester, disconnect; Qty: 1 unit
5. DC Solar Cable: 6mm² UV-resistant double-insulated (IEC 62930), for string wiring; Qty: estimate meters run
6. AC Output Cable: 3.5 to 5.5 sq.mm THHN Cu for inverter AC output to panel; Qty: estimate run
7. DC Circuit Breaker: string-rated 600/1000V DC MCB; Qty: ${numStrings} pcs
8. AC Circuit Breaker: 2P/4P, rated for inverter output current; Qty: 1 unit
9. Surge Protection Device (DC): 1000V DC, 40kA; Qty: 2 unit
10. Surge Protection Device (AC): Type 2, 40kA; Qty: 1 unit
11. Solar Disconnect Switch (DC): load-break rated 1000V DC; Qty: 1 unit
12. Energy Meter (Bidirectional): for net metering, Meralco-approved; Qty: 1 unit
13. Grounding/Bonding Cable: 6mm² bare/green Cu for module frames, racking; Qty: estimate run
14. Ground Rod and Clamps: copper-coated 16mm × 1.5m; Qty: 2 set
15. Conduit and Fittings: EMT/PVC for cable protection; Qty: estimate lot
16. Cable Trays / Cleats: aluminum or powder-coated steel; Qty: lot
${isOffGrid ? `17. Battery Bank: LiFePO4 or VRLA, ${battV}V ${battAh}Ah system; Qty: 1 set
18. Battery Enclosure / Cabinet: IP44, ventilated, with smoke detector; Qty: 1 unit
19. Charge Controller / Battery Management System (BMS); Qty: 1 unit
20. Isolation Transformer (if required by local utility); Qty: 1 unit` : `17. Net Metering Application Package: DOE DC2015-07-0012, Meralco technical requirements; Qty: 1 lot
18. Commissioning and Testing: IV curve tracing, insulation resistance test, anti-islanding test; Qty: 1 lot`}

SOW REQUIREMENTS (8 sections):
1. Scope of Works and Design Basis
2. Solar PV Module Supply and Installation (IEC 62548 string voltage, tilt angle, clearances)
3. Mounting Structure and Roof Works (structural adequacy, waterproofing, load check)
4. Inverter and Electrical Balance of System (BOS) Installation
5. DC Wiring, Combiner, and Protection Devices (1.25× Isc cable sizing per IEC 62548)
6. AC Interconnection and Metering (net metering for grid-tied; battery integration for off-grid/hybrid)
7. Earthing, Bonding, and Lightning Protection (PEC Art. 6, IEC 62561)
8. Testing, Commissioning, and Regulatory Compliance (DOE permit, PEC Electrical Permit, Meralco net metering, IEC 61727 anti-islanding verification)

Write each SOW section as full professional paragraphs starting with "The Contractor shall...": NOT bullet points.
Use short unit codes only (unit, set, pcs, m, lot, run): never descriptive phrases in the unit field.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical: Power Factor Correction BOM + SOW Agent ─────────────────────

async function pfcBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project       = inputs.project_name    || "Power Factor Correction Project";
  const kw            = results.kw             || inputs.load_kw      || "";
  const pfExisting    = results.pf_existing    || inputs.pf_existing  || "";
  const pfTarget      = results.pf_target      || inputs.pf_target    || "";
  const voltageV      = inputs.voltage_v       || 400;
  const phases        = inputs.phases          || 3;
  const kvarRequired  = results.kvar_required  || "";
  const selectedKvar  = results.selected_kvar  || "";
  const kvaReduction  = results.kva_reduction  || "";
  const currentRedPct = results.current_reduction_pct || "";
  const meralcoPenalty= results.meralco_penalty ?? false;

  const prompt = `You are a Philippine electrical engineering expert (IEEE 18, IEEE 1036, PEC 2017 Art. 4.60, IEC 60831-1). Generate a professional BOM and SOW for a POWER FACTOR CORRECTION (capacitor bank) installation project.

PROJECT: ${project}
SYSTEM: ${voltageV}V, ${phases}-phase
LOAD: ${kw} kW at existing PF = ${pfExisting} → target PF = ${pfTarget}
REQUIRED: ${kvarRequired} kVAR → SELECTED CAPACITOR BANK: ${selectedKvar} kVAR
kVA REDUCTION: ${kvaReduction} kVA | Feeder current reduction: ${currentRedPct}%
MERALCO PF SURCHARGE: ${meralcoPenalty ? `YES: existing PF ${pfExisting} is below 0.85 threshold; surcharge eliminated after correction to PF ${pfTarget}` : `NO: existing PF ${pfExisting} is above Meralco 0.85 threshold`}
STANDARDS: IEEE 18, IEEE 1036, PEC 2017 Article 4.60, IEC 60831-1

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Power Factor Correction Capacitor Bank (${selectedKvar} kVAR, ${voltageV}V, ${phases}-phase, IEC 60831-1 certified self-healing type, factory-installed discharge resistors per IEEE 18: terminal voltage < 50V within 5 minutes after disconnection, IP31 minimum indoor rating), Automatic Power Factor Controller / APFC (12-step microprocessor-based controller, Modbus RS-485 communication port, anti-hunting timer to prevent excessive switching cycles, LCD display showing PF, kVAR, step status), Series Detuning Reactor 7% (tuned to 189 Hz to prevent harmonic resonance with VFDs and non-linear loads: rated for 1.3x capacitor rated current, Class H insulation), Dedicated MCCB for Capacitor Feeder (molded-case circuit breaker rated at minimum 135% of capacitor rated current per PEC Art. 4.60.14 and IEEE 1036: provide time-delay characteristic to allow capacitor inrush), Capacitor Panel Enclosure (sheet metal IP31 indoor panel with busbar, din-rail, door interlock and padlock provision, nameplate, anti-condensation heater for humid environments), Copper Busbars (tinned copper, current-rated to 125% of capacitor bank rated current, insulated phase segregation, per PEC Art. 4.60), Copper Conductors: Capacitor Feeder (THHN/THWN-2 75°C copper, sized at 135% of capacitor rated current per PEC Art. 4.60.14 and IEEE 1036), Conduit System (IMC rigid metallic conduit or PVC Schedule 40 for LV, sized per PEC Table 3.10.1, with liquid-tight fittings at panel knockouts), Power Analyzer / Energy Meter (true-RMS multifunction meter with power factor, kW, kVAR, kVAh, harmonic THD display: DIN rail or panel mount), Control Transformer (240V/24V AC for APFC controller and auxiliary relay supply, VA rated to controller load + 20% margin), Earthing and Grounding Materials (copper earth bus, 16 sq.mm green/yellow earth wire, compression lugs, earth bar, bonded to capacitor bank frame and panel enclosure per PEC Art. 2.50), Cable Tray / Cable Duct (perforated cable tray or PVC duct for routing power and control cables, sized for cable fill not more than 40%), Warning Labels and Safety Signs (DANGER: CAPACITOR BANK, DISCHARGE TIME, PPE requirement labels per DOLE OSH and PEC Art. 4.60), Installation Accessories (mounting bolts, anti-vibration pads, terminal lugs, heat shrink tubing, ferrules, cable ties: complete set)

2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Write each content as a full professional paragraph starting with "The Contractor shall...": do NOT use bullet points or keyword lists. Each section must be 3–6 sentences of contractor-facing specification language.
   Cover:
   Section 1: Scope of Works and Design Basis: state that this SOW covers supply, installation, testing, and commissioning of a ${selectedKvar} kVAR power factor correction capacitor bank at ${voltageV}V ${phases}-phase for project ${project}; reference calculation basis (IEEE 18, IEEE 1036, PEC 2017 Article 4.60, IEC 60831-1); state existing PF ${pfExisting} → target PF ${pfTarget}; state kVA reduction ${kvaReduction} kVA and feeder current reduction ${currentRedPct}%; ${meralcoPenalty ? `state that the existing PF of ${pfExisting} is below the Meralco DSM 0.85 threshold and that installation of the specified capacitor bank will eliminate the PF surcharge after correction to PF ${pfTarget}` : `state that correction improves kVA demand and reduces feeder I²R losses`}
   Section 2: Capacitor Bank and APFC Panel Supply: cover supply of IEC 60831-1 certified self-healing capacitor bank at ${selectedKvar} kVAR; factory-installed discharge resistors per IEEE 18; APFC controller with anti-hunting timer; 7% detuning reactor for harmonic protection; factory test certificate requirements; submittal of equipment data sheets and IEC certificates for Engineer's approval before procurement
   Section 3: Capacitor Bank Installation: cover installation at the main distribution board or nearest distribution panel to the load; panel mounting and anchoring; busbar connection torque per manufacturer specification; minimum clearances per PEC; anti-condensation provisions; labeling per PEC Art. 4.60 and DOLE OSH
   Section 4: Protection and Wiring: cover dedicated MCCB rated at 135% of capacitor rated current per PEC Art. 4.60.14; conductor sizing at 135% per IEEE 1036; conduit fill per PEC Table 3.10.1; conductor insulation resistance test ≥ 1 MΩ at 500V DC before energization; earthing and bonding per PEC Art. 2.50
   Section 5: APFC Controller, Metering, and Commissioning: cover APFC controller programming for step count matching the capacitor bank; anti-hunting timer setting (minimum 30 seconds between switching cycles); power analyzer setup for PF, kVAR, kWh, and THD monitoring; pre-energization insulation resistance test; power factor measurement with calibrated power analyzer before and after installation under full load to verify PF ≥ ${pfTarget}; harmonic THD measurement if VFDs or non-linear loads are present
   Section 6: Testing and Commissioning: cover insulation resistance test of all conductors (≥ 1 MΩ at 500V DC megger); step-by-step energization of capacitor bank; APFC automatic switching cycle test (verify each step switches in/out correctly); PF measurement at MDB before correction and after full bank energization: results recorded in test report; ATS or disconnect switching test; 4-hour continuous operation monitoring after full energization; all test results witnessed by the Engineer
   Section 7: Documentation, Permits, and Warranty: cover Electrical Permit from LGU before commencement; all electrical works by a licensed master electrician under the supervision of a PRC-licensed Electrical Engineer; as-built single-line diagram showing capacitor bank, APFC, protection, and metering; certified PF measurement test report (before and after) submitted to Owner and Meralco as required for DSM compliance; O&M manual and manufacturer's warranty documentation submitted at project completion; warranty minimum 12 months on capacitor bank and APFC controller

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical: Cable Tray Sizing BOM + SOW Agent ───────────────────────────

async function cableTrayBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project       = inputs.project_name    || "Cable Tray Route Project";
  const trayType      = inputs.tray_type       || "Ladder";
  const depthMm       = inputs.depth_mm        || 75;
  const fillLimitPct  = inputs.fill_ratio_pct  || 40;
  const spanM         = inputs.span_m          || 1.5;
  const runLengthM    = inputs.run_length_m    || 30;
  const selWidthMm    = results.selected_width_mm  || "";
  const fillActualPct = results.fill_actual_pct    || "";
  const fillCheck     = results.fill_check         || "";
  const nemaClass     = results.nema_load_class    || "";
  const deratingFactor= results.derating_factor    ?? 1.0;
  const deratingApplies = Number(deratingFactor) < 1.0;
  const cables        = Array.isArray(inputs.cables) ? (inputs.cables as Array<{ cable_type: string; od_mm: number; qty: number }>) : [];
  const cableSummary  = cables.map(c => `${c.qty}× ${c.cable_type} (OD ${c.od_mm} mm)`).join(", ");

  const prompt = `You are a Philippine electrical engineering expert (NEMA VE 1, NEC Article 392, PEC 2017 Article 3.92). Generate a professional BOM and SOW for a CABLE TRAY SIZING and installation project.

PROJECT: ${project}
TRAY TYPE: ${trayType}
SELECTED TRAY: ${selWidthMm} mm wide × ${depthMm} mm deep ${trayType} cable tray
NEMA VE 1 LOAD CLASS: ${nemaClass}
FILL: ${fillActualPct}% (limit ${fillLimitPct}%): ${fillCheck}
SUPPORT SPAN: ${spanM} m
CABLE TRAY RUN LENGTH: ${runLengthM} m
CABLES: ${cableSummary}
AMPACITY DERATING: ${deratingApplies ? `APPLIES: fill exceeds 30%, derate conductors to 80% per NEC 392.80` : `NOT REQUIRED: fill ≤ 30%`}
STANDARDS: NEMA VE 1, NEMA VE 2, NEC Article 392, NEC 310.15, PEC 2017 Article 3.92

Generate a JSON object with:
1. "bom_items": array of 12 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Cable Tray: ${trayType} Type (${selWidthMm} mm W × ${depthMm} mm D, hot-dip galvanized steel per NEMA VE 1 Load Class ${nemaClass}, 12-gauge steel minimum, factory-punched rungs at 150/300 mm spacing for Ladder type: supply ${runLengthM} m plus 10% cutting allowance), Cable Tray Covers (solid galvanized steel cover, same width as tray: for outdoor, dusty, or mechanical damage risk areas; quantity per drawing), Cable Tray Splice Plates (NEMA VE 1 matching galvanized splice bars, fitted with self-aligning feature, minimum 2 bolts per side: 2 sets per 3 m tray section), Horizontal Elbows 90° (${selWidthMm} mm matching tray, hot-dip galvanized, bend radius per NEMA VE 1: quantity per routing plan), Horizontal Tees and Crosses (matching tray width and depth, galvanized: quantity per routing plan), Vertical Elbows: Rise/Drop (matching width, galvanized, for elevation changes: quantity per routing plan), End Closures / Cable Entry Plates (galvanized steel end plates per tray opening, prevent animal ingress: 2 per each tray end), Cable Tray Wall Brackets / Trapeze Hangers (galvanized steel wall-mounted brackets or trapeze hanger assemblies, load-rated for NEMA Class ${nemaClass} at ${spanM} m span: quantity = ${Math.ceil(Number(runLengthM) / Number(spanM)) + 2} sets minimum), Threaded Rod and Beam Clamps (M10 or M12 galvanized threaded rod with beam clamps and nuts for trapeze hangers: complete set), Cable Tray Divider Strip (longitudinal divider rail for segregating power cables from control/instrumentation cables per NEMA VE 2: quantity per run length), Bonding Jumpers and Earth Continuity Clamps (copper bonding jumper per splice, earthing lug at each bracket point, 6 mm² green/yellow bonding cable: complete set per NEMA VE 2 Section 4 for electrical continuity of the entire tray run), Installation Hardware: Complete Set (stainless steel M8/M10 bolts, spring nuts, washers, hex nuts, nylon cable ties, warning labels, PEC Art. 3.92 labeling: complete lot)

2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Write each content as a full professional paragraph starting with "The Contractor shall...": do NOT use bullet points or keyword lists. Each section must be 3–6 sentences of contractor-facing specification language.
   Cover:
   Section 1: Scope of Works and Design Basis: state that this SOW covers supply, fabrication, installation, earthing, and testing of a ${selWidthMm} mm × ${depthMm} mm ${trayType} cable tray system for project ${project} along the route as shown in the Electrical Layout Drawings; reference calculation basis (NEMA VE 1 Load Class ${nemaClass}, NEC Article 392, PEC 2017 Article 3.92); state the total cable fill is ${fillActualPct}% (${fillCheck}: limit ${fillLimitPct}%); state that ${deratingApplies ? `conductor ampacity derating at 80% is required because fill exceeds 30% per NEC 392.80: all power cable ampacities shall be derated accordingly` : `no conductor ampacity derating is required as fill does not exceed 30% per NEC 392.80`}; state route total length ${runLengthM} m with ${spanM} m support spacing
   Section 2: Material Supply and Approval: cover supply of NEMA VE 1 Load Class ${nemaClass} hot-dip galvanized steel ${trayType} cable tray, ${selWidthMm} mm wide × ${depthMm} mm deep; require submittal of NEMA VE 1 compliance certificate, load class certification, and hot-dip galvanizing certificate (ASTM A123) to the Engineer for approval before procurement; specify matching fittings (elbows, tees, reducers, splice plates) from the same manufacturer for dimensional compatibility; specify cable tray divider for separation of power cables from control and signal cables
   Section 3: Installation and Support: cover installation of cable tray on galvanized steel wall brackets or trapeze hangers at ${spanM} m centres maximum, anchored to building structure using wedge anchors or beam clamps per NEMA VE 2; state required clearances: minimum 300 mm above tray for cable installation access, 150 mm minimum side clearance per NEC 392.6; specify level installation (±5 mm/m tolerance) with all fittings properly aligned; cover installation of cable tray covers at all outdoor, exposed, or fire-rated sections
   Section 4: Cable Routing and Tray Fill: cover cable installation within the cable tray shall not exceed the calculated fill of ${fillActualPct}% (limit ${fillLimitPct}% per NEC 392.22); cables shall be arranged in a single or multiple layers as required by the fill calculation, with power cables segregated from control and instrumentation cables by a tray divider; all cables to be secured at tray entry/exit points and at each support with approved nylon cable ties or cleats; cables shall have sufficient slack at equipment connections for thermal expansion and maintenance access
   Section 5: Earthing and Bonding: cover installation of copper bonding jumpers across every splice plate and fitting joint to ensure electrical continuity of the complete cable tray system per NEMA VE 2 Section 4 and PEC 2017 Article 2.50; earthing lugs to be installed at every support bracket and connected to the building main earth using 6 mm² green/yellow copper conductors; measured earth continuity resistance of the complete tray run shall not exceed 1 Ω end-to-end; submit measured results to the Engineer as part of the commissioning test report
   Section 6: Testing and Inspection: cover pre-installation inspection of all cable tray sections for galvanizing defects, dimensional compliance with NEMA VE 1, and damaged rungs or rails; post-installation inspection to verify span compliance, levelness, secure anchoring, and correct fitting alignment; earth continuity test of the complete tray run (end-to-end resistance ≤ 1 Ω); visual inspection of fill ratio compliance (actual fill ≤ ${fillLimitPct}%); all test and inspection results to be recorded in a commissioning test report and submitted to the Engineer for approval
   Section 7: Documentation and Regulatory Compliance: cover submission of Electrical Permit from the LGU before commencement of installation; all electrical works to be performed by a licensed master electrician under the supervision of a PRC-licensed Electrical Engineer; submission of as-built cable tray layout drawings showing all tray routes, fittings, support locations, cable groupings, and earthing connections; submission of NEMA VE 1 compliance certificates, galvanizing certificates, and load class certification for all materials; final commissioning test report including earth continuity results and fill ratio inspection; minimum 12-month warranty on all supplied materials against manufacturing defects and corrosion failure

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical: UPS Sizing BOM + SOW Agent ──────────────────────────────────

async function upsSizingBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project      = inputs.project_name    || "UPS Installation Project";
  const topology     = inputs.topology        || "Online (Double-Conversion)";
  const phase        = inputs.phase           || "3-Phase";
  const backupMin    = inputs.backup_min      || 30;
  const growthFactor = inputs.growth_factor   || 1.20;
  const upsEff       = inputs.ups_eff         || 0.96;
  const selectedKVA  = results.selected_kva   || "";
  const loadingPct   = results.loading_pct    || "";
  const battConfig   = results.battery_config || "";
  const battV        = results.battery_voltage_v || "";
  const selectedAh   = results.selected_ah    || "";
  const runtimeMin   = results.actual_runtime_min || "";
  const inputBreakerA= results.input_breaker_a || "";
  const inputCurrentA= results.input_current_a || "";
  const iecClass     = topology === "Online (Double-Conversion)" ? "VFI-SS-111" : topology === "Line Interactive" ? "VI-SS-111" : "VFD-SS-111";

  const prompt = `You are a Philippine electrical engineering expert (IEC 62040-3, IEEE 446, IEEE 1184, PEC 2017 Article 7). Generate a professional BOM and SOW for a UPS SIZING and installation project.

PROJECT: ${project}
UPS TOPOLOGY: ${topology} (IEC 62040-3 ${iecClass})
PHASE: ${phase}
SELECTED UPS: ${selectedKVA} kVA
SYSTEM LOADING: ${loadingPct}% (max 80% recommended per IEEE 446)
GROWTH FACTOR: ${growthFactor}x
UPS EFFICIENCY: ${Math.round(Number(upsEff) * 100)}%
BATTERY BANK: ${battConfig} (${battV}V DC bus, ${selectedAh}Ah per string)
BACKUP AUTONOMY: ${runtimeMin} minutes at design load (required: ${backupMin} min)
INPUT BREAKER: ${inputBreakerA}A dedicated MCCB
INPUT CURRENT: ${inputCurrentA}A at full load
STANDARDS: IEC 62040-1, IEC 62040-3 (${iecClass}), IEEE 446, IEEE 1184, PEC 2017 Article 7

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: UPS Main Unit (${selectedKVA} kVA ${topology} UPS, IEC 62040-3 ${iecClass} certified, ${phase}, input voltage ${phase === "3-Phase" ? "415V ±15% 3-phase 4-wire 60Hz" : "230V ±15% single-phase 60Hz"}, output voltage ${phase === "3-Phase" ? "415V/240V" : "230V"} ±2% regulated, THDv < 2% at linear load, efficiency ≥ ${Math.round(Number(upsEff) * 100)}%, static bypass included, RS-232/SNMP monitoring port, hot-swappable batteries if applicable), Static Bypass Panel (motorized static bypass with open/neutral/UPS positions: for maintenance without loss of supply to critical loads: rated for ${selectedKVA} kVA), Maintenance Bypass Breaker (manual maintenance bypass MCCB, ${Math.ceil(Number(inputCurrentA) * 1.25)} A, interlocked with UPS output breaker to prevent paralleling), VRLA Battery Cabinets (${battConfig}: factory-assembled battery string in ventilated steel cabinet with battery management system, temperature sensor, and individual cell fusing: IEC 62040-1 rated), Battery Disconnect Switch (lockable DC isolator switch rated for ${battV}V DC, ${Math.ceil(Number(selectedAh) * 1.2)} A: one per battery string, for maintenance isolation), Battery Cable Set (flexible copper battery cables, cross-linked PE insulation rated for ${battV}V DC, colour-coded red/black, pre-terminated with compression lugs: complete set per string), UPS Input Isolator / Incomer MCCB (${inputBreakerA}A MCCB, 3-pole, interrupt capacity ≥ 25 kA at 415V: for dedicated UPS input feeder from main distribution panel), UPS Output Distribution Panel (busbar rated for ${selectedKVA} kVA, with individual outgoing MCBs or MCCBs for each critical load circuit: labelled, lockable, with surge protection device on outgoing bus), Network UPS / SNMP Card (SNMP v1/v2/v3 card for remote monitoring of UPS status, battery level, load %, alarms, runtime remaining: integration with building management system or DCIM if applicable), UPS Monitoring Software (vendor-supplied UPS software licence for graceful shutdown of servers on battery: compatible with major hypervisors; include 1-year support subscription), Equipment Base Frame / Seismic Anchor Set (galvanized steel housekeeping pad or anti-vibration isolation frame, seismic anchor bolts for floor fixing of UPS and battery cabinets per ASCE 7 seismic zone requirements), Power Cable: UPS Input (THHN/THWN copper, sized for ${inputBreakerA}A feeder, in EMT or RSC conduit from MDB to UPS input incomer: length per drawing), Power Cable: UPS Output (THHN/THWN copper, sized per output panel schedule, in EMT conduit from UPS to output distribution panel: length per drawing), Earthing and Bonding Set (copper earthing conductor 16 to 25 sq.mm from UPS frame, battery cabinet frame, and bypass panel to building earth bus: complete with compression lugs and earth label tags per PEC Article 2.50)

2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Write each content as a full professional paragraph starting with "The Contractor shall...": do NOT use bullet points. Each section must be 3–6 sentences of contractor-facing specification language.
   Cover:
   Section 1: Scope of Works and Design Basis: state this SOW covers supply, installation, commissioning, and testing of a ${selectedKVA} kVA ${topology} UPS system (IEC 62040-3 ${iecClass}) for project ${project}; reference calculation basis (IEEE 446 loading ${loadingPct}% within 80% limit, backup autonomy ${runtimeMin} min meeting ${backupMin} min requirement, growth factor ${growthFactor}x); state battery bank is ${battConfig} at ${battV}V DC bus; state input incomer is ${inputBreakerA}A dedicated MCCB and static bypass is included for maintenance
   Section 2: Material Supply and Factory Certification: cover supply of a ${selectedKVA} kVA ${topology} UPS carrying valid IEC 62040-1 and IEC 62040-3 ${iecClass} certificates from an accredited test laboratory; require submission of UPS datasheet, factory test report (load bank discharge test at 100% load confirming minimum ${runtimeMin} min runtime), battery datasheet (IEC 62040-1 rated VRLA, ${selectedAh}Ah per cell), and SNMP card specifications for Engineer's approval before procurement; specify that the UPS manufacturer shall provide a minimum 2-year warranty on the UPS unit and batteries
   Section 3: Installation Requirements: cover installation of UPS and battery cabinets on a galvanized steel housekeeping pad anchored to the structural floor slab; state minimum clearances: 1 m front access, 0.6 m rear and side clearance per IEC 62040-1 installation requirements; specify input and output cabling in EMT or RSC conduit, sized per the approved panel schedule; state battery room or UPS room shall be air-conditioned to 20 to 25 degC ambient per IEEE 1184 to achieve design battery life; cover installation of seismic anchor brackets where applicable
   Section 4: Electrical Connections and Earthing: cover connection of the ${inputBreakerA}A MCCB input incomer from the main distribution board on a dedicated feeder: the UPS input shall not share a circuit with other loads; static bypass shall be wired to a separate bypass source feeder (same bus as input, independently fused) to allow complete UPS isolation for maintenance; output distribution panel shall be wired to all critical loads as shown on the approved single-line diagram; UPS frame, battery cabinet, and bypass panel shall be bonded to the building main earth using 16 to 25 sq.mm copper conductors per PEC Article 2.50; measured earth resistance shall not exceed 5 ohm
   Section 5: Battery Installation and Management: cover installation of battery cabinets adjacent to the UPS within the allowable DC cable length (typically up to 5 m for VRLA strings) to minimise voltage drop and inductance; battery strings to be connected in the polarity sequence specified by the UPS manufacturer: reverse polarity will damage the UPS rectifier/inverter and void warranty; install individual string isolation switches (DC rated for ${battV}V) for safe battery replacement under load (hot-swap procedure per manufacturer documentation); battery management system shall monitor individual cell voltage, temperature, and state of charge: alarms to be wired to the SNMP card and building BMS
   Section 6: Testing and Commissioning: cover pre-commissioning checks including insulation resistance test (above 1 Mohm at 500V DC on all AC wiring), DC polarity and voltage verification of each battery string, and earthing continuity test; functional tests to include UPS self-test, mains simulation failure (transfer to battery and back), bypass transfer, and alarm verification; full-load battery discharge test per IEC 62040-3: connect design load (${selectedKVA} kVA at ${loadingPct}% loading = design VA), record battery voltage, load and runtime every 5 minutes until battery low-voltage cutout, confirm measured runtime meets ${backupMin} min minimum; all test results to be recorded in a commissioning test report signed by the Contractor and witnessed by the Engineer
   Section 7: Documentation and Regulatory Compliance: cover submission of Electrical Permit from the LGU before commencement; all electrical works to be performed by a licensed master electrician under supervision of a PRC-licensed Electrical Engineer; submission of as-built single-line diagram showing UPS, bypass, battery bank, input/output breakers, and all distribution circuits; submission of IEC 62040-1 and IEC 62040-3 certificates, factory test report, battery datasheets, and SNMP card configuration guide; commissioning test report including discharge test results; UPS and battery warranty registration documents; O&M manual covering routine maintenance schedule, battery replacement procedure, and emergency bypass procedure

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical: Earthing / Grounding System BOM + SOW Agent ─────────────────

async function earthingBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project    = String(inputs.project_name     || "Earthing System Project");
  const sysType    = String(inputs.system_type      || "Residential / Commercial");
  const elecType   = String(inputs.electrode_type   || "Rod");
  const soilRho    = inputs.soil_resistivity || 100;
  const numElec    = inputs.num_electrodes   || 1;
  const rodLen     = inputs.rod_length_m     || 3.0;
  const rodDia     = inputs.rod_dia_mm       || 16;
  const plateW     = inputs.plate_width_m    || 0.6;
  const plateH     = inputs.plate_height_m   || 0.6;
  const ringDia    = inputs.ring_dia_m       || 10;
  const svcCond    = inputs.service_cond_mm2 || 35;
  const sysVolt    = inputs.system_voltage   || 400;

  const rSingle    = results.r_single_ohm   || "";
  const rParallel  = results.r_parallel_ohm || "";
  const rLimit     = results.r_limit_ohm    || "";
  const passLabel  = results.pass_label     || "FAIL";
  const gecMm2     = results.gec_mm2        || 6;

  const elecDesc = elecType === "Rod"
    ? `${numElec}x copper-bonded steel rod ${rodLen}m L x ${rodDia}mm dia`
    : elecType === "Plate"
    ? `${numElec}x copper plate ${plateW}m x ${plateH}m`
    : `ring/loop conductor ${ringDia}m dia`;

  const limitBasis = sysType === "Substation / HV"
    ? "IEEE 80-2013 (1 Ohm max)"
    : sysType === "Industrial"
    ? "IEEE 142-2007 (5 Ohm max)"
    : "PEC 2017 Art. 2.50 (10 Ohm max)";

  const prompt = `You are a Philippine electrical engineering expert (PEC 2017 Art. 2.50, IEEE 80-2013, IEEE 142-2007, IEC 62305-3, NEC Art. 250). Generate a professional BOM and SOW for an EARTHING / GROUNDING SYSTEM installation project.

PROJECT: ${project}
SYSTEM TYPE: ${sysType}
SYSTEM VOLTAGE: ${sysVolt}V
ELECTRODE TYPE: ${elecType} (${elecDesc})
SOIL RESISTIVITY: ${soilRho} Ohm-m
NUMBER OF ELECTRODES: ${numElec}
CALCULATED R (single): ${rSingle} Ohm
CALCULATED R (combined): ${rParallel} Ohm
RESISTANCE LIMIT: ${rLimit} Ohm (${limitBasis})
COMPLIANCE STATUS: ${passLabel}
GEC SIZE (PEC Table 2.50.66): ${gecMm2} mm2 copper
SERVICE CONDUCTOR: ${svcCond} mm2

Generate a JSON object with:
1. "bom_items": array of 12 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Ground Electrode (${elecDesc}, copper-bonded per UL 467 or equivalent: qty ${numElec}), Ground Electrode Clamp/Connector (exothermic weld or compression-type copper alloy connector, rated for direct burial: qty ${numElec}, one per electrode), Grounding Electrode Conductor / GEC (${gecMm2} mm2 bare or green-insulated stranded copper conductor per PEC Table 2.50.66, qty in metres from service entrance to electrode), GEC Conduit Protection (rigid metallic conduit: 25mm min dia: for GEC where subject to physical damage above grade, qty in metres), Ground Rod Driving Sleeve (for rod installation: one per rod electrode, qty ${numElec}), Earthing Inspection Pit / Test Point (precast concrete or polymer inspection pit with removable cover: for post-installation resistance testing access, qty per electrode cluster), Bonding Jumper: Main (main bonding jumper connecting neutral bus to ground bus in main distribution panel: bare copper, minimum ${gecMm2} mm2, qty 1), Bonding Conductor: Equipment (bare copper or green-insulated stranded conductor for bonding of all metallic equipment enclosures, conduits, and cable trays to the earthing system: qty in metres as per drawing), Soil Treatment Compound (bentonite or equivalent ground enhancement material: GEM or MarconiteR compound for zones with high soil resistivity > 200 Ohm-m: qty in kg depending on site conditions), Copper Ground Bus Bar (tinned copper bus bar 6mm x 50mm, drilled with holes for GEC and bonding conductor terminations: wall-mounted in MDB room, qty 1), Earthing Label / Identification Tape (yellow-green bicolour PVC label tape or embossed stainless ID marker for all earthing conductors per PEC 2017 Art. 2.50 colour identification requirements, qty 1 set), Earth Resistance Test Kit / Wenner Meter (four-pole earth resistance tester, Wenner method per IEEE 81: for soil resistivity measurement and post-installation electrode resistance acceptance test, qty 1: Contractor to provide)

2. "sow_sections": array of 7 sections (each: section_no, title, content)
   Write each content as a full professional paragraph starting with "The Contractor shall...": do NOT use bullet points. Each section must be 3–6 sentences of contractor-facing specification language.
   Cover:
   Section 1: Scope of Works and Design Basis: state this SOW covers supply, installation, testing, and commissioning of the complete earthing and grounding system for ${project}; state the system type is ${sysType} with a calculated combined electrode resistance of ${rParallel} Ohm (${passLabel} vs. ${rLimit} Ohm limit per ${limitBasis}); state electrode type is ${elecType} (${elecDesc}), soil resistivity ${soilRho} Ohm-m; state GEC is ${gecMm2} mm2 copper per PEC 2017 Table 2.50.66; reference applicable standards: PEC 2017 Article 2.50, IEEE 80-2013, IEEE 142-2007, IEC 62305-3, and NEC Article 250
   Section 2: Material Supply and Compliance: cover supply of ${numElec}x ${elecType.toLowerCase()} electrode(s) complying with UL 467 (copper-bonded steel with minimum 0.25 mm copper cladding) or equivalent approved standard; all copper conductors shall be Class B stranded per ASTM B8; require submission of material test certificates, product datasheets, and UL 467 compliance documentation for Engineer review and approval before procurement; bentonite or ground enhancement compound shall be submitted with manufacturer's published resistivity reduction data if soil treatment is specified
   Section 3: Excavation and Electrode Installation: cover excavation for horizontal conductors or inspection pits to the depths shown on the approved earthing layout drawing; vertical rod electrodes shall be driven to the full design depth of ${elecType === "Rod" ? rodLen : 3}m using a mechanical driver or slide hammer: driving shall stop if the rod buckles; plate electrodes shall be buried vertically with the top edge at minimum 600 mm below finished grade and oriented parallel to the building perimeter; ring/loop conductors shall be laid at minimum 500 mm below finished grade in a trench backfilled with compacted soil free of rocks or debris; all earthing conductors in direct contact with soil shall be bare copper or copper with heat-shrink insulation: no aluminium conductors are permitted in direct burial
   Section 4: Conductor Connections and Bonding: cover all conductor-to-electrode and conductor-to-conductor connections in soil using exothermic welding (Cadweld or approved equivalent): mechanical clamps or crimp connectors shall be used only above grade where accessible for inspection; GEC shall run in rigid metallic conduit from the service entrance equipment to the first electrode where the conductor is subject to physical damage; the main bonding jumper connecting the neutral bus to the ground bus shall be installed in the service entrance equipment as a single unspliced conductor of minimum ${gecMm2} mm2; all metallic equipment enclosures, cable trays, conduits, and structural steel within the electrical room shall be bonded to the earthing system with minimum 6 mm2 copper bonding conductors per PEC 2017 Article 2.50
   Section 5: Soil Treatment (If Required): cover the application of bentonite or ground enhancement material (GEM) around each electrode if the initial pre-installation soil resistivity measurement exceeds ${Number(soilRho) > 200 ? "200" : "500"} Ohm-m: the Contractor shall submit the GEM product datasheet and manufacturer's installation procedure for Engineer approval before application; GEM shall be mixed to manufacturer-specified consistency and applied in a collar around each rod or beneath each plate electrode before backfilling; the Contractor shall allow a minimum 48-hour curing period before conducting the post-installation resistance test; if soil treatment does not achieve the required resistance limit, the Contractor shall propose additional electrodes or alternative electrode configurations for Engineer approval at no additional cost
   Section 6: Testing and Acceptance: cover pre-installation soil resistivity measurement by the Wenner four-pin method per IEEE 81 at the proposed electrode locations: results shall be submitted to the Engineer before driving any electrodes; post-installation acceptance test of each electrode using a calibrated fall-of-potential method or clamp-on earth resistance tester per IEEE 81: the measured resistance of the combined electrode system shall not exceed ${rLimit} Ohm as required by ${limitBasis}; bonding continuity test: measure resistance from each bonded equipment frame to the main earth bus using a low-resistance ohmmeter, maximum 0.1 Ohm; all test results including soil resistivity, individual electrode resistance, combined resistance, and bonding continuity shall be recorded in the earthing test register and submitted to the Engineer within 5 working days of test completion; no concrete pouring or permanent backfill over electrodes shall occur until written acceptance of test results by the Engineer
   Section 7: Documentation and Regulatory Compliance: cover submission of Electrical Permit from the LGU before commencement of earthing works; all earthing installation works shall be performed under the direct supervision of a PRC-licensed Electrical Engineer; as-built earthing layout drawings showing electrode locations, depth, conductor routing, inspection pit locations, and all bonding connections shall be submitted within 30 days of project completion; documentation package shall include: soil resistivity test report, post-installation earth resistance test report, bonding continuity test report, material certificates, and earthing test register signed and sealed by the Engineer of Record; the earthing system shall be inspected and retested at minimum every 5 years in accordance with PEC 2017 and IEEE 142 recommendations: include this requirement in the O&M manual

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical: Lightning Protection System BOM + SOW Agent ─────────────────

async function lpsBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project     = inputs.project_name      || "LPS Project";
  const strType     = inputs.structure_type    || "Commercial";
  const lpl         = inputs.lpl               || "LPL II";
  const airMeth     = inputs.air_term_method   || "Rolling Sphere";
  const dcMat       = inputs.dc_material       || "Copper";
  const earthType   = inputs.earth_type        || "Type A - Radial / Vertical Electrodes";
  const loc         = inputs.ng_location       || "Metro Manila / NCR";
  const rR          = results.rolling_sphere_R_m   ?? "30";
  const meshSz      = results.mesh_size_m          ?? "10";
  const nDC         = results.n_down_conductors    ?? "N/A";
  const nAT         = results.n_air_terminals_est  ?? "N/A";
  const dcSpacing   = results.dc_spacing_m         ?? "10";
  const nElec       = results.n_electrodes         ?? "N/A";
  const elecLen     = results.min_electrode_length_m ?? "N/A";
  const spdClass    = results.spd_class            || "Class I + II combination";
  const eff         = results.efficiency_pct       ?? "97";
  const riskCheck   = results.risk_check           || "LPS REQUIRED";

  const prompt = `You are a Philippine electrical engineering expert specializing in lightning protection systems. Generate a professional BOM and SOW for a LIGHTNING PROTECTION SYSTEM (LPS) installation project.

PROJECT: ${project}
STRUCTURE TYPE: ${strType}
LOCATION: ${loc}
LIGHTNING PROTECTION LEVEL: ${lpl} (${eff}% efficiency)
RISK ASSESSMENT RESULT: ${riskCheck}
AIR TERMINATION METHOD: ${airMeth}
ROLLING SPHERE RADIUS: ${rR} m
MESH SIZE: ${meshSz} m × ${meshSz} m
ESTIMATED AIR TERMINALS / MASTS: ${nAT} units
DOWN CONDUCTOR MATERIAL: ${dcMat}
DOWN CONDUCTOR SPACING: ${dcSpacing} m
NUMBER OF DOWN CONDUCTORS: ${nDC}
EARTH TERMINATION TYPE: ${earthType}
MINIMUM ELECTRODE LENGTH: ${elecLen} m
NUMBER OF ELECTRODES: ${nElec}
SPD CLASS: ${spdClass}
STANDARDS: IEC 62305-1/2/3/4, NFPA 780, PEC 2017 Article 2.50

Generate a JSON object with:
1. "bom_items": array of 15 items (each: description, specification, qty, unit, remarks, checked: true)
   Include these items in order:
   1. Air Termination Conductors / Tape: 25mm x 3mm flat copper tape or 8mm dia solid copper rod; corrosion-resistant; installed along roof ridge, parapet, and edges per ${airMeth} method; all joints with listed compression or exothermic connectors. qty: ${nAT}, unit: lot (per roof layout)
   2. Air Termination Masts / Franklin Rods: stainless steel 316L or hot-dip galvanized steel rod, minimum 10mm dia x 300mm exposed above highest point; used at corners and high points of roof to supplement tape network; base clamp with stainless fasteners. qty: ${nAT}, unit: units
   3. Down Conductors: ${dcMat === "Copper" ? "50mm2 bare annealed copper rope conductor" : dcMat === "Aluminum" ? "70mm2 aluminum conductor" : "50mm2 hot-dip galvanized steel flat conductor 25mm x 4mm"}; installed in UV-resistant PVC conduit (25mm dia) where exposed; fixed with non-ferrous saddle clamps at 1m spacing. qty: ${nDC} runs, unit: lot (each run = full height of structure)
   4. Test Joints: disconnectable test joint at base of each down conductor (500mm above finished floor level); allows earth resistance measurement per IEC 62305-3 S5.3.5; listed compression fitting, corrosion-resistant; labelled "LPS TEST JOINT - DO NOT DISCONNECT". qty: ${nDC}, unit: units
   5. Earth Electrode Assembly (${earthType}): ${String(earthType).includes("Type A") ? `copper-bonded steel rod, 20mm dia x ${elecLen}m length; driven vertically at base of each down conductor; 10mm dia bare copper earth lead from test joint to rod top; bentonite backfill where soil resistivity > 200 ohm-m` : `25mm x 4mm copper tape ring electrode buried at 500mm depth around building perimeter; minimum burial depth 300mm; connected to all down conductors and main equipotential bonding bar`}. qty: ${nElec}, unit: units
   6. Earth Rod Driving Materials and Coupling Sleeves: steel coupling sleeve for deep-drive extension; driving head (sacrificial); 3m extension rods if initial resistance > 10 ohms after first rod; bentonite clay powder (20kg bag) per electrode for soil conditioning. qty: ${nElec}, unit: sets
   7. Main Equipotential Bonding Bar (MEBB): 50mm x 6mm tinned copper busbar, minimum 500mm long; wall-mounted in accessible location (ground floor electrical room or at cable entry point); connection lugs for down conductors, LV earth, water pipe, gas pipe, telecommunications earth. qty: 1, unit: unit
   8. Bonding Conductors (Metallic Services): 16mm2 bare copper conductor for bonding of water supply pipe, gas pipe, structural steel, and all metallic services entering structure to MEBB; listed compression connectors at each bond point; installed per IEC 62305-3 S6.2. qty: 1, unit: lot (per site survey)
   9. Surge Protective Devices - SPD at MDB / LV Entry: ${spdClass} SPD at main distribution board LV supply entry; IEC 61643-11 certified; In >= 20kA (10/350us for Type 1); Up <= 2.5kV; with backup fuse or built-in thermal disconnect; DIN-rail mount; 3-pole + N for 3-phase, 1-pole + N for single-phase; submit data sheet for Engineer approval. qty: 1, unit: set
   10. Surge Protective Devices - SPD at Sub-Distribution Boards: Type 2 (Class II) SPD at each SDB / panelboard; IEC 61643-11; In >= 10kA (8/20us); Up <= 1.5kV; one set per SDB identified in load schedule. qty: per number of SDBs (contractor to count from single-line diagram), unit: sets
   11. Surge Protective Devices - Data / Telecommunications Lines: Type 2/3 data line SPD at all metallic cable entries (RJ45, RS-485, coax, telephone); IEC 61643-21; installed at demarcation point where external lines enter structure; flush-mount or wall-mount per cabling type. qty: 1, unit: lot
   12. LPS Conductor Supports and Saddle Clamps: non-ferrous saddle clamps (copper or stainless) for securing flat tape and round conductors to masonry, concrete, and structural steel; at 1m max spacing on horizontal runs, 1.5m on vertical runs; plastic-anchored where drilling into concrete block. qty: 1, unit: lot (per linear meter of conductor run)
   13. PVC Conduit and Fittings for Concealed Down Conductors: 25mm dia heavy-duty PVC conduit for protecting down conductors passing through occupied areas, below-grade sections, and areas subject to mechanical damage; LB fittings, couplings, and elbows as needed; conduit must be non-metallic to avoid eddy currents. qty: 1, unit: lot (per linear meter)
   14. Signage and Warning Labels: stainless steel engraved label at each test joint "LPS TEST JOINT - DISCONNECT FOR TESTING ONLY"; roof access area warning sign "LIGHTNING PROTECTION SYSTEM - AUTHORIZED PERSONNEL ONLY"; LPS single-line diagram in weatherproof frame at MEBB location. qty: 1, unit: lot
   15. Miscellaneous: earth resistance tester (Fall-of-Potential method per IEEE 81, 3-terminal Megger or equivalent); earth resistance test report (all electrodes, combined system); photographic records of all electrode installations; as-built LPS layout drawing; SPD installation certificates; IEC 62305-2 risk assessment report; O&M manual with cleaning and inspection schedule. qty: 1, unit: lot

2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover:
   - "1.0" General Scope: Supply, install, test, and commission a complete Lightning Protection System (LPS) for ${project}, a ${strType} in ${loc}. Design basis: IEC 62305-2 risk assessment result: ${riskCheck}. Protection Level: ${lpl} (${eff}% protection efficiency). Air termination method: ${airMeth}. System consists of air termination network (${nAT} terminals), ${nDC} down conductors at ${dcSpacing}m spacing, ${nElec} earth electrodes (${earthType}), main equipotential bonding bar, and ${spdClass} SPDs. All work in accordance with IEC 62305-1/2/3/4, NFPA 780, and PEC 2017 Article 2.50. BOM quantities are estimates; contractor shall verify against approved architectural and electrical drawings.
   - "2.0" Applicable Standards and Permits: IEC 62305-1:2010 General Principles; IEC 62305-2:2010 Risk Management; IEC 62305-3:2010 Physical Damage (air termination, down conductors, earth termination, bonding); IEC 62305-4:2010 Electrical and Electronic Systems (SPD zones); NFPA 780:2023 Installation of LPS; PEC 2017 Article 2.50 Earthing and Bonding; IEC 61643-11 SPD for LV power systems; IEC 61643-21 SPD for telecommunications; IEEE 81 earth resistance measurement; DOLE OSH Electrical Safety Standards. LGU Electrical Permit required before installation; all electrical works by licensed master electrician under PRC-licensed Electrical Engineer.
   - "3.0" Air Termination Network: Install air termination network using ${airMeth} method to IEC 62305-3. Rolling sphere radius R=${rR}m defines the protected zone; any point on the roof not touched by a sphere of radius ${rR}m rolling over the air terminals is unprotected. Flat copper tape (25mm x 3mm) installed along all roof edges, ridges, and parapets. Franklin rods installed at all corners and high points. All horizontal runs must have continuity with no gaps or high-impedance splices. Tape must not form a loop with unequal path lengths; split at midpoint and run both ways to nearest down-conductor connection. All joints silver-soldered, exothermic-welded, or compression-clamped (no bolted joints in areas subject to corrosion). Roof penetrations sealed against water ingress.
   - "4.0" Down Conductor System: Install ${nDC} down conductors of ${dcMat} at maximum ${dcSpacing}m spacing around building perimeter. Each run must be as straight and vertical as possible; bends of radius < 0.2m are not permitted (IEC 62305-3 S5.3.2). Protect all down conductors from 300mm below finished floor level to 2.4m above with 25mm PVC conduit. Install disconnectable test joint at 500mm above finished floor per down conductor. Maintain minimum separation distance from all metallic structural elements per IEC 62305-3 S6.3 to prevent dangerous sparking. Do not route down conductors through fuel store, gas room, or electrical switchroom.
   - "5.0" Earth Termination System: Install ${nElec} earth electrodes (${earthType}) per IEC 62305-3 S5.4; minimum electrode length ${elecLen}m per IEC 62305-3 Annex E (based on soil resistivity). After installation, measure resistance of each individual electrode using Fall-of-Potential method (IEEE 81 / IEC 62305-3 Annex E). Combined system resistance target <= 10 ohms; if combined resistance > 10 ohms: add additional rods, use bentonite, or install ring electrode. Submit all resistance readings for Engineer approval before connecting to building earthing system. Integrate with LV system earth at MEBB as a single point of connection to avoid circulating currents.
   - "6.0" Equipotential Bonding: Install MEBB at building electrical entry point. Bond all metallic services entering structure (water, gas, telecommunications, structural steel, elevator rails) to MEBB with 16mm2 Cu conductors per IEC 62305-3 S6.2. All bonds as close to building entry point as practicable. Install ${spdClass} SPDs at MDB entry, Type 2 SPDs at all SDBs, and Type 2/3 data-line SPDs at all telecommunications entry points. SPD selection per IEC 62305-4 LPZ zone-to-zone analysis. Up of SPDs must be coordinated (MDB Up <= 2.5kV, SDB Up <= 1.5kV, equipment-level Up <= 1.0kV). Submit SPD data sheets for Engineer approval before procurement.
   - "7.0" Testing, Commissioning, and Handover: Perform continuity test on complete LPS conductor network (air termination to down conductors to test joints to electrodes); resistance from any air termination point to any earth electrode must be <= 1 ohm. Perform earth resistance test (Fall-of-Potential, IEEE 81) on all electrodes individually and combined system. SPD installation verification: correct polarity, backup protection, thermal disconnect functional. All test results documented and submitted to Engineer and Owner. Provide as-built LPS layout drawing (roof plan, elevation, earth termination plan) with conductor routes, electrode locations, and bonding points; SPD certificates; electrode depth records; photographic installation records; IEC 62305-2 risk assessment report; and O&M manual including annual inspection checklist and 5-year electrode replacement schedule.
   - "8.0" Maintenance Schedule and Owner Obligations: Visual inspection after every severe thunderstorm (check for physical damage, disconnected conductors, or displaced air terminals). Annual inspection by licensed electrical engineer (verify continuity, check test joints, inspect SPD condition indicators, measure earth resistance). 5-year full inspection: re-measure earth resistance of all individual electrodes, replace any SPD with tripped thermal disconnect, check exothermic welds for corrosion, verify bonding integrity of all metallic services. LPS inspection report to be kept on file for LGU/BFP/DOLE inspection. SPDs replaced immediately upon activation indicator showing fault. Do not connect additional metallic services or make structural changes without informing the LPS designer, as any change to building profile may invalidate the risk assessment.

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical: Generator Sizing BOM + SOW Agent ────────────────────────────

async function generatorSizingBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name    || "Generator Project";
  const application    = results.application    || inputs.application    || "Standby (ESP)";
  const phaseConfig    = results.phase_config   || inputs.phase_config   || "3-Phase";
  const runningKVA     = results.running_kva    ?? "N/A";
  const runningKW      = results.running_kw     ?? "N/A";
  const designKVA      = results.design_kva     ?? "N/A";
  const selectedKVA    = results.selected_kva   ?? "N/A";
  const selectedKW     = results.selected_kw    ?? "N/A";
  const loadingPct     = results.loading_pct    ?? "N/A";
  const safetyFactor   = results.safety_factor  ?? 1.25;
  const motorHP        = results.motor_hp       ?? 0;
  const startMethod    = results.start_method   || "DOL";
  const startingKVA    = results.starting_kva   ?? 0;
  const overallPF      = results.overall_pf     ?? 0.85;
  const fuel100LHr     = results.fuel_100pct_lhr ?? "N/A";
  const fuel75LHr      = results.fuel_75pct_lhr  ?? "N/A";
  const tank8hrL       = results.tank_8hr_litres ?? "N/A";

  const prompt = `You are a Philippine electrical engineering expert (PEC 2017, ISO 8528-1, NFPA 110). Generate a professional BOM and SOW for a GENERATOR SIZING and installation project.

PROJECT: ${project}
APPLICATION: ${application}
PHASE CONFIGURATION: ${phaseConfig}
OVERALL POWER FACTOR: ${overallPF}
RUNNING DEMAND: ${runningKW} kW / ${runningKVA} kVA
LARGEST MOTOR: ${motorHP} HP: Start Method: ${startMethod}: Starting kVA surge: ${startingKVA} kVA
DESIGN kVA (with ${safetyFactor}× safety factor): ${designKVA} kVA
SELECTED GENSET: ${selectedKVA} kVA / ${selectedKW} kW (at 0.8 PF)
SYSTEM LOADING: ${loadingPct}% of rated capacity
FUEL CONSUMPTION: ${fuel100LHr} L/hr at 100% load; ${fuel75LHr} L/hr at 75% load
MINIMUM FUEL TANK (8-hr NFPA 110 runtime): ${tank8hrL} L
STANDARDS: ISO 8528-1 (genset ratings), PEC 2017 Article 7 (standby systems), NFPA 110 (emergency/standby power), IEC 60947 (switchgear), Philippine DOLE OSH regulations

Generate a JSON object with:
1. "bom_items": array of 18 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Diesel generator set (${selectedKVA} kVA / ${selectedKW} kW at 0.8 PF: ${phaseConfig}, 415V/240V, 60 Hz, ISO 8528-1 rated for ${application} service, DENR AO 2016-07 / Euro-3 emission-compliant diesel engine, synchronous alternator with integrated AVR ±1% voltage regulation, IP23 weather-protected enclosure), automatic transfer switch / ATS panel (4-pole motorized, current-rated at ${Math.ceil(Number(selectedKVA) * 1000 / 415 / 1.732)} A minimum for ${phaseConfig} 415V system: with open/closed/neutral positions, auto/manual/test mode, transfer time ≤ 10 s, retransfer delay timer, PEC Art. 7 compliant), main circuit breaker for genset output (MCCB, rated ≥ 125% of ${selectedKW} kW FLA, interrupt capacity ≥ 25 kA), genset control panel / annunciator (digital controller: auto start/stop, fault alarm outputs: low oil pressure, high coolant temp, overcrank, overspeed, battery failure), battery set for engine starting (maintenance-free lead-acid or VRLA, 12V/24V per manufacturer spec, sized for ≥ 10 cold cranking starts), battery charger (trickle/float type, 10A minimum, with charge status indicator), diesel day tank / base tank (${tank8hrL}L minimum capacity: 8-hr runtime per NFPA 110, UL-listed steel tank with level gauge, vent, drain valve), fuel supply piping (black steel Schedule 40, 25–50 mm diameter from bulk tank to day tank to genset, with isolation valves and flexible connector), flexible exhaust connection and muffler (residential-grade or critical-grade muffler per ambient noise requirements, stainless steel flex bellows, weather-protected exhaust termination ≥ 3 m above grade), exhaust pipe and stack (75–150 mm black steel Schedule 40, insulated where passing through occupied spaces), anti-vibration mounts / base isolation pads (4-point neoprene isolators rated for genset weight, ≤ 5 mm deflection), generator room ventilation louvers (supply and exhaust, motorized dampers, sized for 100% combustion air plus cooling air), earthing / grounding conductor (copper, 16–25 mm² to earth electrode, bonded to genset frame and ATS enclosure, PEC Art. 1.50), output power cable (THHN/THWN copper, sized for ${selectedKW} kW load at 415V: 125% continuous load factor, in EMT conduit), cable tray or conduit system (EMT/IMC, properly sized, from genset to ATS to main distribution panel), remote annunciator panel (if genset room is unmanned: fault alarms, run hours, battery status: mounted at building entrance or security desk), genset commissioning and load bank test report (factory test certificate, site acceptance test at 100% load for minimum 2 hours)
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (ISO 8528-1 ${application} rating, ${phaseConfig} 415V/240V 60 Hz, running demand ${runningKW} kW / ${runningKVA} kVA, design kVA ${designKVA} kVA with ${safetyFactor}× safety factor, selected ${selectedKVA} kVA genset, system loading ${loadingPct}%, starting surge ${startingKVA} kVA via ${startMethod}), Generator Set Installation (concrete inertia base or structural steel skid, anti-vibration mounts, clearances per manufacturer: minimum 1 m all sides, exhaust routing, weatherproofing for outdoor-rated enclosure), Automatic Transfer Switch (ATS) Installation (4-pole ATS wiring to utility and genset bus, normal-to-emergency transfer time ≤ 10 sec per NFPA 110 for Level 1 systems, retransfer delay, test mode, bypass provision), Fuel System (day tank installation at ${tank8hrL}L minimum, bulk fuel storage if provided, fill point, vent routing, overflow containment bund: DENR DAO 2013-22 spill containment requirements, fuel piping isolation valves, fuel level low alarm), Ventilation and Exhaust System (supply air louvers for combustion + cooling: minimum 0.1 m²/100 kW genset rating, critical-grade muffler installation, exhaust stack height and clearance from openings per DOLE OSH, noise assessment if within 30 m of occupied building), Earthing and Bonding (genset frame, ATS enclosure, neutral bonding per PEC Art. 7: single neutral bonding point, resistance ≤ 5 Ω to earth electrode, testing per PEC), Testing and Commissioning (factory test certificate review, no-load run 30 min, block load test at 25%/50%/75%/100% rated load: each step 15 min, ATS transfer and retransfer functional test, battery discharge and recharge test, fuel consumption verification, all fault alarm simulations, vibration and noise level measurement, test report sign-off by licensed PEE), Regulatory Compliance (PEC 2017 Article 7, NFPA 110 Level 1/Level 2 compliance, DOLE OSH mechanical and electrical installation permit, LGU/DENR permit for fuel storage if >200 L, as-built drawings, O&M manual, warranty registration)

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

Return ONLY valid JSON with exactly two keys: "bom_items" and "sow_sections".

"bom_items": array of exactly 18 objects, each: { "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required BOM items:
1. Upright/pendant sprinkler heads, K=${kFactor}, 68C, UL/FM listed: qty: ${nSprinklers}
2. Spare sprinkler heads + head wrench, NFPA 13 minimum 6 spares: qty: 1 set
3. Sprinkler head escutcheon plates, chrome-plated: qty: ${nSprinklers}
4. Riser pipe, ${pipeDiaMM} mm ${pipeMat} SCH40: qty: ${pipeLength} m
5. Branch line pipe, 25-40 mm ${pipeMat} SCH40: qty: 1 lot
6. Cross main pipe, 50-65 mm ${pipeMat} SCH40: qty: 1 lot
7. Pipe fittings and grooved couplings, UL/FM listed: qty: 1 lot
8. Pipe hangers and supports, NFPA 13, max 3.7 m spacing: qty: 1 lot
9. OS&Y gate valve, full-bore, UL/FM listed, with tamper switch: qty: 1 unit
10. Alarm check valve with waterflow alarm switch, UL listed: qty: 1 unit
11. Alarm bell / water motor gong, outdoor audible: qty: 1 unit
12. Alarm pressure gauge set (specification: 0-21 bar glycerin-filled bourdon-tube gauges, 100mm dial, 1/4 inch NPT threaded connection, brass/SS housing; one installed above and one below the alarm check valve for differential pressure monitoring per NFPA 13): qty: 2 pcs
13. Inspector test and drain valve, 25 mm ball valve: qty: 1 unit
14. Fire department siamese connection, 65x65 mm, BFP-compliant: qty: 1 unit
15. Water storage tank, ${waterVolL} L minimum, RC or GRP/HDPE: qty: 1 unit
16. Pressure gauge at system riser, 0-21 bar glycerin-filled: qty: 1 unit
17. Pipe identification labels and directional arrows, NFPA 13: qty: 1 lot
18. Commissioning and testing, hydrostatic and alarm test, BFP: qty: 1 lot

"sow_sections": array of exactly 8 objects, each: { "section_no": string, "title": string, "content": string }

Required SOW sections:
1.0 Scope of Works
2.0 Design Basis (NFPA 13, ${hazard}, density ${density} mm/min, K=${kFactor}, demand ${qTotal} L/min at ${pSource} bar)
3.0 Sprinkler Head Layout and Coverage
4.0 Pipe Installation
5.0 Valves, Alarm Devices, and Fire Department Connection
6.0 Water Supply and Storage Tank
7.0 Inspection, Testing, and Commissioning
8.0 Regulatory Compliance (RA 9514, BFP, NFPA 13/25)

Each content field must be a full professional paragraph starting with "The Contractor shall...".`;

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
    ? `Diesel drive selected: NFPA 20 requires motor rated at minimum 120% of pump BHP. Diesel backup is MANDATORY per BFP IRR for high-rise buildings and critical occupancies.`
    : `Electric motor drive: NFPA 20 requires motor rated at minimum 115% of pump BHP. A diesel backup pump is required in high-rise or critical occupancies per BFP IRR.`;

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
STANDARDS: NFPA 20 (Stationary Fire Pumps), NFPA 13 (Sprinkler Systems: source of flow/pressure), BFP Philippines Fire Code (RA 9514), Philippine Fire Code IRR, National Building Code PD 1096

Generate a JSON object with:
1. "bom_items": array of 16 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Fire pump unit: end suction centrifugal (${flowLpm} L/min @ ${TDH} m TDH, ${recommendedHp} HP ${driveType}, UL/FM listed: NFPA 20 Section 4), pump baseplate and coupling guard (common baseplate, flexible coupling, stainless guard), electric motor: TEFC (${recommendedHp} HP, ${nfpa20Pct}% of BHP per NFPA 20, IP55 enclosure, IE3 efficiency class), diesel engine driver (if applicable: ${isDiesel ? `backup required per BFP IRR, engine HP = ${nfpa20Pct}% x BHP` : "not required for this installation: electric primary selected"}), jockey (pressure maintenance) pump (small centrifugal, approx. 10% of main pump flow, maintains system pressure to prevent false alarms), jockey pump motor (fractional HP, DOL starter), main pump suction pipe: ${pipeDia}mm ${pipeMat} Sch.40 with eccentric reducer and isolation valve (flooded suction configuration per NFPA 20), main pump discharge pipe: ${pipeDia}mm ${pipeMat} Sch.40 with concentric reducer to system main, pump discharge check valve (swing type, UL/FM listed: prevents backflow on pump shutdown), pump discharge gate valve / butterfly valve (OS&Y or LI type with tamper switch, UL/FM listed), pressure relief valve (set at 10% above churn pressure: NFPA 20 requirement), pressure gauges: suction and discharge (glycerin-filled, 0–21 bar, per NFPA 20), flow meter / test header with sight glass or ultrasonic flow meter (for periodic flow testing per NFPA 25), fire pump controller: automatic pressure-sensing type (UL listed per NFPA 20, auto-start on pressure drop, manual stop only, alarm panel with remote signal), automatic transfer switch / ATS (if diesel backup is provided: transfers power on utility failure), vibration isolation pads and anchor bolts (per pump manufacturer specification, seismic restraint if required)
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (NFPA 20 design criteria, ${flowLpm} L/min @ ${requiredPressBar} bar, TDH=${TDH}m, ${driveType} drive, ${nfpa20Note}), Pump and Driver Installation (alignment, baseplate grouting, coupling guard, vibration isolation, NFPA 20 Section 4 clearance requirements), Piping Connections (suction eccentric reducer, discharge concentric reducer, pipe sizing per NFPA 20 velocity limits, hanger spacing, flanged connections to pump nozzles), Valves Instrumentation and Controller (OS&Y isolation valves with tamper switches, check valve, pressure gauges on suction and discharge, automatic fire pump controller per UL 218 / NFPA 20: auto-start, manual-stop-only, alarm outputs), Jockey Pump (sizing and installation, pressure setting to maintain system at ${(requiredPressBar * 100).toFixed(0)} kPa ± 35 kPa, prevent nuisance starts), Inspection Testing and Commissioning (churn/no-flow test, 100% flow test, 150% flow test at 65% pressure per NFPA 20 Section 12, pressure relief valve test, controller and ATS test, BFP acceptance inspection), Regulatory Compliance (RA 9514 Philippine Fire Code, NFPA 20 acceptance test witnessed by BFP AHJ, PRC-licensed Mechanical Engineer sign-off, O&M manual submission)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Fire Protection: Stairwell Pressurization BOM + SOW Agent ───────────────

async function stairwellPressBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name      || "Stairwell Pressurization Project";
  const buildingType   = results.building_type    || inputs.building_type   || "Sprinklered";
  const nStairwells    = Number(results.N_stairwells   ?? inputs.n_stairwells    ?? 2);
  const nFloors        = Number(results.N_floors        ?? inputs.n_floors        ?? 10);
  const doorFit        = String(results.door_fit        ?? inputs.door_fit        ?? "Average");
  const deltaP         = Number(results.delta_P_Pa      ?? inputs.delta_P         ?? 25);
  const fanStaticPa    = Number(results.fan_static_Pa   ?? inputs.fan_static_pressure ?? 400);
  const fanEffPct      = Number(results.fan_eff_pct     ?? inputs.fan_efficiency  ?? 60);

  const Q_per_CMH      = results.Q_per_CMH        ?? "N/A";
  const Q_design_CMH   = results.Q_design_CMH     ?? "N/A";
  const Q_design_m3s   = results.Q_design_m3s     ?? "N/A";
  const P_fan_kW       = results.P_fan_kW         ?? "N/A";
  const P_fan_HP       = results.P_fan_HP         ?? "N/A";
  const selected_HP    = results.selected_HP      ?? "N/A";
  const F_total_N      = results.F_total_N        ?? "N/A";
  const door_force_ok  = Boolean(results.door_force_ok ?? true);
  const delta_P_ok     = Boolean(results.delta_P_ok    ?? true);
  const delta_P_min    = results.delta_P_min      ?? (buildingType === "Sprinklered" ? 12.5 : 25);
  const delta_P_max    = results.delta_P_max      ?? 87;
  const A_total_m2     = results.A_total_m2       ?? "N/A";
  const N_doors_total  = results.N_doors_total    ?? "N/A";

  // Conditional flags
  const forceWarn = !door_force_ok;
  const forceNote = forceWarn
    ? `WARNING: Door opening force of ${F_total_N} N EXCEEDS NFPA 92 limit of 133 N. SOW must include a clause to reduce design pressure or specify lighter door closers before BFP approval.`
    : `Door opening force of ${F_total_N} N is within NFPA 92 limit of 133 N: acceptable.`;
  const pressNote = !delta_P_ok
    ? `WARNING: Design pressure differential of ${deltaP} Pa is OUTSIDE NFPA 92 limits (${delta_P_min}–${delta_P_max} Pa). SOW must flag this for design review.`
    : `Design pressure differential of ${deltaP} Pa is within NFPA 92 limits (${delta_P_min}–${delta_P_max} Pa).`;

  const prompt = `You are a Philippine fire protection engineering expert (NFPA 92, BFP Philippines). Generate a professional BOM and SOW for a STAIRWELL PRESSURIZATION SYSTEM installation project.

PROJECT: ${project}
BUILDING TYPE: ${buildingType}
NUMBER OF STAIRWELLS: ${nStairwells} (one pressurization fan per stairwell)
FLOORS SERVED: ${nFloors} floors
TOTAL STAIRWELL DOORS: ${N_doors_total} doors (${doorFit} fit: NFPA 92 Table B.1)
TOTAL LEAKAGE AREA PER STAIRWELL: ${A_total_m2} m²
DESIGN PRESSURE DIFFERENTIAL: ${deltaP} Pa: ${pressNote}
FAN STATIC PRESSURE: ${fanStaticPa} Pa
FAN EFFICIENCY: ${fanEffPct}%
AIRFLOW PER STAIRWELL: ${Q_per_CMH} m³/h
TOTAL DESIGN AIRFLOW (all stairwells, with 20% safety factor): ${Q_design_CMH} m³/h (${Q_design_m3s} m³/s)
FAN MOTOR POWER: ${P_fan_kW} kW (${P_fan_HP} HP) → Selected: ${selected_HP} HP
DOOR OPENING FORCE: ${F_total_N} N: ${forceNote}
STANDARDS: NFPA 92 (Smoke Control Systems), BFP IRR (Bureau of Fire Protection), National Building Code PD 1096, ASHRAE Handbook HVAC Applications Chapter 53

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Pressurization fan unit: centrifugal or axial, direct-drive, high-temperature rated 250°C/2hr (${nStairwells} units, each ${Q_per_CMH} m³/h at ${fanStaticPa} Pa static, ${selected_HP} HP motor, AMCA certified, smoke-rated per UL 705 or equivalent), pressurization fan motor: TEFC, ${selected_HP} HP, IE3 efficiency, IP55, suitable for emergency power operation (${nStairwells} units), variable frequency drive / VFD with bypass (optional: for modulating airflow to maintain target pressure differential; include if building has automated smoke control per NFPA 92 Section 7), fan inlet and discharge ductwork: galvanized steel, minimum 1.2 mm thick (total duct length per stairwell, including vertical riser to roof or mechanical room), supply air grilles / diffusers in stairwell: sized for ${Q_per_CMH} m³/h, ceiling or high-wall mounted (one per floor level, ${nFloors} units per stairwell, ${nStairwells} stairwells total = ${nFloors * nStairwells} units), duct access panels and balancing dampers (for commissioning and balancing per NFPA 92), backdraft damper at fan discharge (prevents reverse flow when fan is off: ${nStairwells} units), pressure differential sensor / controller (differential pressure transducer, 0-100 Pa range, paired with VFD if modulating control; audible and visual alarm on loss of pressure: ${nStairwells} units), emergency power transfer: automatic transfer switch (ATS) for fan power circuit; pressurization fans operate on emergency power per BFP IRR; generator connection or UPS interface), stairwell door weatherstripping and seals (upgrade to ${doorFit}-fit seals per NFPA 92 Table B.1 if required; perimeter brush or compression seal for all ${N_doors_total} stairwell doors), door closer hardware: rated for fire exit doors (all ${N_doors_total} stairwell doors; ensure opening force does not exceed 133 N per NFPA 92${forceWarn ? `; REDUCE door closer force or increase seal quality to bring door opening force below 133 N: current calc shows ${F_total_N} N` : ""}), duct insulation (50 mm mineral wool or equivalent for any ductwork passing through non-rated spaces), vibration isolation and fan mounting springs (per fan manufacturer specification, inertia base if required), commissioning instruments: handheld differential pressure meter, anemometer, tachometer (for BFP acceptance test and NFPA 92 commissioning verification)
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (NFPA 92 pressurization method, ${buildingType} building, ${deltaP} Pa design differential, ${Q_design_CMH} m³/h total, ${nStairwells} fans at ${selected_HP} HP each), Fan Installation (mounting, alignment, vibration isolation, motor connection, emergency power circuit), Ductwork and Air Distribution (duct sizing, routing from fan to stairwell supply grilles, duct penetrations through fire-rated walls sealed with fire dampers or intumescent sealant), Pressure Control and Instrumentation (pressure differential sensor installation, VFD setup if applicable, alarm setpoints, BAS interface), Door Seals and Hardware (installation of weatherstripping on all ${N_doors_total} stairwell doors, door closer adjustment to maintain opening force below 133 N per NFPA 92${forceWarn ? `: current design shows ${F_total_N} N which EXCEEDS the limit: MANDATORY redesign required before BFP approval` : ""}), Inspection Testing and Commissioning (pressurization test with all stairwell doors closed, differential pressure verification at each floor, door opening force measurement, emergency power transfer test, NFPA 92 Chapter 8 acceptance test witnessed by BFP AHJ), Regulatory Compliance (RA 9514 Philippine Fire Code, BFP high-rise provisions, PRC-licensed Mechanical Engineer sign-off, O&M manual and maintenance schedule submission per NFPA 92 Chapter 9)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Fire Protection: Fire Alarm Battery BOM + SOW Agent ─────────────────────

async function fireAlarmBatteryBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project          = inputs.project_name      || "Fire Alarm System Project";
  const sysVoltage       = Number(inputs.system_voltage    ?? 24);
  const standbyHours     = Number(inputs.standby_hours     ?? 24);
  const alarmMinutes     = Number(inputs.alarm_minutes     ?? 5);
  const panelStandbyMA   = Number(inputs.panel_standby_mA  ?? 50);
  const panelAlarmMA     = Number(inputs.panel_alarm_mA    ?? 200);
  const nAddrSmoke       = Number(inputs.n_addr_smoke       ?? 0);
  const nConvSmoke       = Number(inputs.n_conv_smoke       ?? 0);
  const nHeat            = Number(inputs.n_heat             ?? 0);
  const nPull            = Number(inputs.n_pull             ?? 0);
  const nHornStrobe      = Number(inputs.n_horn_strobe      ?? 0);
  const nStrobe          = Number(inputs.n_strobe           ?? 0);
  const nBell            = Number(inputs.n_bell             ?? 0);

  const I_standby        = results.I_standby_total_mA ?? "N/A";
  const I_alarm          = results.I_alarm_total_mA   ?? "N/A";
  const Ah_standby       = results.Ah_standby         ?? "N/A";
  const Ah_alarm         = results.Ah_alarm           ?? "N/A";
  const Ah_calc          = results.Ah_calc            ?? "N/A";
  const Ah_required      = results.Ah_required        ?? "N/A";
  const selected_Ah      = results.selected_Ah        ?? "N/A";
  const battery_config   = String(results.battery_config ?? `${selected_Ah} Ah SLA/VRLA @ ${sysVoltage}V DC`);

  // Total device count for BOM quantities
  const totalDetectors   = nAddrSmoke + nConvSmoke + nHeat + nPull;
  const totalAppliances  = nHornStrobe + nStrobe + nBell;
  const totalDevices     = totalDetectors + totalAppliances;

  const prompt = `You are a Philippine fire protection engineering expert (NFPA 72, BFP Philippines). Generate a professional BOM and SOW for a FIRE ALARM SYSTEM BATTERY STANDBY installation project.

PROJECT: ${project}
SYSTEM VOLTAGE: ${sysVoltage} V DC
REQUIRED STANDBY: ${standbyHours} hours (NFPA 72 §10.6)
REQUIRED ALARM: ${alarmMinutes} minutes (NFPA 72 §10.6)
SAFETY FACTOR: 1.25 (25% per NFPA 72 §10.6.7)

DEVICE SCHEDULE:
- FACP Panel: 1 unit (standby ${panelStandbyMA} mA, alarm ${panelAlarmMA} mA)
- Addressable Smoke Detectors: ${nAddrSmoke} units
- Conventional Smoke Detectors: ${nConvSmoke} units
- Heat Detectors: ${nHeat} units
- Manual Pull Stations: ${nPull} units
- Horn/Strobe Appliances: ${nHornStrobe} units
- Strobe-Only Appliances: ${nStrobe} units
- Bells: ${nBell} units
- Total Devices: ${totalDevices} units

BATTERY CALCULATION RESULTS:
- Total Standby Current: ${I_standby} mA
- Total Alarm Current: ${I_alarm} mA
- Standby Ah: ${Ah_standby} Ah
- Alarm Ah: ${Ah_alarm} Ah
- Calculated Ah (before SF): ${Ah_calc} Ah
- Required Ah (with 1.25 SF): ${Ah_required} Ah
- Recommended Battery Bank: ${battery_config}

STANDARDS: NFPA 72 (National Fire Alarm and Signaling Code) Section 10.6, BFP IRR (Bureau of Fire Protection), National Building Code PD 1096, PEC (Philippine Electrical Code) for wiring

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: Fire alarm control panel / FACP (addressable or conventional per device schedule, ${sysVoltage}V DC, UL listed, with integral battery charger rated for ${battery_config}, BFP-listed), sealed lead-acid / VRLA standby batteries: the computed bank (${battery_config} minimum, ${sysVoltage}V system: confirm exact configuration: e.g. two 12V batteries in series for 24V system; capacity per NFPA 72 §10.6.7), battery cabinet / rack inside or adjacent to FACP (ventilated, lockable, UL listed for battery storage), addressable smoke detectors: photo-electric type, 2-wire addressable protocol, ${nAddrSmoke} units (UL 268 / EN 54-7, BFP-listed: qty from calc, if 0 omit), conventional smoke detectors: 4-wire, ${nConvSmoke} units (UL 268, BFP-listed: qty from calc, if 0 omit), heat detectors: fixed-temperature or rate-of-rise, ${nHeat} units (UL 521 / EN 54-5, BFP-listed), manual pull stations / break-glass call points: ${nPull} units (UL 38 / BS 5839, surface-mount, red), combination horn/strobe notification appliances: ${nHornStrobe} units (UL 1638 / UL 1971, 15/75 cd minimum, NFPA 72 §18.5), strobe-only appliances: ${nStrobe} units (UL 1971, for hearing-impaired areas), alarm bells: ${nBell} units (6-inch or 10-inch, ${sysVoltage}V DC, weatherproof for outdoor), fire alarm wiring: fire-rated (FPL, FPLR or FPLP) 2-wire twisted pair for initiating circuits and 2-wire for notification circuits (total linear metres estimated from device count and building layout), conduit: EMT or rigid metallic for fire alarm wiring, minimum 19 mm (3/4 inch) (total linear metres), end-of-line resistors (one per initiating circuit and notification circuit: per FACP manufacturer specification), annunciator panel / remote display (lobby-mounted, LED zone display, ${sysVoltage}V DC, for high-rise buildings required by BFP IRR), commissioning and spare parts kit (smoke detector cleaning tool, 5% spare devices per device type, replacement FACP fuses)
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works, Design Basis (NFPA 72 §10.6 battery sizing method, ${sysVoltage}V DC system, ${standbyHours}h standby + ${alarmMinutes}min alarm, ${Ah_required} Ah required, ${battery_config} selected), FACP and Battery Installation (panel location, battery cabinet mounting, charger wiring, ventilation, temperature range per NFPA 72 §10.6.9), Initiating Devices: Detectors and Pull Stations (mounting heights per NFPA 72 Chapter 17, spacing rules, end-of-line resistors, Class A or Class B wiring per NFPA 72 §12.3), Notification Appliances: Horns Strobes and Bells (placement per NFPA 72 Chapter 18, sound pressure levels, strobe candela requirements for hearing-impaired compliance, notification circuit wiring), Fire Alarm Wiring and Conduit (FPL/FPLR/FPLP rated cable, all wiring in metallic conduit per PEC, separation from power wiring, conduit fill per PEC), Inspection Testing and Commissioning (100% point-to-point test, battery load test: disconnect AC and verify ${standbyHours}h standby + ${alarmMinutes}min alarm operation per NFPA 72 §14.4, alarm sound test, BFP acceptance inspection, as-built drawings), Regulatory Compliance (RA 9514 Philippine Fire Code, NFPA 72 acceptance test witnessed by BFP AHJ, PRC-licensed Electrical or Electronics Engineer sign-off, battery replacement schedule every 3-5 years per NFPA 72 §10.6.11, O&M manual submission)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Electrical: Transformer Sizing BOM + SOW Agent ──────────────────────────

async function transformerSizingBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project    = inputs.project_name      || "Transformer Installation Project";
  const ratedKva   = results.rated_kva        ?? inputs.load_kva ?? "N/A";
  const v1         = results.primary_voltage  ?? inputs.primary_voltage ?? "N/A";
  const v2         = results.secondary_voltage?? inputs.secondary_voltage?? "N/A";
  const phases     = results.phases           ?? 3;
  const winding    = results.winding_connection?? "Delta-Star (Dyn11)";
  const impPct     = results.impedance_pct    ?? 5.0;
  const I1         = results.I1_full_load_A   ?? "N/A";
  const I2         = results.I2_full_load_A   ?? "N/A";
  const IscKA      = results.Isc_secondary_kA ?? "N/A";
  const etaFl      = results.efficiency_fl_pct?? "N/A";
  const VR         = results.voltage_regulation_pct ?? "N/A";
  const numUnits   = results.num_units        ?? 1;
  const loadPct    = results.loading_pct      ?? "N/A";

  const prompt = `You are a Philippine electrical engineering expert (PEC 2017, IEC 60076, IEEE C57). Generate a professional BOM and SOW for a POWER TRANSFORMER installation project.

PROJECT: ${project}
TRANSFORMER RATING: ${ratedKva} kVA x ${numUnits} unit(s)
VOLTAGE RATIO: ${v1} V / ${v2} V, ${phases}-Phase
WINDING CONNECTION: ${winding}
IMPEDANCE: ${impPct}%
CALCULATED RESULTS: I1 = ${I1} A, I2 = ${I2} A, Isc = ${IscKA} kA, VR = ${VR}%, Efficiency = ${etaFl}%, Loading = ${loadPct}%

STANDARDS: IEC 60076-1:2011 (Power Transformers), IEEE C57.12.00, PEC 2017 Art. 4.50, Philippine Grid Code

IMPORTANT: Use ASCII characters only. Do NOT use special characters such as superscript 2, multiplication sign, greater-than-or-equal, degree, peso, or subscript digits. Use plain ASCII equivalents: "sq.mm" for square mm, "x" for multiplication, "min" or "not less than" for greater-than-or-equal, "deg C" for temperature, "PHP" for peso.

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: distribution transformer (rated ${ratedKva} kVA, ${v1}/${v2} V, ${phases}-phase, ${winding}, Uz = ${impPct}%, ONAN cooling, IEC 60076-1, DOE-certified, BPS standard), primary disconnecting switch (load-break switch or VCB rated for ${v1} V, fault current not less than ${IscKA} kA, primary current not less than ${I1} A), secondary main circuit breaker (MCCB rated minimum 125% of ${I2} A, IC not less than ${IscKA} kA, TPN for 3-phase), metering current transformers CT (primary: suitable for ${I1} A, accuracy Class 0.5 for metering, 5P20 for protection, qty: one set per phase), voltage transformers VT (primary: ${v1} V, secondary: 110 V, Class 0.5, for metering panel), surge arresters primary side (station class, rated for ${v1} V system, 10 kA discharge capability, IEC 60099-4), transformer earthing conductor (copper conductor 70 sq.mm bare Cu, from transformer tank to main earth bar), neutral earthing resistor NER or solid neutral earthing (per local utility requirements and system earthing philosophy), oil containment / bund wall (concrete or steel bund, 110% of transformer oil volume, with oil separator sump), transformer oil (IEC 60296 inhibited mineral oil, quantity to fill transformer tank, spare: 5% additional), outdoor transformer pad / plinth (reinforced concrete pad, 300 mm above grade, rated for transformer weight, with anchor bolts), HV and LV cable terminations (HV: heatshrink or cold-shrink termination kit for ${v1} V, LV: bolted copper bus connector for ${v2} V), fire protection (CO2 or clean agent extinguisher minimum 9 kg, plus automatic fire detection at transformer bay), commissioning and testing equipment (transformer oil test kit: dielectric strength, dissolved gas analysis; insulation resistance tester; ratio tester; spare breaker fuses)
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works (${ratedKva} kVA x ${numUnits} distribution transformer, ${v1}/${v2} V, ${phases}-phase), Design Basis (IEC 60076-1 rating, ${impPct}% impedance, fault current ${IscKA} kA at secondary, VR ${VR}%, Efficiency ${etaFl}%, loading ${loadPct}%), Civil and Structural Works (transformer pad design, cable trench, bund wall and oil separator, security fencing, outdoor lighting), Primary and Secondary Electrical Works (HV incoming connection, load-break switch installation, LV outgoing breaker, CT/VT installation, bus bars and cable terminations, PEC 2017 Art. 4.50 compliance), Earthing and Bonding (transformer neutral earthing, tank earthing, all metalwork bond to main earth bar per PEC Art. 2.50 / IEEE 80), Protection and Metering (overcurrent and earth fault protection relay settings, energy metering per WESM/distribution utility requirements, CT ratio and class verification), Testing and Commissioning (factory test certificates review, site insulation resistance test, turns ratio test, vector group check, oil sampling and dielectric test, protection relay testing and coordination study, load test at rated current, 24-hour monitoring), Regulatory and Utility Compliance (PEC 2017, DOE certificate of product registration, distribution utility interconnection requirement, Environmental Compliance Certificate for oil-filled equipment, O and M manual and as-built drawings submission to Building Official)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Electrical: Harmonic Distortion BOM + SOW Agent ─────────────────────────

async function harmonicDistortionBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project    = inputs.project_name        || "Harmonic Mitigation Project";
  const THD        = results.THD_I_pct          ?? "N/A";
  const TDD        = results.TDD_pct            ?? "N/A";
  const tddLimit   = results.TDD_limit_pct      ?? 8;
  const kFactor    = results.K_factor           ?? "N/A";
  const overall    = results.overall_pass       ?? false;
  const iscIl      = results.isc_il_ratio       ?? 20;
  const I1         = results.fundamental_current_A ?? inputs.fundamental_current_a ?? 100;
  const sysV       = results.system_voltage_V   ?? inputs.system_voltage_v ?? 400;
  const harmonics  = results.individual_harmonics as Array<{ order: number; current_pct: number; pass: boolean }> || [];
  const failOrders = harmonics.filter(h => !h.pass).map(h => `${h.order}th`).join(", ");
  const status     = overall ? "COMPLIANT" : "NON-COMPLIANT";
  const kRating    = Number(kFactor) > 13 ? "20" : Number(kFactor) > 9 ? "13" : Number(kFactor) > 1 ? "4" : "1";

  const prompt = `You are a Philippine power quality engineering expert (IEEE 519-2022, IEC 61000). Generate a professional BOM and SOW for a HARMONIC DISTORTION ANALYSIS AND MITIGATION project.

PROJECT: ${project}
SYSTEM: ${sysV} V, Fundamental Current ${I1} A, ISC/IL = ${iscIl}
ANALYSIS RESULTS: THD_I = ${THD}%, TDD = ${TDD}% (limit ${tddLimit}%), K-Factor = ${kFactor}, Recommended K-rating = K-${kRating}
STATUS: ${status}
NON-COMPLIANT HARMONICS: ${failOrders || "None"}
MITIGATION REQUIRED: ${overall ? "None - system compliant" : `Yes - TDD exceeds limit. Consider passive filters (5th/7th order tuned), active harmonic filter, or 12-pulse drive upgrade.`}

STANDARDS: IEEE 519-2022 (Recommended Practice for Harmonic Control), IEC 61000-3-2:2018, IEC 61000-3-12, PEC 2017

IMPORTANT: Use ASCII characters only. Do NOT use special characters such as multiplication sign (use "x"), greater-than-or-equal (use "min" or "not less than"), em-dash (use "-"), peso sign (use "PHP"), ampersand-letter combinations (write "and" instead of "&"), superscript or subscript digits.

Generate a JSON object with:
1. "bom_items": array of 12 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: power quality analyzer (class A per IEC 61000-4-30, continuous monitoring, 400V 3-phase, memory min 1 year, Fluke 435-II or equivalent), harmonic current transducers / CTs (accuracy class 0.5, bandwidth DC to 3 kHz, clamping type for easy installation, one per phase), data logger (for long-term THD trending, 4GB internal memory, RS485/Ethernet output for SCADA), ${overall ? "passive harmonic filter (not required - system compliant)" : `passive harmonic filter (single-tuned, 5th and 7th order, rated ${sysV} V, capacitor bank ${Math.ceil(Number(I1) * 0.3)} kVAR, detuning reactor Q not less than 50, IEEE 18 / IEC 60831)`}, ${overall ? "active harmonic filter (not required)" : `active harmonic filter (instantaneous harmonic cancellation, rated for ${Math.ceil(Number(I1) * 0.5)} A harmonic compensation current, 98% efficiency, IGBT-based, ${sysV} V 3-phase)`}, K-rated transformer (K-${kRating} rated, ${sysV} V secondary, for non-linear loads: K-factor = ${kFactor}; required if K greater than 1), harmonic-rated capacitor bank reactors (detuning factor p = 7%, prevents capacitor bank resonance amplification, sized for existing PFC bank if present), surge protection device SPD (Type 2 SPD at main panel, 40 kA discharge, for power quality protection per IEC 61643-11), cable trays and conduit for filter wiring (galvanized steel cable tray 150 x 50 mm, EMT conduit 25 mm, for filter panel to MDB connection), filter enclosure / panel (NEMA 12 / IP54, steel enclosure, ventilated, sized for active or passive filter components), commissioning test instruments (spectrum analyzer, insulation tester, power quality test kit), spare parts kit (filter capacitor bank fuses, relay module, cooling fan for active filter)
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works (power quality audit, harmonic measurement, ${overall ? "compliance documentation" : "harmonic mitigation installation"}, IEEE 519-2022 verification), Design Basis (IEEE 519-2022 Table 2 TDD limit ${tddLimit}% at ISC/IL = ${iscIl}, measured THD = ${THD}%, TDD = ${TDD}%, individual harmonic limits Table 3, K-factor = ${kFactor}), Power Quality Measurement Campaign (3-phase power quality logging minimum 7 days per IEC 61000-4-30 Class A, capture full load, light load and transient conditions, document harmonic spectrum vs. time), ${overall ? "Compliance Documentation (system meets IEEE 519-2022; document and file PQ report, issue Certificate of Compliance, recommend annual monitoring)" : "Harmonic Mitigation Design (passive filter tuning for dominant harmonics, active filter sizing for remaining THD, resonance study to prevent capacitor bank resonance, filter placement at point of common coupling PCC)"}, Equipment Supply and Installation (filter panel installation adjacent to MDB, bus duct or cable connection to MDB, grounding of filter enclosure, interlock wiring with MDB main breaker), Commissioning and Verification Testing (pre-installation baseline THD measurement, post-installation THD and TDD verification per IEEE 519-2022, spectrum analysis at PCC, capacitor bank and filter resonance frequency check, load test at rated and 50% load), Monitoring and Maintenance (power quality analyzer installation and trending setup, quarterly THD report, annual filter inspection, capacitor bank thermal imaging, replacement schedule per manufacturer), Regulatory Compliance (IEEE 519-2022, IEC 61000-3-12, PEC 2017, PSALM / distribution utility interconnection power quality requirements, O and M manual)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Fire Protection: Clean Agent Suppression BOM + SOW Agent ────────────────

async function cleanAgentSuppressionBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project    = inputs.project_name              || "Clean Agent Suppression System";
  const agentLabel = String(results.agent_label       ?? inputs.agent_type ?? "FK-5-1-12");
  const agentKey   = String(results.agent_type        ?? "FK-5-1-12");
  const vol        = results.hazard_volume_m3          ?? inputs.hazard_volume_m3 ?? "N/A";
  const cDesign    = results.design_concentration_pct ?? "N/A";
  const Wcalc      = results.W_calculated_kg           ?? "N/A";
  const Wdesign    = results.W_design_kg               ?? "N/A";
  const cylKg      = results.recommended_cylinder_kg   ?? "N/A";
  const cylQty     = results.recommended_qty           ?? "N/A";
  const totalKg    = results.total_agent_kg            ?? "N/A";
  const nZones     = results.num_zones                 ?? 1;
  const discharge  = results.discharge_time_req        ?? "≤ 10 s";
  const noael      = results.noael_pct                 ?? "N/A";
  const safe       = results.safe_for_occupied_spaces  ?? true;
  const gwp        = results.gwp                       ?? "N/A";

  const prompt = `You are a Philippine fire protection engineering expert (NFPA 2001, ISO 14520, BFP Philippines). Generate a professional BOM and SOW for a CLEAN AGENT FIRE SUPPRESSION SYSTEM installation project.

PROJECT: ${project}
AGENT: ${agentLabel} (GWP = ${gwp})
HAZARD VOLUME: ${vol} m³ × ${nZones} zone(s)
DESIGN CONCENTRATION: ${cDesign}% v/v (NOAEL = ${noael}%)
AGENT REQUIRED: ${Wcalc} kg calculated → ${Wdesign} kg design (with safety factor)
CYLINDER CONFIGURATION: ${cylQty} × ${cylKg} kg cylinders = ${totalKg} kg total
DISCHARGE TIME: ${discharge}
OCCUPIED SPACE: ${safe ? "SAFE — concentration below NOAEL, system approved for occupied areas" : "EVACUATE before discharge — concentration exceeds NOAEL, area must be evacuated"}

STANDARDS: NFPA 2001:2022, ISO 14520:2015, BFP IRR RA 9514, NFPA 72 (detection/alarm), PEC 2017

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks, checked: true)
   Include: clean agent cylinders (${agentKey} agent, ${cylKg} kg each × ${cylQty} units, DOT or UN certified cylinder with integrated valve, pressure gauge, anti-recoil device, UL listed, ${agentLabel}, GWP = ${gwp}), cylinder mounting bracket / rack (steel, powder-coated, wall or floor mount, designed for ${cylKg} kg cylinder weight including agent, with seismic restraint for Philippine seismic zone), discharge manifold (stainless steel 304, rated for clean agent service pressure, sized for ${discharge} full discharge, with check valves per NFPA 2001), discharge nozzles (360° or directional nozzle, stainless steel, orifice sized for design flow per NFPA 2001 §4.4, quantity as per hydraulic calculation), discharge piping (stainless steel 304 Schedule 40 or seamless black steel ASTM A53, sized for ${discharge} discharge, pressure-rated for agent cylinder pressure, hangers per NFPA 13), agent control panel / fire suppression control unit (FSCU, listed per UL 864, microprocessor-based, dual-channel releasing, compatible with FACP by signal input, abort switch input, audible/visual pre-discharge alarm output, end-of-line supervision, 24 VDC), ionisation and photo-electric smoke detectors (cross-zone detection for double-knock system per NFPA 2001 §4.2, UL 268 listed, BFP-listed, addressable type, spacing per NFPA 72 Chapter 17), pre-discharge alarm: alarm bells or sounders (audible alarm minimum 90 dB at 3 m, mounted at every zone entrance, activate 30 seconds before discharge per NFPA 2001), abort station (manual abort switch at each zone entrance, spring-return, key-operated, NFPA 2001 §4.7, labelled "ABORT – PRESS TO HALT DISCHARGE"), safety signage package (NFPA 170 / ISO 7010 compliant: "EVACUATE NOW" strobes, "DO NOT ENTER AFTER DISCHARGE", "CLEAN AGENT SUPPRESSION PROTECTED AREA", "MANUAL DISCHARGE STATION", minimum 1 set per zone entrance), agent monitoring / weighing system (continuous cylinder weight monitoring via load cell or magnetic level indicator, low agent alarm at 5% loss, supervisory signal to FACP per NFPA 2001 §4.6), pressure relief port / explosion vent (for ${safe ? "room pressure relief during discharge" : "mandatory pressure relief due to high concentration: sized per NFPA 2001 §3.6.1"}), commissioning test kit (${agentKey} agent leak detector, room integrity pressurisation test equipment per EN 15004 / NFPA 2001 Annex B, door fan test for room tightness), spare agent (minimum 10% additional agent for annual inspection top-up and one full recharge as required by NFPA 2001 §6.1.2)
2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: Scope of Works (total flooding clean agent system, ${agentKey} agent, ${vol} m³ × ${nZones} zone(s), ${discharge} discharge), Design Basis (NFPA 2001:2022 §5.3 design concentration ${cDesign}% v/v at ${noael}% NOAEL, W = (V/S)×[C/(100-C)], calculated ${Wcalc} kg, design ${Wdesign} kg with 10% safety factor, ${cylQty}×${cylKg} kg = ${totalKg} kg selected), Equipment Supply and Cylinder Manifold Installation (cylinder mounting, manifold fabrication, pressure testing at 1.5× MAWP, connection to discharge piping, NFPA 2001 §4.3), Discharge Piping and Nozzle Installation (pipe routing to minimise bends, pipe support spacing per NFPA 13, nozzle positioning for uniform agent distribution, hydraulic calculation acceptance check, NFPA 2001 §4.4), Detection Control and Alarm System Integration (cross-zone detection wiring, FSCU panel installation, abort station wiring, pre-discharge alarm (30-second countdown per NFPA 2001), interface to building FACP/BMS, end-of-line supervision), Room Integrity and Enclosure Qualification (door fan pressure test per NFPA 2001 Annex B / EN 15004, target: maintain design concentration for minimum 10 minutes, seal all penetrations, pressure relief vent sizing ${safe ? "per NFPA 2001 §3.6" : "MANDATORY: room concentration exceeds NOAEL — strict enclosure integrity and evacuation protocol required"}), Testing and Commissioning (point-to-point wiring test, cross-zone detection simulation, abort station test, pre-discharge alarm timing verification, cylinder weight check vs. design quantity, simulated discharge test with nitrogen (no agent), BFP acceptance inspection, NFPA 2001 acceptance test record), Regulatory Compliance and Maintenance (RA 9514 Philippine Fire Code, BFP permit for suppression system, annual inspection per NFPA 2001 §6, cylinder hydrostatic test every 12 years, agent analysis every 6 years, ${agentKey} GWP=${gwp} — ${gwp === 1 ? "environmentally preferred, zero ozone depletion" : "high GWP: maintain leak log per DENR DAO 2021-19 F-gas reporting"}, O&M manual and as-built drawings to BFP and Building Official)

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Vertical Transportation: Elevator Traffic Analysis BOM + SOW Agent ───────

async function elevatorTrafficBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name   || "Elevator Installation Project";
  const occupancyType  = String(inputs.occupancy_type || "Office");
  const nFloors        = Number(inputs.n_floors        ?? 12);
  const floorHeight    = Number(inputs.floor_height    ?? 3.5);
  const population     = Number(inputs.population      ?? 500);
  const nElevators     = Number(inputs.n_elevators     ?? 3);
  const capacity       = Number(inputs.capacity        ?? 13);
  const speed          = Number(inputs.speed           ?? 1.5);
  const tDoorOpen      = Number(inputs.t_door_open     ?? 2.5);
  const tDoorClose     = Number(inputs.t_door_close    ?? 3.0);
  const tDwell         = Number(inputs.t_dwell         ?? 2.0);

  const RTT_s          = results.RTT_s          ?? "N/A";
  const interval_s     = results.interval_s     ?? "N/A";
  const HC_pct         = results.HC_pct         ?? "N/A";
  const capacity_5min  = results.capacity_5min  ?? "N/A";
  const H_m            = results.H_m            ?? (nFloors * floorHeight).toFixed(1);
  const avg_stops      = results.avg_stops      ?? "N/A";
  const effective_pax  = results.effective_pax  ?? Math.round(capacity * 0.8);
  const target_interval = results.target_interval_s ?? (occupancyType === "Office" ? 30 : 40);
  const target_HC      = results.target_HC_pct  ?? (occupancyType === "Office" ? 12 : 11);

  // Grade assessment flags: drive document tone
  const intervalNum    = Number(interval_s);
  const hcNum          = Number(HC_pct);
  const intervalGrade  = intervalNum <= 30 ? "Excellent" : intervalNum <= 40 ? "Good" : intervalNum <= 60 ? "Adequate" : "Poor";
  const hcGrade        = hcNum >= 12 ? "Excellent" : hcNum >= 11 ? "Good" : hcNum >= 9 ? "Adequate" : "Poor";
  const isPoor         = intervalGrade === "Poor" || hcGrade === "Poor";
  const gradeNote      = isPoor
    ? `WARNING: Grade of service is POOR (Interval=${interval_s}s, HC=${HC_pct}%). SOW must include a remediation clause: consider increasing speed, adding an elevator to the group, or adjusting group supervisory control before building permit submission.`
    : `Grade of service is ${intervalGrade} / ${hcGrade} (Interval=${interval_s}s vs target ${target_interval}s, HC=${HC_pct}% vs target ${target_HC}%): acceptable for a ${occupancyType} building.`;

  // Speed tier drives machine room and drive type recommendations
  const isHighSpeed    = speed >= 2.5;
  const machineType    = isHighSpeed ? "Gearless traction machine (VVVF drive)" : "Geared traction machine (VVVF drive)";
  const motorKW        = Math.round(capacity * speed * 0.15 * nElevators); // rough estimate

  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters such as multiplication sign x, en-dash, em-dash, less-than-or-equal, greater-than-or-equal, sub/superscripts, Greek letters, middle-dot, or degree symbol. Use "x" for multiplication (e.g. "6x19 construction", "1100 mm x 1400 mm"), "to" for ranges, "not less than" for ge, "not more than" for le, "Section" for clause references.`;

  const ratedLoadKg = capacity * 75;  // CIBSE 75 kg/person assumption
  const totalLandingDoors = nFloors * nElevators;

  const prompt = `You are a Philippine vertical transportation engineering expert (ASME A17.1, EN 81, CIBSE Guide D). Generate a professional BOM and SOW for an ELEVATOR INSTALLATION project based on the traffic analysis results.

${asciiDirective}

PROJECT: ${project}
OCCUPANCY TYPE: ${occupancyType}
BUILDING: ${nFloors} floors, ${floorHeight} m floor-to-floor, total rise ${H_m} m
POPULATION SERVED: ${population} persons (up-peak scenario)
ELEVATOR GROUP: ${nElevators} elevator(s), ${capacity}-person capacity each (rated load ${ratedLoadKg} kg)
RATED SPEED: ${speed} m/s | Machine type: ${machineType}
DOOR TIMING: Open ${tDoorOpen}s / Close ${tDoorClose}s / Dwell ${tDwell}s
AVERAGE STOPS PER TRIP: ${avg_stops}
EFFECTIVE PASSENGERS PER TRIP (80% loading): ${effective_pax}

TRAFFIC ANALYSIS RESULTS:
- Round Trip Time (RTT): ${RTT_s} seconds
- Interval Between Arrivals: ${interval_s} s (target not more than ${target_interval} s for ${occupancyType})
- 5-Min Handling Capacity (HC%): ${HC_pct}% (target not less than ${target_HC}% for ${occupancyType})
- 5-Min Capacity: ${capacity_5min} persons of ${population} total
- Interval Grade: ${intervalGrade} | HC Grade: ${hcGrade}
- ${gradeNote}

STANDARDS: ASME A17.1 (Safety Code for Elevators), EN 81-1/EN 81-2 (Safety Rules for Lifts), CIBSE Guide D (Transportation Systems), National Building Code PD 1096, BP 344 / RA 10754 (Accessibility Law: PWD requirements), Philippine Electrical Code (PEC) for elevator motor circuits

Generate a JSON object with:
1. "bom_items": array of 16 items (each: description, specification, qty, unit, remarks)
   Cover the following items with these EXACT specifications (use ASCII, never Unicode):
   (1) Traction Elevator Machine: ${machineType}, ${capacity}-person (${ratedLoadKg} kg) rated load, ${speed} m/s, ${nElevators} units (ASME A17.1 compliant, factory-tested)
   (2) Elevator Car and Sling: ${capacity}-person rated, GI sheet cab with stainless steel interior finish, LED lighting, ventilation fan, emergency light, intercom (${nElevators} units)
   (3) Counterweight Assembly: cast iron blocks, guided by T-section guide rails (${nElevators} sets)
   (4) Guide Rails: T-section steel cold-drawn, for car and counterweight, total rail length ${(Number(H_m) * 2).toFixed(1)} m per elevator (one set of 2 rails: 1 car-side plus 1 counterweight-side, each ${H_m} m), ${nElevators} sets
   (5) Suspension Ropes / Steel Wire Ropes: 6x19 construction or 8x19 (write x with the letter x, NOT the multiplication symbol), factor of safety not less than 12 per ASME A17.1, ${nElevators} sets
   (6) VVVF Drive / Variable Voltage Variable Frequency Controller: regenerative type preferred, rated for ${speed} m/s, ${ratedLoadKg} kg (${nElevators} units)
   (7) Automatic Rescue Device / ARD: brings car to nearest floor on power failure, required for ${nFloors}-floor building (${nElevators} units)
   (8) Landing Doors and Frames: stainless steel, 2-panel center-opening, ${nFloors} floors x ${nElevators} elevators = ${totalLandingDoors} sets (ASME A17.1 door interlock required)
   (9) Car Door Operator and Safety Edge / Light Curtain: full-height infrared light curtain, re-opening on obstruction per ASME A17.1 Section 2.11, ${nElevators} units
   (10) Group Supervisory Controller / Group Dispatch Panel: microprocessor-based, up/down collective with destination dispatch option, for ${nElevators}-elevator group (1 unit)
   (11) Machine Room or Machine-Room-Less MRL Panel: control cabinet with main breaker, door interlock monitoring, overload protection (${nElevators} units)
   (12) Pit Equipment: buffers (spring or oil type per speed ${speed} m/s), pit stop switch, pit lighting, sump pump if required (${nElevators} sets)
   (13) PWD-Compliant Car: minimum 1100 mm x 1400 mm interior (write x with the letter x), Braille plus tactile controls, audible floor announcements, handrail, mirror per BP 344 / RA 10754 (1 unit designated)
   (14) Intercom and Emergency Phone: two-way communication to building security or monitoring station, per ASME A17.1 Section 2.27 (${nElevators} units)
   (15) Elevator Shaft Construction: reinforced concrete hoistway, minimum ${nElevators} shaft(s), internal dimensions per car size plus clearances per ASME A17.1 (civil works: contractor to confirm dimensions, 1 lot)
   (16) Annual Maintenance and Inspection Kit: lubrication, brake adjustment, safety gear test, governor test, load test tools per ASME A17.1 Section 8.6 (1 set per elevator group)

   CRITICAL: every "specification" field must be fully populated; never blank. Use ASCII text only (no Unicode multiplication, less-than-or-equal, greater-than-or-equal, em-dash). Specifically write "6x19 construction" with the LETTER x, "1100 mm x 1400 mm" with the LETTER x, "factor of safety not less than 12" instead of "ge 12".

2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: 1.0 Scope of Works, 2.0 Traffic Analysis Basis (CIBSE Guide D up-peak method, ${nElevators} elevators of ${capacity}-person capacity at ${speed} m/s, RTT=${RTT_s} s, Interval=${interval_s} s [${intervalGrade}], HC=${HC_pct} percent [${hcGrade}]${isPoor ? ": REMEDIATION REQUIRED before permit submission" : ": acceptable for " + occupancyType}), 3.0 Elevator Equipment Supply and Installation (traction machine, 6x19 ropes, T-rail guide rails, counterweight, VVVF drive installation per ASME A17.1 Section 2), 4.0 Hoistway and Machine Room Works (hoistway dimensional requirements per ASME A17.1, machine room ventilation, emergency lighting, fire rating of hoistway walls per NBC), 5.0 Electrical Works (motor circuit sizing per PEC Article 6.20 for elevator motors, machine room panel, emergency power connection, lighting circuit), 6.0 Accessibility Compliance per BP 344 / RA 10754 (one designated PWD-accessible car with Braille controls, 1100 mm x 1400 mm minimum car size [write x as the letter x], audible announcements, handrail, mirror, tactile floor indicators at landings), 7.0 Inspection Testing and Commissioning (no-load and full-load test, governor and safety gear drop test, door interlock test, ARD test, buffer compression test, speed test per ASME A17.1 Section 8: witnessed by DPWH or LGU building official and OSHC-accredited elevator inspector), 8.0 Regulatory Compliance (National Building Code PD 1096, ASME A17.1 acceptance inspection, LGU elevator permit, BP 344 / RA 10754 PWD compliance, annual mandatory inspection per DOLE-OSHC, O&M manual and log book submission)

Each "content" field MUST start with "The Contractor shall..." and use ASCII text only. Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Vertical Transportation: Hoist Capacity BOM + SOW Agent ─────────────────

async function hoistCapacityBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name    || "Hoist System Project";
  const hoistType      = String(inputs.hoist_type    || "Wire Rope Electric");
  const ratedLoadKg    = Number(inputs.rated_load_kg  ?? 2000);
  const hookWeightKg   = Number(inputs.hook_weight_kg ?? 30);
  const slingWeightKg  = Number(inputs.sling_weight_kg ?? 15);
  const liftHeightM    = Number(inputs.lift_height_m  ?? 6);
  const liftSpeedMpm   = Number(inputs.lift_speed_mpm ?? 8);
  const nParts         = Number(inputs.n_parts        ?? 1);
  const safetyFactor   = Number(inputs.safety_factor  ?? 5);
  const mechEffPct     = Number(inputs.mech_eff_pct   ?? 82);

  const grossLoadKg    = results.gross_load_kg       ?? (ratedLoadKg + hookWeightKg + slingWeightKg);
  const grossLoadKN    = results.gross_load_kN        ?? "N/A";
  const MBF_kg         = results.MBF_kg              ?? "N/A";
  const MBF_kN         = results.MBF_kN              ?? "N/A";
  const ropeRec        = String(results.rope_recommendation ?? "6x19 IWRC wire rope");
  // Singular vs plural grammar for "part" / "parts" of line
  const partsLabel     = Number(nParts) === 1 ? "part" : "parts";
  const ropeLengthM    = results.rope_length_m        ?? "N/A";
  const motorHpStd     = results.motor_hp_std         ?? "N/A";
  const motorKW        = results.motor_kW             ?? "N/A";
  const sfCheck        = String(results.safety_factor_check ?? "PASS");
  const ropePullKg     = results.rope_pull_kg         ?? "N/A";

  // PASS/FAIL flag: safety factor below ASME B30.2 minimum of 5:1
  const isSFail        = sfCheck === "FAIL";
  const sfNote         = isSFail
    ? `CRITICAL: Safety factor of ${safetyFactor}:1 is BELOW the ASME B30.2 minimum of 5:1. The hoist MUST NOT be commissioned until the wire rope is upgraded to meet the minimum breaking force. SOW must include a HOLD POINT at rope installation pending third-party inspection.`
    : `Safety factor of ${safetyFactor}:1 meets ASME B30.2 minimum of 5:1: acceptable.`;

  // Hoist type flags: chain hoist vs wire rope electric vs manual
  const isChain        = hoistType.toLowerCase().includes("chain");
  const isManual       = hoistType.toLowerCase().includes("manual");
  const ropeOrChain    = isChain ? "load chain" : "wire rope";
  const doleNote       = Number(ratedLoadKg) > 1000
    ? `DOLE D.O. 13 requires third-party inspection and DOLE accreditation of riggers for hoists above 1 tonne. Include this in SOW as a mandatory pre-commissioning step.`
    : `DOLE D.O. 13 rigging safety standards apply. Rigger competency verification required before first lift.`;

  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters such as multiplication sign x, en-dash, em-dash, less-than-or-equal, greater-than-or-equal, sub/superscripts, Greek letters, middle-dot, degree symbol, or section sign. Use "x" for multiplication (e.g. "6x19 wire rope"), "to" for ranges, "not less than" for ge, "not more than" for le, "Section" for clause references.`;

  const prompt = `You are a Philippine mechanical engineering expert in lifting and rigging (ASME B30.2, ASME B30.16, DOLE D.O. 13). Generate a professional BOM and SOW for a HOIST SYSTEM installation project.

${asciiDirective}

PROJECT: ${project}
HOIST TYPE: ${hoistType}
RATED LOAD (SWL): ${ratedLoadKg} kg
HOOK / BLOCK DEAD WEIGHT: ${hookWeightKg} kg
SLING / RIGGING WEIGHT: ${slingWeightKg} kg
GROSS LOAD (GL): ${grossLoadKg} kg (${grossLoadKN} kN)
LIFT HEIGHT: ${liftHeightM} m
LIFTING SPEED: ${liftSpeedMpm} m/min
PARTS OF LINE (rope falls): ${nParts} ${partsLabel}
SAFETY FACTOR: ${safetyFactor}:1: ${sfNote}
MECHANICAL EFFICIENCY: ${mechEffPct} percent
WIRE ROPE / CHAIN: MBF required = ${MBF_kN} kN (${MBF_kg} kg): Recommended: ${ropeRec}
ROPE / CHAIN LENGTH: ${ropeLengthM} m minimum
ROPE PULL PER PART: ${ropePullKg} kg
HOIST MOTOR: ${motorHpStd} HP (${motorKW} kW)
${doleNote}
STANDARDS: ASME B30.2 (Overhead and Gantry Cranes), ASME B30.16 (Overhead Hoists), ASME B30.9 (Slings), DOLE D.O. 13 s.1998, PCAB Rigging Standards

Generate a JSON object with:
1. "bom_items": array of 14 items (each: description, specification, qty, unit, remarks)
   Use ASCII text only. Include the following items with these exact specifications:
   (1) ${isChain ? `Electric chain hoist: ${ratedLoadKg} kg SWL, ${liftSpeedMpm} m/min, ASME B30.16 compliant, pendant-operated (1 unit)` : `Wire rope electric hoist: ${ratedLoadKg} kg SWL, ${liftSpeedMpm} m/min, ${motorHpStd} HP motor, ASME B30.2 compliant (1 unit)`}
   (2) Hoist motor: ${motorHpStd} HP (${motorKW} kW), TEFC, Class F insulation, designed for S3/S4 duty cycle, IP55 (${isManual ? "not required: manual hoist" : "1 unit"})
   (3) ${ropeOrChain}: ${isChain ? `grade 80 alloy steel load chain, ${ropeLengthM} m, SWL ${ratedLoadKg} kg, ASME B30.9 (1 set)` : `${ropeRec}, ${ropeLengthM} m minimum, MBF not less than ${MBF_kN} kN, ASME B30.2 SF = ${safetyFactor}:1 (1 set)`}
   (4) Hook block assembly: swivel hook with safety latch, rated ${ratedLoadKg} kg SWL, forged alloy steel, ASME B30.10 (1 unit)
   (5) Upper suspension / trolley: plain or motorized trolley for I-beam runway, rated not less than ${Number(grossLoadKg) * 1.25} kg, adjustable flange (1 unit)
   (6) Runway beam / monorail: wide-flange I-beam structural steel, verify size with structural engineer for ${grossLoadKg} kg gross load with 1.25 dynamic impact factor, length per field layout (1 set)
   (7) End stops / bumpers: welded steel stops at both ends of runway beam, rated for full loaded trolley impact (2 units per runway)
   (8) Runway beam support brackets and connections: welded or bolted to building structure, structural engineer to verify adequacy for ${grossLoadKg} kg plus 25 percent impact (1 set)
   (9) Wire rope drum and sheave set: grooved drum, flanged sheaves, D/d ratio not less than 18 per ASME B30.2; reeving for ${nParts} ${partsLabel} of line (1 set)
   (10) Hoist limit switches: upper and lower travel limit switches, automatic cut-off, per ASME B30.16 (1 set)
   (11) Pendant control station: push-button pendant UP/DOWN/STOP, cord-suspended at operator reach height, IP65 (${isManual ? "not applicable: manual hoist" : "1 unit"})
   (12) Sling set: wire rope slings or chain slings, rated ${ratedLoadKg} kg SWL, ASME B30.9, with identification tags (1 set)
   (13) Safety signage: SWL rating plate permanently attached to hoist, rigging safety signs at lift area, per DOLE D.O. 13 (1 set)
   (14) Load test weights and third-party inspection service: static test at 125 percent SWL = ${Math.round(ratedLoadKg * 1.25)} kg, dynamic test per ASME B30.2 Section 2-2.2, DOLE-accredited third-party inspector${isSFail ? " (MANDATORY HOLD POINT before commissioning due to safety factor FAIL)" : ""} (1 set)

   CRITICAL: every "specification" field must be fully populated; never blank. Use ASCII text only (write "6x19" with the letter x, "not less than" for ge, "not more than" for le).

2. "sow_sections": array of 8 sections (each: section_no, title, content)
   Cover: 1.0 Scope of Works, 2.0 Design Basis (ASME B30.2 SWL method, ${ratedLoadKg} kg SWL, GL=${grossLoadKg} kg, MBF=${MBF_kN} kN required, SF=${safetyFactor}:1: ${sfCheck}${isSFail ? " - WIRE ROPE UPGRADE MANDATORY before commissioning" : ""}), 3.0 Structural Verification (runway beam and support structure must be verified by PRC-licensed Civil/Structural Engineer for ${grossLoadKg} kg gross load with 1.25 dynamic impact factor before hoist installation), 4.0 Hoist and Trolley Installation (alignment, end stop installation, limit switch setting, lubrication, per ASME B30.16 manufacturer instructions), 5.0 Wire Rope / Chain Installation and Reeving (${ropeOrChain} installation, reeving diagram for ${nParts} ${partsLabel} of line, not less than 3 dead wraps on drum, end termination per ASME B30.2, mandatory pre-use inspection before first lift), 6.0 Rigging and Sling Requirements (ASME B30.9 sling inspection, angle factor, tag verification, DOLE D.O. 13 rigger competency: ${doleNote}), 7.0 Load Testing and Third-Party Inspection (static proof load test at 125 percent SWL = ${Math.round(ratedLoadKg * 1.25)} kg, dynamic load test at 100 percent SWL through full travel per ASME B30.2 Section 2-2.2, DOLE-accredited inspector, certificate of compliance before first operational use${isSFail ? ": THIS STEP IS A MANDATORY HOLD POINT - do not commission until safety factor deficiency is resolved and re-inspected" : ""}), 8.0 Regulatory Compliance and Maintenance (DOLE D.O. 13, PCAB rigging standards, daily visual inspection log, monthly detailed inspection, annual third-party re-inspection, wire rope replacement criteria per ASME B30.2, PRC-licensed Mechanical Engineer sign-off on this calculation)

Each "content" field MUST start with "The Contractor shall..." and use ASCII text only. Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Chiller System — Air Cooled BOM + SOW Agent ─────────────────────────────

async function chillerAirCooledBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project         = inputs.project_name    || "Chiller Plant Project";
  const nUnits          = Number(inputs.n_units  ?? results.n_units ?? 1);
  const nominalTR       = Number(results.nominal_TR_each ?? 50);
  const nominalKW       = Number(results.nominal_kW_each ?? nominalTR * 3.517);
  const totalTR         = Number(results.nominal_total_TR ?? nominalTR * nUnits);
  const designKW        = Number(results.Q_design_kW ?? 0);
  const compPowerKW     = Number(results.P_total_kW ?? 0);
  const compPerUnitKW   = Number(results.P_per_unit_kW ?? compPowerKW / nUnits);
  const totalKVA        = Number(results.total_kVA ?? compPowerKW / 0.85);
  const totalAmp        = Number(results.total_A_at_400V ?? 0);
  const chwFlowLps      = Number(results.Q_flow_lps ?? 0);
  const chwFlowM3h      = Number(results.Q_flow_m3h ?? 0);
  const airflowCMH      = Number(results.Q_airflow_CMH ?? 0);
  const airflowPerUnit  = Number(results.Q_airflow_CMH_per_unit ?? airflowCMH / nUnits);
  const ambientTemp     = Number(inputs.ambient_temp_C ?? 35);
  const chwSupply       = Number(inputs.chw_supply_C ?? 7);
  const chwReturn       = Number(inputs.chw_return_C ?? 12);
  const dTchw           = Number(results.dT_chw_C ?? (chwReturn - chwSupply));
  const cop             = Number(inputs.cop ?? 3.0);
  const copCheck        = String(results.cop_check ?? "PASS");
  const ashraMinCop     = Number(results.ashrae_min_cop ?? 2.84);
  const refrigerant     = String(results.refrigerant ?? "R-32 or R-410A");
  const safetyFactor    = Number(inputs.safety_factor ?? 1.15);

  // COP FAIL flag: drives mandatory upgrade language in SOW
  const isCopFail = copCheck === "FAIL";
  const copNote   = isCopFail
    ? `FAIL: specified COP ${cop} is below ASHRAE 90.1 minimum of ${ashraMinCop}. Equipment must be re-selected with COP ≥ ${ashraMinCop} before procurement. Proceed with BOM procurement only after COP-compliant equipment is confirmed from manufacturer.`
    : `PASS: COP ${cop} meets ASHRAE 90.1 minimum of ${ashraMinCop}.`;

  // Multi-unit flag: N+1 language for 2+ chillers
  const isMultiUnit = nUnits >= 2;
  const redundancyNote = isMultiUnit
    ? `N+1 redundancy configuration: ${nUnits} units at ${nominalTR} TR each. Lead-lag sequencing required. Each unit must be capable of carrying the design load independently during standby operation.`
    : `Single chiller configuration: no built-in redundancy. Consider portable rental chiller contingency plan for critical facilities.`;

  // CHW pipe sizing estimate (velocity 1.5 m/s) — D_mm = sqrt((Q_m3s)/(π/4·v))·1000, rounded up to 25mm
  const chwPipeEst_mm = chwFlowLps > 0
    ? Math.ceil(Math.sqrt((chwFlowLps / 1000) / (Math.PI / 4 * 1.5)) * 1000 / 25) * 25
    : 50;

  const prompt = `You are a licensed Mechanical Engineer in the Philippines preparing official procurement and contracting documents for an AIR-COOLED CHILLER PLANT installation.

PROJECT: ${project}
DISCIPLINE: HVAC Systems: Air-Cooled Chiller Plant
STANDARDS: ASHRAE 90.1 (energy efficiency), ASHRAE 15 (refrigerant safety), PSME Code, PEC 2017 (electrical), PGBC/BERDE (green building)

CALCULATION RESULTS:
- Building Cooling Load (input): ${designKW / safetyFactor} kW
- Design Load (with ${safetyFactor}× safety factor): ${designKW} kW
- Number of Chiller Units: ${nUnits}
- Selected Nominal Capacity: ${nUnits} × ${nominalTR} TR (${nominalKW} kW) each
- Total Installed Capacity: ${totalTR} TR
- Compressor Power per Unit: ${compPerUnitKW} kW
- Total Compressor Power: ${compPowerKW} kW
- Apparent Power: ${totalKVA} kVA
- Full Load Current (3-phase 400V): ${totalAmp} A
- COP: ${cop}: ASHRAE 90.1 Check: ${copNote}
- CHW Supply / Return: ${chwSupply}°C / ${chwReturn}°C (ΔT = ${dTchw}°C)
- CHW Flow Rate: ${chwFlowLps} L/s (${chwFlowM3h} m³/h)
- Condenser Airflow: ${airflowCMH} CMH total (${airflowPerUnit} CMH per unit)
- Design Ambient Temperature: ${ambientTemp}°C
- Refrigerant: ${refrigerant}
- Redundancy: ${redundancyNote}

Generate a JSON object with exactly two arrays:

ARRAY 1: "bom_items": 15 items for a complete air-cooled chiller plant BOM.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items (use the calculated quantities above):
1. Air-Cooled Chiller Unit: ${nominalTR} TR (${nominalKW} kW) each, ${refrigerant}, COP ≥ ${cop} at ${ambientTemp}°C ambient, ASHRAE 90.1 compliant, factory-tested: qty: ${nUnits}
2. Chiller Controller / BMS Interface: DDC controller with Modbus/BACnet, CHW setpoint reset, lead-lag sequencing (${isMultiUnit ? 'mandatory for ' + nUnits + ' units' : 'optional for single unit'}): qty: 1 set
3. Chilled Water Pump, Base-Mounted: end-suction centrifugal pump, ${Math.round(chwFlowM3h)} m³/h, rated head TBD by hydraulic design, TEFC motor: qty: ${isMultiUnit ? nUnits + 1 : 2} (${isMultiUnit ? 'N+1 duty-standby per chiller' : 'duty + standby'})
4. Chilled Water Pipe, Insulated Carbon Steel Schedule 40: estimated ~${chwPipeEst_mm}mm nominal dia, pre-insulated with 50mm closed-cell foam, all joints flanged or groove-coupled: qty: 1 lot
5. Chilled Water Valves and Fittings: butterfly valves (isolation), globe valves (balancing), strainer, flexible connectors at each chiller/pump: qty: 1 lot
6. Expansion Tank, Closed-Type: ASME rated, pre-charged, sized for ${Math.round(chwFlowM3h * 0.05)} L minimum: qty: 1 unit
7. Chemical Dosing System: inhibitor dosing pot, glycol feeder (if required), water quality test kit, initial chemical charge: qty: 1 set
8. Main Circuit Breaker / Disconnect, 3-phase: MCCB rated ≥ ${Math.ceil(totalAmp * 1.25 / 10) * 10} A, 400V 3-phase, one per chiller: qty: ${nUnits}
9. Power Wiring, 3-phase, Cu XLPE: from MCC/switchboard to each chiller, estimated 30m run per unit, size per PEC 2017 at ${Math.ceil(compPerUnitKW / 0.85 / (Math.sqrt(3) * 0.4) * 1.25)} A: qty: ${nUnits * 30} m
10. Control Wiring, Shielded: from BMS/DDC to each chiller for monitoring and control: qty: 1 lot
11. Equipment Mounting Frames and Anti-Vibration Pads: structural steel mounting frame, neoprene anti-vibration pads rated for chiller weight, each unit: qty: ${nUnits} sets
12. Refrigerant Leak Detection System: electrochemical sensor per machine room, alarm panel, per ASHRAE 15: qty: 1 set
13. Safety Signage and Labels: refrigerant type, pressure ratings, SWL, emergency shutdown location, ASHRAE 15 and PSME required: qty: 1 lot
14. Insulation and Vapor Barrier, CHW Pipes: 50mm closed-cell elastomeric foam, vapor-sealed all joints, for all chilled water pipes and fittings in conditioned space: qty: 1 lot
15. Commissioning, Testing and Balancing: factory witness test report, site commissioning by manufacturer-authorized engineer, hydronic balancing, COP verification at design conditions, O&M manual: qty: 1 lot${isCopFail ? ': HOLD: do not commission until COP-compliant equipment is confirmed' : ''}

ARRAY 2: "sow_sections": 8 sections (each: section_no, title, content).
Cover:
1. Scope of Works: install ${nUnits} × ${nominalTR} TR air-cooled chiller(s), CHW distribution, pumps, controls, electrical, commissioning for ${project}
2. Design Basis: ASHRAE 90.1, cooling load ${designKW} kW (${(designKW/3.517).toFixed(1)} TR) with ${safetyFactor}× safety, CHW ${chwSupply}/${chwReturn}°C, ambient ${ambientTemp}°C, COP ${cop}: ${copCheck}${isCopFail ? `: FAIL: re-select equipment before procurement` : ''}
3. Equipment Supply and Installation: chiller placement with minimum 1.2m clearance all sides for condenser airflow, no condenser air recirculation, alignment per manufacturer, ${isMultiUnit ? 'lead-lag sequencing controller wired and commissioned' : 'BMS connection'}, anti-vibration mounts required
4. Chilled Water System: CHW piping at ${chwFlowLps} L/s (${chwFlowM3h} m³/h), insulate all CHW pipes with 50mm closed-cell foam vapor-sealed, hydronic balancing by certified TAB contractor after commissioning, system flushing before connection to chiller evaporator
5. Refrigerant Safety (ASHRAE 15): ${refrigerant} refrigerant, leak detection required in equipment room, ventilation minimum 6 ACH per ASHRAE 15, refrigerant charge log to be maintained, only PSME/EPA-certified technicians to handle refrigerant
6. Electrical Works: ${totalKVA} kVA total, 3-phase 400V supply, ${totalAmp} A FLA, MCCB per unit rated ≥ ${Math.ceil(totalAmp * 1.25 / 10) * 10} A, all electrical works by PEC-licensed master electrician, electrical permit from LGU before commencement
7. Testing and Commissioning: system pressure test at 1.5× working pressure, CHW flow balancing, COP verification at design conditions (${ambientTemp}°C ambient, ${chwSupply}°C supply, ${chwReturn}°C return), factory witness test report required, O&M manual and as-built drawings to Owner${isCopFail ? `: MANDATORY HOLD POINT: do not energize or commission until COP-compliant replacement equipment is confirmed` : ''}
8. Regulatory Compliance: PSME Code, ASHRAE 90.1/15, PEC 2017, PGBC/BERDE energy performance requirements, DOLE OSH for refrigerant handling, LGU building permit and mechanical permit, PRC-licensed Mechanical Engineer to sign and seal this design calculation

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── AHU Sizing BOM + SOW Agent ──────────────────────────────────────────────

async function ahuBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project      = inputs.project_name   || "AHU Project";
  const spaceType    = inputs.space_type      || "Office";
  const nUnits       = Number(results.n_units || inputs.n_units || 1);
  const ahuCMH       = Number(results.nominal_AHU_CMH_each || 0);
  const ahuCMHtotal  = Number(results.nominal_AHU_CMH_total || ahuCMH * nUnits);
  const coilKW       = Number(results.Q_coil_total_kW || 0);
  const coilTR       = Number(results.Q_coil_TR || 0);
  const fanHP        = Number(results.fan_hp_std || 0);
  const fanHP_total  = Number(results.fan_hp_total || fanHP * nUnits);
  const chwLps       = Number(results.Q_chw_lps || 0);
  const fanStatic    = Number(results.fan_static_Pa || inputs.fan_static_Pa || 400);
  const chwSupply    = Number(results.chw_supply_C || inputs.chw_supply_C || 7);
  const chwReturn    = Number(results.chw_return_C || inputs.chw_return_C || 12);
  const oaPct        = Number(results.oa_pct_used || 20);
  const fanPowerWlps = Number(results.fan_power_W_lps || 0);
  const fanCheck     = String(results.fan_power_check || 'PASS');
  const qoaCMH       = Number(results.Q_oa_CMH || 0);
  const totalFanKVA  = Number(results.total_fan_kVA || 0);
  const totalFanA    = Number(results.total_fan_A_400V || 0);
  const isFanFail    = fanCheck.startsWith('FAIL');
  // CHW pipe size estimate: velocity = 1.5 m/s → D = sqrt(4Q/π/v) in mm
  const chwPipeMm    = chwLps > 0 ? Math.ceil(Math.sqrt((4 * chwLps / 1000) / (Math.PI * 1.5)) * 1000 / 25) * 25 : 50;
  // OA duct estimate: velocity ~2.5 m/s → size
  const oaDuctCMH_each = qoaCMH / nUnits;

  const prompt = `You are a licensed Mechanical Engineer in the Philippines preparing official procurement and contracting documents for an Air Handling Unit (AHU) installation.

CALCULATION RESULTS:
Project: ${project}
Space Type: ${spaceType}
AHU Units: ${nUnits}× AHU, each rated at ${ahuCMH} m³/h (${ahuCMHtotal} m³/h total)
Cooling Coil: ${coilKW} kW (${coilTR} TR) total: CHW ${chwSupply}°C / ${chwReturn}°C supply/return
CHW Flow: ${chwLps} L/s total: estimated pipe size: ${chwPipeMm}mm
Fan Motor: ${fanHP} HP each (${fanHP_total} HP total) at ${fanStatic} Pa static pressure
Fan Power Index: ${fanPowerWlps} W/(L/s): ASHRAE 90.1 limit 0.82: ${isFanFail ? 'FAIL: VFD and higher-efficiency fan required; spec fan to achieve ≤0.82 W/(L/s)' : 'PASS'}
Outside Air: ${oaPct}%: ${qoaCMH} m³/h total (${oaDuctCMH_each.toFixed(0)} m³/h per unit)
Electrical: ${totalFanKVA} kVA / ${totalFanA} A FLA (fan motors, 3-phase 400V)

TASK: Generate a JSON object with exactly two arrays.

IMPORTANT — BOM SPECIFICATION FIELD: For the BOM "specification" strings, use ASCII-only characters. Do NOT use special characters such as superscript 3 (use "m3/h" or "cmh" instead of "m³/h"), degree (use "degC" instead of "°C"), multiplication sign (use "x" instead of "×"), greater-than-or-equal (use "min" or "not less than"), less-than-or-equal (use "not more than"), plus-minus (use "+/-"). The SOW "content" strings may keep Unicode prose.

ARRAY 1: "bom_items": Standard Philippine AHU contractor Bill of Materials.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Air Handling Unit, draw-through type: qty: ${nUnits}: spec: ${ahuCMH} m3/h each, ${coilKW/nUnits} kW cooling coil, ${fanHP} HP supply fan, G4+F7 filter section, CHW ${chwSupply}/${chwReturn} degC
2. Supply Fan Motor, IE3 premium efficiency: qty: ${nUnits}: spec: ${fanHP} HP (${(fanHP*0.7457).toFixed(1)} kW), 3-phase 400V/60Hz, TEFC
3. Variable Frequency Drive (VFD): qty: ${nUnits}: spec: ${(fanHP*0.7457).toFixed(1)} kW, IP54, bypass mode
4. Pre-Filter, G4 panel type: qty: ${nUnits * 4} pcs: spec: 595x595x48mm or as required by AHU manufacturer
5. Bag Filter, F7 medium-efficiency: qty: ${nUnits * 4} pcs: spec: 592x592x600mm, 6-pocket
6. Outside Air Motorized Damper with Actuator: qty: ${nUnits}: spec: low-leakage, AMCA-rated, 24V actuator, fail-closed
7. Chilled Water Supply Valve, 2-way modulating: qty: ${nUnits}: spec: PN16, DN based on ${chwPipeMm}mm pipe, CV per coil manufacturer
8. Chilled Water Return Valve, balancing: qty: ${nUnits}: spec: PN16, manual balancing, DN${chwPipeMm}
9. CHW Flexible Connection, braided stainless: qty: ${nUnits * 2}: spec: DN${chwPipeMm}, 300mm length, PN16
10. CHW Piping, copper/black steel: qty: 1 lot: spec: DN${chwPipeMm}mm supply and return, insulated with 25mm Armaflex
11. Pipe Insulation, closed-cell elastomeric: qty: 1 lot: spec: 25mm thick, for CHW supply and return pipes
12. Supply Air Ductwork, GI sheet metal: qty: 1 lot: spec: SMACNA Class 1 (not more than 500 Pa), gauge per SMACNA Table 5-1, with insulation
13. Return / Exhaust Air Ductwork: qty: 1 lot: spec: SMACNA Class 1, uninsulated (return air duct)
14. Outside Air Intake Ductwork with Louver: qty: 1 lot: spec: ${oaDuctCMH_each.toFixed(0)} m3/h per unit, bird/insect screen, rain louver
15. Vibration Isolators, spring type: qty: ${nUnits * 4}: spec: 25mm deflection, load-rated for AHU weight
16. Condensate Drain Pan and Trap: qty: ${nUnits}: spec: stainless steel, 50mm trap seal, min 20mm PVC drain line
17. MCCB Circuit Breaker, 3-pole: qty: ${nUnits}: spec: ${Math.ceil(totalFanA * 1.25 / nUnits)}A, 400V, 18kA AIC
18. Wiring, THHN 5.5 sq.mm (3C): qty: 1 lot: spec: from MCCB to VFD to AHU motor per PEC 2017
19. Anti-vibration Mounting Pads (supplemental): qty: ${nUnits * 4}: spec: neoprene, 50 Shore A, for AHU base frame
20. Commissioning and TAB (Testing, Adjusting, Balancing): qty: 1 lot: spec: ASHRAE 111 balancing procedure, airflow and CHW delta-T verification report
21. Miscellaneous (hangers, supports, sealing, access doors): qty: 1 lot: spec: per SMACNA

ARRAY 2: "sow_sections": 8 sections of Scope of Works in Philippine engineering document style.
Each object: { "section_no": number, "title": string, "content": string, "checked": true }

IMPORTANT: Each "content" must be a full professional specification paragraph of at least 4–6 complete sentences. Write as a licensed engineer giving binding contractual requirements. Use "The Contractor shall..." sentence structure. Include specific dimensions, standards, test pressures, tolerances, and acceptance criteria. Do NOT use one-word bullets or vague phrases.

Required sections:

1. Scope Overview
content: State that the Contractor shall furnish, deliver, install, test, commission, and hand over a complete and operational Air Handling Unit (AHU) system for ${project} (${spaceType}). Include: ${nUnits}× AHU units each rated at ${ahuCMH} m³/h, cooling coil ${coilKW} kW total (${coilTR} TR) at CHW ${chwSupply}°C/${chwReturn}°C, ${fanHP} HP supply fan each at ${fanStatic} Pa static pressure with VFD, G4+F7 filtration, outside air at ${oaPct}% (${qoaCMH} m³/h total), chilled water piping (DN${chwPipeMm}mm), supply/return/OA ductwork, electrical supply, and full TAB commissioning. All work shall comply with ASHRAE 62.1, ASHRAE 90.1, PSME Code, SMACNA, and PEC 2017.

2. Air Handling Unit Installation
content: Describe installation requirements: The Contractor shall install the AHU on a structural steel base frame or as shown in the mechanical drawings, with spring-type vibration isolators (minimum 25mm static deflection, load-rated for unit weight). Unit shall be leveled to within 3mm using stainless steel shim plates. Minimum 1.0m service clearance shall be maintained on all sides requiring access for filter removal, coil cleaning, and fan maintenance. Flexible canvas connections shall be provided at all duct connections to the AHU casing to prevent vibration transmission. Unit installation shall follow manufacturer's installation manual and ASHRAE Handbook recommendations.

3. Ductwork and Air Distribution
content: The Contractor shall fabricate and install supply air, return air, and outside air ductwork per SMACNA HVAC Duct Construction Standards, Class 1 (≤500 Pa). Duct gauge shall comply with SMACNA Table 5-1 for the applicable pressure class. Supply air ductwork shall be externally insulated with 25mm mineral wool or equivalent (k ≤ 0.040 W/m·K) to prevent condensation. All duct joints and seams shall be sealed with UL-181-rated mastic or foil tape. Duct system shall be pressure-tested at 125% of design static pressure (minimum 500 Pa) with maximum 1% leakage rate before insulation is applied. Outside air intake louver shall have minimum 50% free area, bird/insect screen, and be oriented away from exhaust outlets.

4. Chilled Water Coil Piping
content: The Contractor shall install chilled water supply and return piping in DN${chwPipeMm}mm ${chwPipeMm > 50 ? 'Schedule 40 black steel pipe (ASTM A53)' : 'Type L copper pipe'} complete with strainer (Y-type, 40-mesh), 2-way modulating control valve (PN16, equal-percentage characteristic, CV per coil manufacturer's selection), manual balancing valve (PN16, graduated scale), braided stainless flexible connections (DN${chwPipeMm}mm × 300mm, PN16) at the AHU coil connections, and drain valve at all low points. CHW piping shall be insulated with 25mm closed-cell elastomeric foam (Armaflex or equivalent, thermal conductivity ≤ 0.036 W/m·K) to prevent condensation. System shall be hydraulically pressure-tested at 1.5× working pressure (minimum 600 kPa) for 4 hours with zero visible leakage before insulation is applied. CHW flow shall be balanced to within ±10% of design flow (${chwLps.toFixed(1)} L/s) per AHU.

5. Electrical and Controls
content: ${isFanFail
  ? `MANDATORY HOLD POINT: Fan power index of ${fanPowerWlps} W/(L/s) EXCEEDS ASHRAE 90.1 limit of 0.82 W/(L/s). The Contractor shall NOT energize the fan motors until a Variable Frequency Drive (VFD) is installed AND the fan assembly is replaced or re-selected to achieve ≤0.82 W/(L/s) at design airflow. VFD shall be IP54 minimum, with manual bypass mode, 3-phase 400V/60Hz, rated at ${(fanHP*0.7457).toFixed(1)} kW per unit. Wiring from MCCB to VFD to AHU motor terminal box shall be in accordance with PEC 2017. Outside air motorized damper actuator shall be wired to fail-closed on power loss. Provide one (1) BAS (Building Automation System) digital output point per AHU for remote start/stop and status monitoring.`
  : `The Contractor shall install a Variable Frequency Drive (VFD) for each AHU fan motor (${(fanHP*0.7457).toFixed(1)} kW, IP54, bypass mode, 3-phase 400V/60Hz). Fan power index is ${fanPowerWlps} W/(L/s): ASHRAE 90.1 limit 0.82 W/(L/s): PASS. MCCB (${Math.ceil(totalFanA * 1.25 / nUnits)}A, 3-pole, 400V, 18kA AIC) shall be installed for each AHU circuit. All wiring shall comply with PEC 2017, conductors minimum THHN 5.5mm² (3C). Outside air motorized damper actuator shall be 24V, fail-closed on power loss, interlocked with AHU fan. Provide one (1) BAS digital output point per AHU for remote start/stop, speed signal, and fault status.`}

6. Filtration
content: The Contractor shall install a two-stage filtration system in each AHU: G4 panel pre-filter (595×595×48mm or as dimensioned by AHU manufacturer, MERV 7) upstream, followed by F7 medium-efficiency bag filter (592×592×600mm, 6-pocket, MERV 13) as the final filter. A Magnehelic differential pressure gauge (range 0–250 Pa, accuracy ±2%) shall be installed across each filter bank to indicate loading condition. Replace filters when DP reaches 150 Pa for G4 or 200 Pa for F7. Contractor shall include one (1) complete set of replacement filters (G4 and F7) in the supply contract for handover to the Owner. Contractor shall submit filter manufacturer's efficiency data per ASHRAE 52.2 or EN779 before procurement.

7. Testing and Commissioning
content: The Contractor shall conduct a full Testing, Adjusting, and Balancing (TAB) exercise per ASHRAE Guideline 111 before system handover. TAB shall include: (a) airflow measurement and balancing for each supply air outlet and return air grille: all outlets shall be within ±10% of design CMH; (b) CHW ΔT verification: measured ΔT shall be within ±1°C of design ${(chwReturn - chwSupply).toFixed(0)}°C ΔT; (c) fan motor current measurement at design airflow: shall not exceed nameplate FLA; (d) VFD frequency at design airflow shall be recorded; (e) noise level measurement in the served space (≤NC-45 for office/general space); (f) fail-safe test: verify OA damper closes on power interruption; (g) factory performance data (certified fan curve, coil selection data at design CHW conditions) shall be reviewed against field measurements before final acceptance. TAB report shall be submitted in ASHRAE 111 format and signed by a certified TAB engineer.

8. Regulatory Compliance
content: The Contractor shall be fully responsible for compliance with all applicable Philippine codes and standards including: ASHRAE 62.1: outside air rate shall be field-verified at ${oaPct}% = ${qoaCMH.toFixed(0)} m³/h total (${(qoaCMH/nUnits).toFixed(0)} m³/h per unit), as-measured within ±10%; ASHRAE 90.1: fan power index ≤ 0.82 W/(L/s) shall be field-certified in the TAB report; PSME Code: AHU and ductwork installation, mechanical permit from the LGU Building Official shall be obtained before any mechanical works begin; PEC 2017: all electrical installations; SMACNA: duct construction and sealing; PGBC/BERDE: indoor air quality performance requirements where applicable. A PRC-licensed Mechanical Engineer shall sign and seal all as-built mechanical drawings. System shall not be energized and turned over to the Owner until all permits are obtained and the commissioning report is accepted by the Engineer of Record.

Respond with ONLY the JSON object. No explanation outside the JSON.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Chiller System — Water Cooled BOM + SOW Agent ───────────────────────────

async function chillerWaterCooledBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project        = inputs.project_name   || "Water-Cooled Chiller Plant Project";
  const chillerType    = String(inputs.chiller_type  || results.chiller_type || "Centrifugal");
  const nUnits         = Number(inputs.n_units  ?? results.n_units ?? 2);
  const nominalTR      = Number(results.nominal_TR_each  ?? 100);
  const nominalKW      = Number(results.nominal_kW_each  ?? nominalTR * 3.517);
  const totalTR        = Number(results.nominal_total_TR ?? nominalTR * nUnits);
  const designKW       = Number(results.Q_design_kW ?? 0);
  const compPowerKW    = Number(results.P_total_kW  ?? 0);
  const compPerUnitKW  = Number(results.P_per_unit_kW ?? compPowerKW / nUnits);
  const totalKVA       = Number(results.total_kVA ?? compPowerKW / 0.85);
  const totalAmp       = Number(results.total_A_at_400V ?? 0);
  const chwFlowLps     = Number(results.Q_chw_lps ?? 0);
  const chwFlowM3h     = Number(results.Q_chw_m3h ?? 0);
  const cwFlowLps      = Number(results.Q_cw_lps  ?? 0);
  const cwFlowM3h      = Number(results.Q_cw_m3h  ?? 0);
  const qRejectionKW   = Number(results.Q_rejection_kW ?? 0);
  const qRejectionTR   = Number(results.Q_rejection_TR ?? 0);
  const chwSupply      = Number(inputs.chw_supply_C ?? 7);
  const chwReturn      = Number(inputs.chw_return_C ?? 12);
  const cwSupply       = Number(inputs.cw_supply_C  ?? 29);
  const cwReturn       = Number(inputs.cw_return_C  ?? 35);
  const dTchw          = Number(results.dT_chw_C ?? (chwReturn - chwSupply));
  const dTcw           = Number(results.dT_cw_C  ?? (cwReturn - cwSupply));
  const cop            = Number(inputs.cop ?? 5.5);
  const copCheck       = String(results.cop_check ?? "PASS");
  const ashraeMinCop   = Number(results.ashrae_min_cop ?? 5.00);
  const refrigerant    = String(results.refrigerant ?? "R-134a or R-1234ze(E)");
  const safetyFactor   = Number(inputs.safety_factor ?? 1.10);

  // COP FAIL flag: mandatory upgrade language
  const isCopFail = copCheck === "FAIL";
  const copNote   = isCopFail
    ? `FAIL: COP ${cop} is below ASHRAE 90.1 minimum of ${ashraeMinCop} for ${chillerType}. Equipment must be re-selected before procurement. HOLD: do not procure until COP-compliant chiller is confirmed by manufacturer data sheet.`
    : `PASS: COP ${cop} meets ASHRAE 90.1 minimum of ${ashraeMinCop} for ${chillerType}.`;

  // Multi-unit / redundancy flag
  const isMultiUnit    = nUnits >= 2;
  const redundancyNote = isMultiUnit
    ? `${nUnits}-unit configuration with lead-lag sequencing. Each unit capable of carrying full design load during standby.`
    : `Single-unit configuration: no built-in redundancy. Provide portable chiller contingency for critical facilities.`;

  // Chiller type flag: centrifugal needs magnetic bearings note; screw/scroll different
  const isCentrifugal = chillerType.toLowerCase().includes("centrifugal");

  // Cooling tower note: must be sized for Q_rejection, not Q_evap
  const ctNote = `Cooling tower MUST be sized for heat REJECTION load of ${qRejectionTR} TR (${qRejectionKW} kW): NOT the chiller nominal TR of ${nominalTR * nUnits} TR. Q_rejection = Q_evap + W_compressor. This is a common sizing error that results in an undersized cooling tower and high condenser water temperatures that degrade chiller COP.`;

  // CHW pipe diameter estimate (velocity ~1.5 m/s) — D_mm = sqrt((Q_m3s)/(π/4·v))·1000
  const chwPipeMm = chwFlowLps > 0
    ? Math.ceil(Math.sqrt((chwFlowLps / 1000) / (Math.PI / 4 * 1.5)) * 1000 / 25) * 25
    : 50;
  // CW pipe diameter estimate (velocity ~2.0 m/s)
  const cwPipeMm  = cwFlowLps > 0
    ? Math.ceil(Math.sqrt((cwFlowLps / 1000) / (Math.PI / 4 * 2.0)) * 1000 / 25) * 25
    : 50;

  const prompt = `You are a licensed Mechanical Engineer in the Philippines preparing official procurement and contracting documents for a WATER-COOLED CHILLER PLANT installation.

PROJECT: ${project}
CHILLER TYPE: ${chillerType}
STANDARDS: ASHRAE 90.1 (COP: ${ashraeMinCop} min for ${chillerType}), ASHRAE 15 (refrigerant safety), ASHRAE Guideline 12 (Legionella/CW treatment), CTI STD-201 (cooling tower), PSME Code, PEC 2017, PGBC/BERDE

CALCULATION RESULTS:
- Building Cooling Load: ${designKW / safetyFactor} kW (safety factor: ${safetyFactor})
- Design Load: ${designKW} kW
- Number of Chiller Units: ${nUnits} × ${nominalTR} TR (${nominalKW} kW each)
- Total Installed Capacity: ${totalTR} TR
- Compressor Power per Unit: ${compPerUnitKW} kW
- Total Compressor Power: ${compPowerKW} kW | ${totalKVA} kVA | ${totalAmp} A FLA (3-phase 400V)
- COP: ${cop}: ASHRAE 90.1 Check: ${copNote}
- CHW Supply/Return: ${chwSupply}°C / ${chwReturn}°C (ΔT = ${dTchw}°C)
- CHW Flow Rate: ${chwFlowLps} L/s (${chwFlowM3h} m³/h): estimated pipe ~${chwPipeMm}mm
- Condenser Heat Rejection: ${qRejectionKW} kW = ${qRejectionTR} TR
- ${ctNote}
- CW Supply/Return: ${cwSupply}°C / ${cwReturn}°C (ΔT = ${dTcw}°C)
- CW Flow Rate: ${cwFlowLps} L/s (${cwFlowM3h} m³/h): estimated pipe ~${cwPipeMm}mm
- Refrigerant: ${refrigerant}
- Redundancy: ${redundancyNote}

Generate a JSON object with exactly two arrays:

ARRAY 1: "bom_items": 17 items for a complete water-cooled chiller plant.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Water-Cooled ${chillerType} Chiller: ${nominalTR} TR (${nominalKW} kW) each, ${refrigerant}, COP ≥ ${cop} at ${cwSupply}°C entering condenser water, ASHRAE 90.1 compliant, factory-tested with certified performance data sheet: qty: ${nUnits}${isCopFail ? ': HOLD: re-select with COP ≥ ' + ashraeMinCop + ' before procurement' : ''}
2. Cooling Tower, Induced-Draft Counterflow: sized for ${qRejectionTR} TR heat rejection (${qRejectionKW} kW), NOT chiller TR: CW range ${dTcw}°C, entering ${cwReturn}°C / leaving ${cwSupply}°C, CTI certified, FRP construction, drift eliminator ≤0.001%: qty: ${nUnits} cells
3. Chilled Water Pump (CHW), Base-Mounted: end-suction centrifugal, ${Math.round(chwFlowM3h)} m³/h, head TBD hydraulic design, TEFC motor, back pull-out design: qty: ${isMultiUnit ? nUnits + 1 : 2} (duty-standby)
4. Condenser Water Pump (CW), Base-Mounted: end-suction centrifugal, ${Math.round(cwFlowM3h)} m³/h, head TBD hydraulic design, TEFC motor: qty: ${isMultiUnit ? nUnits + 1 : 2} (duty-standby)
5. Chilled Water Pipe, Carbon Steel Schedule 40: ~${chwPipeMm}mm nominal dia, flanged or grooved joints, hydrostatically tested 1.5× working pressure: qty: 1 lot
6. Condenser Water Pipe, Carbon Steel Schedule 40: ~${cwPipeMm}mm nominal dia, galvanized interior or epoxy-lined for CW service, flanged or grooved: qty: 1 lot
7. CHW Pipe Insulation: 50mm closed-cell elastomeric foam, vapor-sealed all joints and fittings, for all CHW pipes in conditioned space: qty: 1 lot
8. Chilled and Condenser Water Valves: butterfly valves (isolation), globe valves (balancing), Y-strainers (before each pump and chiller), flexible connectors at all rotating equipment: qty: 1 lot
9. Expansion Tank, Closed Bladder-Type, CHW Loop: ASME rated, pre-charged nitrogen, sized for ${Math.round(chwFlowM3h * 0.05)} L minimum: qty: 1 unit
10. Chemical Dosing System: corrosion inhibitor, scale inhibitor, biocide (Legionella control per ASHRAE Guideline 12), automatic dosing pump, chemical day tank, water quality test kit: qty: 1 set
11. Cooling Tower Basin Treatment: side-stream filtration unit (10–25 micron), bleed-off valve with conductivity controller, sand or multimedia filter: qty: 1 set
12. Chiller Controller / BMS Interface: DDC controller, Modbus/BACnet gateway, ${isMultiUnit ? 'lead-lag sequencing (mandatory for ' + nUnits + ' chillers)' : 'BMS integration'}, CHW setpoint reset, cooling tower fan staging, alarm monitoring: qty: 1 set
13. Refrigerant Leak Detection: electrochemical sensor per machine room, rated for ${refrigerant}, audible/visual alarm, per ASHRAE 15: qty: 1 set
14. Machine Room Ventilation: minimum 6 ACH mechanical exhaust per ASHRAE 15, ${chillerType === 'Centrifugal' ? 'interlocked with refrigerant leak detector' : 'interlocked with leak detector'}, explosion-proof fan if required by refrigerant class: qty: 1 set
15. Electrical MCC / Disconnect: MCCB rated ≥ ${Math.ceil(totalAmp * 1.25 / 10) * 10} A total, 3-phase 400V, individual disconnect per chiller and per pump, with overload protection: qty: 1 set
16. Equipment Inertia Bases and Anti-Vibration Isolators: spring/neoprene isolators for all chillers and pumps, inertia bases for pumps to reduce vibration transmission to structure: qty: ${nUnits + (isMultiUnit ? nUnits + 2 : 4)} sets
17. Commissioning, TAB, and Water Treatment Start-Up: hydronic balancing by certified TAB contractor, COP field verification at design conditions (${cwSupply}°C entering condenser water, ${chwSupply}°C CHW supply), factory witness test report, Legionella risk assessment, O&M manual and as-built drawings: qty: 1 lot${isCopFail ? ': MANDATORY HOLD POINT: do not commission until COP-compliant equipment is installed and verified' : ''}

ARRAY 2: "sow_sections": 8 sections (each: section_no, title, content).
Cover:
1. Scope of Works: supply and install ${nUnits} × ${nominalTR} TR water-cooled ${chillerType} chiller(s), ${nUnits}-cell cooling tower (${qRejectionTR} TR rejection), CHW/CW pump systems, BMS controls, chemical treatment, and commissioning
2. Design Basis: ASHRAE 90.1, ${designKW} kW design load (${(designKW/3.517).toFixed(1)} TR) with ${safetyFactor}× safety, CHW ${chwSupply}/${chwReturn}°C, CW ${cwSupply}/${cwReturn}°C, COP ${cop}: ${copCheck}${isCopFail ? ': FAIL: RE-SELECT EQUIPMENT BEFORE PROCUREMENT' : ''}. Cooling tower rated for ${qRejectionTR} TR (NOT chiller TR)
3. Equipment Supply and Installation: chiller placement per ASHRAE 15 machine room requirements, minimum aisle clearance, seismic restraint per PSME, anti-vibration isolation required for all rotating equipment, cooling tower on structural steel support frame (structural engineer to confirm adequacy for tower weight)
4. Chilled Water and Condenser Water Systems: CHW: ${chwFlowLps} L/s (${chwFlowM3h} m³/h), pipe ~${chwPipeMm}mm CS Sch.40, insulate CHW pipes 50mm closed-cell foam vapor-sealed. CW: ${cwFlowLps} L/s (${cwFlowM3h} m³/h), pipe ~${cwPipeMm}mm CS Sch.40 galvanized/epoxy lined. Hydronic balancing mandatory after commissioning
5. Cooling Tower and Water Treatment (Legionella Compliance): cooling tower sized for ${qRejectionTR} TR heat rejection. Water treatment per ASHRAE Guideline 12: corrosion inhibitor, scale inhibitor, biocide dosing, side-stream filtration, conductivity bleed-off control. Legionella risk assessment by qualified water treatment specialist before system start-up. Monthly water quality log mandatory for regulatory compliance
6. Refrigerant Safety (ASHRAE 15): ${refrigerant} refrigerant, machine room ventilation minimum 6 ACH, electrochemical leak detector mandatory, alarm to BMS, refrigerant charge log maintained, only PSME/EPA-certified technicians to handle refrigerant
7. Electrical Works: ${totalKVA} kVA total, 3-phase 400V supply, ${totalAmp} A FLA, MCCB rating ≥ ${Math.ceil(totalAmp * 1.25 / 10) * 10} A, all electrical works by PEC-licensed master electrician, Electrical Permit from LGU before commencement${isCopFail ? '. NOTE: Do not energize equipment until COP-compliant replacement is installed' : ''}
8. Testing, Commissioning, and Regulatory Compliance: hydronic TAB by certified contractor, COP field verification at ${cwSupply}°C entering CW / ${chwSupply}°C CHW supply, factory witness test report, Legionella risk assessment report, PSME Code, ASHRAE 90.1/15, CTI STD-201, PEC 2017, PGBC/BERDE energy compliance, DOLE OSH, LGU Mechanical Permit, PRC-licensed Mechanical Engineer sign-off${isCopFail ? '. MANDATORY HOLD POINT: system must not be commissioned until COP-compliant chiller is confirmed installed and tested' : ''}

Respond ONLY in JSON with keys bom_items and sow_sections.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Cooling Tower Sizing BOM + SOW Agent ────────────────────────────────────

async function coolingTowerBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project      = inputs.project_name  || "Cooling Tower Project";
  const loadSource   = String(inputs.load_source || "direct");
  const nCells       = Number(results.n_cells  ?? inputs.n_cells ?? 1);
  const qRejKW       = Number(results.q_rejection_kw ?? 0);
  const qRejTR       = Number(results.q_rejection_tr ?? 0);
  const qCellKW      = Number(results.q_cell_kw ?? 0);
  const qCellTR      = Number(results.q_cell_tr ?? 0);
  const ewt          = Number(results.ewt ?? inputs.ewt ?? 37);
  const lwt          = Number(results.lwt ?? inputs.lwt ?? 32);
  const wbt          = Number(results.wbt ?? inputs.wbt ?? 27);
  const range        = Number(results.range_c ?? (ewt - lwt));
  const approach     = Number(results.approach_c ?? (lwt - wbt));
  const coc          = Number(results.coc ?? inputs.coc ?? 4);
  const lgRatio      = Number(results.lg_ratio ?? inputs.lg_ratio ?? 1.2);
  const qWlps        = Number(results.q_w_lps ?? 0);
  const qWm3hr       = Number(results.q_w_m3hr ?? 0);
  const fanFlowCMH   = Number(results.fan_flow_CMH ?? 0);
  const fanKWstd     = Number(results.fan_kw_std ?? 0);
  const fanKWtotal   = Number(results.fan_kw_total ?? 0);
  const makeupLhr    = Number(results.makeup_lhr ?? 0);
  const makeupM3day  = Number(results.makeup_m3day ?? 0);
  const evapLhr      = Number(results.evap_lhr ?? 0);
  const blowdownLhr  = Number(results.blowdown_lhr ?? 0);
  const ashraeCheck  = String(results.ashrae_ct_check ?? "PASS");
  const fanKW100kw   = Number(results.fan_kw_per_100kw ?? 0);
  const isAshraePass = ashraeCheck.startsWith("PASS") || ashraeCheck.startsWith("✓");

  // Condenser water pipe size estimate (velocity ~1.5 m/s)
  const cwPipeMm = qWlps > 0
    ? Math.ceil(Math.sqrt((4 * qWlps / 1000) / (Math.PI * 1.5)) * 1000 / 25) * 25
    : 100;

  const chillerNote = loadSource === "chiller"
    ? `Heat source: chiller plant. Cooling tower sized for CONDENSER REJECTION load: NOT chiller nominal TR. Q_rejection = Q_evap + W_compressor.`
    : `Heat source: direct process heat rejection of ${qRejKW} kW.`;

  const prompt = `You are a licensed Mechanical Engineer in the Philippines preparing official procurement and contracting documents for a COOLING TOWER installation.

PROJECT: ${project}
STANDARDS: CTI STD-201 (cooling tower performance), ASHRAE GRP-214 (water loss), ASHRAE 90.1 (fan power ≤ 4 kW/100 kW), ASHRAE Guideline 12 (Legionella control), PSME Code, DOLE OSH, PEC 2017, PGBC/BERDE

CALCULATION RESULTS:
- Heat Source: ${chillerNote}
- Total Heat Rejection: ${qRejKW} kW = ${qRejTR} TR
- Number of Cells: ${nCells} × ${qCellKW} kW (${qCellTR} TR) per cell
- Entering Water Temperature (EWT): ${ewt}°C
- Leaving Water Temperature (LWT): ${lwt}°C
- Wet Bulb Temperature (WBT): ${wbt}°C
- Range: ${range}°C | Approach: ${approach}°C (CTI STD-201 minimum 2°C)
- Cycles of Concentration: ${coc}
- L/G Ratio: ${lgRatio}
- Circulation Flow: ${qWlps} L/s (${qWm3hr} m³/h): estimated CW pipe ~${cwPipeMm}mm
- Fan Airflow: ${fanFlowCMH} m³/h total
- Fan Motor: ${fanKWstd} kW per cell (${fanKWtotal} kW total)
- Fan Power Index: ${fanKW100kw} kW/100 kW: ASHRAE 90.1 limit 4.0 kW/100 kW: ${isAshraePass ? "PASS" : "FAIL: select high-efficiency fan or add cells"}
- Makeup Water: ${makeupLhr} L/hr (${makeupM3day} m³/day): Evap: ${evapLhr} L/hr, Blowdown: ${blowdownLhr} L/hr

IMPORTANT - BOM SPECIFICATION FIELD: For the BOM "specification" strings, use ASCII-only characters. Do NOT use special characters such as superscript 3 (use "m3/h" instead of "m³/h"), degree (use "degC" instead of "°C"), multiplication sign (use "x" instead of "×"), greater-than-or-equal (use "min" or "not less than"), less-than-or-equal (use "not more than"), plus-minus (use "+/-"), superscript 2 (use "sq.mm" instead of "mm²"), en-dash (use "to" instead of "–"). The SOW "content" strings may keep Unicode prose.

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1: "bom_items": 18 items for a complete cooling tower installation.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items:
1. Cooling Tower, Induced-Draft Counterflow, FRP: qty: ${nCells}: spec: ${qCellKW} kW (${qCellTR} TR) heat rejection per cell, EWT ${ewt} degC / LWT ${lwt} degC / WBT ${wbt} degC, CTI STD-201 certified, drift eliminators not more than 0.001%, PVC fill media, hot-dip galvanized or FRP basin
2. Fan Motor, TEFC IE3 premium efficiency: qty: ${nCells}: spec: ${fanKWstd} kW per cell, 3-phase 400V/60Hz, IP55, direct-drive or V-belt as per tower manufacturer${!isAshraePass ? ": HOLD: fan power index exceeds ASHRAE 90.1 limit; re-select before procurement" : ""}
3. Fan Motor VFD (Variable Frequency Drive): qty: ${nCells}: spec: ${fanKWstd} kW, IP54, bypass mode, 3-phase 400V/60Hz: checked: false
4. Condenser Water Pump, Base-Mounted Centrifugal: qty: ${Math.max(2, nCells + 1)}: spec: ${Math.round(qWm3hr / nCells)} m3/h per pump, head TBD from hydraulic design, TEFC motor, duty-standby configuration
5. Condenser Water Piping, CS Schedule 40 Galvanized: qty: 1 lot: spec: ~${cwPipeMm}mm nominal dia, hot-dip galvanized interior or epoxy-lined for CW service, grooved or flanged joints
6. Y-Strainer, Flanged: qty: ${nCells + 2}: spec: DN${cwPipeMm}mm, 40-mesh stainless screen, PN16, before each pump and CT cell inlet
7. Butterfly Valve, Isolation: qty: 1 lot: spec: DN${cwPipeMm}mm, PN16, EPDM seat, cast iron body, locking handle: isolation at each pump suction/discharge and CT cell supply/return
8. Manual Balancing Valve: qty: ${nCells}: spec: DN${cwPipeMm}mm, PN16, graduated scale with memory stop: one per CT cell return
9. Flexible Pipe Connectors, Braided Rubber: qty: ${nCells * 2 + 4}: spec: DN${cwPipeMm}mm x 300mm, PN16, stainless braid, at all pump suction/discharge and CT cell connections
10. Automatic Water Level Control Valve (Makeup): qty: ${nCells}: spec: float-operated or solenoid-operated makeup water valve, PN10, 25mm inlet, for CT basin level control
11. Makeup Water Piping: qty: 1 lot: spec: ${makeupM3day} m3/day demand (${makeupLhr} L/hr), 25mm domestic water feed to each basin, with ball valve isolation and backflow preventer
12. Chemical Dosing System: qty: 1 set: spec: automatic dosing pump for corrosion inhibitor, scale inhibitor, and biocide (Legionella control per ASHRAE Guideline 12); chemical day tank; water quality test kit; side-stream filtration unit (10 to 25 micron) with multimedia filter
13. Conductivity Controller with Blowdown Solenoid: qty: ${nCells}: spec: automatic blowdown control to maintain CoC = ${coc}, conductivity setpoint adjustable, 24V solenoid bleed-off valve
14. Structural Frame & Basin Curb Assembly: qty: 1 lot: spec: hot-dip galvanized steel structural frame including CT basin curb, designed for CT operating weight including water, per structural engineer's certification; anchor bolts per seismic zone (NSCP)
15. Drift Eliminator Replacement Set: qty: ${nCells}: spec: PVC, not more than 0.001% drift loss per CTI STD-201; included for handover to Owner as first replacement set: checked: false
16. Electrical Works: qty: 1 lot: spec: MCCB per cell (${Math.ceil(fanKWstd * 1.25 / 0.85 / (Math.sqrt(3) * 0.4) * 1.25)} A, 3-pole, 400V, 18kA AIC), wiring THHN 3.5 sq.mm (3C) per PEC 2017, conduit in CT area to be rigid galvanized or PVC Schedule 40 (corrosive environment)
17. Legionella Water Management Plan: qty: 1 lot: spec: risk assessment by qualified water treatment specialist, written water safety plan per ASHRAE Guideline 12, monthly water quality logs for COC, pH, biocide residual
18. Testing, Balancing, and Commissioning: qty: 1 lot: spec: CTI STD-201 performance test at design conditions (EWT ${ewt} degC, WBT ${wbt} degC), measured LWT not more than ${(lwt + 0.5).toFixed(1)} degC; CW flow balance within +/-10% of ${qWm3hr} m3/h; fan motor current not more than nameplate FLA; ASHRAE 90.1 fan power not more than 4 kW/100 kW verified; commissioning report signed by PRC-licensed Mechanical Engineer

ARRAY 2: "sow_sections": 8 sections of Scope of Works in Philippine engineering document style.
Each object: { "section_no": number, "title": string, "content": string, "checked": true }

IMPORTANT: Each "content" must be a full professional specification paragraph of at least 4–6 complete sentences. Write as a licensed engineer giving binding contractual requirements. Use "The Contractor shall..." sentence structure. Include specific dimensions, standards, test pressures, tolerances, and acceptance criteria. Do NOT use one-word bullets or vague phrases.

Required sections:

1. Scope Overview
content: State that the Contractor shall furnish, deliver, install, test, commission, and hand over a complete and operational cooling tower system for ${project}. Include: ${nCells} cell(s) × ${qCellTR} TR per cell (${qRejTR} TR total heat rejection at EWT ${ewt}°C / LWT ${lwt}°C / WBT ${wbt}°C, CTI STD-201 certified), condenser water pumps (duty-standby, ${qWm3hr} m³/h total flow), makeup water system (${makeupM3day} m³/day), chemical treatment and Legionella control per ASHRAE Guideline 12, fan motors ${fanKWstd} kW per cell, structural support frame, electrical supply per PEC 2017, and full commissioning per CTI STD-201.

2. Cooling Tower Equipment Installation
content: Describe installation requirements for CTI STD-201 compliance: level mounting on structural steel frame (certified for operating weight including water), anchor bolts per NSCP seismic zone, minimum 2× tower diameter clearance on air inlet faces, no recirculation of exhaust air into air inlet, drift eliminator inspection access from grade or permanent access platform. Tower basin to be cleaned and flushed before chemical treatment start-up. CT orientation shall place prevailing wind on the air inlet face: Contractor to confirm with Architect/Structural Engineer before final placement.

3. Condenser Water Piping System
content: Detail CW piping installation: ${cwPipeMm}mm CS Sch.40 galvanized (interior hot-dip or epoxy-lined) for condenser water service, flanged or grooved mechanical joints, Y-strainers before each pump and cell inlet (40-mesh SS screen, PN16), isolation butterfly valves at all main connections, manual balancing valve per CT cell return (PN16, graduated scale), braided rubber flexible connectors at all pump and CT connections (DN${cwPipeMm}mm × 300mm, PN16). System shall be hydrostatically tested at 1.5× working pressure (minimum 600 kPa) for 4 hours with zero visible leakage. CW flow shall be balanced to within ±10% of design flow (${qWm3hr} m³/h total, ${(qWm3hr/nCells).toFixed(1)} m³/h per cell).

4. Makeup Water and Blowdown Control
content: Makeup water piping shall be sized for ${makeupM3day} m³/day demand (${makeupLhr} L/hr), fed from the domestic water supply to each CT basin via float-operated or solenoid makeup valve, with ball valve isolation and a backflow preventer (RP-type, ASSE 1013) to prevent contamination of potable water supply. A conductivity controller with automatic bleed-off solenoid valve shall be installed per cell, factory-set to maintain cycles of concentration = ${coc} (adjustable range 2–8). Blowdown rate per cell = ${blowdownLhr} L/hr at CoC ${coc}. A flow meter on the makeup line is recommended for water consumption monitoring. Total water consumption = ${makeupM3day} m³/day: Contractor to verify adequacy of incoming water supply pressure (minimum 200 kPa at valve) before proceeding.

5. Fan and Electrical Works
content: Fan motors (${fanKWstd} kW per cell, TEFC IE3, IP55, 3-phase 400V/60Hz) shall be installed per cooling tower manufacturer's instructions with proper belt tension or direct-drive coupling as applicable. Fan power index = ${fanKW100kw} kW per 100 kW heat rejection: ASHRAE 90.1 limit 4.0 kW/100 kW: ${isAshraePass ? "PASS. This shall be field-verified during commissioning at design conditions." : "FAIL: Contractor shall NOT energize fan motors until a high-efficiency fan assembly achieving ≤4.0 kW/100 kW is installed and confirmed by engineer."}  MCCB (3-pole, 400V, 18kA AIC) shall be installed per cell. All wiring shall be THHN 3.5mm² (3C) minimum per PEC 2017, in rigid galvanized conduit or PVC Schedule 40 in the cooling tower area (corrosive/wet environment). Electrical permit from LGU Building Official shall be obtained before any electrical works commence.

6. Chemical Water Treatment and Legionella Control
content: The Contractor shall install a complete automatic chemical dosing system per ASHRAE Guideline 12 for Legionella risk management: corrosion inhibitor, scale inhibitor, and biocide dosing pumps with chemical day tanks, wired to an automatic timer or water meter pulse; a side-stream filtration unit (10–25 micron multimedia filter, minimum 10% of system flow) to remove suspended solids that harbor Legionella biofilm; a written water safety plan (Legionella Water Management Plan) prepared by a qualified water treatment specialist before system start-up; and monthly water quality monitoring with log (pH: 7.0–8.5, conductivity at target CoC ${coc}, biocide residual per product spec, Legionella colony count < 100 CFU/L). System shall be disinfected with hyperchlorination (50 ppm free chlorine, 24-hr contact) before first commissioning and after any shutdown exceeding 7 days.

7. Testing, Commissioning, and Performance Verification
content: The Contractor shall conduct a CTI STD-201 thermal performance test after system stabilization (minimum 4 hours of steady-state operation at ≥75% design load). Test measurements shall include: (a) EWT: measured within ±0.5°C of ${ewt}°C; (b) LWT: measured ≤ ${(lwt + 0.5).toFixed(1)}°C; (c) WBT: measured on-site with sling psychrometer or calibrated sensor; (d) CW flow: within ±10% of ${qWm3hr} m³/h verified by clamp-on ultrasonic meter; (e) fan motor current: shall not exceed nameplate FLA of each motor; (f) fan power index: shall be ≤ 4.0 kW/100 kW per ASHRAE 90.1; (g) drift: visual check and manufacturer's drift eliminator certification ≤0.001%. TAB report and commissioning report shall be signed by a PRC-licensed Mechanical Engineer and submitted to the Owner and Engineer of Record.

8. Regulatory Compliance and Handover
content: The Contractor shall be fully responsible for compliance with all applicable Philippine codes and standards: CTI STD-201: cooling tower performance certification; ASHRAE GRP-214: water loss and makeup water calculation basis; ASHRAE 90.1: fan power ≤ 4.0 kW/100 kW heat rejection; ASHRAE Guideline 12: Legionella Water Management Plan (mandatory before start-up); PSME Code: mechanical installation and LGU Mechanical Permit required before works begin; PEC 2017: all electrical installations; NSCP: structural support frame design and seismic anchorage; DOLE OSH: safety requirements for rotating equipment, chemical handling, and hot water systems; PGBC/BERDE: water efficiency documentation (makeup water consumption = ${makeupM3day} m³/day). At project completion, the Contractor shall hand over: O&M manuals, as-built drawings, CTI certified performance data sheets, chemical dosing log, commissioning report, Legionella risk assessment, and one complete set of spare fill media and drift eliminator panels per cell. A PRC-licensed Mechanical Engineer shall sign and seal all as-built mechanical drawings.

Respond with ONLY the JSON object. No explanation outside the JSON.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Boiler System BOM + SOW Agent ───────────────────────────────────────────

async function boilerBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project       = inputs.project_name   || "Boiler System Project";
  const boilerType    = String(results.boiler_type || inputs.boiler_type || "Steam");
  const isSteam       = boilerType === "Steam";
  const fuelType      = String(inputs.fuel_type  || "Diesel");
  const numBoilers    = Number(inputs.num_boilers ?? 1);
  const qBoilerKw     = results.q_boiler_kw    ?? "N/A";
  const qBoilerBhp    = results.q_boiler_bhp   ?? "N/A";
  const totalKw       = results.total_capacity_kw ?? qBoilerKw;
  const fuelKghr      = results.fuel_consumption_kg_hr ?? "N/A";
  const fuelLhr       = results.fuel_consumption_lhr   ?? "N/A";
  const safetyValve   = results.safety_valve_min_kg_hr ?? results.safety_valve_min_kw ?? "N/A";
  const safetyUnit    = isSteam ? "kg/hr" : "kW";

  // Steam-only fields
  const steamDemand   = results.steam_demand_kg_hr  ?? inputs.steam_demand   ?? "N/A";
  const designPressure= results.design_pressure_barg ?? inputs.design_pressure ?? "N/A";
  const satTemp       = results.t_sat_c ?? "N/A";
  const blowdownPct   = results.blowdown_pct  ?? "N/A";
  const blowdownKghr  = results.blowdown_kg_hr ?? "N/A";
  const tFeedwater    = inputs.feedwater_temp ?? 80;
  const tdsMax        = inputs.tds_max        ?? 3500;
  const tdsMakeup     = inputs.tds_makeup     ?? 200;

  // Hot water fields
  const supplyTemp    = inputs.supply_temp    ?? results.system_pressure_barg ?? "N/A";
  const returnTemp    = inputs.return_temp    ?? "N/A";
  const deltaT        = results.delta_t_c     ?? "N/A";
  const hwPressure    = results.system_pressure_barg ?? "N/A";
  const flowLhr       = inputs.flow_rate_lhr  ?? "N/A";

  // Fuel storage qty (rough: 8 hours at full load + 20% reserve)
  const fuelKghrNum   = Number(fuelKghr) || 0;
  const tankLitres    = Math.round(fuelKghrNum * 8 * 1.2 / (fuelType === "Diesel" ? 0.84 : fuelType === "LPG" ? 0.54 : 0.96));
  const condensatePipe= isSteam ? "50 mm" : "N/A";
  const steamPipeDia  = isSteam ? (Number(steamDemand) > 1000 ? "100 mm" : Number(steamDemand) > 500 ? "80 mm" : "65 mm") : "N/A";
  const hwPipeDia     = !isSteam ? (Number(flowLhr) > 5000 ? "80 mm" : Number(flowLhr) > 2000 ? "65 mm" : "50 mm") : "N/A";

  const systemDesc = isSteam
    ? `${numBoilers > 1 ? numBoilers + '×' : ''}${qBoilerBhp} BHP (${qBoilerKw} kW) ${fuelType}-fired steam boiler at ${designPressure} barg / ${satTemp}°C, steam flow ${steamDemand} kg/hr`
    : `${numBoilers > 1 ? numBoilers + '×' : ''}${qBoilerBhp} BHP (${qBoilerKw} kW) ${fuelType}-fired hot water boiler, supply ${supplyTemp}°C / return ${returnTemp}°C, ΔT ${deltaT}°C`;

  const standards = isSteam
    ? "ASME BPVC Section I (Power Boilers), Philippine Boiler and Pressure Vessel Code (PD 8), PSME Code, PEC 2017, DOLE OSH Department Order No. 13-98, DOE Circular DC2021-11-0019 (energy audit for >500 kW boilers)"
    : "ASME BPVC Section IV (Heating Boilers), Philippine Boiler and Pressure Vessel Code (PD 8), PSME Code, Philippine Plumbing Code, PEC 2017, DOLE OSH Department Order No. 13-98";

  const prompt = `You are a licensed Mechanical Engineer in the Philippines preparing official procurement and contracting documents for a ${boilerType.toLowerCase()} boiler system installation.

CALCULATION RESULT:
Project: ${project}
Boiler Type: ${boilerType}
Fuel: ${fuelType}
Number of Boilers: ${numBoilers}
Boiler Capacity (each): ${qBoilerBhp} BHP (${qBoilerKw} kW)
Total Installed Capacity: ${totalKw} kW
${isSteam ? `Design Pressure: ${designPressure} barg | Saturation Temperature: ${satTemp}°C
Steam Demand: ${steamDemand} kg/hr
Feedwater Temperature: ${tFeedwater}°C
Blowdown Rate: ${blowdownPct}% (${blowdownKghr} kg/hr)
TDS Makeup: ${tdsMakeup} ppm | TDS Max: ${tdsMax} ppm
Safety Valve Rating: ${safetyValve} ${safetyUnit}
Steam Pipe (estimated): ${steamPipeDia}
Condensate Return Pipe: ${condensatePipe}` : `Supply Temperature: ${supplyTemp}°C | Return Temperature: ${returnTemp}°C | ΔT: ${deltaT}°C
Flow Rate: ${flowLhr} L/hr
System Pressure: ${hwPressure} barg
Safety Valve Rating: ${safetyValve} ${safetyUnit}
HW Distribution Pipe (estimated): ${hwPipeDia}`}
Fuel Consumption: ${fuelKghr} kg/hr${fuelType !== "Natural Gas" ? ` (${fuelLhr} L/hr)` : ""}
Estimated Fuel Storage Tank: ${tankLitres} L (8-hr reserve at full load, ×1.20 safety margin)

TASK: Generate a JSON object with exactly two arrays.

ARRAY 1: "bom_items": Standard Philippine mechanical contractor Bill of Materials for a ${boilerType.toLowerCase()} boiler room installation.
Each object: { "item_no": number, "description": string, "specification": string, "qty": number, "unit": string, "remarks": string, "checked": true }

Required items (adapt to ${boilerType} type):
1. ${boilerType} Boiler: qty: ${numBoilers} unit: specify ${fuelType}-fired, ${qBoilerBhp} BHP (${qBoilerKw} kW) per unit, ${isSteam ? `design pressure ${designPressure} barg, ASME Sec I stamped` : `working pressure ${hwPressure} barg, ASME Sec IV stamped`}, PD 8 compliant, CE/UL listed burner
2. Burner Assembly: qty: ${numBoilers} unit: specify forced-draft, modulating type, rated for ${fuelType}${fuelType === "Diesel" ? " (HSD, Bunker C capable)" : ""}, CE marked, integrated air-fuel ratio controller
3. ${isSteam ? "Steam Safety Valve" : "Pressure Relief Valve (PRV)"}: qty: ${numBoilers * 2} pcs: specify ${isSteam ? `ASME Sec I stamped, set pressure ≤ ${(Number(designPressure) * 1.05 + 0.1).toFixed(1)} barg, ${safetyValve} kg/hr` : `ASME Sec IV / PD 8, set pressure ≤ ${(Number(hwPressure) + 0.5).toFixed(1)} barg, ${safetyValve} kW rated`}, spring-loaded, full-lift type
4. ${isSteam ? "Feedwater Pump / Boiler Feed Unit" : "Circulation Pump"}: qty: ${numBoilers} set: specify ${isSteam ? `minimum 110% of maximum boiler steam output capacity, duplex pump set with standby, 316 SS impeller, variable speed drive` : `design flow ${flowLhr} L/hr, variable speed drive (VSD), TEFC motor, IE3 efficiency`}
5. ${isSteam ? "Deaerator / Feed Tank" : "Expansion Tank"}: qty: 1 unit: specify ${isSteam ? `spray-tray type, 30-minute hold capacity, rated for ${designPressure} barg, 316 SS internals, thermostatic vent, O₂ removal ≥ 0.005 cc/L` : `closed expansion tank, ASME stamped, pre-charge pressure per system, rated at ${hwPressure} barg`}
6. ${isSteam ? "Steam Header / Distribution Manifold" : "Hot Water Buffer / Header Manifold"}: qty: 1 set: specify ${isSteam ? `Schedule 40 carbon steel, ${steamPipeDia} nominal, PN40 rated, flanged connections with isolation per boiler` : `Schedule 40 carbon steel, ${hwPipeDia} nominal, PN16 rated, flanged connections`}
7. ${isSteam ? "Steam Piping" : "HW Distribution Piping"}: qty: 1 lot: specify ${isSteam ? `Schedule 40 CS pipe ${steamPipeDia} nominal, 150# class flanges, 25mm mineral wool insulation with aluminum jacket` : `Schedule 40 CS or pre-insulated pipe ${hwPipeDia} nominal, 50mm PU foam insulation, aluminum jacket`}, within boiler room
8. ${isSteam ? "Condensate Return System" : "Return Piping"}: qty: 1 set: specify ${isSteam ? `${condensatePipe} Schedule 40 CS or CPVC, condensate pump if below grade, float-type steam trap at each end point, 25mm insulation` : `${hwPipeDia} Schedule 40 CS, 50mm PU foam insulation, aluminum jacket`}
9. ${isSteam ? "Blowdown Separator and Blowdown Tank" : "Air Separator / Dirt Strainer"}: qty: 1 set: specify ${isSteam ? `continuous blowdown (CBD) with heat exchanger for energy recovery, intermittent blowdown (IBD) tank ≥ 1,000L capacity, TDS controller at ${tdsMax} ppm setpoint` : `combination air/dirt separator, magnetic, rated ${hwPressure} barg, auto-vent, ${hwPipeDia} connections`}
10. ${isSteam ? "Water Treatment System (Boiler Water)" : "Water Treatment System (HW Circuit)"}: qty: 1 set: specify ${isSteam ? `twin-bed softener (to ≤ 5 ppm hardness), chemical dosing pump × 3 (oxygen scavenger, scale inhibitor, corrosion inhibitor), TDS meter and blowdown controller` : `inhibitor dosing unit, pH controller 8.2–9.0, inline dosing pot with isolation valves`}
11. ${fuelType === "Natural Gas" ? "Gas Pressure Regulator Set and Gas Train" : `${fuelType} Day Tank / Fuel Storage Tank`}: qty: 1 set: specify ${fuelType === "Natural Gas" ? "dual-stage pressure regulator, slam-shut valve, MAOP rating, PNOC/DOE compliant, gas leak detection with automatic shut-off" : `double-walled, ${tankLitres} L capacity, UL listed, 3-hr fire-rated, level gauge, overfill protection, fuel transfer pump`}
12. Combustion Flue / Exhaust Stack: qty: 1 lot: specify insulated single-wall or twin-wall flue stack, appropriate draft calculation diameter, height ≥ 2 m above roof line, DENR-compliant, with CO/CO₂ sampling port
13. Instrumentation and Controls: qty: 1 lot: specify boiler management system (BMS), flame detector, high-pressure cut-off, low-water level cut-off, temperature and pressure transmitters, ${isSteam ? "steam flow meter" : "energy meter (BTU meter)"}, interconnected to BAS terminal
14. Boiler Room Ventilation: qty: 1 set: specify forced-draft inlet louver (≥10 air changes/hr), exhaust fan, explosion-proof rated for boiler room hazardous area classification
15. Electrical Works: qty: 1 lot: specify MCC panel with MCCB, burner interlock circuit, emergency stop, PEC 2017 compliant, explosion-proof wiring in boiler room, earthing system
16. Insulation Works (Boiler Shell and Piping): qty: 1 lot: specify 75mm mineral wool or ceramic fiber blanket on boiler shell (hot surfaces), 25–50mm mineral wool on steam/HW piping, all with aluminum jacket
17. Miscellaneous (bolts, gaskets, flanges, supports, commissioning chemicals, spares): qty: 1 lot

Specifications must be specific: include boiler rating (BHP and kW), operating pressure, fuel type, ASME/PD 8 stamp requirements, and Philippine code compliance throughout.

ARRAY 2: "sow_sections": Full contractor Scope of Works in Philippine engineering document style.
Each object: { "section_no": string, "title": string, "content": string, "checked": boolean }

Required sections:
- "1.0" General Scope: checked: true (describe the complete boiler room installation: ${systemDesc}, including all mechanical, piping, instrumentation, electrical, and commissioning works)
- "2.0" Applicable Standards and Codes: checked: true (list: ${standards})
- "3.0" Materials and Equipment: checked: true (all boilers shall be ASME stamped and PD 8 registered; burners CE marked; all pressure vessels inspected and registered with DOLE Boiler Inspection Branch before operation)
- "4.1" Boiler and Burner Installation: checked: true (specify foundation grouting, minimum clearances per ASME/PD 8 and manufacturer (minimum 1.0 m sides, 1.5 m front/rear), burner alignment, combustion air supply, flue connection, refractory inspection and curing procedure before first firing)
- "4.2" Pressure Vessel and Safety Device Installation: checked: true (safety valves to be set and sealed by DOLE-accredited boiler inspector; pressure gauges calibrated per PD 8; low-water cut-off tested per ASME Sec ${isSteam ? "I" : "IV"} CSD-1)
- "4.3" ${isSteam ? "Steam and Condensate Piping" : "Hot Water Piping"}: checked: true (specify material: Schedule 40 CS, slope: ${isSteam ? "minimum 1:100 toward condensate trap" : "minimum 1:200 for air venting"}, support spacing per PSME, thermal expansion loops or expansion joints at headers, all welds 100% VT and 10% RT per ANSI B31.1)
- "4.4" ${isSteam ? "Feedwater and Blowdown System" : "Expansion and Make-Up Water System"}: checked: true (${isSteam ? `deaerator commissioning procedure (check dissolved O₂ ≤ 0.005 cc/L), blowdown tank temperature ≤ 60°C before drain, TDS controller calibration at ${tdsMax} ppm setpoint, continuous and intermittent blowdown valves tested` : `expansion tank pre-charge verification, make-up water float valve setting, inhibitor dosing commissioning, system fill and venting procedure`})
- "4.5" Fuel System: checked: true (${fuelType === "Natural Gas" ? "gas train leak test at 1.5× MAOP, PNOC clearance, DOE gas permit required before connection, gas leak detection system calibration" : `fuel tank pressure test, leak test for all fuel lines at 1.5× design pressure, fire protection provisions per BFP, fuel transfer pump commissioning, 8-hr fuel reserve to be confirmed before first firing`})
- "4.6" Water Treatment and Chemical Dosing: checked: true (${isSteam ? `softener commissioning (verify hardness ≤ 5 ppm post-softener), initial boiler water conditioning per manufacturer, chemical dosing calibration, blowdown controller set at ${tdsMax} ppm, pre-operational boilout with alkaline solution to remove mill scale and oil` : `system fill with pre-treated water, inhibitor dosing commissioning, pH setpoint 8.2–9.0, initial system purge and vent to remove dissolved oxygen before first heat-up`})
- "4.7" Instrumentation and Controls: checked: true (boiler management system (BMS) programming and loop testing; burner flame scanner calibration; low-water level alarm and cut-off function test; high-pressure cut-off test; ${isSteam ? "steam flow meter calibration" : "BTU energy meter calibration"}; all interlocks verified before live firing)
- "4.8" Boiler Room Safety and Ventilation: checked: true (boiler room air changes minimum 10 per hour verified by air flow measurement; explosion-proof wiring inspection; emergency stop button test; CO₂/CO alarm sensor calibration; fire suppression system pre-commissioning if provided; DOLE boiler inspection clearance to be obtained before first firing)
- "4.9" Hydraulic/Hydrostatic Pressure Test: checked: true (all piping systems pressure tested at 1.5× maximum working pressure, minimum 30 minutes, zero drop, witnessed by DOLE boiler inspector; boiler shell tested per ASME Sec ${isSteam ? "I" : "IV"} before insulation is applied)
- "4.10" First Firing and Performance Test: checked: true (dry-out firing sequence per manufacturer (low fire → full fire over 48–72 hours for ${isSteam ? "steam" : "hot water"} boilers to cure refractory and prevent thermal shock); combustion analysis: CO₂ target 13–14% for ${fuelType === "Natural Gas" ? "gas" : "oil/diesel"}, O₂ 2–3%, CO < 100 ppm; verify design output of ${qBoilerKw} kW at design pressure; thermal efficiency measurement and submission)
- "4.11" Testing, Commissioning, and Handover: checked: true (submit commissioning report signed by PRC-licensed ME; submit DOLE Certificate of Boiler Inspection and Registration; submit as-built drawings, O&M manuals, manufacturer warranties; train Owner's operators for minimum 4 hours on safe operation, emergency shutdown, blowdown, and routine maintenance)
- "5.0" Inclusions: checked: false (list what is included: boiler, burner, all piping within boiler room, controls, insulation, commissioning, DOLE inspection coordination, operator training)
- "6.0" Exclusions: checked: false (civil and structural works, boiler room building shell, chimney foundation, electrical service entrance, fuel supply main line, water source connection, building permits, DENR air emission permit)
- "7.0" Warranty: checked: false (1 year workmanship from DOLE acceptance; 1 year parts and labor per boiler manufacturer; pressure vessel warranty per ASME and PD 8 registration; burner warranty per manufacturer)

Each section content must be 3–5 sentences in professional Philippine engineering contractor style. Reference the specific system: ${systemDesc}, for project ${project}. All safety and compliance requirements must cite the specific Philippine code or ASME section.

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);

  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── HVAC: Duct Sizing BOM + SOW Agent ───────────────────────────────────────

async function ductSizingBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project      = inputs.project_name  || "HVAC Duct System Project";
  const ductShape    = String(inputs.duct_shape    || "Circular");
  const frRate       = Number(inputs.friction_rate || 1.0);
  const airDensity   = Number(inputs.air_density   || 1.20);
  const ductMat      = String(inputs.duct_material || "Galvanized Steel");
  const nSegments    = ((inputs.segments as unknown[]) || []).length;
  const totalDpPa    = Number(results.total_dp_pa  || 0);
  const fanStaticPa  = Number(results.fan_static_pa || 0);
  const fanMotorHp   = Number(results.fan_motor_hp_std || 0);
  const fanMotorKw   = Number(results.fan_motor_kw || 0);
  const maxFlowLps   = Number(results.max_flow_lps || 0);
  const totalLenM    = Number(results.total_length_m || 0);
  const fittingsFactor   = Number(results.fittings_factor || 1.5);
  const fittingsExtraPct = Math.round((fittingsFactor - 1) * 100);

  // SMACNA pressure class binding to actual fan static (HVAC Duct Construction Standards 3rd Ed.)
  const smacnaClass = fanStaticPa <= 250 ? "Class 1 (250 Pa, 24 gauge typical)"
                    : fanStaticPa <= 500 ? "Class 2 (500 Pa, 22 gauge typical)"
                    : fanStaticPa <= 750 ? "Class 3 (750 Pa, 20 gauge typical)"
                    : fanStaticPa <= 1000 ? "Class 4 (1000 Pa, 20 gauge typical)"
                    : fanStaticPa <= 1500 ? "Class 6 (1500 Pa, 18 gauge typical)"
                    : "Class 10 (2500 Pa, 16 gauge typical)";

  const systemDesc = `${ductShape} ${ductMat} ductwork, fr=${frRate} Pa/m, ρ=${airDensity} kg/m³, ${nSegments} segments, System ΔP=${totalDpPa}Pa, Fan Static=${fanStaticPa}Pa, Fan Motor=${fanMotorHp}HP (${fanMotorKw}kW), Max Flow=${maxFlowLps}L/s, Total Length=${totalLenM}m`;

  const prompt = `You are a senior HVAC engineer preparing a Bill of Materials (BOM) and Scope of Works (SOW) for a Philippine HVAC duct system based on an Equal Friction Method design calculation. All items, quantities, and specifications must reflect Philippine procurement practice (PSME Code, SMACNA standards, ASHRAE 62.1).

System: ${systemDesc}
Project: ${project}

Generate a JSON object with exactly two keys:

SMACNA Pressure Class binding (Fan Static = ${fanStaticPa} Pa): ${smacnaClass}.
Item 1 spec MUST cite this exact SMACNA Pressure Class (do not over-spec).

"bom_items": array of 12 objects, each with:
  { "description": string, "specification": string, "unit": string, "qty": number, "remarks": string }

BOM items must cover:
1. Supply air rectangular or circular ductwork (${smacnaClass}, gauge per SMACNA matched to Fan Static ${fanStaticPa} Pa)
2. Return air ductwork (same SMACNA class as supply)
3. Duct insulation (25mm acoustic/thermal lining for supply mains)
4. Duct fittings allowance (elbows, tees, reducers: ${fittingsExtraPct}% extra of straight run by weight, per design fittings_factor ${fittingsFactor.toFixed(2)}x)
5. Supply air diffusers / grilles
6. Return air grilles
7. Volume control dampers (VCD): manual balancing
8. Fan unit (centrifugal inline or AHU fan section, ${fanMotorHp}HP / ${fanMotorKw}kW)
9. Fan motor VFD (variable frequency drive)
10. Flexible duct connections to fan (anti-vibration, max 300mm)
11. Duct support hangers (galvanized threaded rod + trapeze, per SMACNA)
12. TAB (Testing, Adjusting, Balancing) service (lump sum)

"sow_sections": array of 6 objects, each with:
  { "section_no": string, "title": string, "content": string }

SOW sections:
- "1.0" Scope of Works (duct fabrication, installation, insulation, commissioning for ${systemDesc})
- "2.0" Design Standards and References (ASHRAE Ch.21 equal friction; SMACNA Duct Construction Standards: pressure class per operating static; ASHRAE 62.1 velocity limits; PSME Code; PEC 2017 Art.4.30)
- "3.0" Materials and Equipment (galvanized steel gauge per SMACNA; duct insulation spec; diffuser and grille spec; VCD spec; fan and motor spec with VFD)
- "4.0" Installation Requirements (support spacing per SMACNA; joint sealing; flex duct max 1.5m; TAB by accredited TAB contractor)
- "5.0" Testing and Commissioning (SMACNA duct leakage test; TAB report within 10% of design airflow at all terminals; fan performance verification)
- "6.0" Submittals and Documentation (shop drawings with SMACNA pressure class; fan performance curve; material certificates; TAB report; O&M manual; as-built drawings)

Each content field must be a full professional paragraph starting with "The Contractor shall...". Reference specific standards and the system parameters.

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── HVAC: Refrigerant Pipe Sizing BOM + SOW Agent ───────────────────────────

async function refrigPipeSizingBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project    = inputs.project_name  || "Refrigerant Pipe Sizing Project";
  const refrig     = String(inputs.refrigerant || "R-410A");
  const capKw      = Number(inputs.capacity_kw || 0);
  const app        = String(inputs.application || "AC");
  const condTemp   = Number(inputs.cond_temp_c || 40);
  const evapTemp   = results.evap_temp_c ?? "";
  const massFlow   = results.mass_flow_kgs ?? "";
  const lineArr    = (results.lines as Array<{name:string;line_type:string;selected_od_mm:number;selected_id_mm:number;equiv_length_m:number;velocity_ms:number;vel_check:string}>) || [];

  const linesSummary = lineArr.map(l =>
    `${l.name} (${l.line_type}): ${l.selected_od_mm}mm OD ACR copper, L=${l.equiv_length_m}m, v=${l.velocity_ms}m/s ${l.vel_check}`
  ).join("; ");

  const totalSucLenM  = lineArr.filter(l => l.line_type?.includes("Suction")).reduce((s, l) => s + l.equiv_length_m, 0);
  const totalDisLenM  = lineArr.filter(l => l.line_type === "Discharge").reduce((s, l) => s + l.equiv_length_m, 0);
  const totalLiqLenM  = lineArr.filter(l => l.line_type === "Liquid").reduce((s, l) => s + l.equiv_length_m, 0);
  const totalLenM     = lineArr.reduce((s, l) => s + l.equiv_length_m, 0);

  const systemDesc = `${refrig} refrigerant, ${capKw}kW ${app} service, evap ${evapTemp}°C / cond ${condTemp}°C, ṁ=${massFlow}kg/s. Lines: ${linesSummary}`;

  const prompt = `You are a senior Refrigeration/HVAC engineer in the Philippines preparing a Bill of Materials (BOM) and Scope of Works (SOW) for refrigerant pipe installation per ASTM B280 and ASHRAE 2022 Refrigeration Handbook Chapter 1.

System: ${systemDesc}
Project: ${project}
Total suction line length: ${totalSucLenM} m
Total discharge line length: ${totalDisLenM} m
Total liquid line length: ${totalLiqLenM} m
Total pipe length: ${totalLenM} m

Generate a JSON object with exactly two keys:

"bom_items": array of 12 objects, each with:
  { "description": string, "specification": string, "unit": string, "qty": number, "remarks": string }

BOM items must cover:
1. Suction line ACR copper tube (ASTM B280): sized per design, dehydrated and capped: qty: ${Math.ceil(totalSucLenM * 1.10)} m (10% wastage)
2. Discharge line ACR copper tube (ASTM B280): sized per design: qty: ${Math.ceil(totalDisLenM * 1.10)} m
3. Liquid line ACR copper tube (ASTM B280): sized per design: qty: ${Math.ceil(totalLiqLenM * 1.10)} m
4. Suction line insulation: closed-cell elastomeric foam, 19mm thick, ASTM C534, pre-slit with self-adhesive seam: qty: ${Math.ceil(totalSucLenM * 1.10)} m
5. Discharge and liquid line insulation: closed-cell elastomeric foam, 9mm thick: qty: ${Math.ceil((totalDisLenM + totalLiqLenM) * 1.10)} m
6. Copper fittings and elbows allowance (solder/braze type, ACR grade): 20% extra of straight run: qty: 1 lot
7. Nitrogen (OFN) for purge brazing and pressure testing: 99.999% dry nitrogen: qty: 3 cylinders
8. Silver brazing alloy (15% Ag) and flux: for all brazed joints: qty: 1 lot
9. Pipe hangers and supports (insulated pipe saddles, galvanized steel brackets, threaded rod): 1.5m spacing: qty: ${Math.ceil(totalLenM / 1.5)} sets
10. Refrigerant charge, ${refrig}: per manufacturer specification adjusted for actual line set length (${capKw}kW system): qty: 1 lot
11. Filter drier (replaceable core, bidirectional): liquid line, rated for ${refrig}: qty: ${lineArr.filter(l=>l.line_type==="Liquid").length || 1} pc
12. Sight glass with moisture indicator: liquid line, rated for ${refrig}: qty: ${lineArr.filter(l=>l.line_type==="Liquid").length || 1} pc

"sow_sections": array of 6 objects, each with:
  { "section_no": string, "title": string, "content": string }

SOW sections:
- "1.0" Scope of Works (supply, install, and commission ${refrig} refrigerant line sets for ${capKw}kW ${app} system per ASTM B280 and ASHRAE Refrigeration Handbook Ch.1)
- "2.0" Design Standards and References (ASTM B280 ACR copper tube; ASHRAE 2022 Refrigeration Handbook Chapter 1 velocity method; ASHRAE 90.1 insulation; PEC 2017 Article 4 branch circuit protection; PSME Code)
- "3.0" Materials and Equipment (ASTM B280 ACR copper must be dehydrated and capped; ${refrig} refrigerant must have safety data sheet; insulation spec ASTM C534; filter drier and sight glass specs)
- "4.0" Installation Requirements (OFN nitrogen purge brazing for all joints; oil traps at suction riser bases; suction line pitch toward compressor; insulate suction lines before pressure test; no bare copper in wet/outdoor areas)
- "5.0" Testing and Commissioning (pressure test at 1.1x MAWP with dry nitrogen: 24-hour hold minimum; evacuation to 500 microns or below with vacuum pump before charging; refrigerant charge by weight per manufacturer; record charge weight on equipment tag)
- "6.0" Submittals and Documentation (ASTM B280 material certificate; refrigerant SDS; pressure test chart and evacuation log; refrigerant weight-in record; as-built drawings showing all joints, routing, and insulation; O&M manual)

Each content field must be a full professional paragraph starting with "The Contractor shall...". Reference specific standards and the system parameters (${refrig}, ${capKw}kW, ASTM B280).

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── HVAC: FCU Selection BOM + SOW Agent ──────────────────────────────────────

async function fcuSelectionBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project    = inputs.project_name    || "FCU Selection Project";
  const pipeSys    = String(inputs.pipe_system    || "2-Pipe (Cooling Only)");
  const mountType  = String(inputs.mounting_type  || "Ceiling Cassette");
  const chwSup     = Number(inputs.chw_supply_c   || 7);
  const chwRet     = Number(inputs.chw_return_c   || 12);
  const divF       = Number(inputs.diversity_factor || 0.85);
  const totalDesKW = Number(results.total_design_kw  || 0).toFixed(2);
  const totalDesTR = Number(results.total_design_tr  || 0).toFixed(2);
  const totalChw   = Number(results.total_chw_lps    || 0).toFixed(3);
  const mainNps    = results.main_pipe_nps_mm  ?? "—";
  const totalUnits = Number(results.total_units || 0);
  const roomArr    = (results.rooms as Array<{room_name:string; qty:number; selected_model:string; selected_kw:number; selected_tr:number; airflow_cmh:number; chw_flow_lps_total:number}>) || [];

  const roomSummary = roomArr.map(r =>
    `${r.room_name}: ${r.qty} x ${r.selected_model} (${r.selected_kw} kW / ${r.selected_tr} TR each, ${r.airflow_cmh} CMH, CHW ${r.chw_flow_lps_total} L/s total)`
  ).join("; ");

  const prompt = `You are a senior HVAC/Mechanical engineer in the Philippines preparing a Bill of Materials (BOM) and Scope of Works (SOW) for fan coil unit (FCU) installation per ASHRAE HVAC Systems and Equipment Handbook and PSME Code.

Project: ${project}
Pipe system: ${pipeSys}
Mounting type: ${mountType}
CHW supply/return: ${chwSup}°C / ${chwRet}°C (ΔT = ${(chwRet - chwSup).toFixed(1)}°C)
Diversity factor: ${divF}
Design load: ${totalDesKW} kW / ${totalDesTR} TR
Total CHW flow: ${totalChw} L/s
CHW main pipe: ${mainNps} mm NPS Black Steel SCH40
Total FCU units: ${totalUnits}
Room schedule: ${roomSummary}

Generate a JSON object with exactly two keys:

"bom_items": array of 12 objects, each with:
  { "description": string, "specification": string, "unit": string, "qty": number, "remarks": string }

BOM items must cover:
1. Fan Coil Units: ${mountType} type, ${pipeSys} coil configuration, per FCU schedule above: qty: ${totalUnits} units
2. CHW Supply Piping: Black Steel SCH40, ${mainNps}mm NPS main, per ASTM A53 Grade B: qty: 1 lot
3. CHW Return Piping: Black Steel SCH40, same sizing as supply: qty: 1 lot
4. Chilled Water Valves: ball valves for isolation (supply + return per FCU): qty: ${totalUnits * 2} pcs
5. Pressure Independent Control Valves (PICV): for CHW balancing, one per FCU: qty: ${totalUnits} pcs
6. CHW Branch Piping: copper or Black Steel, sized per individual FCU flow: qty: 1 lot
7. Pipe Insulation: closed-cell elastomeric foam 19mm thick, for all CHW piping (ASTM C534): qty: 1 lot
8. FCU Condensate Drain Piping: UPVC Schedule 40, 20mm minimum, sloped 1:100 to nearest drain: qty: 1 lot
9. Pipe Hangers and Supports: clevis hangers with insulation shields, galvanized, per MSS SP-58: qty: 1 lot
10. FCU Controls: digital room thermostat with 2-position CHW valve actuator per FCU: qty: ${totalUnits} sets
11. Flexible Connections: braided stainless steel, supply and return connection per FCU: qty: ${totalUnits * 2} pcs
12. Air Vent and Drain Valves: automatic air vents at high points, manual drains at low points: qty: 1 lot

"sow_sections": array of 6 objects, each with:
  { "section_no": string, "title": string, "content": string }

SOW sections:
- "1.0" Scope of Works (supply, install, and commission ${totalUnits} FCUs at ${totalDesKW}kW / ${totalDesTR}TR design load, ${pipeSys}, ${mountType} mounting)
- "2.0" Design Standards and References (ASHRAE 2023 HVAC Systems and Equipment Handbook; ASHRAE 62.1 ventilation; ASHRAE 90.1 efficiency EER min 3.5; PSME Code; ASTM A53 piping; ASTM C534 insulation)
- "3.0" Materials and Equipment (FCU specs: ${pipeSys} coil, ${mountType}, nominal capacities per schedule; Black Steel SCH40 ASTM A53 Grade B piping; closed-cell elastomeric insulation ASTM C534 19mm min; PICV balancing valves)
- "4.0" Installation Requirements (pipe slope for condensate: 1:100 minimum; pipe insulation to extend to FCU coil connection; FCU mounting height per ASHRAE 62.1 effective air distribution; electrical connection per PEC 2017 Article 4; CHW velocity 0.6-2.5 m/s in branches)
- "5.0" Testing and Commissioning (hydrostatic test at 1.5x working pressure for 1 hour minimum; flush CHW piping before FCU connection; balance CHW flow at each FCU via PICV per ASHRAE commissioning guidelines; verify FCU cooling capacity at design CHW flow; TAB report required)
- "6.0" Submittals and Documentation (manufacturer FCU product data sheets; ASTM A53 material certificate for CHW piping; hydrostatic test record; TAB report within 10% of design airflows; as-built drawings; O&M manuals and spare parts list; PRC-licensed ME signature on final documents)

Each content field must be a full professional paragraph starting with "The Contractor shall...". Reference specific standards and the project parameters (${totalDesKW}kW, ${totalUnits} FCUs, ${mainNps}mm NPS main, ${pipeSys}).

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── HVAC: Expansion Tank Sizing BOM + SOW Agent ─────────────────────────────

async function expansionTankBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {

  const project    = inputs.project_name      || "Expansion Tank Sizing Project";
  const sysType    = String(inputs.system_type    || "Chilled Water");
  const sysVol     = Number(results.system_volume_L || inputs.system_volume_L || 0).toFixed(0);
  const fillT      = Number(inputs.fill_temp_c    || 20).toFixed(0);
  const maxT       = Number(inputs.max_temp_c     || 18).toFixed(0);
  const head       = Number(inputs.static_head_m  || 10).toFixed(1);
  const pMax       = Number(inputs.max_pressure_kpa_g || 400).toFixed(0);
  const tankL      = results.selected_tank_L  ?? "—";
  const reqL       = Number(results.required_volume_L || 0).toFixed(1);
  const alpha      = results.acceptance_factor ?? "—";
  const precharge  = results.precharge_kpa_g  ?? "—";
  const fillP      = results.fill_pressure_kpa_g ?? "—";

  const prompt = `You are a senior Mechanical/HVAC engineer in the Philippines preparing a Bill of Materials (BOM) and Scope of Works (SOW) for the installation of a pre-pressurised bladder expansion tank on a closed hydronic loop per ASHRAE 2023 Handbook HVAC Systems and Equipment, ASME BPVC Section VIII, and PSME Code.

Project: ${project}
System type: ${sysType}
System water volume: ${sysVol} L
Fill temperature: ${fillT}°C | Maximum operating temperature: ${maxT}°C
Static head: ${head} m | Maximum system pressure: ${pMax} kPa g
Pre-charge pressure: ${precharge} kPa g | Fill pressure: ${fillP} kPa g
Acceptance factor (α): ${alpha} (ASHRAE minimum: 0.25)
Required acceptance volume: ${reqL} L → Selected tank: ${tankL} L bladder/diaphragm

Generate a JSON object with exactly two keys:

"bom_items": array of 10 objects, each with:
  { "description": string, "specification": string, "unit": string, "qty": number, "remarks": string }

BOM items must cover:
1. Bladder Expansion Tank: pre-pressurised, ASME VIII-listed, ${tankL}L, EPDM bladder, rated for ${pMax} kPa g MAWP: qty: 1 unit
2. Tank Isolation Valve: full-bore ball valve, PN25, same pipe size as tank connection: qty: 1 pc
3. Pressure Gauge: 0-${Math.round(Number(pMax) * 1.5)} kPa range, glycerin-filled, 100mm dial, 1/2 inch BSP connection: qty: 1 pc
4. Tank Connection Pipe: Black Steel SCH40, ASTM A53 Grade B, sized to match tank port: qty: 1 lot
5. Pipe Insulation (tank connection): closed-cell elastomeric foam 19mm, ASTM C534: qty: 1 lot
6. System Fill / Make-up Water Connection: 1/2 inch make-up water solenoid valve with backflow preventer: qty: 1 set
7. Pressure Relief Valve: set to ${pMax} kPa g, ASME-stamped, bronze body: qty: 1 pc
8. Manual Drain Valve: 1/2 inch ball valve at tank drain port: qty: 1 pc
9. Air Separator: magnetic, inline, to remove dissolved gases before they accumulate in tank: qty: 1 unit
10. Pipe Hangers and Supports: per MSS SP-58, galvanised, for tank connection piping: qty: 1 lot

"sow_sections": array of 5 objects, each with:
  { "section_no": string, "title": string, "content": string }

SOW sections:
- "1.0" Scope of Works (supply, install, and commission ${tankL}L pre-pressurised EPDM bladder expansion tank on the ${sysType} closed hydronic loop, system volume ${sysVol}L, acceptance factor ${alpha})
- "2.0" Design Standards and References (ASHRAE 2023 Handbook HVAC Systems and Equipment Ch.12; ASME BPVC Section VIII Division 1; ASHRAE 90.1; PSME Code; ASTM A53 Grade B piping; ASTM C534 insulation)
- "3.0" Materials and Equipment (ASME VIII-listed bladder tank, EPDM bladder rated min ${pMax} kPa MAWP; PN25 full-bore isolation valve; glycerin-filled pressure gauge; ASTM A53 Grade B SCH40 connection piping; closed-cell elastomeric insulation ASTM C534 19mm minimum)
- "4.0" Installation Requirements (locate tank on suction side of primary pump at point of no pressure change; set factory pre-charge to ${precharge} kPa g with system depressurised; fill system to ${fillP} kPa g before start-up; install with tank neck up for top-mounted connections; provide access for periodic inspection per ASME VIII)
- "5.0" Testing and Commissioning (verify pre-charge pressure matches factory setting ${precharge} kPa g; system pressure test at 1.25x MAWP = ${Math.round(Number(pMax)*1.25)} kPa for 1 hour; confirm acceptance factor min 0.25 after commissioning per ASHRAE; verify pressure relief valve opens at ${pMax} kPa g; submit commissioning report with pressure readings and acceptance factor calculation; PRC-licensed Mechanical Engineer to sign and seal)

Each content field must be a full professional paragraph starting with "The Contractor shall...". Reference specific standards and actual project parameters (${tankL}L tank, acceptance factor ${alpha}, ${sysType}).

Return ONLY the JSON object. No markdown. No explanation. No code fences.`;

  const raw    = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return {
    bom_items:    parsed.bom_items    || [],
    sow_sections: parsed.sow_sections || [],
  };
}

// ─── Machine Design: Shaft Design BOM + SOW Agent ────────────────────────────

async function shaftDesignBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {
  const project   = inputs.project_name  || "Shaft Design Project";
  const powerKW   = Number(inputs.power_kW    || 0).toFixed(1);
  const speedRPM  = Number(inputs.shaft_rpm || inputs.speed_rpm || 0);
  const material  = String(inputs.material    || "AISI 1045");
  const dMin      = Number(results.d_min_mm   || 0).toFixed(1);
  const dStd      = Number(results.d_standard_mm || 0);
  const dUsed     = Number(results.d_used_mm  || dStd);
  const nfGood    = Number(results.nf_goodman || 0).toFixed(2);
  const nyYld     = Number(results.ny_yield   || 0).toFixed(2);
  const critRPM   = Number(results.critical_speed_rpm || 0);
  const keyW      = Number(results.key_width_mm  || 0);
  const keyH      = Number(results.key_height_mm || 0);
  const keyL      = Number(results.key_length_mm || (1.5 * Number(dUsed))).toFixed(0);
  const nKey      = Number(results.n_key || 0).toFixed(2);
  const keyOk     = Boolean(results.key_ok ?? (Number(nKey) >= 1.5));
  const torque    = Number(results.torque_Nm || 0).toFixed(1);
  const twistDPM  = Number(results.twist_deg_per_m || 0);
  const twistOk   = Boolean(results.twist_ok ?? (twistDPM <= 1.0 && twistDPM > 0));
  const dTwistReq = Number(results.d_twist_required_mm || 0).toFixed(0);
  const dTwistStd = Number(results.d_twist_std_mm || dUsed);
  // Governing diameter: max of strength minimum and twist minimum
  const dGoverning = Math.max(Number(dUsed), twistOk ? 0 : Number(dTwistStd));
  const twistNote = twistOk
    ? `within 1 deg/m limit`
    : `exceeds 1 deg/m limit by ${(twistDPM / 1.0).toFixed(1)}x; UPSIZED diameter to ${dTwistStd} mm to satisfy ASME B106.1M angle-of-twist limit (required d >= ${dTwistReq} mm)`;
  const keyNote = keyOk
    ? `n_key=${nKey} (meets 1.5 minimum per ASME B17.1)`
    : `n_key=${nKey} BELOW 1.5 minimum per ASME B17.1: increase key length beyond ${keyL} mm or upsize shaft`;

  // ASCII-only directive: Groq output strips Unicode (degree, multiplication, sub/superscript)
  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters such as multiplication sign x, degree symbol, em-dash, en-dash, sub/superscripts, Greek letters, or middle-dot. Use "x" for multiplication, "deg" for degree, "phi" or "dia" for diameter, "Nm" or "N.m" for newton-meters, "MPa" for megapascals, "/" for fractions.`;

  const prompt = `You are a senior Mechanical Engineer in the Philippines preparing a Bill of Materials (BOM) and Scope of Works (SOW) for a power transmission shaft per ASME B106.1M, ASME B17.1, Shigley's Mechanical Engineering Design (10th Ed.), and PSME Code.

${asciiDirective}

Project: ${project}
Power transmitted: ${powerKW} kW at ${speedRPM} RPM
Torque: ${torque} Nm
Material: ${material}
Strength-only minimum diameter (DE-Goodman): ${dMin} mm -> Strength-selected standard: ${dUsed} mm
Goodman fatigue safety factor nf: ${nfGood}; Yield safety factor ny: ${nyYld}
Critical speed: ${critRPM.toLocaleString()} RPM (operating speed must remain below 75% or above 125%)
Angle of twist: ${twistDPM.toFixed(2)} deg/m (${twistNote})
GOVERNING SHAFT DIAMETER (use this for Item 1 and all SOW references): ${dGoverning} mm
Key (ASME B17.1, square): ${keyW} x ${keyH} mm, length ${keyL} mm; ${keyNote}

Generate a JSON object with exactly two keys:

"bom_items": array of 10 objects with { "description", "specification", "unit", "qty", "remarks" }

Per-item EXACT structure with description="short item name only" and specification="full standard + dimensions + grade":
(1) description="Shaft Stock", specification="${material} cold-drawn round bar, ${dGoverning} mm dia x length per drawing, ASTM A108 or DIN 1652, mill certificate Sut not less than ${Number(results.Sut_MPa || 570)} MPa", qty=1, unit="length"
(2) description="Parallel Key", specification="ASME B17.1 square key, ${keyW} mm width x ${keyH} mm height x ${keyL} mm length, AISI 1045 cold-drawn or carburized C1018, surface hardness HRC 45-50", qty=1, unit="piece"
(3) description="Flexible Shaft Coupling", specification="elastomeric jaw or disc-type coupling, bore ${dGoverning} mm finished, rated torque not less than ${(Number(torque) * 1.5).toFixed(0)} Nm (1.5x service factor), AGMA 9002 keyway tolerance", qty=2, unit="set"
(4) description="Deep-Groove Ball Bearing", specification="single-row deep-groove ball bearing, bore ${dGoverning} mm (series 60xx or 62xx selected per radial load), C1 clearance, ABEC-1 tolerance, ISO 281", qty=2, unit="piece"
(5) description="Bearing Housing", specification="cast-iron pillow-block or flange housing per ISO 113, bore matched to ${dGoverning} mm bearing OD, two grease nipples (M6 x 1), powder-coated finish", qty=2, unit="piece"
(6) description="Shaft Seal", specification="rotary lip seal per ISO 6194, NBR (nitrile) for oil environment or FKM (Viton) for high-temp, ${dGoverning} mm shaft dia, double lip with garter spring", qty=2, unit="piece"
(7) description="Locking Device", specification="hex locknut KM-series + tab lockwasher MB-series per DIN 981/5406, sized for ${dGoverning} mm bearing journal", qty=2, unit="set"
(8) description="Keyway Milling Cutter Set", specification="HSS-Co5 staggered-tooth side-and-face cutters, ${keyW} mm width, dia 50-100 mm with 22 mm bore, ANSI/ASME B94.19", qty=1, unit="set"
(9) description="Surface Treatment", specification="manganese phosphate per MIL-DTL-16232 Type M Class 4 or black oxide per MIL-DTL-13924 Class 1, 5-15 micron coating thickness for corrosion resistance", qty=1, unit="lot"
(10) description="Shaft Alignment Tool", specification="dial indicator (0.01 mm resolution, 10 mm travel) with magnetic base + laser shaft alignment kit (rim-and-face method), per ISO 10816-3 commissioning requirements", qty=1, unit="set"

CRITICAL: Every "specification" field MUST be fully populated, never empty or just the item name. All specs MUST cite the actual numeric values shown above (${dGoverning} mm, ${torque} Nm, ${keyW} x ${keyH} x ${keyL} mm, etc.).

"sow_sections": array of 5 objects with { "section_no", "title", "content" }
Section 1.0 Scope: state the contractor shall design, fabricate, supply, and install a power transmission shaft transmitting ${powerKW} kW at ${speedRPM} RPM (torque ${torque} Nm), ${dGoverning} mm dia, ${material}, per ASME B106.1M Elliptic Criterion${twistOk ? '' : ` with the ${dGoverning} mm diameter selected to satisfy both DE-Goodman fatigue and 1 deg/m angle-of-twist limit`}. Reference governing safety factors: nf=${nfGood}, ny=${nyYld}, ${keyOk ? '' : 'and address the marginal n_key per Section 4 procedure'}.
Section 2.0 Standards: cite ASME B106.1M (Design of Transmission Shafting), ASME B17.1 (Keys and Keyseats), Shigley's MED 10th Ed. (DE-Goodman fatigue), ISO 286 (shaft and hub fits), ISO 6194 (rotary lip seals), ISO 10816-3 (vibration severity zones), and PSME Code.
Section 3.0 Materials: specify ${material} cold-drawn round bar (Sut not less than ${Number(results.Sut_MPa || 570)} MPa, Sy not less than ${Number(results.Sy_MPa || 310)} MPa per mill certificate), ASTM A108 grade. Reference BOM Items 1-10 for full materials list. ${keyOk ? '' : `Note: increase key length beyond ${keyL} mm or specify higher-grade key (AISI 4140 Q&T) to bring n_key to or above 1.5.`}
Section 4.0 Procedure: machine ${dGoverning} mm shaft to bearing-seat tolerance h6 (ISO 286), coupling-fit tolerance k6, keyway tolerance JS9 per ASME B17.1. Surface roughness Ra not more than 1.6 micron at journals, Ra not more than 3.2 micron elsewhere. Mount couplings using induction heating to 80-100 deg C; verify shaft alignment within 0.05 mm TIR using dial indicator (BOM Item 10). Install keys with ${keyOk ? `verified key length ${keyL} mm minimum` : `INCREASED key length above ${keyL} mm to address marginal n_key=${nKey}`}.
Section 5.0 Inspection and Commissioning: perform vibration check per ISO 10816-3 (Zone B not more than 4.5 mm/s rms) at 50%, 75%, and 100% load after 4-hour run-in. Verify operating speed remains below 75% of critical (${critRPM.toLocaleString()} RPM) or above 125% if running supercritical. Record bearing temperature (not more than 70 deg C above ambient) and shaft TIR runout. Submit commissioning report with signed mill certificates and inspection logs to the Engineer for approval before handover.

Each "content" field MUST start with "The Contractor shall..." and use ASCII text only. Return ONLY the JSON object. No markdown, no preamble.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Machine Design: Gear / Belt Drive BOM + SOW Agent ───────────────────────

async function gearBeltDriveBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {
  const project    = inputs.project_name  || "Drive Design Project";
  const driveType  = String(inputs.drive_type || results.drive_type || "Gear Drive");
  const powerKW    = Number(inputs.power_kW    || 0).toFixed(1);
  const nDriver    = Number(inputs.driver_rpm || inputs.n_driver_rpm || 0);
  const nDriven    = Number(inputs.driven_rpm || inputs.n_driven_rpm || 0);
  const ratio      = Number(results.overall_ratio || results.speed_ratio || 0).toFixed(3);
  const nBelts     = Number(results.n_belts || 0);
  const section    = String(results.section || inputs.belt_section || "—");
  const beltDesig  = String(results.belt_designation || section);
  const beltL      = Number(results.belt_length_mm || 0);
  const dSmall     = Number(results.d_small_mm || inputs.driver_dia_mm || 0);
  const dLarge     = Number(results.d_large_mm || results.driven_dia_mm || 0);
  const module     = Number(results.module_mm || inputs.module_mm || 0);
  const chainNo    = String(results.chain_number || "—");

  const isBelt  = driveType.includes('Belt');
  const isGear  = driveType.includes('Gear');
  const isChain = driveType.includes('Chain');

  // ASCII-only directive: Groq output strips Unicode (degree, multiplication, sub/superscript)
  // so all spec strings must use plain ASCII (deg, x, ^, /, mm, kW, etc.)
  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters such as degree symbol, multiplication sign x, subscripts/superscripts, em-dash, en-dash, or Greek letters. Use "deg" not the degree symbol, "x" not the multiplication sign, "Ohm" not the Greek letter, "/" for fractions. Sheave diameters use "Phi" or "dia" prefix (e.g., "dia 125mm" or "Phi 125mm"), NOT the diameter symbol.`;

  const driveStandards = isBelt
    ? 'RMA IP-20 (Classical V-Belt Drives) / ASME B17.1 (Keys and Keyseats) / AGMA 9002 (Bores and Keyways for Flexible Couplings)'
    : isGear
    ? 'AGMA 2001-D04 (Bending and Pitting Resistance) / ASME B17.1 (Keys and Keyseats)'
    : 'ANSI B29.1 (Roller Chain) / ASME B17.1 (Keys and Keyseats)';

  const driveItemsBlock = isBelt
    ? `Items must be V-Belt-specific: (1) Matched V-Belt set (Section ${section}, designation ${beltDesig}, ${nBelts} belts, ${beltL}mm pitch length), (2) Driver Sheave (dia ${dSmall}mm pitch dia, Section ${section}, taper-lock bore for ${nDriver} RPM driver), (3) Driven Sheave (dia ${dLarge}mm pitch dia, Section ${section}, taper-lock bore for ${nDriven} RPM driven shaft), (4) Taper-Lock Bushings (qty 2, standard size 1610/2012/2517 selected per shaft dia), (5) Sheave Mounting Keys (parallel keys per ASME B17.1, qty 2, sized per shaft dia), (6) Tension Idler Pulley (Section ${section}, spring-loaded automatic tensioner OR fixed-base manual), (7) Belt Guard (per OSHA 1910.219 / DOLE D.O.13-1998, 16 ga galvanized sheet metal, painted yellow with black caution stripes), (8) Motor Sliding Base / Tensioning Rails (cast iron or fabricated steel, slot length min 1.5 x belt-length take-up), (9) Mounting Hardware (Grade 8.8 bolts/nuts/washers, anti-vibration washers), (10) Alignment Tools (laser sheave alignment kit OR straight-edge with feeler gauge). DO NOT include shaft couplings: V-belts ARE the coupling between driver and driven equipment.`
    : isGear
    ? `Items must be Gear-Drive-specific: (1) Pinion gear (module ${module}mm, hardened steel), (2) Driven gear (module ${module}mm), (3) Gearbox housing (cast iron or fabricated steel), (4) Shaft coupling (flexible coupling for input/output shafts), (5) Bearings (deep-groove ball or tapered roller per ISO 281), (6) Oil seals (lip seal per ISO 6194), (7) Lubricant (ISO VG-220 or VG-320 gear oil), (8) Mounting bolts (Grade 8.8), (9) Alignment tools, (10) Vibration-damping pads.`
    : `Items must be Chain-Drive-specific: (1) Roller chain (ANSI No.${chainNo}), (2) Driver sprocket, (3) Driven sprocket, (4) Chain tensioner (spring-loaded), (5) Chain guard (per OSHA 1910.219), (6) Sprocket mounting keys (ASME B17.1), (7) Lubricator (drip or splash bath), (8) Chain breaker tool, (9) Mounting hardware (Grade 8.8), (10) Alignment tools.`;

  const driveSummary = isBelt
    ? `Belt section: ${section} (designation ${beltDesig}), No. of belts: ${nBelts}, Belt pitch length: ${beltL}mm, Driver sheave: dia ${dSmall}mm, Driven sheave: dia ${dLarge}mm`
    : isGear
    ? `Module: ${module}mm`
    : `Chain No.: ${chainNo}`;

  const prompt = `You are a senior Mechanical Engineer in the Philippines preparing a BOM and SOW for a ${driveType} per ${driveStandards} and PSME Code.

${asciiDirective}

Project: ${project}
Drive type: ${driveType}
Power: ${powerKW} kW
Driver: ${nDriver} RPM -> Driven: ${nDriven} RPM (ratio ${ratio}:1)
${driveSummary}

Generate a JSON object with exactly two keys:

"bom_items": array of 10 objects with { "description", "specification", "unit", "qty", "remarks" }
${driveItemsBlock}
Each "specification" field MUST include the actual numeric values from the design summary above (sheave dia, belt length, RPM, section, etc.).

"sow_sections": array of 5 objects with { "section_no", "title", "content" }
Sections: 1.0 Scope, 2.0 Standards (${driveStandards}, PSME Code, OSHA 1910.219 for guards), 3.0 Materials, 4.0 Installation (${isBelt ? 'sheave alignment within 0.5 deg parallelism, belt tension per RMA IP-20 force-deflection method, re-tension after 4-8 hours run-in' : isGear ? 'gear backlash 0.05-0.15mm, oil fill to sight glass, alignment within 0.05mm TIR' : 'chain tension 2-4% of slack-side span sag, lubrication every 8 hours'}), 5.0 Testing and Commissioning (run-in procedure, vibration check per ISO 10816-3 Zone B max 4.5 mm/s, temperature monitoring, no-load then load test).

Content fields must start "The Contractor shall..." and reference the specific ${driveType} parameters. Return ONLY the JSON. No markdown.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Machine Design: Bearing Life BOM + SOW Agent ────────────────────────────

async function bearingLifeBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {
  const project       = inputs.project_name   || "Bearing Selection Project";
  const bearingType   = String(inputs.bearing_type || "Ball");
  const bearingNo     = String(inputs.bearing_no   || "to be selected from manufacturer catalog");
  const speedRPM      = Number(inputs.speed_rpm    || 0);
  // Adjusted life is the actual operational life (a1 applied); prefer it over basic
  const L10h          = Number(results.L10h_adj || results.L10h || results.L10_hours || 0).toFixed(0);
  const L10hBasic     = Number(results.L10h || 0).toFixed(0);
  const L10m          = Number(results.L10_Mrev || results.L10_million_revs || 0).toFixed(2);
  const cRating       = Number(inputs.C_kN         || 0).toFixed(1);
  const cRequired     = Number(results.C_required_kN || 0).toFixed(1);
  const FrkN          = Number(inputs.Fr_kN || 0).toFixed(1);
  const FakN          = Number(inputs.Fa_kN || 0).toFixed(1);
  const PkN           = Number(results.P_kN || 0).toFixed(2);
  const requiredLifeH = Number(inputs.required_life_h || 25000);
  const reliabilityPct = Number(inputs.reliability_pct || 90);
  const lifeCheck     = String(results.life_check || '');
  const adequate      = results.bearing_adequate ?? !lifeCheck.toUpperCase().includes('FAIL');
  const lifeStatus    = adequate ? 'PASS' : 'FAIL';

  // ASCII-only directive: Groq output strips Unicode (degree, multiplication, sub/superscript).
  // All spec strings must use plain ASCII.
  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters (degree symbol, multiplication sign, subscripts/superscripts, em-dash, en-dash, Greek letters). Use "deg" not the degree symbol, "x" not the multiplication sign, "/" for fractions, "+/-" not the plus-minus symbol.`;

  // FAIL-state guidance: prompt must call for upgraded bearing meeting required_life_h
  const cSpecForBOM = adequate
    ? `dynamic load rating C minimum ${cRating} kN (existing rating meets ${requiredLifeH.toLocaleString()} h target at ${reliabilityPct}% reliability)`
    : `UPGRADED dynamic load rating C minimum ${cRequired} kN (existing C=${cRating} kN gives only ${L10h} h vs ${requiredLifeH.toLocaleString()} h target — bearing must be re-selected)`;

  const scopeForSow = adequate
    ? `supply and install ${bearingType} bearings per ISO 281 with verified L10h_adj of ${L10h} hours (PASS, target ${requiredLifeH.toLocaleString()} hours)`
    : `supply REPLACEMENT ${bearingType} bearings with C minimum ${cRequired} kN to meet required L10h target of ${requiredLifeH.toLocaleString()} hours; the originally specified C=${cRating} kN bearing is undersized (yields only ${L10h} h)`;

  const materialsForSow = adequate
    ? `select bearing with dynamic load rating C minimum ${cRating} kN, grade NLGI 2 lithium-complex grease suitable for ${speedRPM} RPM operation`
    : `select REPLACEMENT bearing with dynamic load rating C minimum ${cRequired} kN (the original C=${cRating} kN bearing is INADEQUATE for ${requiredLifeH.toLocaleString()} h target life), grade NLGI 2 lithium-complex grease suitable for ${speedRPM} RPM operation`;

  const prompt = `You are a senior Mechanical Engineer in the Philippines preparing a BOM and SOW for bearing selection and installation per ISO 281, ISO 15243 (failure modes), and SKF/FAG application guidelines.

${asciiDirective}

Project: ${project}
Bearing type: ${bearingType}
Reference bearing No.: ${bearingNo}
Operating speed: ${speedRPM} RPM
Loads: Fr=${FrkN} kN, Fa=${FakN} kN, equivalent P=${PkN} kN
Existing C: ${cRating} kN
Required life: ${requiredLifeH.toLocaleString()} hours at ${reliabilityPct}% reliability
Calculated L10h_adj: ${L10h} hours (basic L10h=${L10hBasic} hours, ${L10m} million rev)
Result: ${lifeStatus}${adequate ? '' : ` — minimum C required = ${cRequired} kN`}

Generate a JSON object with exactly two keys:

"bom_items": array of 10 objects, each with EXACTLY this structure:
{
  "description": "short item name only (e.g. 'Bearing', 'Bearing housing', 'Grease') — NO standards or specs in this field",
  "specification": "FULL specification string with standard, type, dimensions, ratings — this field MUST be populated, never empty",
  "unit": "pc / set / kg / etc.",
  "qty": number,
  "remarks": "context note referencing the bearing parameters"
}

REQUIRED ITEMS (always populate the "specification" field with the parenthesized detail):
1. description="Bearing", specification="ISO 281, type ${bearingType}, No. ${bearingNo}, ${cSpecForBOM}", unit="pc", qty=1
2. description="Bearing housing", specification="split or solid pillow block per shaft diameter, cast iron GG-25 or fabricated steel, with grease fitting", unit="pc", qty=1
3. description="Shaft seal", specification="contact lip seal (e.g. SKF CR Wave) or V-ring seal, NBR rubber, suitable for ${speedRPM} RPM and ambient -20 to +100 deg C", unit="pc", qty=2
4. description="Locking device", specification="ISO 2982 KM-series locknut + MB-series tab washer (or equivalent SKF), sized per shaft thread", unit="set", qty=1
5. description="Grease", specification="NLGI Grade 2 lithium-complex base, dropping point not less than 180 deg C, EP additive, suitable for ${speedRPM} RPM continuous operation", unit="kg", qty=0.5
6. description="Grease nipple", specification="DIN 71412 type A (M6 or M8 thread, straight), zinc-plated steel", unit="pc", qty=2
7. description="Bearing puller set", specification="2-jaw or 3-jaw mechanical puller, capacity range matching bearing OD, with case", unit="set", qty=1
8. description="Induction heater", specification="bearing-mount induction heater, max temperature 110 deg C, with thermocouple and demagnetization cycle, suitable for bearing OD up to 200mm", unit="pc", qty=1
9. description="Alignment tools", specification="laser shaft alignment kit OR dial indicator with magnetic base, accuracy 0.01mm", unit="set", qty=1
10. description="Temperature monitoring", specification="infrared thermometer (range -30 to +500 deg C, accuracy +/-2 deg C) OR PT100 RTD probe with transmitter for permanent install", unit="pc", qty=1

CRITICAL: Every "specification" field above MUST be filled in the JSON output. Do not leave any specification field empty or null. Do not put the standards/dimensions into the description field.

"sow_sections": array of 5 objects with { "section_no", "title", "content" }
Section content fields must START with "The Contractor shall..." and use these exact mappings:
1.0 Scope: ${scopeForSow}.
2.0 Standards: ISO 281:2007 (Rolling bearings dynamic ratings and rating life), ISO 76 (static load ratings), ISO 15243 (failure mode classification), SKF General Catalog or equivalent manufacturer manual, PSME Code.
3.0 Materials: ${materialsForSow}.
4.0 Installation: mount bearing using induction heater to 80-100 deg C (do NOT exceed 120 deg C), verify shaft and housing fits per ISO 286 tolerance class (typically k5/k6 shaft, H7/H8 housing), install seals before bearing engagement, fill grease to 30-50 percent of bearing free volume.
5.0 Monitoring: establish initial grease fill quantity per SKF General Catalog / DIN 51825 lubrication guide, set re-lubrication interval based on speed factor (n*dm) and operating temperature per SKF Catalog re-lubrication chart, take vibration baseline within first 100 operating hours per ISO 10816-3, monitor bearing temperature and inspect for ISO 15243 failure modes (flaking, smearing, corrosion) at scheduled PM intervals.

Return ONLY the JSON. No markdown.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Machine Design: Bolt Torque BOM + SOW Agent ─────────────────────────────

async function boltTorqueBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {
  const project       = inputs.project_name  || "Bolted Joint Project";
  const boltSize      = String(inputs.bolt_size  || "M16");
  const grade         = String(inputs.bolt_grade || "8.8");
  const nBolts        = Number(inputs.n_bolts    || 8);
  const torqueNm      = Number(results.torque_Nm || 0).toFixed(1);
  // Calc engine returns Fi_kN (target preload). Older field preload_kN is preserved as fallback.
  const preloadkN     = Number(results.Fi_kN || results.preload_kN || 0).toFixed(2);
  const torque30pct   = Number(results.torque_30pct || 0).toFixed(1);
  const torque70pct   = Number(results.torque_70pct || 0).toFixed(1);
  const FpkN          = Number(results.Fp_kN || 0).toFixed(2);
  const SpMPa         = Number(results.Sp_MPa || 0).toFixed(0);
  const sigmaMPa      = Number(results.sigma_MPa || 0).toFixed(1);
  const stressCheck   = String(results.stress_check || 'PASS');
  const totalClampkN  = Number(results.total_clamp_kN || 0).toFixed(1);
  const separationSF  = results.separation_sf == null ? 'n/a' : Number(results.separation_sf).toFixed(2);
  const jointCheck    = String(results.joint_check || 'PASS');
  const extLoadkN     = Number(results.ext_load_kN ?? inputs.ext_load_kN ?? 0).toFixed(1);
  const nBoltsMin     = Number(results.n_bolts_min || 1);
  const preloadPct    = Number(results.preload_pct ?? inputs.preload_pct ?? 75);
  const nutFactor     = Number(results.nut_factor ?? inputs.nut_factor ?? 0.20);
  const nutCondition  = String(results.nut_condition || 'As-received (dry)');
  const dMM           = Number(results.d_mm || 16);
  const wrenchMax     = Math.ceil(Number(torqueNm) * 1.2);

  // ASCII-only directive: Groq strips Unicode (degree, multiplication, en/em-dash, middle-dot,
  // sub/superscripts, Greek). All output spec strings must be plain ASCII.
  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters (degree symbol, multiplication sign, middle-dot, em-dash, en-dash, subscripts/superscripts, Greek letters). Use "Nm" not "N.m" with the middle-dot, "deg" not the degree symbol, "x" not the multiplication sign, "/" or " to " for ranges (NOT "-" hyphen-as-range or en-dash).`;

  const prompt = `You are a senior Mechanical Engineer in the Philippines preparing a BOM and SOW for a bolted joint assembly per ISO 898-1, VDI 2230, and ASME PCC-1.

${asciiDirective}

Project: ${project}
Bolt size: ${boltSize} Grade ${grade} (nominal dia ${dMM}mm)
No. of bolts: ${nBolts} (minimum required for SF >= 1.5: ${nBoltsMin})
Proof strength Sp: ${SpMPa} MPa
Proof load Fp: ${FpkN} kN
Target preload Fi: ${preloadkN} kN per bolt (${preloadPct}% of Fp)
Bolt stress sigma: ${sigmaMPa} MPa (Stress check: ${stressCheck} vs Sp ${SpMPa} MPa)
Tightening torque T: ${torqueNm} Nm (3-pass schedule: ${torque30pct} Nm at 30%, ${torque70pct} Nm at 70%, ${torqueNm} Nm at 100%)
Nut factor K: ${nutFactor} (${nutCondition})
External load: ${extLoadkN} kN, Total clamp: ${totalClampkN} kN, Separation SF: ${separationSF} (${jointCheck})

Generate a JSON object with exactly two keys:

"bom_items": array of 10 objects, each with EXACTLY this structure:
{
  "description": "short item name only (e.g. 'Hex bolt', 'Hex nut') - NO standards/grades/dimensions in this field",
  "specification": "FULL specification string with standard, grade, dimensions - this field MUST be populated, never empty",
  "unit": "pc / set / kg / etc.",
  "qty": number,
  "remarks": "context note tying back to this joint design"
}

REQUIRED ITEMS (every "specification" field MUST be populated as shown):
1. description="Hex bolt", specification="${boltSize} Grade ${grade} per ISO 898-1, hex head per ISO 4014, length per joint stack-up (thread engagement minimum 1.0d to 1.5d, i.e. ${dMM} to ${Math.round(dMM*1.5)}mm engaged), zinc-plated or hot-dip galvanized for outdoor", unit="pc", qty=${nBolts}
2. description="Hex nut", specification="Grade 8 per ISO 898-2 (compatible with Grade ${grade} bolt), hex pattern per ISO 4032, same finish as bolt", unit="pc", qty=${nBolts}
3. description="Hardened flat washer", specification="ISO 7091 or DIN 125 hardened steel washer for ${boltSize}, OD per ISO 7091 Table 1, hardness 200-300 HV", unit="pc", qty=${nBolts*2}
4. description="Spring lock washer", specification="DIN 127B split spring washer for ${boltSize}, spring steel, hardness 41-51 HRC (use ONLY if joint subject to vibration; can be omitted with thread locker)", unit="pc", qty=${nBolts}
5. description="Anti-seize compound", specification="copper-based (Loctite LB 8008 or equivalent) for carbon-steel-on-carbon-steel; nickel-based (Loctite LB 8150) for stainless or high-temperature joints (>150 deg C)", unit="kg", qty=0.5
6. description="Thread locker", specification="Loctite 243 medium-strength removable (blue) for vibrating joints; Loctite 263 high-strength (red) for permanent joints; verify chemical compatibility with anti-seize", unit="pc", qty=1
7. description="Calibrated torque wrench", specification="click-type or digital torque wrench, range 0 to ${wrenchMax} Nm (covers ${torqueNm} Nm target with 20 percent margin), accuracy +/- 4 percent at 20 percent to 100 percent of full scale per ISO 6789-1", unit="pc", qty=1
8. description="Torque audit sticker + marker", specification="weather-proof tamper-evident torque-seal sticker (e.g. Torque Seal F-900 yellow) + permanent paint marker for rotation-indicator line across bolt head, nut, and joint flange", unit="set", qty=1
9. description="Torque wrench calibration certificate", specification="ISO 6789-1 / ISO 6789-2 calibration certificate with traceability to NIST or PTB primary standard, valid less than 12 months, attached to torque wrench at site", unit="pc", qty=1
10. description="Feeler gauge set", specification="0.05 to 1.0mm leaf set (10 to 13 leaves), hardened spring steel, for joint-gap verification per VDI 2230 (no detectable gap after final torque)", unit="set", qty=1

CRITICAL: Every "specification" field above MUST be filled in the JSON output. Do not leave any specification field empty or null. Do not put the standards/dimensions into the description field.

"sow_sections": array of 5 objects with { "section_no", "title", "content" }
Section content fields MUST start with "The Contractor shall..." and reference the specific values above.

1.0 Scope: supply, install, and pre-tension all ${nBolts} ${boltSize} Grade ${grade} bolts in this joint to a preload of ${preloadkN} kN per bolt (${preloadPct} percent of proof load) using a calibrated torque wrench at ${torqueNm} Nm tightening torque per ISO 898-1 / VDI 2230, and verify joint integrity to a minimum separation safety factor of 1.5 against the design external load of ${extLoadkN} kN.
2.0 Standards: ISO 898-1 (mechanical properties of carbon and alloy steel fasteners), ISO 898-2 (mechanical properties of nuts), VDI 2230 Part 1 (systematic calculation of high-duty bolted joints), ASME PCC-1 (pressure boundary flange joint assembly), AISC 360 Chapter J (steel structural connections), ISO 6789 (torque wrench calibration), and PSME Code.
3.0 Materials: supply ${boltSize} Grade ${grade} hex bolts per ISO 898-1, matching Grade 8 hex nuts per ISO 898-2, hardened flat washers per ISO 7091, anti-seize compound (copper or nickel base per joint material), thread locker (Loctite 243 or equivalent for vibrating joints), and a calibrated torque wrench with valid ISO 6789 certificate covering 0 to ${wrenchMax} Nm range.
4.0 Tightening Procedure: clean and inspect threads (reject damaged or corroded fasteners), apply anti-seize to bolt threads and underhead bearing surface only (NOT to thread locker if used), tighten in a star or cross pattern in 3 passes (Pass 1 at ${torque30pct} Nm = 30 percent, Pass 2 at ${torque70pct} Nm = 70 percent, Pass 3 at ${torqueNm} Nm = 100 percent), apply final torque slowly without overshoot, mark each bolt head and joint with paint marker for rotation reference.
5.0 Inspection and Re-check: verify torque wrench calibration certificate within 12 months of work date, confirm cross-pattern sequence and 3-pass schedule were followed (sign Quality Record), retorque all bolts after first thermal cycle or 24 hours of service for gasketed flanges (gasket creep relaxes preload by 10 to 20 percent), verify NO detectable joint gap with feeler gauge per VDI 2230, photograph final torque-seal markings and retain in QA file.

Return ONLY the JSON. No markdown.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Machine Design: Beam / Column Design BOM + SOW Agent ────────────────────

async function beamColumnBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {
  const project    = inputs.project_name   || "Structural Member Project";
  const memberType = String(inputs.member_type || results.member_type || "Steel Beam");
  const isSteel    = memberType.includes("Steel");
  const isBeam     = memberType.includes("Beam");
  const isColumn   = memberType.includes("Column");
  const span       = Number(inputs.span_m  || 0);
  const section    = String(results.section || inputs.section || "W310x45");
  const grade      = String(results.steel_grade || inputs.steel_grade || (isSteel ? "A36" : "f'c 28 MPa"));
  const fyMPa      = Number(results.Fy_MPa || (grade === "A36" ? 250 : grade.includes("A992") ? 345 : 250));
  const dcrM       = Number(results.DCR_moment  || 0).toFixed(3);
  const dcrV       = Number(results.DCR_shear   || 0).toFixed(3);
  const dcrA       = Number(results.DCR_axial   || 0).toFixed(3);
  const phiMpKNm   = Number(results.phi_Mp_kNm  || 0).toFixed(1);
  const phiVnKN    = Number(results.phi_Vn_kN   || 0).toFixed(1);
  const phiPnKN    = Number(results.phi_Pn_kN   || 0).toFixed(1);
  const defMM      = Number(results.deflection_mm || 0).toFixed(2);
  const defLim     = Number(results.deflection_limit_mm || (span * 1000 / 360)).toFixed(2);
  const wKnm       = Number(inputs.w_kNm || 0).toFixed(1);
  const muKnm      = Number(inputs.Mu_kNm || 0).toFixed(1);
  const vuKn       = Number(inputs.Vu_kN || 0).toFixed(1);
  const puKn       = Number(inputs.Pu_kN || 0).toFixed(1);
  const momentOk   = results.moment_ok !== false;
  const shearOk    = results.shear_ok  !== false;
  const axialOk    = results.axial_ok  !== false;
  const overallOk  = momentOk && shearOk && (isBeam || axialOk);

  // ── Steel-section physical metadata for accurate BOM quantities ─────────────
  // Section weight per metre (kg/m) parsed from designation suffix (e.g. W310x45 -> 45 kg/m).
  // Surface area per metre (m^2/m) approximated from W-section perimeter:
  // perimeter approx = 2*d + 4*bf - 2*tw (outer flange surfaces + web sides + flange tips).
  // Fallback to typical 1.2 m^2/m if section dims unavailable.
  const sectionKgMatch = section.match(/x(\d+)/i);
  const sectionKgM     = sectionKgMatch ? Number(sectionKgMatch[1]) : 45;
  const beamWeightKg   = Math.round(sectionKgM * span);
  // Typical W-section perimeters (m^2/m): W200~0.95, W310~1.20, W410~1.45, W530~1.70
  const sectionPerimMatch = section.match(/W(\d+)/i);
  const sectionDepthMm    = sectionPerimMatch ? Number(sectionPerimMatch[1]) : 310;
  const surfacePerMeter   = Math.round((0.0035 * sectionDepthMm + 0.10) * 100) / 100; // m^2/m linear approx
  const surfaceAreaM2     = Math.round(surfacePerMeter * span * 10) / 10;
  // Bolt size per beam depth: W200 -> M16, W310 -> M20, W410+ -> M24
  const boltSize = sectionDepthMm <= 250 ? "M16" : sectionDepthMm <= 360 ? "M20" : "M24";
  const boltGrip = sectionDepthMm <= 250 ? "60mm" : sectionDepthMm <= 360 ? "80mm" : "100mm";
  // Welding electrode budget: ~1.5% of section weight
  const electrodeKg       = Math.max(2, Math.round(beamWeightKg * 0.015 * 10) / 10);
  // Connection plate weight estimate: 2 end-plates @ 200x200x12mm A36
  const connPlateKg       = Math.round(2 * 0.2 * 0.2 * 0.012 * 7850 * 10) / 10;

  // ASCII-only directive: Groq strips Unicode (multiplication, sub/superscript, le/ge, em-dash)
  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters such as multiplication sign x, sub/superscripts, less-than-or-equal, greater-than-or-equal, em-dash, en-dash, Greek letters, or middle-dot. Use "x" for multiplication, "not more than" for less-than-or-equal, "not less than" for greater-than-or-equal, "kNm" or "kN.m" for kilonewton-meters, "L/360" or "L/500" for span ratios, "phi" for diameter prefix.`;

  // Steel-only items (RC variant uses different list — see else branch)
  // Branch: Beam vs Column to omit base plate / anchor bolts / grout for beams.
  const steelItemsBlock = isBeam
    ? `Steel BEAM specifically — DO NOT include base plates, anchor bolts, or grout (those apply only to columns).
Per-item EXACT structure with description="short item name only" and specification="full standard + dimensions + grade":
(1) description="Structural Steel Section", specification="${section} wide-flange section, ASTM ${grade} (Fy=${fyMPa} MPa, Fu=400 MPa min), mill-rolled per ASTM A6, length per drawing not less than ${span} m, section weight ${sectionKgM} kg/m, total weight ${beamWeightKg} kg", qty=${beamWeightKg}, unit="kg"
(2) description="End-Plate / Splice Plate", specification="ASTM A36 mild steel plate, 12mm thk x 200mm x 200mm both ends, factory-prepared bolt holes per AISC connection design", qty=${connPlateKg}, unit="kg"
(3) description="High-Strength Bolts", specification="${boltSize} ASTM A325 (Type 1) heavy hex structural bolts with grip length ${boltGrip}, hot-dip galvanized per ASTM F2329, supplied with hardened washers (F436) and heavy hex nuts (A563 Gr DH)", qty=8, unit="set", remarks="2 connections x 4 bolts each end"
(4) description="Welding Electrode", specification="E7018 low-hydrogen SMAW electrode per AWS A5.1, 3.2mm dia (1/8 inch), packaged in hermetically sealed cans, dry-store and re-bake per AWS D1.1 Annex N", qty=${electrodeKg}, unit="kg"
(5) description="Stiffener Plates", specification="ASTM A36 plate 8mm thk, web stiffeners under concentrated loads/bearing per AISC 360-22 Section J10 (omit if no concentrated loads)", qty=4, unit="kg", remarks="As required at bearing points"
(6) description="Shear Tab / Connection Angle", specification="ASTM A36 plate or angle L100x100x10, beam-to-girder shear connection per AISC 14th Ed Manual Part 10", qty=8, unit="kg", remarks="2 ends x estimate"
(7) description="Fireproofing", specification="cementitious spray-applied fireproofing (SFRM) per UL Design X-series for ${sectionDepthMm <= 310 ? '1-hour' : '2-hour'} fire rating, density not less than 240 kg/m3, thickness per UL listing (typical 25mm for 1hr, 38mm for 2hr), prime surface with compatible primer first", qty=${surfaceAreaM2}, unit="m2"
(8) description="Surface Primer", specification="zinc-rich epoxy primer (organic) per SSPC-Paint 20 Type II, 2-component, 75 micron DFT, applied to SSPC-SP6 commercial blast-cleaned surface", qty=${surfaceAreaM2}, unit="m2"
(9) description="Topcoat Paint", specification="alkyd enamel 2-coat system per SSPC-Paint Spec, total 50 micron DFT (25 micron per coat), color per architect schedule (typical safety yellow for exposed steel)", qty=${surfaceAreaM2}, unit="m2"
(10) description="Beam Camber (if specified)", specification="mill camber per AISC 360-22 Section M5: ${span >= 7.5 ? `not less than ${Math.round(span * 1000 / 1000)} mm at midspan (L/1000 typical for spans not less than 7.5 m)` : 'no camber required for spans less than 7.5 m'}", qty=1, unit="lot", remarks="${span >= 7.5 ? 'Required' : 'Not required for this span'}"`
    : `Steel COLUMN — include base plate, anchor bolts, grout, but no shear tabs or end plates (those apply to beams).
Per-item EXACT structure:
(1) description="Structural Steel Section", specification="${section} wide-flange column section, ASTM ${grade} (Fy=${fyMPa} MPa), height ${span} m, section weight ${sectionKgM} kg/m, total ${beamWeightKg} kg", qty=${beamWeightKg}, unit="kg"
(2) description="Base Plate", specification="ASTM A36 plate 25mm thk x 400mm x 400mm (sized per AISC Design Guide 1 for axial Pu=${puKn} kN), drilled for ${boltSize} anchor bolts at corners", qty=1, unit="piece"
(3) description="Anchor Bolts", specification="${boltSize} ASTM F1554 Grade 36 anchor rods, embedment 12 x dia (${boltSize.replace('M','')} x 12 = ${Number(boltSize.replace('M',''))*12} mm minimum) into concrete pier, with sleeve and template per OSHA 1926.755", qty=4, unit="set"
(4) description="Anchor Bolt Template", specification="2x4 lumber template OR steel jig holding anchor bolts in correct pattern during concrete pour, per OSHA 1926.755 four-bolt minimum", qty=1, unit="lot"
(5) description="Cap Plate", specification="ASTM A36 plate 12mm thk x column cross-section dimensions, top of column for beam-to-column connection", qty=1, unit="piece"
(6) description="Welding Electrode", specification="E7018 low-hydrogen SMAW per AWS A5.1, base-to-column and cap-to-column fillet welds per AWS D1.1", qty=${electrodeKg}, unit="kg"
(7) description="Fireproofing", specification="SFRM per UL Design X-series for ${sectionDepthMm <= 310 ? '2-hour' : '3-hour'} fire rating (column rating typically higher than beam), density not less than 240 kg/m3", qty=${surfaceAreaM2}, unit="m2"
(8) description="Surface Primer", specification="zinc-rich epoxy primer per SSPC-Paint 20 Type II, 75 micron DFT", qty=${surfaceAreaM2}, unit="m2"
(9) description="Topcoat Paint", specification="alkyd enamel 2-coat per SSPC, total 50 micron DFT", qty=${surfaceAreaM2}, unit="m2"
(10) description="Non-Shrink Grout", specification="non-shrink cementitious grout per ASTM C1107 Grade B, 50 MPa compressive strength at 28 days, applied between base plate and concrete pier 25 mm thk minimum", qty=2, unit="bag"`;

  // RC items branch (concrete beam or column)
  const rcItemsBlock = isBeam
    ? `Reinforced concrete BEAM — formwork-and-pour scope.
Per-item EXACT structure:
(1) description="Ready-Mix Concrete", specification="f'c=${results.fc_MPa || 28} MPa (${results.fc_MPa === 21 ? 'Class A' : 'Class AA'}) per ACI 318-19 / ASTM C94, slump 100 mm to 150 mm, max aggregate size 20 mm, with retarder if pour time not less than 90 minutes", qty=${Math.round((Number(inputs.b_mm || 300) * Number(inputs.h_mm || 500) * span * 1e-9) * 10) / 10}, unit="m3"
(2) description="Deformed Rebar (Main)", specification="${inputs.bar_dia_mm || 20}mm dia ASTM A615 ${inputs.rebar_grade || 'Grade 60'} (fy=${results.fy_MPa || 414} MPa), mill cert required, qty per drawing schedule", qty=${(inputs.n_bars || 4)}, unit="length"
(3) description="Stirrups / Shear Reinforcement", specification="${results.stirrup_dia_mm || 10}mm dia ASTM A615 Grade 40, U-shape stirrups at 150 mm OC for full beam length, 100 mm OC at supports per ACI 318-19 Sec 9.7", qty=${Math.ceil(span * 1000 / 150)}, unit="piece"
(4) description="Formwork Lumber", specification="2x4 SPF kiln-dried lumber for beam side and bottom forms, span sized per ACI 347R formwork pressure", qty=${Math.round(span * 4)}, unit="board-foot"
(5) description="Formwork Plywood", specification="19mm marine-grade plywood per PNS 196:2009, sealed and form-oiled before pour", qty=${Math.round((Number(inputs.b_mm || 300) + 2 * Number(inputs.h_mm || 500)) * span / 1000 * 10) / 10}, unit="m2"
(6) description="Form Release Agent", specification="non-staining bond breaker per ACI 347R, biodegradable type for tropical/marine application", qty=1, unit="liter", remarks="approx 0.05 L/m2 form area"
(7) description="Concrete Cover Spacers", specification="${results.cover_mm || 40}mm plastic concrete cover spacers (clip-on or pin-type), per ACI 318-19 Sec 20.6.1.3 minimum cover", qty=${Math.ceil(span * 4)}, unit="piece"
(8) description="Concrete Vibrator", specification="immersion poker vibrator 38 mm head, 8000 vpm minimum, per ACI 309R consolidation requirements", qty=1, unit="day", remarks="Rental"
(9) description="Curing Compound", specification="membrane curing compound per ASTM C309 Type 1-D Class B, white-pigmented for hot weather, applied within 1 hour of finishing", qty=1, unit="liter", remarks="approx 0.2 L/m2 surface"
(10) description="Concrete Cylinder Test Set", specification="6 cylinders 100x200mm per ASTM C31 / ASTM C39 (3 for 7-day, 3 for 28-day strength tests), accredited testing lab per DPWH-BRS", qty=1, unit="set"`
    : `Reinforced concrete COLUMN — vertical formwork and tied-bar scope.
Per-item EXACT structure:
(1) description="Ready-Mix Concrete", specification="f'c=${results.fc_MPa || 28} MPa Class AA per ACI 318-19 / ASTM C94, slump 75 mm to 125 mm, max aggregate 20 mm", qty=${Math.round((Number(inputs.b_mm || 300) * Number(inputs.h_mm || 300) * span * 1e-9) * 10) / 10}, unit="m3"
(2) description="Vertical Rebar", specification="${inputs.bar_dia_mm || 20}mm dia ASTM A615 ${inputs.rebar_grade || 'Grade 60'}, full column height plus development length per ACI 318-19 Ch 25", qty=${(inputs.n_bars || 6)}, unit="length"
(3) description="Lateral Ties", specification="${results.tie_dia_mm || 10}mm dia ASTM A615 ties, spacing not more than 16 x main bar dia or 48 x tie bar dia or column least dim, whichever smallest, per ACI 318-19 Sec 25.7.2", qty=${Math.ceil(span * 1000 / 250)}, unit="piece"
(4) description="Column Formwork", specification="19mm marine plywood with 2x4 SPF studs and steel column clamps at 600 mm vertical spacing", qty=${Math.round(2 * (Number(inputs.b_mm || 300) + Number(inputs.h_mm || 300)) * span / 1000 * 10) / 10}, unit="m2"
(5) description="Form Release Agent", specification="non-staining bond breaker per ACI 347R", qty=1, unit="liter"
(6) description="Cover Spacers", specification="${results.cover_mm || 40}mm plastic, per ACI 318-19 Sec 20.6.1.3", qty=${Math.ceil(span * 8)}, unit="piece"
(7) description="Anchor Dowels (to footing)", specification="${inputs.bar_dia_mm || 20}mm dia ASTM A615, embedded into footing per ACI 318-19 development-length requirements", qty=${(inputs.n_bars || 6)}, unit="piece"
(8) description="Concrete Vibrator", specification="immersion vibrator 25 mm head for column pour", qty=1, unit="day", remarks="Rental"
(9) description="Curing Compound", specification="membrane curing per ASTM C309 Type 1-D Class B", qty=1, unit="liter"
(10) description="Cylinder Test Set", specification="6 cylinders per ASTM C31, 7-day and 28-day strength tests", qty=1, unit="set"`;

  const itemsBlock = isSteel ? steelItemsBlock : rcItemsBlock;

  const sowMaterials = isSteel
    ? `specify ${section} wide-flange (ASTM ${grade}, Fy=${fyMPa} MPa, Fu=400 MPa, ductility class per ASTM A6), ASTM A325 high-strength bolts size ${boltSize}, AWS D1.1 E7018 electrodes, base plate ASTM A36, ASTM F1554 anchor bolts (columns only). Mill certificates and material test reports (MTR) required for the structural section`
    : `specify ready-mix concrete f'c=${results.fc_MPa || 28} MPa per ACI 318-19, ASTM A615 deformed rebar (${inputs.rebar_grade || 'Grade 60'}, fy=${results.fy_MPa || 414} MPa), 19mm marine-grade plywood formwork per PNS 196:2009, ${results.cover_mm || 40} mm minimum concrete cover per ACI 318-19 Sec 20.6.1.3`;

  const sowProcedure = isSteel
    ? `${isBeam ? `shop-fabricate the ${section} beam to AISC tolerances (camber per Section M5 if span not less than 7.5 m), perform full-penetration groove welds and fillet welds per AWS D1.1 with qualified WPS/PQR, deliver to site with shipping marks per drawing` : `field-erect the ${section} column plumb within L/500, install on grouted base plate (25 mm grout bed per AISC Design Guide 1), bolt up with ${boltSize} A325 bolts torqued per RCSC turn-of-nut method or DTI washer indicator`}. Field bolting per RCSC Specification, snug-tight installation followed by ${isBeam ? '1/3 turn (slip-critical: 1/2 turn for short bolts)' : 'turn-of-nut to 2/3 turn'}. Visual weld inspection (VT) by AWS-CWI for all welds; UT/RT for full-penetration welds per AWS D1.1 Table 6.7. Surface preparation SSPC-SP6 commercial blast, primer + topcoat per spec`
    : `cast in proper formwork with cover spacers placed every 600 mm along bars, place concrete in lifts not more than 1.5 m height with internal vibration, finish surface and apply curing compound within 1 hour of finishing, cure for not less than 7 days minimum. Stripping after 24 hours for sides, 7 days for soffit beams (longer for spans not less than 6 m per ACI 347R)`;

  const sowInspection = isSteel
    ? `perform 100% visual weld inspection by AWS-CWI per AWS D1.1 Table 6.1, ultrasonic testing on full-penetration welds per AWS D1.1 Sec 6.13, high-strength bolt installation verification (10% sample with calibrated wrench per RCSC Spec), final plumb check on columns L/500, beam camber verification (if specified) within plus or minus 25%, fireproofing thickness verification per UL listing tolerance. Submit weld inspection reports, bolt installation reports, and material test reports (MTR) to the Structural Engineer of Record (SER) for sign-off before proceeding`
    : `cast 6 concrete cylinders per pour for 7-day and 28-day compressive strength tests per ASTM C31/C39 at a DPWH-accredited lab, perform rebar placement inspection before pour (cover, spacing, splices per ACI 318-19), document slump test per ASTM C143 at delivery (target 100-150 mm beam, 75-125 mm column), and submit cylinder test reports to the SER. Reject any pour with cylinder strength less than 0.85 x f'c at 28 days`;

  const prompt = `You are a senior Structural / Civil Engineer in the Philippines preparing a Bill of Materials (BOM) and Scope of Works (SOW) for a ${memberType} per NSCP 2015 Vol.1 and ${isSteel ? 'AISC 360-22 LRFD' : 'ACI 318-19'}.

${asciiDirective}

Project: ${project}
Member: ${memberType} | Span: ${span.toFixed(1)} m
${isSteel
    ? `Section: ${section} | Grade: ${grade} (Fy=${fyMPa} MPa) | Section weight: ${sectionKgM} kg/m | Total weight: ${beamWeightKg} kg | Surface area for coatings: ${surfaceAreaM2} m2`
    : `Dimensions: ${inputs.b_mm}x${inputs.h_mm} mm | f'c: ${results.fc_MPa} MPa | fy: ${results.fy_MPa} MPa | As: ${results.As_mm2} mm2`}
${isBeam ? `Loads: w=${wKnm} kN/m UDL, Mu=${muKnm} kNm, Vu=${vuKn} kN | phiMp=${phiMpKNm} kNm DCR_M=${dcrM} (${momentOk ? 'PASS' : 'FAIL'}) | phiVn=${phiVnKN} kN DCR_V=${dcrV} (${shearOk ? 'PASS' : 'FAIL'}) | Deflection ${defMM} mm (limit L/360 = ${defLim} mm)`
          : `Axial: Pu=${puKn} kN | phiPn=${phiPnKN} kN DCR=${dcrA} (${axialOk ? 'PASS' : 'FAIL'})`}
Overall member status: ${overallOk ? 'ADEQUATE' : 'INADEQUATE — requires resizing'}
Bolt size selected by depth (${sectionDepthMm} mm): ${boltSize} with grip ${boltGrip}; estimated electrode budget ${electrodeKg} kg

Generate a JSON object with exactly two keys:

"bom_items": array of 10 objects with { "description", "specification", "unit", "qty", "remarks" }

${itemsBlock}

CRITICAL: Every "specification" field MUST be fully populated, never empty or just the item name. All quantities MUST come from the values supplied above (${beamWeightKg} kg, ${surfaceAreaM2} m2, ${electrodeKg} kg, etc.) — do not invent quantities.

"sow_sections": array of 5 objects with { "section_no", "title", "content" }

Section 1.0 Scope: state the contractor shall design, fabricate, supply, erect, and inspect a ${memberType} per NSCP 2015 Vol.1 and ${isSteel ? 'AISC 360-22 LRFD' : 'ACI 318-19'}, ${isBeam ? `${section} section spanning ${span.toFixed(1)} m, factored Mu=${muKnm} kNm and Vu=${vuKn} kN, deflection ${defMM} mm (limit L/360 = ${defLim} mm)` : `${section} section ${span.toFixed(1)} m tall, factored Pu=${puKn} kN`}. Member status ${overallOk ? 'verified ADEQUATE' : 'INADEQUATE — resize before fabrication'} per the design calculation (DCR_M=${dcrM}${isBeam ? `, DCR_V=${dcrV}` : `, DCR_A=${dcrA}`}).

Section 2.0 Standards: cite NSCP 2015 Vol.1 (governing), ${isSteel
  ? 'AISC 360-22 (steel design), AWS D1.1/D1.1M (welding), ASTM A6 (mill standards), ASTM A36/A992 (steel grades), ASTM A325/F3125 (high-strength bolts), ASTM F1554 (anchor rods), RCSC Specification (bolt installation), SSPC-SP6 / SSPC-Paint 20 (surface prep / primer)'
  : 'ACI 318-19 (concrete design), ASTM C94 (ready-mix), ASTM A615 (rebar), ACI 305R (hot-weather concreting), ACI 347R (formwork), ASTM C31 / C39 (cylinder tests), PNS 196:2009 (plywood formwork)'}, and DOLE D.O.13 (construction safety).

Section 3.0 Materials: ${sowMaterials}; reference BOM Items 1-10 for full procurement scope.

Section 4.0 Procedure: ${sowProcedure}.

Section 5.0 Inspection: ${sowInspection}.

Each "content" field MUST start with "The Contractor shall..." and use ASCII text only. Return ONLY the JSON. No markdown, no preamble.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Machine Design: Pressure Vessel BOM + SOW Agent ─────────────────────────

async function pressureVesselBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {
  const project   = inputs.project_name       || "Pressure Vessel Project";
  const pDesign   = Number(results.design_pressure_bar || 0).toFixed(1);
  const pTest     = Number(results.hydro_test_bar      || 0).toFixed(2);
  const mawp      = Number(results.mawp_bar            || 0).toFixed(2);
  const material  = String(results.material            || "SA-516 Gr.70");
  const sAllow    = Number(results.allowable_stress_MPa || 138);
  const jointEff  = Number(results.joint_efficiency || 1.0);
  const tShell    = Number(results.t_shell_actual_mm   || 0);
  const tHead     = Number(results.t_head_actual_mm    || 0);
  const ID        = Number(results.inner_diameter_mm   || 0);
  const OD        = Number(results.outer_diameter_mm   || 0).toFixed(0);
  const length    = Number(inputs.shell_length_mm      || 2000);
  const weightKg  = Number(results.weight_empty_kg     || 0).toFixed(0);
  const nozzles   = Number(results.n_nozzles           || 2);
  const nozzDia   = Number(results.nozzle_diameter_mm  || 100);
  const designTC  = Number(inputs.design_temperature_C || 150);
  const headType  = String(results.head_type || inputs.head_type || "Ellipsoidal (2:1)");
  const CA        = Number(results.corrosion_allowance_mm || 1.6);
  const isHotService = designTC >= 60;
  const isManholeReqd = (Math.PI * Math.pow(ID/2000, 2) * length / 1000) >= 1.0;  // m3 internal volume

  // Pressure gauge range (rounded to nearest 5 bar above 1.5 x MAWP per ASME B40.100)
  const gaugeMaxBar = Math.ceil(Number(mawp) * 1.5 / 5) * 5;
  // SRV capacity per UG-125: relieving capacity in kg/h for steam/air; size at MAWP
  const srvCapacityKgHr = Math.round(Number(mawp) * 50 * (ID / 100));  // empirical sizing
  // Vessel internal volume m3
  const volumeM3 = Math.round(Math.PI * Math.pow(ID/2000, 2) * length / 1000 * 100) / 100;
  // Shell plate dimensions: rolled from 1 plate sized to circumference x length + 50mm allowance
  const shellPlateLen  = Math.round(Math.PI * Number(OD) + 50);  // mm circumferential
  const shellPlateMass = Math.round(Number(OD) * length * tShell * 1e-9 * 7850 * Math.PI);  // kg approx
  // Head plate: ellipsoidal 2:1 stamped from disk OD ~ 1.2 x ID
  const headDiskMm     = Math.round(Number(ID) * 1.20);

  // ASCII directive (Groq strips Unicode: en-dash, em-dash, multiplication x, le/ge, sub/superscripts)
  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters such as multiplication sign x, en-dash, em-dash, sub/superscripts (m3 not m cubed-glyph), less-than-or-equal, greater-than-or-equal, Greek letters, or middle-dot. Use "x" for multiplication, "to" for ranges (e.g. "0 to 17.5 bar"), "Phi" or "dia" for diameter prefix, "deg C" for temperature, "m3" for cubic meters, "not less than" for ge, "not more than" for le, "Nm" or "N.m" for newton-meters, "MPa" for megapascals.`;

  // Items list — 12 items, with deterministic computed quantities and dimensions.
  // Manhole and Insulation now branch on volume/temp instead of being conditional in spec text.
  const itemsBlock = `Per-item EXACT structure with description="short item name only" and specification="full standard + dimensions + grade":

(1) description="Shell Plate", specification="${material}, ${tShell} mm thk x ${shellPlateLen} mm circumference x ${length} mm length, ASME SA-516 plate (Sec II Part A), allowable S=${sAllow} MPa at ${designTC} deg C, joint efficiency E=${jointEff} (${jointEff === 1.0 ? 'full radiography' : jointEff >= 0.85 ? 'spot radiography' : 'no radiography'}), mill cert per ASME SA-20", qty=${shellPlateMass}, unit="kg"

(2) description="Head Plate", specification="${material}, ${tHead} mm thk, ${headType} stamped from disk OD ${headDiskMm} mm, ASME SA-516, formed per ASME UG-32${headType.includes('llipsoidal') ? '(d)' : headType.includes('emisph') ? '(c)' : '(e)'}, knuckle radius and crown per code", qty=2, unit="piece"

(3) description="Nozzle Pipe", specification="${nozzDia} mm dia, SA-106 Gr.B seamless carbon steel pipe per ASTM A106, schedule 80 minimum or sized per ASME B31.3 for ${pDesign} bar at ${designTC} deg C, length per nozzle projection drawing", qty=${nozzles}, unit="piece"

(4) description="Nozzle Flange", specification="${nozzDia} mm dia, ASME B16.5 ANSI Class 150 RF (raised face) weld-neck flange, ASTM A105 forged carbon steel, surface finish 125 to 250 microinch (Ra)", qty=${nozzles}, unit="piece"

${isManholeReqd ? `(5) description="Manhole Assembly", specification="450 mm NB (DN450), ASME B16.5 ANSI Class 150 RF, davit-hinged cover with quick-opening bolts, davit per ASME B16.5 Annex F; required because vessel internal volume = ${volumeM3} m3 (not less than 1 m3 per industry practice)", qty=1, unit="set"` : `(5) description="Inspection Opening", specification="100 mm dia handhole with bolted cover plate, ASME B16.5 ANSI Class 150 RF; manhole not required since vessel internal volume = ${volumeM3} m3 (less than 1 m3)", qty=1, unit="piece"`}

(6) description="Safety / Relief Valve", specification="ASME Sec VIII UV-stamped pressure-relief valve set at MAWP = ${mawp} bar (1.0 x MAWP per UG-125), conventional spring-loaded balanced bellows or pilot-operated, body ASTM A216 Gr WCB, trim 316SS, capacity not less than ${srvCapacityKgHr} kg/h steam or equivalent (sized per UG-127 / API 520), inlet ${nozzDia >= 50 ? '50 mm' : '40 mm'} flanged, outlet to safe vent location with discharge piping per API 521", qty=1, unit="piece"

(7) description="Pressure Gauge", specification="bourdon-tube glycerin-filled gauge, range 0 to ${gaugeMaxBar} bar (range covers 1.5 x MAWP = ${(Number(mawp) * 1.5).toFixed(1)} bar per ASME B40.100), 100 mm dial dia, accuracy class 1.0 (plus or minus 1 percent FSD), bottom 1/4 inch NPT connection, brass/stainless wetted parts", qty=1, unit="piece"

(8) description="Drain Valve", specification="1 inch (DN25) ball valve, full-bore, ASTM A105 carbon steel body, 316SS ball and stem, ASME B16.34 Class 800, threaded NPT or socket weld ends, lockable lever handle for safety", qty=1, unit="piece"

(9) description="Nameplate", specification="ASME U-stamp nameplate per UG-119 + UG-118, stainless steel 316L, dimensions 100 x 150 mm minimum, stamped fields: manufacturer, MAWP at design temp, hydro test pressure, U-stamp serial number, year built, NB number (Philippine BOI registration); attached by tack-welded studs to a permanent location on shell", qty=1, unit="piece"

(10) description="Saddle Support", specification="carbon steel saddle per Zick analysis (ASME PTB-4 / Zick 1951 paper), 120 deg contact angle minimum, web thickness 8 mm, base plate 16 mm thk x 200 mm wide x circumference per saddle width; located at L/5 from each tangent line per Zick optimum; anchor-bolt holes per design (typically M20 x 4 holes per saddle); shop-coated with rust-inhibitive primer", qty=2, unit="piece"

${isHotService ? `(11) description="Insulation", specification="rock-wool insulation 75 mm thk per ASTM C547, density not less than 64 kg/m3, surface temperature reduction to less than 60 deg C from process ${designTC} deg C; outer aluminum cladding 0.7 mm sheet per ASTM B209, banded with 12 mm SS bands at 300 mm OC; weather-tight expansion joints at saddles", qty=${Math.round(Math.PI * Number(OD) * length / 1e6 * 10) / 10}, unit="m2"` : `(11) description="Surface Protection (no insulation)", specification="surface protection only (process temperature ${designTC} deg C is below 60 deg C threshold for hot-service insulation); apply zinc-rich epoxy primer per SSPC-Paint 20 (75 micron DFT) plus alkyd topcoat (50 micron DFT) on external surfaces", qty=${Math.round(Math.PI * Number(OD) * length / 1e6 * 10) / 10}, unit="m2"`}

(12) description="Gaskets", specification="spiral-wound 316 stainless steel + flexible graphite filler per ASME B16.20, ANSI Class 150 dimensions matching ${nozzDia} mm flanges, with inner ring (CS) and outer ring (CS) for blow-out resistance; one set per flanged nozzle plus 50 percent spare", qty=${nozzles + Math.ceil(nozzles * 0.5)}, unit="piece"

CRITICAL: Every "specification" field MUST be fully populated with the actual numeric values shown above (${tShell} mm, ${ID} mm, ${nozzDia} mm, ${mawp} bar, ${gaugeMaxBar} bar, ${srvCapacityKgHr} kg/h, etc.). Never leave a spec blank or use the item name alone. Every quantity MUST come from the supplied values, not invented.`;

  const prompt = `You are a senior Mechanical / Pressure Vessel Engineer in the Philippines preparing a Bill of Materials (BOM) and Scope of Works (SOW) for an ASME BPVC Section VIII Division 1 pressure vessel.

${asciiDirective}

Project: ${project}
Material: ${material} (allowable S = ${sAllow} MPa at ${designTC} deg C, joint efficiency E = ${jointEff})
Geometry: ID = ${ID} mm, OD = ${OD} mm, shell length = ${length} mm, internal volume = ${volumeM3} m3
Thickness: shell t = ${tShell} mm (incl CA = ${CA} mm), head t = ${tHead} mm, ${headType} head
Pressure: P_design = ${pDesign} bar at ${designTC} deg C, MAWP = ${mawp} bar, Hydro test = ${pTest} bar (1.3 x MAWP per UG-99(b))
Nozzles: ${nozzles} x ${nozzDia} mm dia, ANSI Class 150 RF
Empty weight: ${weightKg} kg; reinforcement pad ${results.nozzle_reinforcement_pad_required ? 'REQUIRED' : 'NOT required'} per UG-37
Hot service insulation: ${isHotService ? 'INCLUDED (design temp >= 60 deg C)' : 'NOT included (design temp below 60 deg C)'}
Manhole: ${isManholeReqd ? 'INCLUDED (volume >= 1 m3)' : 'NOT included (volume below 1 m3, handhole only)'}

Generate a JSON object with exactly two keys:

"bom_items": array of 12 objects with { "description", "specification", "unit", "qty", "remarks" }

${itemsBlock}

"sow_sections": array of 6 objects with { "section_no", "title", "content" }

Section 1.0 Scope: state the contractor shall design, fabricate, NDE-test, hydrostatically test, ASME-stamp, and deliver an unfired pressure vessel per ASME BPVC Section VIII Division 1 with the following: ${material} construction, ID = ${ID} mm, shell length = ${length} mm, ${tShell} mm shell thickness, ${tHead} mm ${headType} head thickness, design pressure ${pDesign} bar at ${designTC} deg C, MAWP = ${mawp} bar, ${nozzles} x ${nozzDia} mm nozzles ANSI Class 150 RF; including U-stamp registration and DOLE Philippines pressure vessel registration before first operation.

Section 2.0 Standards: cite ASME BPVC Section VIII Division 1 (governing design code), ASME Section II Part D (allowable stress S = ${sAllow} MPa for ${material} at design temperature), ASME Section IX (welding procedure qualification WPS/PQR), ASME Section V (NDE methods), ASME B16.5 (flanges and flanged fittings), ASME B16.20 (metallic gaskets), DOLE OSHS PD 856 (Philippine pressure vessel registration for MAWP not less than 15 psi or 1.03 bar), Philippine Boiler and Pressure Vessel Inspection Code, and PNS/ISO 16528 (boilers and pressure vessels - performance requirements).

Section 3.0 Materials and Fabrication: specify ${material} certified per ASME SA-516 (or applicable SA-spec) with mill certificates and material test reports (MTR) traceable to heat number. Allowable stress S = ${sAllow} MPa, joint efficiency E = ${jointEff} (${jointEff === 1.0 ? 'full radiography per UW-51' : jointEff >= 0.85 ? 'spot radiography per UW-52' : 'no radiography'}). Welding procedures (WPS) qualified per ASME Section IX with welder performance qualification (WPQ); use only qualified welders. Post-weld heat treatment (PWHT) required if t_shell exceeds 38 mm carbon steel per UCS-56 (current shell t = ${tShell} mm: ${tShell > 38 ? 'PWHT REQUIRED' : 'PWHT not required'}). Forming of head plates per UG-79; minimum elongation per material spec.

Section 4.0 NDE and Inspection: perform ${jointEff === 1.0 ? '100 percent radiographic testing (RT) per ASME Section V Article 2 / UW-51' : jointEff >= 0.85 ? 'spot radiographic testing (RT) per UW-52, 1 ft per 50 ft of weld minimum' : 'visual inspection only (Category B and Category C welds)'} on all longitudinal and circumferential pressure-retaining welds. Ultrasonic testing (UT) per ASME Section V Article 5 on shell-to-head welds where RT not feasible. Magnetic particle inspection (MT) on nozzle-to-shell weld toes after PWHT. Authorized Inspector (AI) commissioned by ASME shall witness all pressure tests, review NDE reports, and authorize ASME U-stamp application before any vessel leaves the shop.

Section 5.0 Hydrostatic Test: conduct a hydrostatic pressure test at ${pTest} bar (1.3 x MAWP at design temperature per UG-99(b)) for a hold period of not less than 30 minutes after the test pressure is reached. Use clean potable water at temperature not less than 17 deg C above MDMT to avoid brittle fracture. AI witness required; record test pressure, hold time, ambient temperature, and observations on hydro test report. Vent all high points before pressurization. After test, drain completely, dry interior, and apply preservation per shop standard.

Section 6.0 Regulatory Compliance and Documentation: complete ASME U-stamp inspection and submit Manufacturer Data Report Form U-1 (UG-120) to the National Board of Boiler and Pressure Vessel Inspectors (NB) for registration. Complete Philippine DOLE pressure vessel registration per PD 856 and OSHS Rule 1170; submit U-1 data report, hydro test record, AI final inspection certificate, and material mill certs to DOLE Regional Office before first commissioning. Maintain all documentation (MDR, NDE reports, welder logs, mill certs) on file for the life of the vessel; provide owner with final data book at handover.

Each "content" field MUST start with "The Contractor shall..." and use ASCII text only. Return ONLY the JSON. No markdown.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Machine Design / HVAC: Heat Exchanger BOM + SOW Agent ───────────────────

async function heatExchangerBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {
  const project   = inputs.project_name     || "Heat Exchanger Project";
  const dutyKW    = Number(results.duty_kW  || 0).toFixed(1);
  const aReq      = Number(results.A_required_m2 || 0).toFixed(2);
  const aStd      = Number(results.A_standard_m2 || 0);
  const nTubes    = Number(results.n_tubes  || 0);
  const shellID   = Number(results.shell_id_estimate_mm || 0).toFixed(0);
  const tubeOD    = Number(results.tube_od_mm || 19.05).toFixed(2);
  const tubeLen   = Number(results.tube_length_m || 3).toFixed(1);
  const tubeMat   = String(inputs.tube_material || "Stainless Steel 316");
  const shellType = String(inputs.shell_type || "E (single pass)");
  const uDesign   = Number(results.U_design_W_m2K || 0).toFixed(1);
  const temaClass = "R";

  const prompt = `You are a senior Process/Mechanical Engineer in the Philippines preparing a BOM and SOW for a shell-and-tube heat exchanger per TEMA ${temaClass} Class and ASME BPVC Section VIII Division 1.

Project: ${project}
Heat duty: ${dutyKW} kW
Required area: ${aReq} m² → Standard: ${aStd} m²
Shell type: ${shellType} | Shell ID: ~${shellID}mm
Tubes: ${nTubes} × ${tubeOD}mm OD × ${tubeLen}m long (${tubeMat})
Overall U (design): ${uDesign} W/m²·K

Generate a JSON object with exactly two keys:

"bom_items": array of 12 objects with { "description", "specification", "unit", "qty", "remarks" }
Cover: (1) Shell (carbon steel SA-516 Gr.70, ID ${shellID}mm), (2) Tube bundle (${nTubes} tubes × ${tubeOD}mm OD ${tubeMat} ASTM A312/B111), (3) Tubesheets (${tubeMat} or CS clad, ASME Code), (4) Baffles (25% cut, 304SS), (5) Channel and channel cover (CS), (6) Pass partition plates (carbon steel 6mm thk, welded to channel cover per TEMA RCB-9), (7) Tie rods and spacers (carbon steel 12mm dia x 1500mm, qty per TEMA RGP-1.6 baffle support), (8) ANSI flanges (inlet/outlet nozzles both sides), (9) Gaskets (spiral wound 316SS/graphite), (10) Support saddles (2 sets, CS), (11) Thermometer wells (inlet/outlet each stream), (12) Pressure gauges (0 to ${Math.ceil(Number(inputs.design_pressure_bar || 10)*2)} bar, 4 total: inlet/outlet each stream).

"sow_sections": array of 6 objects with { "section_no", "title", "content" }
Sections: 1.0 Scope (supply, install, and commission ${dutyKW}kW shell-and-tube HX per TEMA Class ${temaClass}), 2.0 Standards (TEMA 10th Ed., ASME BPVC Sec.VIII Div.1, ASME B31.3 for piping, ASME Sec.IX for welding), 3.0 Design and Fabrication (TEMA Class ${temaClass} tolerances, tube-to-tubesheet joint per TEMA §RCB-7, hydro test per UG-99), 4.0 Installation (pipe supports within 300mm of nozzles, flow direction per nameplate, expansion loop on hot side piping, insulation of hot surfaces), 5.0 Hydrostatic Testing (shell-side and tube-side tested separately at 1.3×MAWP per UG-99, AI witness required for ASME stamp), 6.0 Commissioning (flush piping before HX connection, verify flow rates per design, monitor fouling factor: clean when U drops 20% below design U=${uDesign}W/m²·K).

Content fields must start "The Contractor shall..." Return ONLY the JSON. No markdown.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Machine Design: Vibration Analysis BOM + SOW Agent ──────────────────────

async function vibrationAnalysisBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {
  const project     = inputs.project_name    || "Vibration Assessment Project";
  const machClass   = String(results.machine_class || inputs.machine_class || "Class II");
  const isoZone     = String(results.iso_zone || "Zone B");
  // Strip "Zone " prefix for places where we already prefix
  const isoZoneTail = isoZone.replace(/^Zone\s+/i, '');
  const vRms        = Number(results.V_rms_mm_s || results.v_assessed_mm_s || 0).toFixed(2);
  const fnHz        = Number(results.fn_Hz   || 0).toFixed(2);
  const fopHz       = Number(results.f_op_Hz || inputs.excitation_freq_hz || 10).toFixed(2);
  const ratioR      = Number(results.frequency_ratio_r || 0).toFixed(2);
  const isolType    = String(results.isolator_type || inputs.isolator_type || "Rubber mount (medium)");
  const isolOk      = results.isolation_ok   ?? true;
  const isolEff     = Number(results.isolation_efficiency_pct || 0).toFixed(1);
  const resRisk     = results.resonance_risk ?? false;
  const TR          = Number(results.transmissibility || 0).toFixed(3);
  const MF          = Number(results.magnification_factor || 0).toFixed(3);
  const gGrade      = String(results.balance_grade || "G6.3");
  const massKg      = Number(inputs.mass_kg || 500);
  const speedRpm    = Number(inputs.speed_rpm || 1450);
  const stiffness   = Number(inputs.stiffness_N_m || 200000);
  const damping     = Number(inputs.damping_ratio || 0.05);
  // Per-isolator load: mass distributed across 4 mount points
  const isolatorLoadKg = Math.round(massKg / 4);
  // Inertia base mass: ASHRAE/SMACNA recommend 3-5x equipment mass for rotating equipment
  const inertiaBaseMassKg = massKg * 3;
  // Isolator stiffness for given fn: k = (2*pi*fn)^2 * m, divided by 4 mounts
  const stiffnessPerIsoNmm = Math.round(Math.pow(2 * Math.PI * Number(fnHz), 2) * massKg / 4 / 1000);  // N/mm
  // SS conduit length estimate: 5m per transducer
  const conduitLengthM = 10;

  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters such as multiplication sign x, en-dash, em-dash, less-than-or-equal, greater-than-or-equal, sub/superscripts, Greek letters (zeta, omega), or middle-dot. Use "x" for multiplication, "to" for ranges (e.g. "4 to 20 mA"), "not less than" for ge, "not more than" for le, "deg C" for temperature, "deg" for angles, "Hz" for frequency, "mm/s" for velocity, "Phi" or "dia" for diameter prefix.`;

  const prompt = `You are a senior Rotating Equipment / Mechanical Engineer in the Philippines preparing a Bill of Materials (BOM) and Scope of Works (SOW) for vibration isolation and condition monitoring per ISO 10816-3, ISO 20816-1, and ISO 21940-11.

${asciiDirective}

Project: ${project}
Machine class: ${machClass} (per ISO 10816-3 Annex)
Mass: ${massKg} kg | Operating speed: ${speedRpm} RPM | Excitation freq: ${fopHz} Hz
Stiffness k: ${stiffness} N/m | Damping ratio zeta: ${damping}
Natural frequency fn: ${fnHz} Hz | Frequency ratio r = f_op / fn: ${ratioR}
Magnification factor MF: ${MF} | Transmissibility TR: ${TR}
Isolation efficiency: ${isolEff} percent (${isolOk ? 'isolator effective, r exceeds sqrt(2)' : 'WARN: isolator amplifying, r below sqrt(2)'})
Assessed velocity v_rms: ${vRms} mm/s -> ${isoZone}
Resonance risk: ${resRisk ? 'YES: operating speed within plus/minus 10 percent of fn' : 'No'}
Balancing grade target: ${gGrade}
Per-isolator load (4 mount points): ${isolatorLoadKg} kg
Inertia base recommended mass: ${inertiaBaseMassKg} kg (3 x machine mass per ASHRAE)
Isolator stiffness target: ${stiffnessPerIsoNmm} N/mm per mount

Generate a JSON object with exactly two keys:

"bom_items": array of 10 objects with { "description", "specification", "unit", "qty", "remarks" }

Per-item EXACT structure with description="short item name only" and specification="full standard + dimensions + grade + numeric ratings":

(1) description="Vibration Isolator", specification="${isolType} per ISO 10816, rated load not less than ${isolatorLoadKg} kg per mount (machine mass ${massKg} kg / 4 mount points), durometer 50 to 60 Shore A, deflection 6 to 12 mm at rated load, target vertical stiffness ${stiffnessPerIsoNmm} N/mm to achieve fn = ${fnHz} Hz, mounting bolt M16 with anti-vibration washer", qty=4, unit="piece"

(2) description="Inertia Base Frame", specification="concrete-filled welded steel frame, mass not less than ${inertiaBaseMassKg} kg (3 x machine mass per ASHRAE Applications Handbook Ch 48), structural ASTM A36 steel channel C200 x 76 mm minimum, concrete fill f'c=21 MPa, anchor bolts M20 cast in for machine mounting, isolator pockets at 4 corners", qty=1, unit="piece"

(3) description="Accelerometer (Vibration Transducer)", specification="piezoelectric accelerometer per ISO 5348 mounting standard, sensitivity 100 mV/g, frequency response 0.5 to 10000 Hz (plus/minus 5 percent), temperature range -50 to +120 deg C, IEPE-powered constant-current 2 to 10 mA, top-mount stainless steel housing 1/4-28 UNF stud, IP67 rated", qty=2, unit="piece"

(4) description="Vibration Monitoring Transmitter", specification="continuous 2-wire 4 to 20 mA loop-powered vibration transmitter per ISO 20816-1, accepts IEPE accelerometer input, RMS velocity output 0 to 25 mm/s, RS-485 Modbus secondary output to plant DCS/SCADA, NEMA 4X enclosure, 24 VDC input, ATEX Zone 2 if hazardous area", qty=1, unit="piece"

(5) description="Field Dynamic Balancing Kit", specification="portable single-plane and two-plane dynamic balancing instrument per ISO 21940-11, includes trial-weight set (5 g to 500 g graduated), phase-reference photo-tach, magnetic mounting bases, calibration certificate traceable to NIST, target balancing grade ${gGrade}", qty=1, unit="set"

(6) description="Anti-Vibration Pad", specification="neoprene-cork-neoprene sandwich pad, 50 mm thk x 100 mm x 100 mm, durometer 40 to 50 Shore A, natural frequency fn = 8 to 12 Hz under rated load, oil and water resistant, temperature range -30 to +80 deg C; supplementary isolation under inertia base", qty=4, unit="piece"

(7) description="Flexible Pipe Connector", specification="EPDM rubber expansion joint with floating flanges, ANSI Class 150 RF, sized to match process pipe diameter, working pressure not less than ${Math.max(10, Math.round(Number(inputs.system_pressure_bar || 10)))} bar, working temperature not more than 100 deg C, length 250 mm minimum to absorb 10 mm axial movement at machine inlet/outlet", qty=2, unit="piece"

(8) description="Flexible Electrical Conduit", specification="liquid-tight flexible metal conduit (LFMC) per UL 360, 3/4 inch trade size, stainless steel core with PVC jacket, IP67, with EMI/RFI shielding for 4 to 20 mA signal cables, length sized to allow 50 mm of machine movement at all 4 mounting points", qty=${conduitLengthM}, unit="m"

(9) description="Anchor Bolt with Vibration Washer", specification="M20 ASTM F1554 Grade 36 anchor rod, 250 mm embedment into inertia base concrete, supplied with hex nut, hardened washer (F436), and vibration-isolation Belleville washer or wave washer to maintain preload under cyclic loading", qty=8, unit="set"

(10) description="Vibration Data Collector / Analyzer", specification="portable handheld vibration analyzer with built-in ISO 10816-3 zone assessment, accepts IEPE accelerometer input, FFT spectrum analyzer 100 to 10000 line resolution, time-waveform capture, on-board database for trending baseline measurements, intrinsically safe certified for hazardous areas, calibration certificate traceable to NIST", qty=1, unit="piece"

CRITICAL: Every "specification" field MUST be fully populated with the actual numeric values shown above (${massKg} kg, ${fnHz} Hz, ${isolatorLoadKg} kg, ${inertiaBaseMassKg} kg, etc.) — never blank, never just the item name.

"sow_sections": array of 5 objects with { "section_no", "title", "content" }

Section 1.0 Scope: state the contractor shall furnish, install, balance, and commission a vibration isolation and condition-monitoring system for a ${machClass} rotating machine (mass ${massKg} kg, operating speed ${speedRpm} RPM, fn = ${fnHz} Hz, frequency ratio r = ${ratioR}) achieving ISO 10816-3 ${isoZone} severity (assessed v_rms = ${vRms} mm/s) with isolation efficiency not less than ${isolEff} percent (TR = ${TR}). Include inertia base, ${isolType.toLowerCase()} isolators at 4 mount points, accelerometer instrumentation, continuous transmitter wired to plant DCS/SCADA, and field dynamic balancing per ISO 21940-11.

Section 2.0 Standards: cite ISO 10816-3 (Mechanical vibration - Evaluation of machine vibration by measurements on non-rotating parts), ISO 20816-1 (Mechanical vibration - Measurement and evaluation of machine vibration, general guidelines), ISO 21940-11 (Mechanical vibration - Rotor balancing - Procedures and tolerances for rotors with rigid behavior), ISO 5348 (Mechanical vibration and shock - Mechanical mounting of accelerometers), ISO 2372 (legacy reference - severity criteria, retained for cross-reference), and ASHRAE Applications Handbook Chapter 48 (vibration and noise control for HVAC and rotating equipment), plus PSME Code and DOLE D.O. 13 occupational vibration exposure limits.

Section 3.0 Isolation System Installation: size the inertia base to not less than ${inertiaBaseMassKg} kg (3 x machine mass per ASHRAE) and pour with f'c = 21 MPa concrete cured 7 days minimum before isolator installation. Select ${isolType.toLowerCase()} isolators rated not less than ${isolatorLoadKg} kg per mount (machine mass / 4) with target vertical stiffness ${stiffnessPerIsoNmm} N/mm to achieve natural frequency fn = ${fnHz} Hz and frequency ratio r = ${ratioR} (must exceed sqrt(2) = 1.414 for effective isolation). Torque isolator mounting bolts to manufacturer specification (typically 100 to 200 Nm for M16); verify isolator deflection at 50 percent and 100 percent load before machine startup.

Section 4.0 Balancing and Alignment: perform field dynamic balancing of all rotating components to balance grade ${gGrade} per ISO 21940-11 using a portable single- or two-plane balancer (BOM Item 5); record initial unbalance, trial-weight response, and final residual unbalance on a balancing certificate. Verify shaft alignment within not more than 0.05 mm TIR (angular and parallel) using laser shaft alignment kit. Capture baseline vibration measurement after balance and alignment using BOM Item 10 vibration analyzer; record FFT spectrum, time waveform, and ISO 10816-3 zone classification at all four bearing locations.

Section 5.0 Monitoring and Acceptance: install accelerometers (BOM Item 3) at all four bearing locations per ISO 5348 mounting practice (epoxy-bonded stud mount, surface flatness not more than 0.025 mm/m). Wire each accelerometer to the vibration transmitter (BOM Item 4) via flexible conduit (BOM Item 8) for protection against machine micro-movement. Provide continuous 4 to 20 mA signals to plant DCS/SCADA with the following alert/shutdown thresholds per ISO 10816-3 Class ${machClass.replace(/[^IVX]/g, '') || 'II'}: alert at Zone B/C boundary (${(machClass.includes('I') && !machClass.includes('II')) ? '4.5' : machClass.includes('III') ? '7.1' : '4.5'} mm/s), shutdown at Zone D (${machClass.includes('III') ? '11.0' : machClass.includes('IV') ? '18.0' : '11.0'} mm/s). Document the commissioning baseline (FFT spectrum, time waveform, zone classification) and require monthly trending against the baseline.

Each "content" field MUST start with "The Contractor shall..." and use ASCII text only. Return ONLY the JSON. No markdown.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Machine Design: Fluid Power BOM + SOW Agent ─────────────────────────────

async function fluidPowerBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {
  const project   = inputs.project_name       || "Hydraulic System Project";
  const pBar      = Number(results.inputs_used?.P_bar || results.system_pressure_bar || inputs.system_pressure_bar || 200).toFixed(0);
  const qLpm      = Number(results.inputs_used?.Q_lpm || inputs.flow_lpm || 40).toFixed(1);
  // Sanitize fluid (form sends "ISO VG 46 (40°C)" — degree symbol strips through Groq)
  const fluidRaw  = String(results.inputs_used?.fluid || inputs.fluid || "ISO VG 46");
  const fluidTemp = fluidRaw.match(/\((\d+)/)?.[1] || "40";
  const fluidGrade= fluidRaw.replace(/\s*\([^)]*\)\s*/g, "").trim() || "ISO VG 46";
  const cyl       = (results.cylinder as Record<string, unknown>) || {};
  const boreMM    = Number(results.bore_selected_mm || cyl.bore_mm || 0);
  const rodMM     = Number(results.rod_selected_mm || cyl.rod_mm || 0);
  const strokeMM  = Number(inputs.stroke_mm || inputs.cylinder_stroke_mm || 200);
  const fExtKn    = Number(cyl.F_extend_kN || 0).toFixed(1);
  const fRetKn    = Number(cyl.F_retract_kN || 0).toFixed(1);
  const vExtMs    = Number(cyl.v_extend_m_s || 0).toFixed(3);
  const pumpDispl = Number(results.pump_displacement_cm3 || 0);
  const motorKW   = Number((results.pump as Record<string, unknown> | undefined)?.P_motor_kW || 0).toFixed(2);
  const motorKwStd = Math.max(0.37, Math.ceil(Number(motorKW) * 1.25 * 10) / 10);  // next standard size with 25% margin
  const accVolNum = Number((results.accumulator as Record<string, unknown> | undefined)?.V_recommended_L || 0);
  const includeAccumulator = accVolNum > 0;
  const accVol    = accVolNum.toFixed(1);
  const pLineOD   = Number((results.pressure_line as Record<string, unknown> | undefined)?.od_mm || 6);
  const pLineId   = Number((results.pressure_line as Record<string, unknown> | undefined)?.id_mm || 4);
  // Reservoir capacity per ISO 4413 = 3 to 5 x Q [L/min]
  const reservoirL = Math.ceil(Number(qLpm) * 3);
  // Pressure-gauge range: round up to next 10 bar above 1.25 x system pressure
  const gaugeMaxBar = Math.ceil(Number(pBar) * 1.25 / 10) * 10;
  // SAE J517 hose class: pick by pressure (100R1 to 350bar, 100R2 to 415bar, 100R12 above)
  const hoseClass = Number(pBar) <= 350 ? "SAE 100R2 (Type 2 wire-braid, working pressure not less than 415 bar for nominal sizes up to 1 inch)"
                                        : "SAE 100R12 (Type 12 spiral-wire, working pressure not less than 415 bar large bore)";
  // Cylinder spec: ISO 6020/6022 mounting standards
  const cylMountStd = "ISO 6020-2 (medium duty) foot or trunnion mount";

  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters such as multiplication sign x, en-dash, em-dash, less-than-or-equal, greater-than-or-equal, sub/superscripts (cm3 not cm cubed-glyph), Greek letters (eta, delta, pi), middle-dot, or degree symbol. Use "x" for multiplication, "to" for ranges (e.g. "0 to 250 bar"), "not less than" for ge, "not more than" for le, "deg C" for temperature, "Phi" or "dia" for diameter prefix, "cm3/rev" for displacement, "Nm" or "N.m" for newton-meters.`;

  const itemsBlock = `Per-item EXACT structure with description="short item name only" and specification="full standard + dimensions + grade + numeric ratings":

(1) description="Hydraulic Power Unit (HPU)", specification="axial piston pump ${pumpDispl} cm3/rev variable-displacement, swashplate type with pressure compensator and load-sensing control, mounted directly on reservoir cover with bell-housing, working pressure not less than ${gaugeMaxBar} bar, Bosch Rexroth A10VSO or equivalent", qty=1, unit="set"

(2) description="Electric Motor", specification="three-phase AC induction motor ${motorKwStd} kW (next standard size above ${motorKW} kW with 25 percent service margin) IE3 efficiency class, IP55 TEFC enclosure, B5 flange mount per IEC 60072, 380-415 V / 50 Hz / 1450 RPM (4-pole)", qty=1, unit="piece"

(3) description="Hydraulic Reservoir", specification="welded mild-steel tank, capacity ${reservoirL} L (3 x ${qLpm} L/min flow rate per ISO 4413 sizing), with internal baffle separating suction from return, breather filter (3-micron desiccant) on top, sight glass with integrated thermometer, magnetic drain plug, return diffuser, fluid level switch low/high alarm contacts", qty=1, unit="piece"

(4) description="Hydraulic Cylinder", specification="double-acting cylinder, bore Phi ${boreMM} mm, rod Phi ${rodMM} mm, stroke ${strokeMM} mm, ${cylMountStd}, hard-chromed rod (HRC 55 to 60), polyurethane rod and piston seals (NBR backup), end-of-stroke cushioning both ends adjustable, working pressure not less than ${gaugeMaxBar} bar, pressure-test 1.5 x working", qty=1, unit="piece"

(5) description="Directional Control Valve", specification="solenoid-operated 4/3 spring-centered closed-center spool, 24 VDC dual coils with manual override, port size CETOP 5 (NG10) or CETOP 7 (NG16) sized to ${qLpm} L/min flow, working pressure not less than ${pBar} bar, mounted on subplate", qty=1, unit="piece"

(6) description="Pressure Relief Valve", specification="cartridge-type pilot-operated relief valve, set pressure ${pBar} bar (1.0 x system pressure), cracking pressure not less than 10 percent below set, rated flow not less than ${qLpm} L/min, mounted on HPU manifold per ISO 4413 safety requirement", qty=1, unit="piece"

(7) description="Pressure Reducing Valve", specification="direct-acting pressure reducing valve for low-pressure auxiliary circuits (e.g. clamp, return-line lubrication), pilot range 10 to ${Math.round(Number(pBar) * 0.5)} bar, rated flow ${Math.round(Number(qLpm) * 0.3)} L/min minimum, CETOP 3 (NG6) port size", qty=1, unit="piece"

${includeAccumulator ? `(8) description="Bladder Accumulator", specification="${accVolNum.toFixed(1)} L bladder accumulator per ISO 4413 / DOT-3AAA, working pressure ${pBar} bar, pre-charge nitrogen pressure 0.9 x P_min (per Boyle isothermal sizing), bladder material HNBR (compatible with ${fluidGrade}), shell ASTM A372 carbon steel with U-stamp, ASME UA-9 certified", qty=1, unit="piece"` : `(8) description="Accumulator (Optional)", specification="bladder accumulator 1 to 5 L recommended for systems with rapid demand changes or thermal expansion compensation; size per design intent (none specified in current calculation)", qty=0, unit="piece", remarks="Optional - not required for steady-state circuits"`}

(9) description="Return Line Filter", specification="spin-on or in-tank return filter, 10-micron absolute (beta-10 not less than 200) per ISO 4406 class 17/15/12 cleanliness target, with visual differential-pressure indicator and bypass valve at delta-P 25 psi, sized for ${Math.round(Number(qLpm) * 1.5)} L/min flow (1.5 x system flow per ISO 4413)", qty=1, unit="piece"

(10) description="Suction Strainer", specification="full-flow wire-mesh strainer 150 micron, sized to not less than 2 x pump flow (${Math.round(Number(qLpm) * 2)} L/min) to prevent suction starvation, mounted inside reservoir at pump suction port, brass/SS construction with magnetic insert", qty=1, unit="piece"

(11) description="High-Pressure Hose Assembly", specification="${hoseClass}, OD ${pLineOD} mm / ID ${pLineId} mm, length per drawing (typical 1 to 3 m), JIC 37-degree flared end fittings (male and female), pressure-tested 1.5 x working pressure, EN ISO 1402 hydraulic test certified, color black with white print", qty=4, unit="piece"

(12) description="Hydraulic Fittings", specification="JIC 37-degree flared fittings per SAE J514, brass or steel adapters and tees, all sized for ${pLineOD} mm OD tube; includes 90-degree elbows, tees, straight unions, and tube-to-NPT adapters as required by piping schematic", qty=20, unit="piece"

(13) description="Hydraulic Oil", specification="${fluidGrade} mineral hydraulic fluid per ISO 11158 HV (high-VI), 46 cSt at 40 deg C, viscosity index not less than 140, anti-wear additive (FZG load stage not less than 10), demulsibility (40-40-0) at 30 minutes, anti-foam, oxidation stability per ASTM D2272 not less than 1000 minutes; initial fill ${reservoirL} L plus 20 percent commissioning spare", qty=${reservoirL}, unit="L"

(14) description="Pressure Gauge", specification="bourdon-tube glycerin-filled gauge, range 0 to ${gaugeMaxBar} bar (covers 1.25 x system pressure ${pBar} bar per ASME B40.100), 100 mm dial dia, accuracy class 1.0 (plus or minus 1 percent FSD), 1/4 inch NPT bottom connection, brass/stainless wetted parts; one at pump discharge, one before filter, one at cylinder cap end", qty=3, unit="piece"

CRITICAL: Every "specification" field MUST be fully populated with the actual numeric values shown above (${boreMM} mm, ${rodMM} mm, ${strokeMM} mm, ${pBar} bar, ${qLpm} L/min, ${pumpDispl} cm3/rev, ${motorKwStd} kW, ${reservoirL} L, ${gaugeMaxBar} bar, etc.). Never blank, never just the item name.`;

  const prompt = `You are a senior Hydraulic Systems Engineer in the Philippines preparing a Bill of Materials (BOM) and Scope of Works (SOW) for a hydraulic power unit and cylinder system per ISO 4413:2010 (Safety Requirements for Hydraulic Fluid Power Systems) and NFPA T2.12.10.

${asciiDirective}

Project: ${project}
System pressure: ${pBar} bar
Flow rate Q: ${qLpm} L/min
Fluid: ${fluidGrade} at ${fluidTemp} deg C
Cylinder: bore Phi ${boreMM} mm, rod Phi ${rodMM} mm, stroke ${strokeMM} mm
Cylinder force: F_extend = ${fExtKn} kN, F_retract = ${fRetKn} kN
Cylinder velocity (extend): ${vExtMs} m/s
Pump displacement Vg: ${pumpDispl} cm3/rev
Motor power: ${motorKW} kW (specify next standard size: ${motorKwStd} kW with 25 percent margin)
Accumulator: ${includeAccumulator ? `${accVolNum.toFixed(1)} L bladder type included` : 'not required for this circuit'}
Pressure line: Phi ${pLineOD} mm OD x Phi ${pLineId} mm ID
Reservoir: ${reservoirL} L (3 x flow rate per ISO 4413)

Generate a JSON object with exactly two keys:

"bom_items": array of 14 objects with { "description", "specification", "unit", "qty", "remarks" }

${itemsBlock}

"sow_sections": array of 5 objects with { "section_no", "title", "content" }

Section 1.0 Scope: state the contractor shall design, procure, fabricate, install, test, and commission a hydraulic power unit and cylinder system per ISO 4413:2010 with the following specifications: ${pBar} bar system pressure, ${qLpm} L/min flow rate, ${fluidGrade} fluid at ${fluidTemp} deg C, double-acting cylinder Phi ${boreMM} mm bore x ${strokeMM} mm stroke producing ${fExtKn} kN extend force, axial-piston pump ${pumpDispl} cm3/rev driven by ${motorKwStd} kW motor, complete with reservoir, filtration, control valves, ${includeAccumulator ? `${accVolNum.toFixed(1)} L bladder accumulator,` : ''} pressure gauges, hoses, and instrumentation per BOM Items 1 to 14.

Section 2.0 Standards: cite ISO 4413:2010 (Hydraulic fluid power - General rules and safety requirements for systems and their components), ISO 4406 (Hydraulic fluid power - Method for coding the level of contamination by solid particles), ISO 10767-1 (Hydraulic fluid power - Determination of pressure ripple levels), ISO 11158 (Hydraulic oil category HV/HM), SAE J517 (hydraulic hose), SAE J514 (JIC 37-degree flared fittings), ISO 6020-2 / ISO 6022 (cylinder mounting), ASME B40.100 (pressure gauge accuracy), DOLE D.O. 13 (occupational safety), and PSME Code.

Section 3.0 Design and Procurement: specify all pressure-containing components rated not less than ${gaugeMaxBar} bar (1.25 x ${pBar} bar system pressure margin) per ISO 4413 sizing rule. Hydraulic hoses per ${hoseClass}; all hoses pressure-tested at 1.5 x working pressure with EN ISO 1402 certificate. Cylinder cushioning at both ends adjustable for the ${strokeMM} mm stroke per ISO 6020-2. Pump and motor matched as a coupling assembly through bell-housing per IEC 60072 B5 flange. Reservoir baffle layout separates suction from return per ISO 4413 Annex G. All fittings JIC 37-degree flared per SAE J514 (no NPT in pressure-side circuits). Submit material data sheets and pressure-test certificates to the Engineer for approval before procurement.

Section 4.0 Installation: install the reservoir on rubber anti-vibration mounts (deflection 5 to 10 mm at rated load) on a level concrete pad. Flush all piping and hoses to ISO 4406 class 17/15/12 cleanliness target before cylinder connection (use offline filter cart for not less than 8 hours). Pressure-test the assembled system at 1.5 x ${pBar} bar = ${(Number(pBar) * 1.5).toFixed(0)} bar for 30 minutes minimum, hold and inspect all joints for leaks; document on a hydraulic pressure-test report. Bleed all air from cylinder and pressure-line high points before commissioning. Ground the HPU per PEC 2017 / ISO 4413 anti-static requirements.

Section 5.0 Testing and Commissioning: perform a full-stroke test of 10 cycles (extend-retract) at no-load to verify smooth motion, then 10 cycles at rated load to verify ${fExtKn} kN extend and ${fRetKn} kN retract forces; record cycle time within plus or minus 5 percent of design (${vExtMs} m/s extend speed). Conduct pressure-hold test at ${pBar} bar for 5 minutes; pressure decay not more than 2 percent. Verify oil temperature steady-state remains not more than 60 deg C with continuous duty operation; if exceeded, investigate cooler sizing or relief-valve recirculation losses. Conduct noise-level check per ISO 4413 clause 7.3 (sound power level not more than 80 dBA at 1 m). Submit commissioning report with full-stroke test log, pressure-decay log, fluid cleanliness analysis (ISO 4406 class), and noise survey to the Engineer for handover sign-off.

Each "content" field MUST start with "The Contractor shall..." and use ASCII text only. Return ONLY the JSON. No markdown.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Machine Design: Noise / Acoustics BOM + SOW Agent ───────────────────────

async function noiseAcousticsBomSowAgent(
  inputs: Record<string, unknown>,
  results: Record<string, unknown>
): Promise<{ bom_items: unknown[]; sow_sections: unknown[] }> {
  const project   = inputs.project_name    || "Noise Control Project";
  const calcMode  = String(inputs.calc_type || "Room");
  const lwDb      = Number(results.source_Lw_dB || inputs.source_Lw_dB || 90).toFixed(1);
  const lpDb      = Number(results.Lp_at_distance_dB || 0).toFixed(1);
  const distM     = Number(results.distance_m || inputs.distance_m || 5).toFixed(1);
  const dose      = (results.dose as Record<string, unknown>) || {};
  const twa       = Number(dose?.TWA_dBA || 0).toFixed(1);
  const limitExc  = dose?.limit_exceeded ?? false;
  const spaceType = String(inputs.space_type || "Industrial");
  const ncLimit   = Number(results.NC_limit || 40);
  const barrierIL = Number(results.barrier_IL_dB || 0).toFixed(1);
  const alpha     = Number(inputs.avg_absorption_coeff || 0.15);
  const requiredReductionDb = Math.max(0, Number(lpDb) - 65);  // typical NC-40 ~ 50 dBA, so reduce
  const exposedWorkers = String(inputs.exposed_workers_count || 50);

  const asciiDirective = `IMPORTANT: All output text must be ASCII only. Do NOT use Unicode characters such as multiplication sign x, en-dash, em-dash, less-than-or-equal, greater-than-or-equal, sub/superscripts, Greek letters (alpha, sigma), middle-dot, degree symbol, or section sign. Use "x" for multiplication, "to" for ranges, "not less than" for ge, "not more than" for le, "Section" for clause references (not the section sign), "deg" for degree, "alpha" for the absorption coefficient symbol.`;

  const prompt = `You are a senior Acoustic / Environmental Engineer in the Philippines preparing a Bill of Materials (BOM) and Scope of Works (SOW) for a noise assessment and control project per ISO 9613-2, OSHA 29 CFR 1910.95, DOLE D.O. 13 Series 1998, and ASHRAE Applications Handbook Chapter 8.

${asciiDirective}

Project: ${project}
Assessment mode: ${calcMode}
Source Lw: ${lwDb} dB
Receiver Lp at ${distM} m: ${lpDb} dB
Space type: ${spaceType} | NC target: NC ${ncLimit}
Average room absorption coefficient: ${alpha}
${calcMode === 'Dose' ? `8-hour TWA: ${twa} dBA (${limitExc ? 'EXCEEDS DOLE/OSHA limit' : 'within limit'})` : ''}
${calcMode === 'Barrier' ? `Barrier insertion loss: ${barrierIL} dB` : ''}
Estimated exposed workers: ${exposedWorkers} (audiometric program scope)
Required noise reduction (Lp to NC ${ncLimit} target): approximately ${requiredReductionDb} dB

Generate a JSON object with exactly two keys:

"bom_items": array of 10 objects with { "description", "specification", "unit", "qty", "remarks" }

Per-item EXACT structure with description="short item name only" and specification="full standard + dimensions + grade + numeric ratings":

(1) description="Sound Level Meter", specification="IEC 61672-1 Class 1 precision integrating sound level meter, A/C weighting, octave-band filter set per ISO 266 (1/1 octave) and ISO 266 (1/3 octave) optional, measurement range 25 to 140 dB, calibration certificate traceable to NIST, includes acoustic calibrator (94 dB / 114 dB at 1 kHz)", qty=1, unit="set"

(2) description="Real-Time Octave-Band Analyzer", specification="real-time spectrum analyzer with 1/1 and 1/3 octave-band capability, ISO 266 centre frequencies (16 Hz to 20 kHz), FFT to 25 kHz, integrated data logger 32 GB minimum, USB and Bluetooth interface for PC analysis software, NIST-traceable calibration", qty=1, unit="piece"

(3) description="Personal Noise Dosimeter", specification="OSHA/DOLE-compliant personal dosimeter with 5 dB exchange rate (OSHA Hearing Conservation), 80 dB threshold, 90 dB criterion level, A-weighted slow response, 8-hour battery life minimum, intrinsically safe rating ATEX Zone 2 if hazardous environment, calibration certificate", qty=5, unit="piece", remarks="Personnel exposure surveys"

(4) description="Acoustic Enclosure Panel", specification="composite panel 50 mm thk - 18-gauge perforated steel inner facing (22 percent open area) plus 50 mm rock-mineral wool core (density not less than 64 kg/m3) plus 22-gauge solid steel outer skin, NRC not less than 0.90 (ISO 354), STC not less than 35 (ASTM E90), modular bolt-together construction with neoprene gasket joints, hot-dip galvanized hardware", qty=100, unit="m2"

(5) description="Acoustic Barrier Wall", specification="dense barrier per OSHA 1910.95 - 200 mm CMU concrete block (mass not less than 480 kg/m2) OR mass-loaded vinyl (MLV, 4.9 kg/m2) on stud framing, both achieve STC not less than 35 (ASTM E90); height not less than line-of-sight from source to receiver plus 1 m freeboard for diffraction control", qty=50, unit="m2"

(6) description="Anti-Vibration Mount", specification="elastomeric machine isolator, durometer 50 to 60 Shore A, rated load 100 to 1000 kg per mount (size per machine mass / 4 mounts), natural frequency 8 to 12 Hz to isolate primary excitation; alternative: spring-isolator with viscous damper for fn below 5 Hz; mounting bolt M16 with anti-vibration washer, supplied with deflection gauge for installation verification", qty=10, unit="set"

(7) description="HVAC Duct Silencer", specification="passive dissipative duct silencer per ASHRAE Applications Handbook Ch 48, length 900 to 1200 mm, dynamic insertion loss not less than 25 dB at 250 Hz octave-band centre, perforated steel splitter design with mineral wool acoustic infill (kraft-paper-faced for clean-air applications), pressure drop not more than 75 Pa at design airflow, ULC S110 fire-classified", qty=5, unit="piece"

(8) description="Acoustic Door Seal", specification="full-perimeter door seal kit per ASTM E283 air leakage class - aluminium retainer with neoprene compression bulb on hinge and strike sides, automatic drop-down threshold seal at base (cam-operated), STC not less than 35 (ASTM E90 with door assembly); fits standard 900 x 2100 mm door slab", qty=5, unit="set", remarks="Treatment rooms / acoustic isolation booths"

(9) description="Hearing Protection (PPE)", specification="ANSI S3.19 / EN 352-1 certified hearing protection - earmuffs with NRR not less than 25 dB (band-pass attenuation 125 Hz to 8 kHz) AND/OR foam-roll earplugs with NRR not less than 33 dB (single-use, polyurethane); PPE supplied for all ${exposedWorkers} exposed workers plus 25 percent spare; hearing-conservation training per DOLE D.O. 13 Section 7", qty=${Math.ceil(Number(exposedWorkers) * 1.25)}, unit="set", remarks="One earmuff plus pack of plugs per worker"

(10) description="Acoustic Absorption Panel", specification="ceiling and wall treatment - 50 mm fibreglass core (density 24 to 32 kg/m3) wrapped in fabric-faced (acoustically transparent) tile 600 mm x 600 mm or 1200 mm x 600 mm, NRC not less than 0.85 (ISO 354), Class A fire rating per ASTM E84 (flame spread 25, smoke 50), suspended from grid ceiling with anti-vibration clips", qty=200, unit="m2"

CRITICAL: Every "specification" field MUST be fully populated with the actual numeric values shown above (Lw=${lwDb} dB, Lp=${lpDb} dB at ${distM} m, NC ${ncLimit}, alpha=${alpha}, ${exposedWorkers} workers, etc.). Never blank, never just the item name.

"sow_sections": array of 5 objects with { "section_no", "title", "content" }

Section 1.0 Scope: state the contractor shall conduct a baseline noise survey, design and supply noise-control engineering measures, install hearing-protection PPE, and verify by post-installation re-measurement that the assessed receiver level Lp meets the target NC ${ncLimit} in the ${spaceType} per ISO 9613-2 and DOLE D.O. 13 Series 1998. Current source level Lw = ${lwDb} dB produces Lp = ${lpDb} dB at ${distM} m receiver position; required noise reduction to meet NC ${ncLimit} target is approximately ${requiredReductionDb} dB. Scope includes treatment of approximately ${Math.ceil(Number(exposedWorkers) * 1.25)} hearing-protection PPE sets for ${exposedWorkers} exposed workers plus 25 percent spare per BOM Item 9.

Section 2.0 Standards: cite ISO 9613-2 (Attenuation of sound during propagation outdoors - General method of calculation), ISO 3745 (Determination of sound power levels - Precision methods for anechoic and hemi-anechoic rooms), ISO 266 (Preferred frequencies for measurements), IEC 61672-1 (Sound level meters - Specifications), OSHA 29 CFR 1910.95 (Occupational Noise Exposure), DOLE Department Order No. 13 Series 1998 (Health and Safety in Construction), ASHRAE Applications Handbook 2019 Chapter 8 (Sound and Vibration Control), ASTM E90 (Sound transmission loss - STC rating), ASTM E84 (surface burning), and PSME Code.

Section 3.0 Baseline Survey: measure equivalent continuous sound pressure level Leq and 1/1 octave-band Lp at all occupied worker positions during normal operation cycles using IEC 61672-1 Class 1 sound level meter (BOM Item 1). Determine Noise Criterion (NC) rating per ASHRAE Ch 48 method (compare octave-band Lp curve against NC reference curves; report highest tangent NC). Document positions exceeding the NC ${ncLimit} target and OSHA/DOLE 8-hour TWA action level (85 dBA) on a survey report with site plan showing measurement positions, instrument calibration log, and weather conditions for outdoor-propagation measurements.

Section 4.0 Noise Control Measures: implement the engineering hierarchy per ISO 11690 / DOLE D.O. 13 - first reduce at source (modify equipment, vibration isolation per BOM Item 6), then control propagation path (acoustic enclosures BOM Item 4, barriers BOM Item 5, duct silencers BOM Item 7, room absorption BOM Item 10 to achieve average alpha not less than ${alpha}), then administrative controls (work rotation, exposure-time reduction per OSHA 1910.95 Table G-16), and finally hearing-protection PPE BOM Item 9 as a LAST resort (not a substitute for engineering controls per DOLE D.O. 13 Section 7). Acoustic doors and seals BOM Item 8 required at the boundary between treated and untreated spaces.

Section 5.0 Verification and Monitoring: post-installation re-measurement to confirm NC ${ncLimit} target achieved at all previously-exceeding positions; re-measure at the same instrument positions with the same calibrated meter (within 24 hours of calibration). Establish a hearing-conservation program per DOLE D.O. 13 Section 14 with annual noise dosimetry (BOM Item 3, all exposed workers, full 8-hour shift) and baseline plus annual audiometric testing for all ${exposedWorkers} exposed workers; maintain medical records for not less than 30 years per OSHA 1910.95(m). Submit baseline survey, post-control re-measurement, and audiometric program rollout plan to the Engineer for sign-off before project closeout.

Each "content" field MUST start with "The Contractor shall..." and use ASCII text only. Return ONLY the JSON. No markdown.`;

  const raw = await callGroq(prompt);
  const parsed = JSON.parse(raw);
  return { bom_items: parsed.bom_items || [], sow_sections: parsed.sow_sections || [] };
}

// ─── Main handler ─────────────────────────────────────────────────────────────

serve(async (req) => {
  const corsHeaders = getCorsHeaders(req);
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

    // Discipline router: add branches here for Pump Sizing, Electrical, etc.
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
    } else if (discipline === "Mechanical" && calc_type === "Boiler System") {
      result = await boilerBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Water Supply Pipe Sizing") {
      result = await waterSupplyBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Hot Water Demand") {
      result = await hotWaterBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Drainage Pipe Sizing") {
      result = await drainageBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Septic Tank Sizing") {
      result = await septicBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Water Softener Sizing") {
      result = await waterSoftenerBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Water Treatment System") {
      result = await waterTreatmentBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Wastewater Treatment (STP)") {
      result = await wastewaterSTPBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Storm Drain / Stormwater") {
      result = await stormDrainBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Grease Trap Sizing") {
      result = await greaseTrapBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Plumbing" && calc_type === "Roof Drain Sizing") {
      result = await roofDrainBomSowAgent(calc_inputs || {}, calc_results);
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
    } else if (discipline === "Electrical" && calc_type === "Solar PV System") {
      result = await solarPVBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Power Factor Correction") {
      result = await pfcBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Cable Tray Sizing") {
      result = await cableTrayBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "UPS Sizing") {
      result = await upsSizingBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Earthing / Grounding System") {
      result = await earthingBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Lightning Protection System (LPS)") {
      result = await lpsBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Generator Sizing") {
      result = await generatorSizingBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Transformer Sizing") {
      result = await transformerSizingBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Electrical" && calc_type === "Harmonic Distortion") {
      result = await harmonicDistortionBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Fire Protection" && calc_type === "Clean Agent Suppression") {
      result = await cleanAgentSuppressionBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Fire Protection" && calc_type === "Fire Sprinkler Hydraulic") {
      result = await fireSprinklerBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Fire Protection" && calc_type === "Fire Pump Sizing") {
      result = await firePumpBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Fire Protection" && calc_type === "Stairwell Pressurization") {
      result = await stairwellPressBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Fire Protection" && calc_type === "Fire Alarm Battery") {
      result = await fireAlarmBatteryBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Vertical Transportation" && calc_type === "Elevator Traffic Analysis") {
      result = await elevatorTrafficBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Vertical Transportation" && calc_type === "Hoist Capacity") {
      result = await hoistCapacityBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "HVAC Systems" && calc_type === "Chiller System — Air Cooled") {
      result = await chillerAirCooledBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "HVAC Systems" && calc_type === "Chiller System — Water Cooled") {
      result = await chillerWaterCooledBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "HVAC Systems" && calc_type === "AHU Sizing") {
      result = await ahuBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "HVAC Systems" && calc_type === "Cooling Tower Sizing") {
      result = await coolingTowerBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "HVAC Systems" && calc_type === "Duct Sizing (Equal Friction)") {
      result = await ductSizingBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "HVAC Systems" && calc_type === "Refrigerant Pipe Sizing") {
      result = await refrigPipeSizingBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "HVAC Systems" && calc_type === "FCU Selection") {
      result = await fcuSelectionBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "HVAC Systems" && calc_type === "Expansion Tank Sizing") {
      result = await expansionTankBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "HVAC Systems" && calc_type === "Heat Exchanger") {
      result = await heatExchangerBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Machine Design" && calc_type === "Shaft Design") {
      result = await shaftDesignBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Machine Design" && (calc_type === "Gear / Belt Drive" || calc_type === "V-Belt Drive Design")) {
      result = await gearBeltDriveBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Machine Design" && calc_type === "Bearing Life (L10)") {
      result = await bearingLifeBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Machine Design" && calc_type === "Bolt Torque & Preload") {
      result = await boltTorqueBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Machine Design" && calc_type === "Beam / Column Design") {
      result = await beamColumnBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Machine Design" && calc_type === "Pressure Vessel") {
      result = await pressureVesselBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Machine Design" && calc_type === "Heat Exchanger") {
      result = await heatExchangerBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Machine Design" && calc_type === "Vibration Analysis") {
      result = await vibrationAnalysisBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Machine Design" && calc_type === "Fluid Power") {
      result = await fluidPowerBomSowAgent(calc_inputs || {}, calc_results);
    } else if (discipline === "Machine Design" && calc_type === "Noise / Acoustics") {
      result = await noiseAcousticsBomSowAgent(calc_inputs || {}, calc_results);
    } else {
      return new Response(
        JSON.stringify({ error: `BOM+SOW not yet available for ${discipline} / ${calc_type}` }),
        { status: 422, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    result.bom_items = sanitizeBomItems(result.bom_items);
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
