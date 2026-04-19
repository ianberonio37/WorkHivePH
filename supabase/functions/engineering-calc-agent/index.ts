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

// ─── Pump Sizing (TDH) Calculation ───────────────────────────────────────────
// Method: Darcy-Weisbach for friction head + static head + velocity head + fittings
// Standards: PSME, ASHRAE, Hydraulic Institute

// Pipe friction factor approximation (Hazen-Williams C factor → converted to Darcy-Weisbach)
// We use Hazen-Williams formula: V = 0.8492 * C * R^0.63 * S^0.54
// For simplicity in field design: use explicit head loss formula

const PIPE_C_VALUES: Record<string, number> = {
  "PVC":                 150,
  "Galvanized Steel":    120,
  "Cast Iron":           100,
  "Stainless Steel":     140,
  "HDPE":                150,
  "Copper":              140,
};

// Standard pump HP sizes (commercial pumps available in PH)
const PUMP_HP_SIZES = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 75.0, 100.0];

function roundUpToPumpHP(hp: number): number {
  return PUMP_HP_SIZES.find(s => s >= hp) || Math.ceil(hp / 5) * 5;
}

// Standard pipe sizes (nominal diameter in mm)
const PIPE_SIZES_MM = [15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400];

// Recommended velocity range: 0.9 - 3.0 m/s for water in pipes
// Select pipe diameter to keep velocity between 1.0 - 2.5 m/s
function selectPipeDiameter(flowM3s: number, targetVelocity = 1.5): number {
  // A = Q / V, D = sqrt(4A/pi)
  const area = flowM3s / targetVelocity;
  const diamM = Math.sqrt((4 * area) / Math.PI);
  const diamMM = diamM * 1000;
  return PIPE_SIZES_MM.find(d => d >= diamMM) || Math.ceil(diamMM / 25) * 25;
}

function calcPumpSizingTDH(inputs: Record<string, number | string>) {
  const flowRate       = Number(inputs.flow_rate);       // L/min
  const staticHead     = Number(inputs.static_head);     // m (suction + discharge elevation diff)
  const pipeLength     = Number(inputs.pipe_length);     // m (total equivalent length)
  const pipeDiaInput   = Number(inputs.pipe_diameter);   // mm (0 = auto-select)
  const pipeMaterial   = String(inputs.pipe_material || "PVC");
  const pumpEfficiency = Number(inputs.pump_efficiency) || 70; // %
  const motorEfficiency= Number(inputs.motor_efficiency) || 90; // %
  const fluidDensity   = Number(inputs.fluid_density)   || 1000; // kg/m3 (water=1000)
  const pressureHead   = Number(inputs.pressure_head)   || 0;   // m (discharge pressure requirement)
  const fittingsAllowance = Number(inputs.fittings_allowance) || 20; // % extra for fittings

  // Convert flow rate to m3/s
  const flowM3s  = flowRate / (1000 * 60); // L/min to m3/s
  const flowM3hr = flowRate * 60 / 1000;   // L/min to m3/hr

  // Auto-select or use input pipe diameter
  const pipeDiaMM = pipeDiaInput > 0 ? pipeDiaInput : selectPipeDiameter(flowM3s);
  const pipeDiaM  = pipeDiaMM / 1000;
  const pipeArea  = Math.PI * Math.pow(pipeDiaM / 2, 2); // m2

  // Flow velocity
  const velocity = flowM3s / pipeArea; // m/s

  // Hazen-Williams friction head loss
  // hf = (10.67 * L * Q^1.852) / (C^1.852 * D^4.87)
  // where Q in m3/s, D in m, L in m
  const C = PIPE_C_VALUES[pipeMaterial] || 150;
  const hfBase = (10.67 * pipeLength * Math.pow(flowM3s, 1.852)) / (Math.pow(C, 1.852) * Math.pow(pipeDiaM, 4.87));

  // Add fittings allowance
  const hfTotal = hfBase * (1 + fittingsAllowance / 100);

  // Velocity head
  const g = 9.81;
  const velocityHead = Math.pow(velocity, 2) / (2 * g);

  // Total Dynamic Head
  const TDH = staticHead + hfTotal + velocityHead + pressureHead;

  // Hydraulic power (kW)
  const hydraulicPower = (fluidDensity * g * flowM3s * TDH) / 1000; // kW

  // Brake power (shaft power, accounting for pump efficiency)
  const brakePower = hydraulicPower / (pumpEfficiency / 100); // kW

  // Motor power (accounting for motor efficiency)
  const motorPower = brakePower / (motorEfficiency / 100); // kW

  // Convert to HP
  const motorHP = motorPower / 0.7457;

  // Round up to next standard pump HP
  const recommendedHP = roundUpToPumpHP(motorHP);
  const recommendedKW = Math.round(recommendedHP * 0.7457 * 100) / 100;

  // NPSH available estimate (simplified, assumes suction lift scenario)
  const suctionHead  = Number(inputs.suction_head) || 0; // m (positive = flooded, negative = lift)
  const vaporPressure = 0.25; // m at 30°C water approximation
  const atmHead = 10.33; // m water at sea level (Philippine coastal plants)
  const npshA = atmHead + suctionHead - vaporPressure - (hfBase * 0.3); // simplified

  return {
    // Flow
    flow_lpm:         flowRate,
    flow_m3hr:        Math.round(flowM3hr * 100) / 100,
    // Pipe
    pipe_dia_mm:      pipeDiaMM,
    pipe_velocity:    Math.round(velocity * 100) / 100,
    velocity_ok:      velocity >= 0.9 && velocity <= 3.0,
    // Head components
    static_head:      Math.round(staticHead * 100) / 100,
    friction_head:    Math.round(hfTotal * 100) / 100,
    velocity_head:    Math.round(velocityHead * 100) / 100,
    pressure_head:    Math.round(pressureHead * 100) / 100,
    TDH:              Math.round(TDH * 100) / 100,
    // Power
    hydraulic_kw:     Math.round(hydraulicPower * 100) / 100,
    brake_kw:         Math.round(brakePower * 100) / 100,
    motor_kw:         Math.round(motorPower * 100) / 100,
    motor_hp:         Math.round(motorHP * 100) / 100,
    recommended_hp:   recommendedHP,
    recommended_kw:   recommendedKW,
    // NPSH
    npsh_available:   Math.round(npshA * 100) / 100,
    // Efficiencies used
    inputs_used: {
      pipe_material:       pipeMaterial,
      C_factor:            C,
      pipe_dia_mm:         pipeDiaMM,
      pipe_dia_source:     pipeDiaInput > 0 ? "User input" : "Auto-selected",
      fittings_allowance:  fittingsAllowance,
      pump_efficiency:     pumpEfficiency,
      motor_efficiency:    motorEfficiency,
      fluid_density:       fluidDensity,
      hf_base:             Math.round(hfBase * 100) / 100,
    }
  };
}

