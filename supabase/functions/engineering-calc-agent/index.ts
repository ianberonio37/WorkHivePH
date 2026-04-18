import { serve } from "https://deno.land/std@0.168.0/http/server.ts";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
};

// ─── HVAC Lookup Tables (Philippine Tropical Climate) ───────────────────────

const U_VALUES: Record<string, number> = {
  "Standard":  0.45,
  "Good":      0.35,
  "Excellent": 0.25,
};

const ROOF_U_VALUES: Record<string, number> = {
  "Standard":  0.50,
  "Good":      0.38,
  "Excellent": 0.28,
};

const GLASS_SHGC: Record<string, number> = {
  "Standard":  0.87,
  "Tinted":    0.55,
  "LowE":      0.35,
};

const HEAT_PER_PERSON: Record<string, { sensible: number; latent: number }> = {
  "Office":           { sensible: 75,  latent: 55  },
  "Conference":       { sensible: 75,  latent: 55  },
  "Server Room":      { sensible: 0,   latent: 0   },
  "Production Floor": { sensible: 90,  latent: 90  },
  "Warehouse":        { sensible: 90,  latent: 90  },
  "Retail":           { sensible: 75,  latent: 55  },
};

const LIGHTING_WPM2: Record<string, number> = {
  "Office":           12,
  "Conference":       12,
  "Server Room":      8,
  "Production Floor": 15,
  "Warehouse":        8,
  "Retail":           20,
};

const AC_SIZES_KW = [0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.5, 10.0, 12.5, 15.0, 20.0, 25.0];

function roundUpToACSize(kw: number): number {
  return AC_SIZES_KW.find(s => s >= kw) || kw;
}

// ─── HVAC Cooling Load Calculation (Simplified Total Heat Gain) ──────────────

function calcHVACCoolingLoad(inputs: Record<string, number | string>) {
  const floorArea     = Number(inputs.floor_area);
  const ceilingHeight = Number(inputs.ceiling_height);
  const wallArea      = Number(inputs.wall_area) || (Math.sqrt(floorArea) * 4 * ceilingHeight);
  const glassArea     = Number(inputs.glass_area) || (wallArea * 0.20);
  const persons       = Number(inputs.persons);
  const equipKW       = Number(inputs.equipment_kw);
  const outdoorTemp   = Number(inputs.outdoor_temp)  || 35;
  const indoorTemp    = Number(inputs.indoor_temp)   || 24;
  const insulation    = String(inputs.insulation     || "Standard");
  const glassType     = String(inputs.glass_type     || "Standard");
  const roomFunction  = String(inputs.room_function  || "Office");

  const deltaT = outdoorTemp - indoorTemp;

  const uWall  = U_VALUES[insulation]      || 0.45;
  const qWalls = uWall * (wallArea - glassArea) * deltaT;

  const roofArea = floorArea;
  const uRoof  = ROOF_U_VALUES[insulation] || 0.50;
  const qRoof  = uRoof * roofArea * deltaT * 1.15;

  const shgc   = GLASS_SHGC[glassType]    || 0.87;
  const qGlass = (0.57 * glassArea * deltaT) + (glassArea * shgc * 200);

  const heatPP  = HEAT_PER_PERSON[roomFunction] || { sensible: 75, latent: 55 };
  const qPeople = persons * (heatPP.sensible + heatPP.latent);

  const qEquipment = equipKW * 1000 * 0.85;

  const litWpm2   = LIGHTING_WPM2[roomFunction] || 12;
  const qLighting = litWpm2 * floorArea;

  const volume        = floorArea * ceilingHeight;
  const qInfiltration = 0.5 * volume * 0.35 * deltaT;

  const qSensibleTotal = qWalls + qRoof + qGlass + qPeople + qEquipment + qLighting + qInfiltration;
  const qLatent        = qPeople * 0.42;
  const qTotal         = qSensibleTotal + qLatent;
  const qDesign        = qTotal * 1.10;

  const kW = qDesign / 1000;
  const TR = kW / 3.517;

  const recommendedKW = roundUpToACSize(kW);
  const recommendedTR = recommendedKW / 3.517;

  return {
    components: {
      q_walls:        Math.round(qWalls),
      q_roof:         Math.round(qRoof),
      q_glass:        Math.round(qGlass),
      q_people:       Math.round(qPeople),
      q_equipment:    Math.round(qEquipment),
      q_lighting:     Math.round(qLighting),
      q_infiltration: Math.round(qInfiltration),
    },
    q_sensible_total: Math.round(qSensibleTotal),
    q_latent:         Math.round(qLatent),
    q_total:          Math.round(qTotal),
    q_design:         Math.round(qDesign),
    kW:               Math.round(kW * 100) / 100,
    TR:               Math.round(TR * 100) / 100,
    recommended_kW:   recommendedKW,
    recommended_TR:   Math.round(recommendedTR * 100) / 100,
    inputs_used: {
      wall_area:       Math.round(wallArea),
      glass_area:      Math.round(glassArea),
      roof_area:       Math.round(floorArea),
      u_wall:          uWall,
      u_roof:          uRoof,
      shgc:            shgc,
      delta_t:         deltaT,
      lighting_wpm2:   litWpm2,
      heat_per_person: heatPP,
    }
  };
}

