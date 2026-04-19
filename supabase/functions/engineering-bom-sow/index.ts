import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// ─── Gemini Flash REST helper ─────────────────────────────────────────────────

async function callGemini(prompt: string): Promise<string> {
  const GEMINI_KEY = Deno.env.get("GEMINI_API_KEY") || "";
  const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${GEMINI_KEY}`;

  const body = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: {
      temperature: 0.2,
      responseMimeType: "application/json",
    },
  };

  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const err = await res.text();
    throw new Error(`Gemini API error ${res.status}: ${err}`);
  }

  const data = await res.json();
  return data?.candidates?.[0]?.content?.parts?.[0]?.text || "{}";
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

  const raw = await callGemini(prompt);
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
    const { discipline, calc_type, calc_inputs, calc_results } = await req.json();

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