// ─── Pipe Sizing Calculation (Velocity Method + Hazen-Williams) ──────────────
// Standards: PSME, ASHRAE, ASHRAE Plumbing Engineering Design Guide
// Selects pipe diameter to keep velocity within acceptable range,
// then computes pressure drop per metre and total friction loss.

// Velocity limits by service type (m/s)
const VELOCITY_LIMITS: Record<string, { min: number; max: number; recommended: number; label: string }> = {
  "Chilled Water Supply":  { min: 0.6, max: 3.0, recommended: 1.5, label: "Chilled Water Supply" },
  "Chilled Water Return":  { min: 0.6, max: 3.0, recommended: 1.2, label: "Chilled Water Return" },
  "Hot Water Supply":      { min: 0.6, max: 3.0, recommended: 1.5, label: "Hot Water Supply" },
  "Condenser Water":       { min: 0.9, max: 3.5, recommended: 2.0, label: "Condenser Water" },
  "Cold Water Supply":     { min: 0.6, max: 2.5, recommended: 1.2, label: "Cold Water Supply (Domestic)" },
  "Fire Protection":       { min: 1.5, max: 4.5, recommended: 3.0, label: "Fire Protection / Sprinkler" },
  "Steam":                 { min: 10,  max: 40,  recommended: 25,  label: "Steam (Low Pressure)" },
  "Compressed Air":        { min: 5,   max: 15,  recommended: 8,   label: "Compressed Air" },
  "General Water":         { min: 0.6, max: 3.0, recommended: 1.5, label: "General Water Service" },
};