// ─── Ventilation / ACH Calculation (ASHRAE 62.1 Ventilation Rate Procedure) ──

// Rp = outdoor air per person (L/s/person), Ra = per unit area (L/s/m²)
const VENTILATION_RATES: Record<string, { rp: number; ra: number; min_ach: number; label: string }> = {
  "Office":           { rp: 2.5, ra: 0.30, min_ach: 6,  label: "Office - General" },
  "Conference":       { rp: 2.5, ra: 0.30, min_ach: 10, label: "Conference / Meeting Room" },
  "Server Room":      { rp: 0.0, ra: 0.00, min_ach: 20, label: "Server Room / Data Center" },
  "Production Floor": { rp: 2.5, ra: 0.50, min_ach: 10, label: "Production / Manufacturing Floor" },
  "Warehouse":        { rp: 0.0, ra: 0.15, min_ach: 4,  label: "Warehouse / Storage" },
  "Toilet / CR":      { rp: 0.0, ra: 0.00, min_ach: 10, label: "Toilet / Comfort Room (exhaust)" },
  "Kitchen":          { rp: 0.0, ra: 0.00, min_ach: 15, label: "Commercial Kitchen (exhaust)" },
  "Laboratory":       { rp: 2.5, ra: 0.50, min_ach: 10, label: "Laboratory" },
  "Lobby":            { rp: 2.5, ra: 0.30, min_ach: 4,  label: "Lobby / Reception" },
  "Hospital Ward":    { rp: 2.5, ra: 0.30, min_ach: 6,  label: "Hospital Ward" },
};

// Standard fan sizes in CMH (cubic meters per hour)
const FAN_SIZES_CMH = [100,150,200,300,400,500,600,750,1000,1200,1500,2000,2500,3000,4000,5000,6000,8000,10000];

function roundUpToFanSize(cmh: number): number {
  return FAN_SIZES_CMH.find(s => s >= cmh) || Math.ceil(cmh / 500) * 500;
}

function calcVentilationACH(inputs: Record<string, number | string>) {
  const floorArea     = Number(inputs.floor_area);
  const ceilingHeight = Number(inputs.ceiling_height) || 3.0;
  const persons       = Number(inputs.persons)        || 0;
  const roomFunction  = String(inputs.room_function   || "Office");
  const ventType      = String(inputs.vent_type       || "Supply and Exhaust");

  const volume = floorArea * ceilingHeight; // m3

  const rates = VENTILATION_RATES[roomFunction] || { rp: 2.5, ra: 0.30, min_ach: 6, label: roomFunction };

  // ASHRAE 62.1 Ventilation Rate Procedure
  // Breathing zone outdoor airflow (L/s)
  let vbz = (rates.rp * persons) + (rates.ra * floorArea);

  // For exhaust-only rooms (toilet, kitchen), use minimum ACH method
  const useMinACH = (rates.rp === 0 && rates.ra === 0);
  if (useMinACH) {
    vbz = (rates.min_ach * volume) / 3.6; // convert CMH to L/s: divide by 3.6
  }

  // Required ACH from ASHRAE calc
  const achFromASHRAE = (vbz * 3.6) / volume; // L/s to CMH: multiply by 3.6, then / volume

  // Use the more conservative of ASHRAE calc vs minimum ACH
  const requiredACH = Math.max(achFromASHRAE, rates.min_ach);

  // Supply airflow
  const supplyAirflow_CMH = requiredACH * volume;          // m3/hr
  const supplyAirflow_LS  = supplyAirflow_CMH / 3.6;       // L/s
  const supplyAirflow_CFM = supplyAirflow_LS * 2.119;      // CFM

  // Design airflow with 15% safety margin
  const designAirflow_CMH = supplyAirflow_CMH * 1.15;
  const designAirflow_CFM = supplyAirflow_CFM * 1.15;

  // Fan sizing
  const recommendedFan_CMH = roundUpToFanSize(designAirflow_CMH);
  const recommendedFan_CFM = Math.round(recommendedFan_CMH / 3.6 * 2.119);

  // Outdoor air fraction (if supply+exhaust, outdoor air = vbz)
  const outdoorAir_CMH = vbz * 3.6;
  const outdoorAir_CFM = vbz * 2.119;

  return {
    room_volume:          Math.round(volume * 10) / 10,
    vbz_ls:               Math.round(vbz * 10) / 10,
    ach_ashrae:           Math.round(achFromASHRAE * 100) / 100,
    required_ach:         Math.round(requiredACH * 100) / 100,
    min_ach_required:     rates.min_ach,
    supply_cmh:           Math.round(supplyAirflow_CMH),
    supply_ls:            Math.round(supplyAirflow_LS * 10) / 10,
    supply_cfm:           Math.round(supplyAirflow_CFM),
    design_cmh:           Math.round(designAirflow_CMH),
    design_cfm:           Math.round(designAirflow_CFM),
    recommended_fan_cmh:  recommendedFan_CMH,
    recommended_fan_cfm:  recommendedFan_CFM,
    outdoor_air_cmh:      Math.round(outdoorAir_CMH),
    outdoor_air_cfm:      Math.round(outdoorAir_CFM),
    inputs_used: {
      rp:           rates.rp,
      ra:           rates.ra,
      min_ach:      rates.min_ach,
      space_label:  rates.label,
      vent_type:    ventType,
      use_min_ach:  useMinACH,
    }
  };
}

