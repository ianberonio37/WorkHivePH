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