function calcPipeSizing(inputs: Record<string, number | string>) {
  const flowLPM       = Number(inputs.flow_rate);        // L/min
  const pipeLength    = Number(inputs.pipe_length);      // m
  const serviceType   = String(inputs.service_type || "General Water");
  const pipeMaterial  = String(inputs.pipe_material || "PVC");
  const fittingsPct   = Number(inputs.fittings_allowance) || 20; // %
  const fluidDensity  = Number(inputs.fluid_density) || 1000;    // kg/m3

  const flowM3s  = flowLPM / (1000 * 60);
  const flowM3hr = flowLPM * 60 / 1000;
  const flowLPS  = flowLPM / 60;

  const limits = VELOCITY_LIMITS[serviceType] || VELOCITY_LIMITS["General Water"];
  const C      = PIPE_C_VALUES[pipeMaterial] || 150;
  const g      = 9.81;

  // Try each standard pipe size and find the best fit
  const candidates = PIPE_SIZES_MM.map(dMM => {
    const dM   = dMM / 1000;
    const area = Math.PI * Math.pow(dM / 2, 2);
    const v    = flowM3s / area;
    // Hazen-Williams head loss per metre (m/m)
    const hfPerM = (10.67 * Math.pow(flowM3s, 1.852)) / (Math.pow(C, 1.852) * Math.pow(dM, 4.87));
    const pressDropPerM = hfPerM * fluidDensity * g / 1000; // kPa/m
    return { dMM, v, hfPerM, pressDropPerM };
  });

  // Recommended: smallest pipe that keeps velocity <= max AND >= min
  const recommended = candidates.find(c => c.v <= limits.max && c.v >= limits.min)
    || candidates.find(c => c.v <= limits.max)
    || candidates[candidates.length - 1];

  // Also compute for one size smaller (to show comparison)
  const smallerIdx = PIPE_SIZES_MM.indexOf(recommended.dMM) - 1;
  const smaller = smallerIdx >= 0 ? candidates[smallerIdx] : null;

  // Total friction loss for recommended pipe
  const equivLength  = pipeLength * (1 + fittingsPct / 100); // equivalent pipe length incl fittings
  const hfTotal      = recommended.hfPerM * equivLength;     // m
  const pressDropTot = recommended.pressDropPerM * equivLength; // kPa

  // Velocity head
  const velocityHead = Math.pow(recommended.v, 2) / (2 * g); // m

  // Reynolds number (approximate, for water at ~30°C: kinematic viscosity ~0.8e-6 m2/s)
  const nu = 0.8e-6; // m2/s kinematic viscosity water at 30°C
  const Re = (recommended.v * (recommended.dMM / 1000)) / nu;
  const flowRegime = Re < 2300 ? "Laminar" : Re < 4000 ? "Transitional" : "Turbulent";

  // Build size comparison table (±2 sizes around recommended)
  const recIdx = PIPE_SIZES_MM.indexOf(recommended.dMM);
  const compRange = candidates.slice(Math.max(0, recIdx - 2), recIdx + 3);

  return {
    // Flow
    flow_lpm:          flowLPM,
    flow_m3hr:         Math.round(flowM3hr * 100) / 100,
    flow_lps:          Math.round(flowLPS * 100) / 100,
    // Recommended pipe
    recommended_dia_mm:    recommended.dMM,
    recommended_velocity:  Math.round(recommended.v * 100) / 100,
    velocity_ok:           recommended.v >= limits.min && recommended.v <= limits.max,
    velocity_min:          limits.min,
    velocity_max:          limits.max,
    velocity_recommended:  limits.recommended,
    // Friction losses
    hf_per_m:          Math.round(recommended.hfPerM * 1000) / 1000,  // m/m
    press_drop_per_m:  Math.round(recommended.pressDropPerM * 1000) / 1000, // kPa/m
    equiv_length:      Math.round(equivLength * 10) / 10,
    hf_total:          Math.round(hfTotal * 100) / 100,
    press_drop_total:  Math.round(pressDropTot * 100) / 100,
    velocity_head:     Math.round(velocityHead * 1000) / 1000,
    // Flow regime
    reynolds_number:   Math.round(Re),
    flow_regime:       flowRegime,
    // Comparison table
    size_comparison: compRange.map(c => ({
      dia_mm:         c.dMM,
      velocity:       Math.round(c.v * 100) / 100,
      hf_per_m:       Math.round(c.hfPerM * 1000) / 1000,
      press_kpa_m:    Math.round(c.pressDropPerM * 1000) / 1000,
      recommended:    c.dMM === recommended.dMM,
    })),
    inputs_used: {
      service_type:   serviceType,
      pipe_material:  pipeMaterial,
      C_factor:       C,
      fittings_pct:   fittingsPct,
      equiv_length:   Math.round(equivLength * 10) / 10,
      velocity_limits: limits,
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
    } else if (calc_type === "Pump Sizing (TDH)") {
      results = calcPumpSizingTDH(inputs);
    } else if (calc_type === "Pipe Sizing") {
      results = calcPipeSizing(inputs);
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