// ─── Gemini AI — Report Narrative ────────────────────────────────────────────

async function generateReportNarrative(
  calcType: string,
  inputs: Record<string, number | string>,
  results: Record<string, unknown>
): Promise<{ objective: string; assumptions: string; recommendations: string }> {

  const GEMINI_API_KEY = Deno.env.get("GEMINI_API_KEY");
  if (!GEMINI_API_KEY) {
    return {
      objective: "To determine the required cooling load and recommend appropriate air conditioning capacity for the subject space.",
      assumptions: "Standard Philippine tropical climate conditions applied. Outdoor design conditions: 35°C DB / 28°C WB. Indoor design conditions: 24°C / 55% RH. Safety factor of 10% applied to total heat gain.",
      recommendations: "Provide air conditioning unit(s) with a minimum combined capacity as computed. Ensure proper ventilation per ASHRAE 62.1 minimum outdoor air requirements.",
    };
  }

  const prompt = `You are a licensed Mechanical Engineer in the Philippines writing a professional design calculation report.
Calculation type: ${calcType}
Inputs: ${JSON.stringify(inputs, null, 2)}
Results: ${JSON.stringify(results, null, 2)}

Write three short professional sections (2-4 sentences each):
1. OBJECTIVE - what this calculation determines and why
2. ASSUMPTIONS - key design assumptions and conditions used
3. RECOMMENDATIONS - what to specify or install based on results

Respond in JSON format only:
{
  "objective": "...",
  "assumptions": "...",
  "recommendations": "..."
}`;

  const res = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${GEMINI_API_KEY}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: { temperature: 0.3, maxOutputTokens: 512 },
      }),
    }
  );

  const json = await res.json();
  const text = json?.candidates?.[0]?.content?.parts?.[0]?.text || "";
  const cleaned = text.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();

  try {
    return JSON.parse(cleaned);
  } catch {
    return {
      objective: "To determine the required cooling load and recommend appropriate air conditioning capacity for the subject space.",
      assumptions: "Standard Philippine tropical climate conditions applied. Outdoor design conditions: 35°C DB / 28°C WB. Indoor design conditions: 24°C / 55% RH. Safety factor of 10% applied to total heat gain.",
      recommendations: `Provide air conditioning unit(s) with minimum capacity of ${(results as Record<string, unknown>).recommended_kW} kW (${(results as Record<string, unknown>).recommended_TR} TR). Ensure proper ventilation per ASHRAE 62.1.`,
    };
  }
}

// ─── Main Handler ─────────────────────────────────────────────────────────────

serve(async (req) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: corsHeaders });
  }

  try {
    const { calc_type, inputs } = await req.json();

    if (!calc_type || !inputs) {
      return new Response(
        JSON.stringify({ error: "Missing calc_type or inputs" }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    let results: Record<string, unknown>;

    if (calc_type === "HVAC Cooling Load") {
      results = calcHVACCoolingLoad(inputs);
    } else if (calc_type === "Ventilation / ACH") {
      results = calcVentilationACH(inputs);
    } else {
      return new Response(
        JSON.stringify({ error: `Calculation type "${calc_type}" not yet implemented.` }),
        { status: 400, headers: { ...corsHeaders, "Content-Type": "application/json" } }
      );
    }

    const narrative = await generateReportNarrative(calc_type, inputs, results);

    return new Response(
      JSON.stringify({ results, narrative }),
      { headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );

  } catch (err) {
    return new Response(
      JSON.stringify({ error: String(err) }),
      { status: 500, headers: { ...corsHeaders, "Content-Type": "application/json" } }
    );
  }
});
