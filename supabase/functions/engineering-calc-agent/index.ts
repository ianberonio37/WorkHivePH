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

// ─── Compressed Air System Calculation ───────────────────────────────────────
// Method: Connected load method with demand factor + diversity factor
// Standards: PSME, ISO 8573, Compressed Air & Gas Institute (CAGI)
// Output: Required compressor FAD (Free Air Delivery) in CFM and L/s,
//         receiver tank size, and distribution pipe sizing.

// Tool demand factors (% of rated consumption actually used simultaneously)
const TOOL_DEMAND: Record<string, { cfm: number; label: string; duty: number }> = {
  "Angle Grinder":      { cfm: 5.0,  label: "Angle Grinder (4-5 in)",     duty: 0.25 },
  "Impact Wrench 1/2":  { cfm: 4.0,  label: "Impact Wrench (1/2 in)",      duty: 0.25 },
  "Impact Wrench 3/4":  { cfm: 7.0,  label: "Impact Wrench (3/4 in)",      duty: 0.25 },
  "Air Drill":          { cfm: 3.0,  label: "Air Drill",                   duty: 0.30 },
  "Die Grinder":        { cfm: 4.0,  label: "Die Grinder",                 duty: 0.25 },
  "Blow Gun":           { cfm: 2.5,  label: "Blow Gun / Air Duster",       duty: 0.20 },
  "Sand Blaster":       { cfm: 50.0, label: "Sand / Bead Blaster",         duty: 0.50 },
  "Paint Spray Gun":    { cfm: 12.0, label: "Spray Paint Gun",             duty: 0.40 },
  "Pneumatic Cylinder": { cfm: 2.0,  label: "Pneumatic Cylinder (small)",  duty: 0.50 },
  "Air Hammer":         { cfm: 3.5,  label: "Air Hammer / Chisel",         duty: 0.20 },
  "Ratchet Wrench":     { cfm: 2.5,  label: "Ratchet Wrench",              duty: 0.20 },
  "Air Sander":         { cfm: 6.0,  label: "Air Sander (random orbital)", duty: 0.30 },
  "Needle Scaler":      { cfm: 4.0,  label: "Needle Scaler",               duty: 0.25 },
  "Air Saw":            { cfm: 5.0,  label: "Air Saw (reciprocating)",     duty: 0.20 },
  "Custom":             { cfm: 0.0,  label: "Custom Tool",                 duty: 0.50 },
};

// Standard compressor sizes (HP → FAD in CFM approx)
const COMPRESSOR_HP_CFM: Array<{ hp: number; cfm: number }> = [
  { hp: 1,   cfm: 4   }, { hp: 2,   cfm: 8   }, { hp: 3,   cfm: 12  },
  { hp: 5,   cfm: 20  }, { hp: 7.5, cfm: 30  }, { hp: 10,  cfm: 40  },
  { hp: 15,  cfm: 60  }, { hp: 20,  cfm: 80  }, { hp: 25,  cfm: 100 },
  { hp: 30,  cfm: 120 }, { hp: 40,  cfm: 160 }, { hp: 50,  cfm: 200 },
  { hp: 60,  cfm: 240 }, { hp: 75,  cfm: 300 }, { hp: 100, cfm: 400 },
];

function roundUpToCompressorHP(cfm: number): { hp: number; cfm: number } {
  return COMPRESSOR_HP_CFM.find(c => c.cfm >= cfm) || { hp: Math.ceil(cfm / 4), cfm };
}

function calcCompressedAir(inputs: Record<string, number | string>) {
  // Parse tool entries: array of { tool_type, quantity, custom_cfm }
  const tools = inputs.tools as Array<{ tool_type: string; quantity: number; custom_cfm?: number }> || [];
  const workingPressure   = Number(inputs.working_pressure)    || 7.0;  // bar(g)
  const diversityFactor   = Number(inputs.diversity_factor)    || 0.70; // 70% default
  const safetyFactor      = Number(inputs.safety_factor)       || 1.25; // 25% margin
  const pipeLength        = Number(inputs.pipe_length)         || 0;    // m distribution
  const leakagePct        = Number(inputs.leakage_allowance)   || 10;   // % for leakage
  const receiverPressure  = workingPressure + 1.5;                      // bar(a) cut-in
  const atmPressure       = 1.01325;                                    // bar(a)

  // Sum connected load (CFM at working pressure, free air equivalent)
  const toolBreakdown = tools.map(t => {
    const info   = TOOL_DEMAND[t.tool_type] || TOOL_DEMAND["Custom"];
    const cfmPer = t.tool_type === "Custom" ? (t.custom_cfm || 0) : info.cfm;
    const qty    = Number(t.quantity) || 1;
    const totalCFM = cfmPer * qty;
    const demandCFM = totalCFM * info.duty;  // demand-weighted
    return {
      tool:       info.label || t.tool_type,
      qty,
      cfm_each:   cfmPer,
      total_cfm:  Math.round(totalCFM * 10) / 10,
      duty:       info.duty,
      demand_cfm: Math.round(demandCFM * 10) / 10,
    };
  });

  const connectedCFM = toolBreakdown.reduce((s, t) => s + t.total_cfm, 0);
  const demandCFM    = toolBreakdown.reduce((s, t) => s + t.demand_cfm, 0);

  // Apply diversity factor (not all tools run simultaneously)
  const diversityCFM = demandCFM * diversityFactor;

  // Add leakage allowance
  const leakageCFM   = diversityCFM * (leakagePct / 100);
  const totalCFM     = diversityCFM + leakageCFM;

  // Apply safety factor
  const designCFM    = totalCFM * safetyFactor;

  // Convert to L/s and m3/min
  const designLPS    = designCFM * 0.4719;
  const designM3min  = designCFM * 0.02832;

  // Select standard compressor
  const compressor = roundUpToCompressorHP(designCFM);

  // Receiver tank sizing (CAGI method)
  // V = (Q x t x Pa) / (P1 - P2)
  // Q = compressor FAD (m3/min), t = on-time (min), Pa = atm pressure (bar), P1-P2 = pressure differential
  const Q_m3min  = compressor.cfm * 0.02832;
  const t_min    = 1.0;           // 1 minute on-time assumption
  const P1       = receiverPressure;
  const P2       = workingPressure;
  const receiverM3 = (Q_m3min * t_min * atmPressure) / (P1 - P2);
  const receiverL  = receiverM3 * 1000;

  // Round up to standard receiver sizes (litres)
  const STD_RECEIVERS = [100,150,200,300,500,750,1000,1500,2000,3000,5000];
  const recommendedReceiver = STD_RECEIVERS.find(r => r >= receiverL) || Math.ceil(receiverL / 100) * 100;

  // Distribution pipe sizing for compressed air
  // Use velocity method: recommended 6-10 m/s for distribution headers
  // Flow in SCFM at atmospheric conditions
  const atmFlowM3s = designLPS / 1000; // m3/s at atm
  // At working pressure, volume is reduced: V_system = V_atm * Pa / P_system
  const P_abs = workingPressure + atmPressure;
  const sysFlowM3s = atmFlowM3s * (atmPressure / P_abs);
  const targetV  = 8.0; // m/s recommended for distribution
  const areaNeed = sysFlowM3s / targetV;
  const diaNeed  = Math.sqrt((4 * areaNeed) / Math.PI) * 1000; // mm
  const recPipeMM = PIPE_SIZES_MM.find(d => d >= diaNeed) || Math.ceil(diaNeed / 25) * 25;

  return {
    // Connected load
    connected_cfm:       Math.round(connectedCFM * 10) / 10,
    demand_cfm:          Math.round(demandCFM * 10) / 10,
    diversity_cfm:       Math.round(diversityCFM * 10) / 10,
    leakage_cfm:         Math.round(leakageCFM * 10) / 10,
    total_cfm:           Math.round(totalCFM * 10) / 10,
    design_cfm:          Math.round(designCFM * 10) / 10,
    design_lps:          Math.round(designLPS * 10) / 10,
    design_m3min:        Math.round(designM3min * 100) / 100,
    // Compressor selection
    recommended_hp:      compressor.hp,
    recommended_cfm:     compressor.cfm,
    // Receiver
    receiver_m3:         Math.round(receiverM3 * 100) / 100,
    receiver_litres:     Math.round(receiverL),
    recommended_receiver_L: recommendedReceiver,
    // Pipe
    recommended_pipe_mm: recPipeMM,
    // Tool breakdown
    tool_breakdown:      toolBreakdown,
    inputs_used: {
      working_pressure:   workingPressure,
      diversity_factor:   diversityFactor,
      safety_factor:      safetyFactor,
      leakage_pct:        leakagePct,
    }
  };
}

// ─── Water Supply Pipe Sizing (Hunter's Fixture Unit Method) ─────────────────
// Standards: Philippine Plumbing Code (PPC), UPC, ASHRAE Plumbing Design Guide
// Method: Sum fixture units → convert to peak flow (L/s) via Hunter's curve →
//         select pipe diameter to keep velocity 0.9 - 2.5 m/s

// Fixture units and flow rates (Philippine Plumbing Code / UPC Table A-2)
const FIXTURE_UNITS: Record<string, { wfu: number; pfr_lpm: number; label: string; type: string }> = {
  "Water Closet (Flush Valve)":  { wfu: 10, pfr_lpm: 18.9, label: "Water Closet (Flush Valve)",   type: "cold" },
  "Water Closet (Flush Tank)":   { wfu: 3,  pfr_lpm: 9.5,  label: "Water Closet (Flush Tank)",    type: "cold" },
  "Urinal (Flush Valve)":        { wfu: 5,  pfr_lpm: 11.4, label: "Urinal (Flush Valve)",          type: "cold" },
  "Urinal (Flush Tank)":         { wfu: 3,  pfr_lpm: 5.7,  label: "Urinal (Flush Tank)",           type: "cold" },
  "Lavatory / Hand Sink":        { wfu: 1,  pfr_lpm: 3.8,  label: "Lavatory / Hand Sink",          type: "both" },
  "Kitchen Sink (residential)":  { wfu: 2,  pfr_lpm: 7.6,  label: "Kitchen Sink (Residential)",    type: "both" },
  "Kitchen Sink (commercial)":   { wfu: 4,  pfr_lpm: 11.4, label: "Kitchen Sink (Commercial)",     type: "both" },
  "Bathtub / Shower":            { wfu: 2,  pfr_lpm: 9.5,  label: "Bathtub / Shower",              type: "both" },
  "Shower Head":                 { wfu: 2,  pfr_lpm: 7.6,  label: "Shower Head",                   type: "both" },
  "Laundry Tray":                { wfu: 3,  pfr_lpm: 9.5,  label: "Laundry Tray",                  type: "both" },
  "Washing Machine":             { wfu: 3,  pfr_lpm: 11.4, label: "Washing Machine",                type: "both" },
  "Drinking Fountain":           { wfu: 1,  pfr_lpm: 1.9,  label: "Drinking Fountain",             type: "cold" },
  "Hose Bibb (each)":            { wfu: 3,  pfr_lpm: 11.4, label: "Hose Bibb / Garden Tap",        type: "cold" },
  "Floor Drain":                 { wfu: 1,  pfr_lpm: 3.8,  label: "Floor Drain (trap primer)",     type: "cold" },
  "Mop Sink":                    { wfu: 3,  pfr_lpm: 11.4, label: "Mop Sink",                      type: "both" },
  "Custom":                      { wfu: 0,  pfr_lpm: 0,    label: "Custom Fixture",                 type: "both" },
};

// Hunter's curve: WFU → peak flow (L/s) — piecewise interpolation
// Based on Table A-3 of Philippine Plumbing Code
const HUNTERS_CURVE: Array<{ wfu: number; lps: number }> = [
  { wfu: 1,    lps: 0.10 }, { wfu: 2,    lps: 0.13 }, { wfu: 3,    lps: 0.16 },
  { wfu: 5,    lps: 0.22 }, { wfu: 10,   lps: 0.32 }, { wfu: 20,   lps: 0.50 },
  { wfu: 30,   lps: 0.65 }, { wfu: 40,   lps: 0.76 }, { wfu: 50,   lps: 0.85 },
  { wfu: 75,   lps: 1.05 }, { wfu: 100,  lps: 1.22 }, { wfu: 150,  lps: 1.52 },
  { wfu: 200,  lps: 1.79 }, { wfu: 300,  lps: 2.25 }, { wfu: 400,  lps: 2.65 },
  { wfu: 500,  lps: 3.00 }, { wfu: 750,  lps: 3.66 }, { wfu: 1000, lps: 4.20 },
  { wfu: 1500, lps: 5.00 }, { wfu: 2000, lps: 5.70 },
];

function hunterLPS(totalWFU: number): number {
  if (totalWFU <= 0) return 0;
  const curve = HUNTERS_CURVE;
  if (totalWFU <= curve[0].wfu) return curve[0].lps;
  if (totalWFU >= curve[curve.length - 1].wfu) return curve[curve.length - 1].lps;
  for (let i = 0; i < curve.length - 1; i++) {
    if (totalWFU >= curve[i].wfu && totalWFU <= curve[i + 1].wfu) {
      const t = (totalWFU - curve[i].wfu) / (curve[i + 1].wfu - curve[i].wfu);
      return curve[i].lps + t * (curve[i + 1].lps - curve[i].lps);
    }
  }
  return 0;
}

function calcWaterSupplyPipeSizing(inputs: Record<string, number | string>) {
  const fixtures    = inputs.fixtures as Array<{ fixture_type: string; quantity: number; custom_wfu?: number; custom_lpm?: number }> || [];
  const supplyType  = String(inputs.supply_type || "Cold and Hot");
  const pipeMaterial= String(inputs.pipe_material || "PVC");
  const pipeLength  = Number(inputs.pipe_length)  || 0;
  const minPressure = Number(inputs.min_pressure) || 70;  // kPa min residual at fixture
  const supplyPress = Number(inputs.supply_pressure) || 350; // kPa available at meter/main
  const fittingsPct = Number(inputs.fittings_allowance) || 20;

  // Sum fixture units
  const fixtureBreakdown = fixtures.map(f => {
    const info   = FIXTURE_UNITS[f.fixture_type] || FIXTURE_UNITS["Custom"];
    const qty    = Number(f.quantity) || 1;
    const wfuEa  = f.fixture_type === "Custom" ? (f.custom_wfu || 1) : info.wfu;
    const lpmEa  = f.fixture_type === "Custom" ? (f.custom_lpm || 3.8) : info.pfr_lpm;
    return {
      fixture:    info.label || f.fixture_type,
      qty,
      wfu_each:   wfuEa,
      total_wfu:  wfuEa * qty,
      lpm_each:   lpmEa,
      total_lpm:  Math.round(lpmEa * qty * 10) / 10,
    };
  });

  const totalWFU = fixtureBreakdown.reduce((s, f) => s + f.total_wfu, 0);

  // Hunter's curve: WFU → peak design flow
  const peakLPS  = hunterLPS(totalWFU);
  const peakLPM  = peakLPS * 60;
  const peakM3hr = peakLPS * 3.6;

  // Select pipe diameter (velocity 0.9 - 2.5 m/s for water supply)
  const C = PIPE_C_VALUES[pipeMaterial] || 150;
  const flowM3s = peakLPS / 1000;

  const pipeCandidates = PIPE_SIZES_MM.map(dMM => {
    const dM   = dMM / 1000;
    const area = Math.PI * Math.pow(dM / 2, 2);
    const v    = flowM3s / area;
    const hfPerM = (10.67 * Math.pow(flowM3s, 1.852)) / (Math.pow(C, 1.852) * Math.pow(dM, 4.87));
    return { dMM, v, hfPerM };
  });

  const recommended = pipeCandidates.find(c => c.v <= 2.5 && c.v >= 0.9)
    || pipeCandidates.find(c => c.v <= 2.5)
    || pipeCandidates[pipeCandidates.length - 1];

  const equivLength  = pipeLength * (1 + fittingsPct / 100);
  const hfTotal      = recommended.hfPerM * equivLength;       // m head
  const pressDropKPa = hfTotal * 9.81;                         // kPa (approx, water)

  // Pressure check
  const pressAvail    = supplyPress - pressDropKPa;
  const pressureOk    = pressAvail >= minPressure;

  // Size comparison
  const recIdx    = PIPE_SIZES_MM.indexOf(recommended.dMM);
  const compRange = pipeCandidates.slice(Math.max(0, recIdx - 2), recIdx + 3);

  return {
    total_wfu:          totalWFU,
    peak_lps:           Math.round(peakLPS * 1000) / 1000,
    peak_lpm:           Math.round(peakLPM * 10) / 10,
    peak_m3hr:          Math.round(peakM3hr * 100) / 100,
    recommended_dia_mm: recommended.dMM,
    pipe_velocity:      Math.round(recommended.v * 100) / 100,
    velocity_ok:        recommended.v >= 0.9 && recommended.v <= 2.5,
    hf_per_m:           Math.round(recommended.hfPerM * 1000) / 1000,
    equiv_length:       Math.round(equivLength * 10) / 10,
    hf_total_m:         Math.round(hfTotal * 100) / 100,
    press_drop_kpa:     Math.round(pressDropKPa * 10) / 10,
    pressure_available: Math.round(pressAvail * 10) / 10,
    pressure_ok:        pressureOk,
    min_pressure:       minPressure,
    fixture_breakdown:  fixtureBreakdown,
    size_comparison: compRange.map(c => ({
      dia_mm:    c.dMM,
      velocity:  Math.round(c.v * 100) / 100,
      hf_per_m:  Math.round(c.hfPerM * 1000) / 1000,
      ok:        c.v >= 0.9 && c.v <= 2.5,
      recommended: c.dMM === recommended.dMM,
    })),
    inputs_used: { C_factor: C, pipe_material: pipeMaterial, fittings_pct: fittingsPct },
  };
}

// ─── Electrical: Load Estimation — PEC Article 2.10 / 2.20 ──────────────────
const LOAD_DEMAND_FACTOR: Record<string, number> = {
  "Lighting (General)": 1.0, "Lighting (Emergency)": 1.0,
  "Convenience Receptacles": 1.0, "Air Conditioning (Unit)": 1.0,
  "Air Conditioning (Central Chiller)": 1.0,
  "Motor (General)": 1.25, "Motor (Fire Pump)": 1.25,
  "Water Heater": 1.0, "Elevator / Escalator": 1.25,
  "Server / IT Equipment": 1.0, "Kitchen Equipment": 1.0,
  "Welding Equipment": 0.5, "Custom": 1.0,
};
const STANDARD_BREAKER_A = [15,20,30,40,50,60,70,80,90,100,125,150,175,200,225,250,300,350,400,500,600];

function calcLoadEstimation(inputs: Record<string, number | string>): Record<string, unknown> {
  const loads      = inputs.loads as Array<{ load_type: string; quantity: number; watts_each: number; power_factor: number }> || [];
  const phaseConfig = String(inputs.phase_config || "3-Phase 4-Wire (400V)");
  const isThreePhase = phaseConfig.includes("3-Phase");
  const voltage    = isThreePhase ? 400 : 230;

  const breakdown = loads.map(l => {
    const qty     = Number(l.quantity) || 1;
    const w       = Number(l.watts_each) || 0;
    const pf      = Number(l.power_factor) || 0.85;
    const df      = LOAD_DEMAND_FACTOR[l.load_type] || 1.0;
    const connVA  = qty * w / pf;
    const demVA   = connVA * df;
    return {
      load_type: l.load_type, qty,
      watts_each: w, pf, demand_factor: df,
      connected_va: Math.round(connVA),
      demand_va:    Math.round(demVA),
    };
  });

  const totalConnVA  = breakdown.reduce((s, l) => s + l.connected_va, 0);
  const totalDemVA   = breakdown.reduce((s, l) => s + l.demand_va, 0);
  const factor       = isThreePhase ? (Math.sqrt(3) * voltage) : voltage;
  const computedA    = totalDemVA / factor;
  const withSpare    = computedA * 1.25;
  const recBreaker   = STANDARD_BREAKER_A.find(s => s >= withSpare) || Math.ceil(withSpare / 25) * 25;

  return {
    phase_config:         phaseConfig,
    voltage,
    total_connected_va:   Math.round(totalConnVA),
    total_connected_kva:  Math.round(totalConnVA / 1000 * 100) / 100,
    total_connected_kw:   Math.round(totalConnVA * 0.85 / 1000 * 100) / 100,
    total_demand_va:      Math.round(totalDemVA),
    total_demand_kva:     Math.round(totalDemVA / 1000 * 100) / 100,
    total_demand_kw:      Math.round(totalDemVA * 0.85 / 1000 * 100) / 100,
    computed_ampacity:    Math.round(computedA * 100) / 100,
    ampacity_with_spare:  Math.round(withSpare * 100) / 100,
    recommended_breaker_A: recBreaker,
    load_breakdown:       breakdown,
  };
}

// ─── Electrical: Voltage Drop — PEC Article 2.10.19 / 2.20 ──────────────────
const WIRE_SIZES_MM2 = [2.0, 3.5, 5.5, 8.0, 14, 22, 30, 38, 50, 60, 80, 100, 125, 150, 200, 250];
const RESISTIVITY_CU = 0.0220; // Ω·mm²/m at 75°C for copper (THHN/THWN)
const RESISTIVITY_AL = 0.0354; // Ω·mm²/m at 75°C for aluminium

function calcVoltageDrop(inputs: Record<string, number | string>): Record<string, unknown> {
  const circuitType  = String(inputs.circuit_type || "Branch Circuit");
  const phase        = String(inputs.phase || "Single-phase");
  const voltage      = Number(inputs.voltage) || 230;
  const current      = Number(inputs.current) || 20;
  const wireLength   = Number(inputs.wire_length) || 30;
  const conductorMM2 = Number(inputs.conductor_mm2) || 3.5;
  const material     = String(inputs.conductor_mat || "Copper");
  const vdLimit      = Number(inputs.vd_limit) || 3;

  const resistivity = material === "Aluminium" ? RESISTIVITY_AL : RESISTIVITY_CU;
  const R = resistivity * 1000 / conductorMM2; // Ω/km
  const factor = phase === "Three-phase" ? Math.sqrt(3) : 2;

  const computeVD = (sizeMM2: number) => {
    const r = resistivity * 1000 / sizeMM2;
    const vd = factor * current * r * wireLength / 1000;
    const vdPct = (vd / voltage) * 100;
    const maxLen = (vdLimit / 100 * voltage * 1000) / (factor * current * r);
    return { size_mm2: sizeMM2, resistance: Math.round(r * 100) / 100, vd_v: Math.round(vd * 100) / 100, vd_pct: Math.round(vdPct * 100) / 100, pass: vdPct <= vdLimit, max_length_m: Math.round(maxLen), is_selected: sizeMM2 === conductorMM2 };
  };

  const vdV    = factor * current * R * wireLength / 1000;
  const vdPct  = (vdV / voltage) * 100;
  const maxLen = (vdLimit / 100 * voltage * 1000) / (factor * current * R);
  const vdLimitV = vdLimit / 100 * voltage;

  const comparison = WIRE_SIZES_MM2.map(s => computeVD(s));

  return {
    circuit_type: circuitType, phase, voltage, current, wire_length: wireLength,
    conductor_mm2: conductorMM2, conductor_mat: material,
    vd_limit: vdLimit, vd_limit_volts: Math.round(vdLimitV * 100) / 100,
    resistivity, resistance_ohm_km: Math.round(R * 100) / 100,
    vd_volts: Math.round(vdV * 100) / 100,
    vd_pct:   Math.round(vdPct * 100) / 100,
    pass:     vdPct <= vdLimit,
    max_length_m: Math.round(maxLen),
    size_comparison: comparison,
  };
}

// ─── Electrical: Wire Sizing — PEC Table 3.10.1 ──────────────────────────────
// Copper THHN/THWN-2 at 75°C — table ampacities
const PEC_AMPACITY_75C: Record<number, number> = {
  2.0: 20, 3.5: 25, 5.5: 35, 8.0: 50, 14: 65, 22: 85, 30: 100,
  38: 115, 50: 135, 60: 150, 80: 175, 100: 200, 125: 230, 150: 260, 200: 300, 250: 340,
};
const TEMP_FACTOR_75C: Record<number, number> = {
  30: 1.00, 35: 0.94, 40: 0.87, 45: 0.82, 50: 0.75, 55: 0.67, 60: 0.58, 65: 0.47,
};
const FILL_FACTOR: Record<string, number> = {
  "1-3": 1.00, "4-6": 0.80, "7-9": 0.70, "10-20": 0.50,
};

function calcWireSizing(inputs: Record<string, number | string>): Record<string, unknown> {
  const loadType    = String(inputs.load_type   || "General Load");
  const phase       = String(inputs.phase       || "Single-phase");
  const voltage     = Number(inputs.voltage)    || 230;
  const powerW      = Number(inputs.power_w)    || 1000;
  const pf          = Number(inputs.power_factor) || 0.85;
  const ambientTemp = Number(inputs.ambient_temp) || 30;
  const conduitFill = String(inputs.conduit_fill || "1-3");

  const isMotor = loadType.includes("Motor") || loadType.includes("HVAC");
  const isContinuous = loadType.includes("continuous") || loadType.includes("Lighting");
  const demandMult = (isMotor || isContinuous) ? 1.25 : 1.0;

  const sqrt3 = Math.sqrt(3);
  const loadCurrent = phase === "Three-phase"
    ? powerW / (voltage * sqrt3 * pf)
    : powerW / (voltage * pf);
  const designCurrent = loadCurrent * demandMult;

  // Nearest temp factor (round down to nearest table entry)
  const tempKeys = Object.keys(TEMP_FACTOR_75C).map(Number).sort((a, b) => a - b);
  const tempKey  = tempKeys.filter(k => k <= ambientTemp).pop() || 30;
  const tempFactor = TEMP_FACTOR_75C[tempKey] || 1.0;
  const fillFactor = FILL_FACTOR[conduitFill] || 1.0;

  const sizeComparison = WIRE_SIZES_MM2.map(s => {
    const tableA   = PEC_AMPACITY_75C[s] || 0;
    const correctedA = tableA * tempFactor * fillFactor;
    return {
      size_mm2:         s,
      ampacity_table:   tableA,
      temp_factor:      tempFactor,
      fill_factor:      fillFactor,
      corrected_ampacity: Math.round(correctedA * 10) / 10,
      adequate:         correctedA >= designCurrent,
      recommended:      false,
    };
  });

  // Find smallest adequate size
  const recEntry = sizeComparison.find(c => c.adequate);
  if (recEntry) recEntry.recommended = true;
  const recSizeMM2     = recEntry?.size_mm2 || WIRE_SIZES_MM2[WIRE_SIZES_MM2.length - 1];
  const recAmpacity    = recEntry?.corrected_ampacity || 0;
  const recBreaker     = STANDARD_BREAKER_A.find(s => s >= designCurrent) || Math.ceil(designCurrent / 5) * 5;

  return {
    load_type: loadType, phase, voltage,
    power_w: powerW, power_factor: pf,
    load_current:    Math.round(loadCurrent * 100) / 100,
    demand_multiplier: demandMult,
    design_current:  Math.round(designCurrent * 100) / 100,
    ambient_temp:    ambientTemp,
    temp_factor:     tempFactor,
    conduit_fill:    conduitFill,
    fill_factor:     fillFactor,
    recommended_size_mm2:   recSizeMM2,
    recommended_ampacity:   recAmpacity,
    recommended_breaker_A:  recBreaker,
    size_comparison: sizeComparison,
  };
}

// ─── Septic Tank Sizing — Occupancy-Based Method (PPC / DOH) ─────────────────
// Standards: Philippine Plumbing Code, DOH Sanitation Code (P.D. 856),
// DENR DAO 2016-08 Effluent Standards, DPWH Blue Book

const SEPTIC_WW_RATES: Record<string, number> = {
  "Residential":              150,
  "Office / Commercial":       50,
  "School / Institutional":    45,
  "Hospital / Clinic":        400,
  "Restaurant / Food Service": 25,
  "Hotel / Dormitory":        180,
  "Industrial / Factory":      50,
  "Custom":                   100,
};

function calcSepticTankSizing(inputs: Record<string, number | string>): Record<string, unknown> {
  const occType      = String(inputs.occupancy_type || "Residential");
  const occupants    = Number(inputs.occupants)      || 20;
  const wwRate       = Number(inputs.ww_rate)        || (SEPTIC_WW_RATES[occType] || 150);
  const retentionDays= Number(inputs.retention_days) || 1;
  const desludgeYrs  = Number(inputs.desludge_years) || 3;
  const liquidDepth  = Number(inputs.liquid_depth)   || 1.5;
  const lwRatio      = Number(inputs.lw_ratio)       || 3;
  const compartments = Number(inputs.compartments)   || 2;

  // Volume components
  const dailyFlowL    = occupants * wwRate;
  const liquidVolL    = dailyFlowL * retentionDays;
  const sludgeL       = 40 * occupants * desludgeYrs;   // PPC: 40 L/person/year
  const scumL         = 15 * occupants * desludgeYrs;   // PPC: 15 L/person/year
  const totalVolL     = liquidVolL + sludgeL + scumL;

  // PPC minimum: 1000 L for any size building
  const designVolL    = Math.max(totalVolL, 1000);
  const designVolM3   = Math.round(designVolL / 1000 * 100) / 100;

  // Dimensions
  const floorAreaM2   = designVolM3 / liquidDepth;
  const widthM        = Math.sqrt(floorAreaM2 / lwRatio);
  const lengthM       = floorAreaM2 / widthM;
  const totalDepthM   = liquidDepth + 0.30; // freeboard
  const actualLWRatio = Math.round((lengthM / widthM) * 10) / 10;

  // Round dimensions to practical 0.1 m increments
  const widthR  = Math.ceil(widthM * 10) / 10;
  const lengthR = Math.ceil(lengthM * 10) / 10;

  // Compartment split: 2/3 and 1/3 per PPC
  const comp1L   = Math.round(designVolL * (2 / 3));
  const comp2L   = designVolL - comp1L;
  const comp1Lm  = Math.round(lengthR * (2 / 3) * 10) / 10 + ' m';
  const comp2Lm  = Math.round(lengthR * (1 / 3) * 10) / 10 + ' m';

  return {
    // Inputs echoed
    occupancy_type:   occType,
    occupants,
    ww_rate:          wwRate,
    retention_days:   retentionDays,
    desludge_years:   desludgeYrs,
    liquid_depth:     liquidDepth,
    lw_ratio:         lwRatio,
    compartments,
    // Volumes
    daily_flow_L:     Math.round(dailyFlowL),
    liquid_volume_L:  Math.round(liquidVolL),
    sludge_L:         Math.round(sludgeL),
    scum_L:           Math.round(scumL),
    total_volume_L:   Math.round(totalVolL),
    design_volume_L:  Math.round(designVolL),
    design_volume_m3: designVolM3,
    // Dimensions
    floor_area_m2:    Math.round(floorAreaM2 * 100) / 100,
    tank_width_m:     widthR,
    tank_length_m:    lengthR,
    total_depth_m:    Math.round(totalDepthM * 10) / 10,
    actual_lw_ratio:  actualLWRatio,
    // Compartments
    comp1_L:    comp1L,
    comp2_L:    comp2L,
    comp1_L_m:  comp1Lm,
    comp2_L_m:  comp2Lm,
  };
}

// ─── Drainage Pipe Sizing — DFU Method (Philippine Plumbing Code / UPC) ─────
// Standards: PPC Table 7-3 (DFU values), UPC Table 7-5 (pipe sizing),
// Manning's formula for self-cleansing velocity verification

const DRAIN_DFU: Record<string, { dfu: number; label: string }> = {
  "Water Closet":               { dfu: 4, label: "Water Closet" },
  "Lavatory / Hand Sink":       { dfu: 1, label: "Lavatory / Hand Sink" },
  "Bathtub":                    { dfu: 2, label: "Bathtub" },
  "Shower":                     { dfu: 2, label: "Shower" },
  "Kitchen Sink (residential)": { dfu: 2, label: "Kitchen Sink (residential)" },
  "Kitchen Sink (commercial)":  { dfu: 4, label: "Kitchen Sink (commercial)" },
  "Urinal (flush valve)":       { dfu: 4, label: "Urinal (flush valve)" },
  "Urinal (flush tank)":        { dfu: 2, label: "Urinal (flush tank)" },
  "Floor Drain (50mm)":         { dfu: 2, label: "Floor Drain (50mm)" },
  "Floor Drain (75mm)":         { dfu: 3, label: "Floor Drain (75mm)" },
  "Laundry Tray":               { dfu: 2, label: "Laundry Tray" },
  "Washing Machine":            { dfu: 2, label: "Washing Machine" },
  "Dishwasher":                 { dfu: 2, label: "Dishwasher" },
  "Drinking Fountain":          { dfu: 1, label: "Drinking Fountain" },
  "Mop Sink":                   { dfu: 3, label: "Mop Sink" },
  "Custom":                     { dfu: 0, label: "Custom" },
};

// UPC Table 7-5 — Horizontal branches at 1%, 2%, 4% slope (mm → max DFU)
const HORIZ_DRAIN_TABLE: Record<string, Record<number, number>> = {
  "1%": { 75: 21, 100: 96,  125: 216, 150: 384,  200: 864,  250: 1584, 300: 2520 },
  "2%": { 50: 21, 75: 42,  100: 180, 125: 390,  150: 700,  200: 1600, 250: 2900, 300: 4600 },
  "4%": { 40: 3,  50: 21,  75: 42,  100: 180,  125: 390,  150: 700,  200: 1600 },
};

// UPC Table 7-5 — Stacks (total DFU on stack)
const STACK_TABLE: Record<number, number> = {
  50: 10, 75: 48, 100: 240, 125: 540, 150: 960, 200: 2200, 250: 3800, 300: 6000,
};

// Manning's n per pipe material
const MANNING_N: Record<string, number> = {
  "PVC": 0.009, "Cast Iron": 0.012, "Concrete": 0.013, "Clay Tile": 0.013,
};

function calcDrainagePipeSizing(inputs: Record<string, number | string>): Record<string, unknown> {
  const fixtures     = inputs.fixtures as Array<{ fixture_type: string; quantity: number; custom_dfu?: number }> || [];
  const systemType   = String(inputs.system_type || "Horizontal Branch");
  const slopeStr     = String(inputs.slope || "2%");
  const slopePct     = parseFloat(slopeStr) / 100;
  const pipeMaterial = String(inputs.pipe_material || "PVC");
  const n            = MANNING_N[pipeMaterial] || 0.009;

  // Sum DFU
  const fixtureBreakdown = fixtures.map(f => {
    const info    = DRAIN_DFU[f.fixture_type] || DRAIN_DFU["Custom"];
    const qty     = Number(f.quantity) || 1;
    const dfuEach = f.fixture_type === "Custom" ? (Number(f.custom_dfu) || 1) : info.dfu;
    return {
      fixture:   info.label || f.fixture_type,
      qty,
      dfu_each:  dfuEach,
      dfu_total: qty * dfuEach,
    };
  });

  const totalDFU = fixtureBreakdown.reduce((s, f) => s + f.dfu_total, 0);

  // Select table based on system type
  const isStack = systemType === "Drain Stack";
  const tableRaw: Record<number, number> = isStack ? STACK_TABLE : (HORIZ_DRAIN_TABLE[slopeStr] || HORIZ_DRAIN_TABLE["2%"]);
  const sortedSizes = Object.keys(tableRaw).map(Number).sort((a, b) => a - b);

  // Smallest diameter where capacity >= totalDFU
  const recommended = sortedSizes.find(d => tableRaw[d] >= totalDFU) || sortedSizes[sortedSizes.length - 1];

  // Manning's flow capacity for each pipe size (half-full for horizontal, full for stacks)
  const halfFull = !isStack;
  const candidates = sortedSizes.filter(d => d >= sortedSizes[0] && d <= Math.max(recommended * 2, 300));

  const comparison = candidates.map(dMM => {
    const dM  = dMM / 1000;
    const A   = halfFull ? (Math.PI * dM * dM / 8) : (Math.PI * dM * dM / 4);
    const R   = dM / 4; // hydraulic radius = D/4 (same for half-full and full in circular pipe)
    const S   = isStack ? 1.0 : slopePct; // stacks: use 1.0 vertical slope for Manning's
    const Q   = (1 / n) * A * Math.pow(R, 2 / 3) * Math.pow(S, 1 / 2);
    const V   = Q / A;
    return {
      dia_mm:      dMM,
      max_dfu:     tableRaw[dMM] || 0,
      q_ls:        Math.round(Q * 1000 * 100) / 100,
      velocity:    Math.round(V * 100) / 100,
      velocity_ok: V >= 0.6,
      ok:          (tableRaw[dMM] || 0) >= totalDFU,
      recommended: dMM === recommended,
    };
  });

  const recData      = comparison.find(c => c.dia_mm === recommended);
  const slopeMmPerM  = Math.round(slopePct * 1000 * 10) / 10;

  return {
    total_dfu:           totalDFU,
    system_type:         systemType,
    slope_pct:           parseFloat(slopeStr),
    slope_mm_per_m:      isStack ? null : slopeMmPerM,
    recommended_dia_mm:  recommended,
    capacity_q_ls:       recData?.q_ls || 0,
    design_velocity:     recData?.velocity || 0,
    velocity_ok:         (recData?.velocity || 0) >= 0.6,
    pipe_material:       pipeMaterial,
    manning_n:           n,
    fixture_breakdown:   fixtureBreakdown,
    size_comparison:     comparison,
  };
}

// ─── Hot Water Demand — ASHRAE Use Rate Method ───────────────────────────────
// Standards: ASHRAE HVAC Applications Handbook Ch.50, Philippine Plumbing Code
// Method: Sum daily demand per use type → heat energy → heater power → storage

const HW_DEMAND_RATES: Record<string, { rate_L: number; label: string }> = {
  "Hotel Room":                { rate_L: 135,  label: "Hotel Room" },
  "Hospital Bed":              { rate_L: 225,  label: "Hospital Bed" },
  "Dormitory / Boarding":      { rate_L: 90,   label: "Dormitory / Boarding" },
  "Office Worker":             { rate_L: 6,    label: "Office Worker" },
  "Restaurant Meal":           { rate_L: 12,   label: "Restaurant Meal" },
  "Residential (person)":      { rate_L: 70,   label: "Residential" },
  "Shower Stall":              { rate_L: 60,   label: "Shower Stall" },
  "Commercial Kitchen":        { rate_L: 15,   label: "Commercial Kitchen" },
  "Laundry (residential)":     { rate_L: 60,   label: "Laundry (residential)" },
  "Laundry (commercial)":      { rate_L: 100,  label: "Laundry (commercial)" },
  "Lavatory (hand wash)":      { rate_L: 4,    label: "Lavatory (hand wash)" },
  "Custom":                    { rate_L: 0,    label: "Custom" },
};

const HW_HEATER_KW = [1.5,2.0,3.0,4.0,5.0,6.0,8.0,10.0,12.0,15.0,18.0,20.0,24.0,30.0,36.0,40.0,48.0,60.0,72.0,80.0,100.0];
const HW_TANK_SIZES_L = [50,80,100,120,150,200,250,300,400,500,750,1000,1500,2000,2500,3000,4000,5000];

function calcHotWaterDemand(inputs: Record<string, number | string>): Record<string, unknown> {
  const uses          = inputs.uses as Array<{ use_type: string; quantity: number; daily_count: number; custom_rate_L?: number }> || [];
  const T_supply      = Number(inputs.supply_temp)    || 28;
  const T_hot         = Number(inputs.hot_temp)       || 60;
  const recoveryHrs   = Number(inputs.recovery_hours) || 2;
  const peakFraction  = Number(inputs.peak_fraction)  || 0.25;
  const storageFactor = Number(inputs.storage_factor) || 1.25;
  const pipeLossPct   = Number(inputs.pipe_loss_pct)  || 10;

  const deltaT = T_hot - T_supply;
  const Cp     = 4.186; // kJ/(kg·°C)

  // Build use breakdown
  const useBreakdown = uses.map(u => {
    const info   = HW_DEMAND_RATES[u.use_type] || HW_DEMAND_RATES["Custom"];
    const qty    = Number(u.quantity)    || 1;
    const count  = Number(u.daily_count) || 1;
    const rateL  = u.use_type === "Custom" ? (Number(u.custom_rate_L) || 0) : info.rate_L;
    const dailyL = qty * count * rateL;
    return {
      use_type:   info.label || u.use_type,
      qty,
      daily_count: count,
      rate_L:     rateL,
      daily_L:    Math.round(dailyL),
    };
  });

  const totalDailyNetL = useBreakdown.reduce((s, u) => s + u.daily_L, 0);

  // Apply pipe heat loss (increases volume needed from heater)
  const totalDailyL = Math.round(totalDailyNetL * (1 + pipeLossPct / 100));

  // Peak hour demand
  const peakHourL = Math.round(totalDailyL * peakFraction);

  // Storage volume
  const storageLComputed   = Math.round(peakHourL * storageFactor);
  const recommendedStorageL = HW_TANK_SIZES_L.find(s => s >= storageLComputed) || Math.ceil(storageLComputed / 500) * 500;

  // Heat energy: Q = m * Cp * deltaT
  const heatEnergyKJ  = totalDailyL * Cp * deltaT;
  const heatEnergyKWh = heatEnergyKJ / 3600;

  // Heater power: deliver all energy within recovery time
  const heaterKWComputed    = heatEnergyKJ / (recoveryHrs * 3600);
  const recommendedHeaterKW = HW_HEATER_KW.find(s => s >= heaterKWComputed) || Math.ceil(heaterKWComputed);

  // Recovery rate at recommended heater
  const recoveryLPH = Math.round((recommendedHeaterKW * 3600) / (Cp * deltaT));

  return {
    // Temperatures
    T_supply,
    T_hot,
    delta_T:             deltaT,
    // Demand
    total_daily_without_loss_L: Math.round(totalDailyNetL),
    pipe_loss_pct:       pipeLossPct,
    total_daily_L:       totalDailyL,
    peak_fraction:       peakFraction,
    peak_hour_L:         peakHourL,
    storage_factor:      storageFactor,
    storage_L_computed:  storageLComputed,
    recommended_storage_L: recommendedStorageL,
    // Heat energy
    heat_energy_kJ:      Math.round(heatEnergyKJ),
    heat_energy_kWh:     Math.round(heatEnergyKWh * 10) / 10,
    // Heater
    heater_kW_computed:  Math.round(heaterKWComputed * 100) / 100,
    recommended_heater_kW: recommendedHeaterKW,
    recovery_rate_lph:   recoveryLPH,
    recovery_hours:      recoveryHrs,
    // Breakdown
    use_breakdown:       useBreakdown,
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

  try {
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
    const parsed = JSON.parse(cleaned);
    if (parsed.objective && parsed.assumptions && parsed.recommendations) return parsed;
    throw new Error("incomplete");
  } catch {
    // Gemini unavailable, rate-limited, or returned unparseable JSON — build fallback from results directly
    const rec = results as Record<string, unknown>;
    const kw  = rec.recommended_kW  ?? rec.design_kW  ?? '';
    const tr  = rec.recommended_TR  ?? rec.design_TR  ?? '';

    let recommendations = "Refer to the results summary table for specific design values. Ensure all equipment is selected to meet or exceed the computed minimum requirements, and that installation complies with the applicable Philippine and international engineering standards.";

    if (calcType === "HVAC Cooling Load" && kw) {
      recommendations = `Provide air conditioning unit(s) with minimum combined capacity of ${kw} kW${tr ? ` (${tr} TR)` : ''}. Ensure proper outdoor air ventilation per ASHRAE 62.1 and PNS/ASHRAE 55 thermal comfort standards.`;
    } else if (calcType === "Ventilation / ACH") {
      const fan = rec.recommended_fan_cmh ?? rec.design_cmh ?? '';
      const ach = rec.required_ach ?? rec.ach_ashrae ?? '';
      recommendations = `Provide supply/exhaust fans with minimum combined capacity of ${fan} CMH to achieve ${ach} air changes per hour. Size ductwork for a maximum face velocity of 2.5 m/s. Verify outdoor air fraction meets ASHRAE 62.1 minimum requirements.`;
    } else if (calcType === "Pump Sizing (TDH)") {
      const hp = rec.recommended_hp ?? '';
      const tdh = rec.TDH ?? '';
      recommendations = `Provide a centrifugal pump rated at minimum ${hp} hp (TDH = ${tdh} m). Select a pump with an efficiency curve that encompasses the design point. Install with gate valves, check valve, and pressure gauge on discharge per PSME standards.`;
    } else if (calcType === "Pipe Sizing") {
      const dia = rec.pipe_dia_mm ?? rec.recommended_dia_mm ?? '';
      recommendations = `Use minimum ${dia} mm nominal bore pipe for the design flow rate. Verify actual velocity stays within 1.5–3.0 m/s for liquid services. Install expansion joints and supports per PSME Piping Code.`;
    } else if (calcType === "Compressed Air") {
      const hp = rec.recommended_hp ?? '';
      const cfm = rec.recommended_cfm ?? '';
      const pipe = rec.recommended_pipe_mm ?? '';
      recommendations = `Provide a rotary screw or reciprocating compressor rated at minimum ${hp} hp (${cfm} CFM FAD). Size distribution piping at ${pipe} mm minimum bore. Install an air dryer and particulate filter downstream of the receiver to protect pneumatic equipment.`;
    } else if (calcType === "Water Supply Pipe Sizing") {
      const dia = rec.recommended_dia_mm ?? '';
      recommendations = `Use minimum ${dia} mm nominal bore pipe for the main supply branch. Verify static pressure at the most remote fixture is not less than 70 kPa. Install pressure-reducing valves where supply pressure exceeds 550 kPa per the Philippine Plumbing Code.`;
    } else if (calcType === "Hot Water Demand") {
      const heater = rec.recommended_heater_kW ?? rec.heater_kW_computed ?? '';
      const storage = rec.recommended_storage_L ?? '';
      recommendations = `Provide a water heater rated at minimum ${heater} kW with ${storage} L storage capacity. Insulate all hot water piping to minimize heat loss. Install a tempering valve to deliver water at maximum 50°C at fixtures per PPC safety requirements.`;
    } else if (calcType === "Drainage Pipe Sizing") {
      const branch = rec.branch_dia_mm ?? rec.recommended_dia_mm ?? '';
      recommendations = `Use minimum ${branch} mm nominal bore for the branch drain and size the stack accordingly per the Philippine Plumbing Code Table of fixture unit loads. Maintain minimum 2% slope on horizontal branches. Provide cleanouts at every change of direction and at 15 m intervals.`;
    } else if (calcType === "Septic Tank Sizing") {
      const vol = rec.total_volume_L ?? '';
      recommendations = `Construct a septic tank with minimum liquid capacity of ${vol} L using watertight reinforced concrete or fiberglass. Provide inspection covers on each compartment and a subsurface leachfield sized per DENR DAO 2016-08 effluent standards. Desludge per the computed interval.`;
    } else if (calcType === "Load Estimation") {
      const kva = rec.total_kVA ?? rec.demand_kVA ?? rec.demand_kW ?? '';
      recommendations = `Size the main circuit breaker and service entrance conductors for minimum ${kva} kVA demand load with 20% future expansion margin. Provide separate circuit breakers for each circuit per PEC 2017. Label all breakers and maintain an accurate load schedule as a permanent record.`;
    } else if (calcType === "Voltage Drop") {
      const vd = rec.vd_pct ?? '';
      const pass = rec.pass;
      recommendations = pass === false
        ? `Computed voltage drop of ${vd}% exceeds the allowable limit. Increase conductor size or reduce circuit length to bring voltage drop within limits per PEC 2017. Consider using a higher-voltage distribution system for long runs.`
        : `Computed voltage drop of ${vd}% is within the allowable limit. Maintain this conductor size and route. Document this calculation in the project electrical design file.`;
    } else if (calcType === "Wire Sizing") {
      const wire = rec.recommended_size_mm2 ?? '';
      const breaker = rec.recommended_breaker_A ?? '';
      recommendations = `Use ${wire} mm² THHN/THWN-2 copper conductor in conduit. Protect with a ${breaker} A molded-case circuit breaker per PEC 2017 Table 3.10.1. Verify derating factors for ambient temperature and conduit fill before finalizing.`;
    } else if (calcType === "Fire Alarm Battery") {
      const ah = rec.Ah_required ?? '';
      const cfg = rec.battery_config ?? '';
      recommendations = `Provide sealed lead-acid (SLA/VRLA) batteries rated at minimum ${ah} Ah. Recommended battery bank: ${cfg}. Replace every 3–5 years per NFPA 72 §10.6.11. Submit this calculation to BFP as part of the fire alarm permit package.`;
    } else if (calcType === "Fire Sprinkler Hydraulic") {
      const flow = rec.Q_total ?? '';
      const press = rec.P_source ?? '';
      recommendations = `Provide a fire pump rated at minimum ${flow} L/min at ${press} bar. Provide a dedicated fire water storage tank sized for the computed duration. Submit to BFP as part of the fire protection permit application. A PRC-licensed engineer must sign and seal this document.`;
    } else if (calcType === "Fire Pump Sizing") {
      const bhp = rec.motor_hp ?? '';
      recommendations = `Provide a fire pump with motor rated at minimum ${bhp} hp. Verify the pump curve at 150% rated flow per NFPA 20 §4.28. Submit to BFP as part of the fire protection permit package. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "Stairwell Pressurization") {
      const q = rec.Q_total_m3h ?? '';
      recommendations = `Provide pressurization fans supplying minimum ${q} m³/h total across all stairwells. Verify door opening force does not exceed 133 N per NFPA 92. Commission and test the system with all doors closed before occupancy. Submit to BFP as part of the smoke control permit package.`;
    } else if (calcType === "Elevator Traffic Analysis") {
      const rtt = rec.RTT_s ?? '';
      const intv = rec.interval_s ?? '';
      const hc = rec.HC_pct ?? '';
      recommendations = `Computed RTT is ${rtt} s (interval ${intv} s, HC% ${hc}%). Install group supervisory control to optimize dispatching. At least one elevator must comply with BP 344 / RA 10754 (min car 1100 mm × 1400 mm, Braille controls). If interval exceeds the target, consider increasing speed or adding an elevator. Submit traffic analysis to DPWH / LGU as part of the building permit application. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "Shaft Design") {
      const d = rec.d_std_mm ?? rec.d_min_mm ?? '';
      const mat = (inputs.material as string) || '';
      const twist = rec.twist_deg_per_m ?? '';
      recommendations = `Specify ${d} mm diameter ${mat} solid shaft. Calculated minimum: ${rec.d_min_mm ?? ''} mm. Angle of twist: ${twist}°/m (ASME limit: 1.0°/m). Verify critical speed — operating speed must be below 50% of first critical speed. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "Bearing Life (L10)") {
      const life = rec.L10h_adj ?? rec.L10h ?? '';
      const pass = rec.life_check ?? '';
      const creq = rec.C_required_kN ?? '';
      recommendations = `Adjusted bearing life (Lna): ${life} hours — ${pass}. ${pass === 'FAIL' ? 'Select a bearing with C ≥ ' + creq + ' kN.' : 'Bearing is adequate for the application.'} Verify static rating C0 against peak shock loads. Specify sealed bearing (2RS) for humid/dusty Philippine plant environments. Establish lubrication intervals per manufacturer. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "V-Belt Drive Design") {
      const nb   = rec.n_belts ?? '';
      const belt = rec.belt_designation ?? '';
      const ddia = rec.driven_dia_mm ?? '';
      recommendations = `Provide ${nb} matched Section ${(inputs.belt_section as string) || ''} belt(s), designation ${belt}. Driven sheave: ${ddia} mm pitch diameter. Tension to manufacturer spec and re-tension after 4–8 hours. Verify sheave alignment before commissioning. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "Hoist Capacity") {
      const mbf = rec.MBF_kN ?? '';
      const rope = rec.rope_recommendation ?? '';
      const hp = rec.motor_hp_std ?? '';
      recommendations = `Provide wire rope with minimum breaking force of ${mbf} kN (${rope}). Hoist motor: ${hp} HP with duty class M3/M4. Maintain SF ${rec.safety_factor_check} per ASME B30.2. Inspect wire rope daily (visual) and monthly (detailed) per DOLE D.O. 13. Runway structure must be verified by a structural engineer. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "Short Circuit") {
      const isc  = rec.Isc_kA ?? '';
      const chk  = rec.ic_check ?? '';
      const ic   = (inputs.breaker_ic_kA as number) ?? '';
      const recIC = rec.ic_min_recommended ?? '';
      recommendations = `Available fault current at panel: ${isc} kA (3-phase symmetrical). Breaker IC check: ${chk}. ${chk === 'FAIL' ? `Installed IC of ${ic} kA is insufficient — replace with minimum ${recIC} kA interrupting capacity breaker immediately. This is a critical safety deficiency.` : `Installed IC of ${ic} kA is adequate for ${isc} kA available fault.`} Verify IC rating of every branch breaker in this panel — fault current is the same at all points in the same panel. Request utility confirmation of available fault current at the point of delivery for final documentation. A PRC-licensed Electrical Engineer must sign and seal this document.`;
    } else if (calcType === "Bolt Torque & Preload") {
      const torque = rec.torque_Nm ?? '';
      const size   = (inputs.bolt_size as string) || '';
      const grade  = (inputs.bolt_grade as string) || '';
      const sf     = rec.separation_sf ?? '';
      const jchk   = rec.joint_check ?? '';
      recommendations = `Tighten ${size} Grade ${grade} bolts to ${torque} N·m using a calibrated torque wrench. Use the 3-pass cross-torquing method: 30% → 70% → 100% of target torque. Joint separation SF = ${sf} (${jchk}). Never reuse torque-to-yield bolts (Grade 10.9 / 12.9 one-time use). Apply thread lubricant (K=${(inputs.nut_factor as number) ?? ''}) consistently — dry/lubricated torque differs by up to 30%. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    }
    return {
      objective: `To determine the required ${calcType} design parameters for the subject project in accordance with applicable Philippine and international engineering standards.`,
      assumptions: "Standard Philippine tropical climate and code conditions applied. Safety factors as specified in the applicable standard have been applied to all computed values.",
      recommendations,
    };
  }
}

// ─── Electrical: Short Circuit Analysis (PEC 2017 / IEC 60909 / IEEE 141) ────

function calcShortCircuit(inputs: Record<string, number | string>): Record<string, unknown> {
  const round4 = (v: number) => Math.round(v * 10000) / 10000;
  const round2 = (v: number) => Math.round(v * 100) / 100;

  const xfmr_kva   = Number(inputs.xfmr_kva   ?? 100);
  const z_pct      = Number(inputs.z_pct       ?? 4.5);
  const voltage_ll = Number(inputs.voltage_ll  ?? 400);
  const cable_mm2  = Number(inputs.cable_mm2   ?? 38);
  const cable_len_m= Number(inputs.cable_len_m ?? 30);
  const breaker_ic = Number(inputs.breaker_ic_kA ?? 10);

  // Step 1: Transformer base impedance
  const Z_base_ohm = round4(Math.pow(voltage_ll, 2) / (xfmr_kva * 1000));

  // Step 2: Transformer impedance
  const Z_xfmr_ohm = round4(Z_base_ohm * (z_pct / 100));

  // Step 3: Cable resistance (copper resistivity 0.0175 Ω·mm²/m)
  const R_cable_ohm = round4((0.0175 / cable_mm2) * cable_len_m);

  // Step 4: Total impedance
  const Z_total_ohm = round4(Z_xfmr_ohm + R_cable_ohm);

  // Step 5: 3-phase symmetrical fault current
  const Isc_A = voltage_ll / (Math.sqrt(3) * Z_total_ohm);
  const Isc_kA = round2(Isc_A / 1000);

  // Step 6: Asymmetrical peak (IEC 60909 factor 1.8)
  const Ipeak_kA = round2(1.8 * Isc_kA);

  // Step 7: Breaker IC check
  const ic_check = breaker_ic >= Isc_kA ? 'PASS' : 'FAIL';
  const ic_margin = round2(breaker_ic - Isc_kA);

  // Recommended minimum IC
  const IC_STANDARD = [6, 10, 25, 36, 50, 65, 100];
  const ic_min_recommended = IC_STANDARD.find(v => v >= Isc_kA) ?? 100;

  return {
    Z_base_ohm,
    Z_xfmr_ohm,
    R_cable_ohm,
    Z_total_ohm,
    Isc_kA,
    Ipeak_kA,
    ic_check,
    ic_margin,
    ic_min_recommended,
  };
}

// ─── Machine Design: Bolt Torque & Preload (ISO 898-1 / VDI 2230 / ASME PCC-1) ─

function calcBoltTorque(inputs: Record<string, number | string>): Record<string, unknown> {
  const round2 = (v: number) => Math.round(v * 100) / 100;
  const round1 = (v: number) => Math.round(v * 10) / 10;

  // Bolt data: [nominal_dia_mm, stress_area_mm2]
  const BOLT_DATA: Record<string, [number, number]> = {
    'M10': [10,  58.0],
    'M12': [12,  84.3],
    'M16': [16, 157.0],
    'M20': [20, 245.0],
    'M24': [24, 353.0],
    'M30': [30, 561.0],
  };

  // Proof strength (Sp) in MPa per grade — ISO 898-1
  const SP_MAP: Record<string, number> = {
    '4.6':  225,
    '4.8':  310,
    '8.8':  600,
    '10.9': 830,
    '12.9': 970,
  };

  const bolt_size    = String(inputs.bolt_size  || 'M16');
  const bolt_grade   = String(inputs.bolt_grade || '8.8');
  const nut_factor   = Number(inputs.nut_factor  ?? 0.20);
  const preload_pct  = Number(inputs.preload_pct ?? 75);
  const ext_load_kN  = Number(inputs.ext_load_kN ?? 0);
  const n_bolts      = Math.max(1, Math.round(Number(inputs.n_bolts ?? 4)));

  const [d_mm, At_mm2] = BOLT_DATA[bolt_size] ?? [16, 157];
  const Sp_MPa         = SP_MAP[bolt_grade]   ?? 600;

  // Proof load & preload
  const Fp_kN  = round2((At_mm2 * Sp_MPa) / 1000);
  const Fi_kN  = round2((preload_pct / 100) * Fp_kN);

  // Stress check
  const sigma_MPa  = round1((Fi_kN * 1000) / At_mm2);
  const stress_util = round1((sigma_MPa / Sp_MPa) * 100); // %
  const stress_check = sigma_MPa <= Sp_MPa ? 'PASS' : 'FAIL';

  // Tightening torque T = K × d × Fi
  const d_m      = d_mm / 1000;
  const Fi_N     = Fi_kN * 1000;
  const torque_Nm = round1(nut_factor * d_m * Fi_N);

  // 3-pass torque values
  const torque_30pct = round1(torque_Nm * 0.30);
  const torque_70pct = round1(torque_Nm * 0.70);

  // Joint separation check
  const total_clamp_kN = round2(n_bolts * Fi_kN);
  const separation_sf  = ext_load_kN > 0 ? round2(total_clamp_kN / ext_load_kN) : null;
  const n_bolts_min    = ext_load_kN > 0 ? Math.ceil((ext_load_kN * 1.5) / Fi_kN) : 1;
  const joint_check    = n_bolts >= n_bolts_min ? 'PASS' : 'FAIL';

  // Nut factor condition label
  const NUT_LABELS: Record<string, string> = {
    '0.12': 'Waxed/MoS2 lubricated',
    '0.15': 'Machine oil lubricated',
    '0.20': 'As-received (dry)',
    '0.25': 'Heavily oxidised/dirty',
  };
  const nut_condition = NUT_LABELS[String(nut_factor)] ?? `K=${nut_factor}`;

  return {
    bolt_size,
    bolt_grade,
    d_mm,
    At_mm2,
    Sp_MPa,
    Fp_kN,
    preload_pct,
    Fi_kN,
    sigma_MPa,
    stress_util,
    stress_check,
    nut_factor,
    nut_condition,
    torque_Nm,
    torque_30pct,
    torque_70pct,
    n_bolts,
    ext_load_kN,
    total_clamp_kN,
    separation_sf,
    n_bolts_min,
    joint_check,
  };
}

// ─── Machine Design: Shaft Design (ASME B106.1M / Shigley's Elliptic) ───────

function calcShaftDesign(inputs: Record<string, number | string>): Record<string, unknown> {
  const power_kW         = Number(inputs.power_kW)          || 7.5;
  const shaft_rpm        = Number(inputs.shaft_rpm)          || 1450;
  const transverse_load_N= Number(inputs.transverse_load_N)  || 2000;
  const span_mm          = Number(inputs.span_mm)            || 300;
  const material         = (inputs.material as string)       || 'AISI 1045';
  const keyway           = (inputs.keyway as string)         || 'Yes';
  const shock_type       = (inputs.shock_type as string)     || 'Minor';

  const round2 = (n: number) => Math.round(n * 100) / 100;
  const round1 = (n: number) => Math.round(n * 10)  / 10;

  // Material ultimate tensile strength (MPa)
  const Sut_map: Record<string, number> = {
    'AISI 1020': 380,
    'AISI 1045': 570,
    'AISI 4140': 655,
    'AISI 4340': 1035,
  };
  const Sut_MPa = Sut_map[material] || 570;

  // Allowable shear stress
  const Ss_factor = keyway === 'Yes' ? 0.18 : 0.30;
  const Ss_allow_MPa = round1(Ss_factor * Sut_MPa);
  const Ss_allow_Pa  = Ss_allow_MPa * 1e6;

  // Shock factors
  const shock_map: Record<string, { Kb: number; Kt: number }> = {
    'Steady':   { Kb: 1.0, Kt: 1.0 },
    'Minor':    { Kb: 1.5, Kt: 1.0 },
    'Moderate': { Kb: 2.0, Kt: 1.5 },
    'Heavy':    { Kb: 3.0, Kt: 2.0 },
  };
  const { Kb, Kt } = shock_map[shock_type] || shock_map['Minor'];

  // Torque (N·m)
  const T_Nm = round1(power_kW * 9549.3 / shaft_rpm);

  // Bending moment — simply supported, point load at midspan
  const M_Nm = round1(transverse_load_N * (span_mm / 1000) / 4);

  // Combined load term (ASME elliptic)
  const combined_Nm = round1(Math.sqrt(Math.pow(Kb * M_Nm, 2) + Math.pow(Kt * T_Nm, 2)));

  // Minimum diameter (m)
  const d_cubed_m3 = (16 / Math.PI) * combined_Nm / Ss_allow_Pa;
  const d_min_m    = Math.pow(d_cubed_m3, 1/3);
  const d_min_mm   = round1(d_min_m * 1000);

  // Standard shaft diameters (mm) — PH market
  const std_diams = [15,16,17,18,19,20,22,24,25,28,30,32,35,38,40,42,45,48,50,52,55,58,60,63,65,70,75,80,85,90,95,100,105,110,115,120];
  let d_std_mm = std_diams[std_diams.length - 1];
  for (const d of std_diams) {
    if (d >= d_min_mm) { d_std_mm = d; break; }
  }

  // Angle of twist
  const G = 80e9; // Pa (steel)
  const d_std_m = d_std_mm / 1000;
  const J_m4 = (Math.PI * Math.pow(d_std_m, 4)) / 32;
  const L_m  = span_mm / 1000;
  const twist_rad = (T_Nm * L_m) / (G * J_m4);
  const twist_deg = round2(twist_rad * 180 / Math.PI);
  const twist_deg_per_m = round2(twist_deg / L_m);

  return {
    power_kW: round2(power_kW),
    Sut_MPa,
    Ss_allow_MPa,
    Ss_allow_Pa: round1(Ss_allow_Pa / 1e6) + ' MPa', // display only
    Kb,
    Kt,
    T_Nm,
    M_Nm,
    combined_Nm,
    d_cubed_m3: round2(d_cubed_m3 * 1e6).toFixed(2) + 'e-6',
    d_min_mm,
    d_std_mm,
    J_m4: (J_m4 * 1e8).toFixed(3) + 'e-8',
    twist_rad: round2(twist_rad * 1000) / 1000,
    twist_deg,
    twist_deg_per_m,
  };
}

// ─── Machine Design: Bearing Life L10 (ISO 281:2007) ────────────────────────

function calcBearingLife(inputs: Record<string, number | string>): Record<string, unknown> {
  const bearing_type    = (inputs.bearing_type as string) || 'Ball';
  const C_kN            = Number(inputs.C_kN)            || 25.5;
  const speed_rpm       = Number(inputs.speed_rpm)        || 1450;
  const Fr_kN           = Number(inputs.Fr_kN)            || 5.0;
  const Fa_kN           = Number(inputs.Fa_kN)            || 0;
  const reliability_pct = Number(inputs.reliability_pct)  || 90;
  const required_life_h = Number(inputs.required_life_h)  || 25000;

  const round2 = (n: number) => Math.round(n * 100) / 100;
  const round1 = (n: number) => Math.round(n * 10)  / 10;

  // Life exponent
  const p_exp = bearing_type === 'Roller' ? 10/3 : 3;

  // Load factors X, Y based on Fa/Fr ratio (ISO 281 simplified for deep groove ball bearings)
  const Fa_Fr_ratio = round2(Fr_kN > 0 ? Fa_kN / Fr_kN : 0);
  let X = 1.0, Y = 0.0;
  if (Fa_kN > 0) {
    if (bearing_type === 'Ball') {
      // Deep groove ball bearing: ISO 281 simplified
      if (Fa_Fr_ratio <= 0.44) { X = 1.0; Y = 0.0;  }
      else if (Fa_Fr_ratio <= 0.72) { X = 0.56; Y = 1.71; }
      else if (Fa_Fr_ratio <= 1.02) { X = 0.56; Y = 1.40; }
      else if (Fa_Fr_ratio <= 1.44) { X = 0.56; Y = 1.27; }
      else if (Fa_Fr_ratio <= 2.28) { X = 0.56; Y = 1.17; }
      else { X = 0.56; Y = 1.00; }
    } else {
      // Roller bearing: typically X=0.4, Y depends on contact angle (use 1.5 as conservative)
      X = 0.67; Y = 0.67;
    }
  }

  // Equivalent dynamic load
  const P_kN = round2(X * Fr_kN + Y * Fa_kN);
  const C_over_P = round2(C_kN / P_kN);

  // Basic rating life (million revolutions)
  const L10_Mrev = round2(Math.pow(C_over_P, p_exp));

  // L10 in hours
  const L10h = Math.round(L10_Mrev * 1e6 / (60 * speed_rpm));

  // Reliability factor a1
  const a1_map: Record<number, number> = { 90: 1.00, 95: 0.62, 99: 0.21, 96: 0.53, 97: 0.44, 98: 0.33 };
  const a1 = a1_map[reliability_pct] ?? 1.00;

  // Adjusted life
  const L10h_adj = Math.round(a1 * L10h);

  // Pass/fail
  const life_check = L10h_adj >= required_life_h ? 'PASS' : 'FAIL';

  // Minimum C required to meet required life at current reliability
  const C_required_kN = round1(P_kN * Math.pow((required_life_h / a1 * 60 * speed_rpm) / 1e6, 1 / p_exp));

  return {
    p_exp: bearing_type === 'Roller' ? '10/3' : '3',
    Fa_Fr_ratio,
    X,
    Y,
    P_kN,
    C_over_P,
    L10_Mrev,
    L10h,
    a1,
    L10h_adj,
    life_check,
    C_required_kN,
  };
}

// ─── Machine Design: V-Belt Drive (RMA IP-20 / ASME B17.1) ──────────────────

function calcVBeltDrive(inputs: Record<string, number | string>): Record<string, unknown> {
  const power_kW       = Number(inputs.power_kW)       || 7.5;
  const service_factor = Number(inputs.service_factor)  || 1.2;
  const driver_rpm     = Number(inputs.driver_rpm)      || 1450;
  const driven_rpm     = Number(inputs.driven_rpm)      || 720;
  const belt_section   = (inputs.belt_section as string) || 'B';
  const driver_dia_mm  = Number(inputs.driver_dia_mm)   || 150;
  const center_dist_mm = Number(inputs.center_dist_mm)  || 500;

  const round2 = (n: number) => Math.round(n * 100) / 100;
  const round1 = (n: number) => Math.round(n * 10)  / 10;

  // Design power
  const design_power_kW  = round2(power_kW * service_factor);
  const rated_power_kW   = round2(power_kW);

  // Speed ratio and driven sheave diameter
  const speed_ratio     = round2(driver_rpm / driven_rpm);
  const driven_dia_mm   = Math.round(driver_dia_mm * speed_ratio / 5) * 5; // round to 5mm
  const actual_driven_rpm = Math.round(driver_rpm * driver_dia_mm / driven_dia_mm);

  // Belt speed (m/s)
  const belt_speed_ms = round2(Math.PI * (driver_dia_mm / 1000) * driver_rpm / 60);

  // Belt length (mm)
  const C  = center_dist_mm;
  const D  = driven_dia_mm;
  const d  = driver_dia_mm;
  const L_calc = 2 * C + (Math.PI / 2) * (D + d) + Math.pow(D - d, 2) / (4 * C);
  const belt_length_mm = Math.round(L_calc);

  // Belt designation — RMA standard lengths per section (datum length in inches, label in mm)
  // Approximate standard lengths (mm) for each section
  const std_lengths: Record<string, number[]> = {
    A: [500,530,560,580,610,640,660,690,710,740,760,790,810,840,860,890,910,940,965,990,1015,1040,1065,1090,1120,1145,1170,1220,1270,1320,1370,1420,1470,1525,1575,1625,1680,1730,1780,1830,1880,1930,1980,2030,2080,2130,2180,2230,2290,2340,2390],
    B: [610,640,690,710,740,760,790,810,840,860,890,910,940,965,990,1015,1040,1065,1090,1120,1145,1170,1220,1270,1320,1370,1420,1470,1525,1575,1625,1680,1730,1780,1830,1880,1930,1980,2030,2130,2230,2330,2430,2540,2640,2740,2840,2950,3050,3150],
    C: [965,990,1040,1090,1120,1170,1220,1270,1320,1370,1420,1470,1525,1575,1625,1680,1730,1780,1830,1880,1930,1980,2030,2080,2130,2180,2230,2290,2340,2390,2540,2640,2740,2840,2950,3050,3150,3350,3550,3750,3950,4060,4160,4370,4570,4780,5080],
    D: [2540,2640,2740,2840,2950,3050,3150,3350,3550,3750,3950,4060,4160,4370,4570,4780,5080,5330,5590,5840,6100,6350,6600],
  };
  const lengths = std_lengths[belt_section] || std_lengths['B'];
  let selected_length = lengths[lengths.length - 1];
  for (const l of lengths) {
    if (l >= belt_length_mm) { selected_length = l; break; }
  }

  // Belt designation: section + datum number (datum ≈ length in inches, RMA convention)
  const datum_inches = Math.round(selected_length / 25.4);
  const belt_designation = `${belt_section}-${datum_inches}`;

  // Arc of contact on small sheave (degrees)
  const arc_deg = round1(180 - 60 * (D - d) / C);

  // Arc correction factor Kθ (RMA IP-20 interpolated)
  function getKtheta(theta: number): number {
    if (theta >= 180) return 1.00;
    if (theta >= 174) return 0.99;
    if (theta >= 168) return 0.97;
    if (theta >= 162) return 0.96;
    if (theta >= 156) return 0.94;
    if (theta >= 150) return 0.92;
    if (theta >= 144) return 0.91;
    if (theta >= 138) return 0.89;
    if (theta >= 132) return 0.87;
    if (theta >= 126) return 0.85;
    if (theta >= 120) return 0.82;
    if (theta >= 114) return 0.80;
    if (theta >= 108) return 0.77;
    return 0.74;
  }
  const K_theta = getKtheta(arc_deg);

  // Belt length correction factor KL (relative to standard reference length per section)
  const ref_lengths: Record<string, number> = { A: 914, B: 1270, C: 1575, D: 2540 };
  const L_ref = ref_lengths[belt_section] || 1270;
  const K_L = round2(Math.pow(selected_length / L_ref, 0.09)); // RMA empirical exponent

  // Rated power per belt (RMA IP-20 table approximation)
  // Power rating ≈ empirical formula based on sheave dia and belt speed
  // Using simplified RMA table interpolation
  const section_factors: Record<string, number> = { A: 1.0, B: 1.75, C: 3.2, D: 6.5 };
  const sf = section_factors[belt_section] || 1.75;
  const power_per_belt_kW = round2(sf * Math.pow(driver_dia_mm / 100, 0.5) * Math.pow(belt_speed_ms / 10, 0.7));

  // Corrected power per belt
  const corrected_power_kW = round2(power_per_belt_kW * K_theta * K_L);

  // Number of belts
  const n_belts_calc = round2(design_power_kW / corrected_power_kW);
  const n_belts = Math.ceil(n_belts_calc);

  // Capacity and margin
  const total_power_capacity_kW = round2(n_belts * corrected_power_kW);
  const capacity_margin_pct = Math.round((total_power_capacity_kW / design_power_kW - 1) * 100);

  return {
    rated_power_kW,
    design_power_kW,
    speed_ratio,
    driven_dia_mm,
    actual_driven_rpm,
    belt_speed_ms,
    belt_length_mm,
    selected_length,
    belt_designation,
    arc_deg,
    K_theta,
    K_L,
    power_per_belt_kW,
    corrected_power_kW,
    n_belts_calc,
    n_belts,
    total_power_capacity_kW,
    capacity_margin_pct,
  };
}

// ─── Vertical Transportation: Hoist Capacity (ASME B30.2 / B30.16) ───────────

function calcHoistCapacity(inputs: Record<string, number | string>): Record<string, unknown> {
  const rated_load_kg   = Number(inputs.rated_load_kg)   || 2000;
  const hook_weight_kg  = Number(inputs.hook_weight_kg)  || 30;
  const sling_weight_kg = Number(inputs.sling_weight_kg) || 15;
  const lift_height_m   = Number(inputs.lift_height_m)   || 6;
  const lift_speed_mpm  = Number(inputs.lift_speed_mpm)  || 8;
  const n_parts         = Number(inputs.n_parts)         || 1;
  const safety_factor   = Number(inputs.safety_factor)   || 5;
  const mech_eff_pct    = Number(inputs.mech_eff_pct)    || 82;

  const round2 = (n: number) => Math.round(n * 100) / 100;
  const round1 = (n: number) => Math.round(n * 10) / 10;

  // Gross load
  const gross_load_kg = rated_load_kg + hook_weight_kg + sling_weight_kg;
  const gross_load_kN = round2(gross_load_kg * 9.81 / 1000);

  // Minimum breaking force
  const MBF_kg = gross_load_kg * safety_factor;
  const MBF_kN = round2(MBF_kg * 9.81 / 1000);

  // Rope efficiency factor (0.98 per sheave/part)
  const rope_eff_per_part = 0.98;
  const rope_efficiency_factor = round2(Math.pow(rope_eff_per_part, n_parts));

  // Rope pull (N)
  const rope_pull_kg = round1(gross_load_kg / (n_parts * rope_efficiency_factor));
  const rope_pull_N  = Math.round(rope_pull_kg * 9.81);

  // Speed in m/s
  const speed_ms = round2(lift_speed_mpm / 60);

  // Power at rope (W)
  const power_W = Math.round(rope_pull_N * speed_ms);

  // Motor HP (calculated)
  const mech_eff = mech_eff_pct / 100;
  const motor_hp_calc = round2(power_W / (mech_eff * 746));

  // Standard motor HP sizes (IEC/NEMA common sizes used in Philippines)
  const std_hp = [0.5, 1, 1.5, 2, 3, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200];
  const motor_hp_with_sf = motor_hp_calc * 1.15; // 15% service factor
  let motor_hp_std = std_hp[std_hp.length - 1];
  for (const hp of std_hp) {
    if (hp >= motor_hp_with_sf) { motor_hp_std = hp; break; }
  }
  const motor_kW = round2(motor_hp_std * 0.746);

  // Wire rope recommendation based on MBF_kN
  // Common 6×19 IWRC EIPS wire rope breaking strengths (approximate)
  const rope_sizes = [
    { dia: '8 mm',  MBF: 38.7 },
    { dia: '10 mm', MBF: 60.4 },
    { dia: '12 mm', MBF: 87.1 },
    { dia: '14 mm', MBF: 118 },
    { dia: '16 mm', MBF: 154 },
    { dia: '18 mm', MBF: 195 },
    { dia: '20 mm', MBF: 241 },
    { dia: '22 mm', MBF: 291 },
    { dia: '24 mm', MBF: 347 },
    { dia: '26 mm', MBF: 406 },
    { dia: '28 mm', MBF: 471 },
    { dia: '32 mm', MBF: 615 },
    { dia: '36 mm', MBF: 779 },
  ];
  let selected_rope = rope_sizes[rope_sizes.length - 1];
  for (const r of rope_sizes) {
    if (r.MBF >= MBF_kN) { selected_rope = r; break; }
  }
  const rope_recommendation = `${selected_rope.dia} diameter, 6×19 IWRC EIPS wire rope (MBF = ${selected_rope.MBF} kN)`;

  // Rope length on drum
  const dead_wrap_length = 3 * Math.PI * 0.15; // approx 3 wraps on ~150mm core drum
  const rope_length_m = Math.ceil(lift_height_m * n_parts + dead_wrap_length);

  // Safety factor check
  const safety_factor_check = safety_factor >= 5 ? 'PASS' : 'FAIL';

  return {
    gross_load_kg,
    gross_load_kN,
    MBF_kg,
    MBF_kN,
    rope_efficiency_factor,
    rope_pull_kg,
    rope_pull_N,
    speed_ms,
    power_W,
    motor_hp_calc,
    motor_hp_std,
    motor_kW,
    rope_recommendation,
    rope_length_m,
    safety_factor_check,
  };
}

// ─── Vertical Transportation: Elevator Traffic Analysis (CIBSE Guide D / ASME A17.1) ─

function calcElevatorTraffic(inputs: Record<string, number | string>): Record<string, unknown> {
  const n_floors     = Number(inputs.n_floors)     || 12;   // floors served
  const floor_height = Number(inputs.floor_height) || 3.5;  // m
  const population   = Number(inputs.population)   || 500;  // persons
  const n_elevators  = Number(inputs.n_elevators)  || 3;
  const capacity     = Number(inputs.capacity)      || 13;   // persons
  const speed        = Number(inputs.speed)         || 1.5;  // m/s
  const t_door_open  = Number(inputs.t_door_open)  || 2.5;  // s
  const t_door_close = Number(inputs.t_door_close) || 3.0;  // s
  const t_dwell      = Number(inputs.t_dwell)       || 2.0;  // s
  const occupancy    = (inputs.occupancy_type as string) || 'Office';

  const loading_efficiency = 0.80; // CIBSE Guide D: 80% car loading
  const effective_pax = Math.round(capacity * loading_efficiency);

  // Total rise (m) — ground floor to highest floor
  const H_m = Math.round((n_floors - 1) * floor_height * 10) / 10;

  // Flight time (round trip, no acceleration correction for standard speeds)
  const t_flight_s = Math.round((2 * H_m / speed) * 10) / 10;

  // Average number of stops (S) — CIBSE Guide D formula:
  // S = n * [1 - (1 - 1/n)^P]  where n = floors-1 (excluding ground), P = effective_pax
  const n = n_floors - 1;
  const S_raw = n * (1 - Math.pow(1 - 1 / n, effective_pax));
  const avg_stops = Math.round(S_raw * 10) / 10;

  // Stop time = (dwell + door open + door close) × avg_stops
  const t_per_stop = t_dwell + t_door_open + t_door_close;
  const t_stops_s  = Math.round(t_per_stop * avg_stops * 10) / 10;

  // Loading/unloading time — estimated as 0.8 s per passenger (CIBSE typical)
  const t_load_s = Math.round(effective_pax * 0.8 * 10) / 10;

  // Round Trip Time (s)
  const RTT_s = Math.round((t_flight_s + t_stops_s + t_load_s) * 10) / 10;

  // Interval between arrivals (s)
  const interval_s = Math.round((RTT_s / n_elevators) * 10) / 10;

  // 5-minute handling capacity (persons)
  const capacity_5min = Math.round((n_elevators * 300 / RTT_s) * effective_pax);

  // HC% = capacity_5min / population × 100
  const HC_pct = Math.round((capacity_5min / population) * 1000) / 10;

  // Target values by occupancy type (CIBSE Guide D)
  const targets: Record<string, { interval: number; HC: number }> = {
    'Office':       { interval: 30, HC: 12 },
    'Residential':  { interval: 60, HC: 7  },
    'Hotel':        { interval: 40, HC: 10 },
    'Mixed-Use':    { interval: 40, HC: 11 },
  };
  const tgt = targets[occupancy] || targets['Office'];

  return {
    H_m,
    t_flight_s,
    avg_stops,
    t_stops_s,
    t_load_s,
    RTT_s,
    interval_s,
    effective_pax,
    capacity_5min,
    HC_pct,
    target_interval_s: tgt.interval,
    target_HC_pct:     tgt.HC,
  };
}

// ─── Fire Protection: Fire Sprinkler Hydraulic (NFPA 13 Design Area Method) ──

function calcFireSprinklerHydraulic(inputs: Record<string, number | string>): Record<string, unknown> {
  const hazard      = (inputs.occupancy_hazard as string) || 'Ordinary Group 1';
  const K           = Number(inputs.k_factor)          || 80;   // L/min / bar^0.5
  const P_min       = Number(inputs.operating_pressure) || 0.7; // bar at remote sprinkler
  const pipe_mat    = (inputs.pipe_material as string)  || 'Black Steel';
  const pipe_length = Number(inputs.pipe_length)        || 30;  // m, riser to remote head

  // NFPA 13 design parameters by occupancy hazard classification
  const hazardTable: Record<string, { density: number; area: number; coverage: number; hose: number; duration: number }> = {
    'Light Hazard':       { density: 4.1,  area: 139, coverage: 18.6, hose: 250,  duration: 30  },
    'Ordinary Group 1':   { density: 6.1,  area: 139, coverage: 12.1, hose: 500,  duration: 60  },
    'Ordinary Group 2':   { density: 8.1,  area: 139, coverage: 12.1, hose: 500,  duration: 60  },
    'Extra Hazard Grp 1': { density: 12.2, area: 232, coverage: 9.3,  hose: 950,  duration: 90  },
    'Extra Hazard Grp 2': { density: 16.3, area: 279, coverage: 9.3,  hose: 950,  duration: 120 },
  };
  const hd = hazardTable[hazard] || hazardTable['Ordinary Group 1'];

  // Hazen-Williams C factor by pipe material
  const C_map: Record<string, number> = { 'Black Steel': 120, 'CPVC': 150, 'Copper': 140 };
  const C = C_map[pipe_mat] || 120;

  // Number of sprinklers in design area
  const N_sprinklers = Math.ceil(hd.area / hd.coverage);

  // Flow per sprinkler from density method
  const Q_per_sprinkler_density = (hd.density * hd.area) / N_sprinklers; // L/min

  // Required pressure from K-factor: P = (Q/K)^2
  const P_required = Math.pow(Q_per_sprinkler_density / K, 2);
  const P_design   = Math.max(P_required, P_min); // bar

  // Actual flow per sprinkler at design pressure: Q = K x sqrt(P)
  const Q_per_head = K * Math.sqrt(P_design);
  const Q_sprinklers_total = Q_per_head * N_sprinklers; // L/min

  // Auto-select pipe diameter to keep velocity <= 3.0 m/s
  const std_sizes = [25, 32, 40, 50, 65, 80, 100, 125, 150]; // mm
  let pipe_dia = 150;
  for (const d of std_sizes) {
    const A_m2 = Math.PI * Math.pow(d / 1000, 2) / 4;
    const v    = (Q_sprinklers_total / 1000 / 60) / A_m2;
    if (v <= 3.0) { pipe_dia = d; break; }
  }

  // Hazen-Williams friction loss: hL (bar/m) = 6.05e4 x Q^1.85 / (C^1.85 x d^4.87)
  const hL_per_m  = 6.05e4 * Math.pow(Q_sprinklers_total, 1.85) / (Math.pow(C, 1.85) * Math.pow(pipe_dia, 4.87));
  const H_friction = hL_per_m * pipe_length; // bar

  // Required source pressure = design pressure + friction losses
  const P_source     = P_design + H_friction;
  const P_source_kPa = P_source * 100;

  // Total flow including hose stream allowance
  const Q_hose  = hd.hose;
  const Q_total = Q_sprinklers_total + Q_hose;

  // Water storage volume
  const water_L  = Q_total * hd.duration;
  const water_m3 = water_L / 1000;

  // Velocity check
  const A_pipe   = Math.PI * Math.pow(pipe_dia / 1000, 2) / 4;
  const velocity = (Q_sprinklers_total / 1000 / 60) / A_pipe;

  return {
    hazard,
    N_sprinklers,
    Q_per_head:           Math.round(Q_per_head * 10) / 10,
    P_design:             Math.round(P_design * 100) / 100,
    Q_sprinklers_total:   Math.round(Q_sprinklers_total),
    Q_hose,
    Q_total:              Math.round(Q_total),
    pipe_dia,
    pipe_material:        pipe_mat,
    velocity:             Math.round(velocity * 100) / 100,
    H_friction:           Math.round(H_friction * 1000) / 1000,
    P_source:             Math.round(P_source * 100) / 100,
    P_source_kPa:         Math.round(P_source_kPa),
    duration:             hd.duration,
    water_volume_L:       Math.round(water_L),
    water_volume_m3:      Math.round(water_m3 * 100) / 100,
    density:              hd.density,
    design_area:          hd.area,
    coverage_per_head:    hd.coverage,
    inputs_used: {
      hazard, K, P_design, pipe_dia, C, pipe_length, density: hd.density,
      design_area: hd.area, N_sprinklers, hose: hd.hose, duration: hd.duration,
    },
  };
}

// ─── Fire Protection: Fire Pump Sizing (NFPA 20) ─────────────────────────────

function calcFirePumpSizing(inputs: Record<string, number | string>): Record<string, unknown> {
  const Q_Lmin         = Number(inputs.required_flow)        || 500;   // L/min from sprinkler calc
  const P_req_bar      = Number(inputs.required_pressure)    || 7.0;   // bar at system connection
  const elev_m         = Number(inputs.elevation)            || 0;     // m, pump to highest outlet
  const suction_type   = (inputs.suction_type as string)     || 'Flooded Suction';
  const suction_head   = Number(inputs.suction_head)         || 1.5;   // m (positive = flooded, value used as magnitude)
  const pipe_mat       = (inputs.pipe_material as string)    || 'Steel';
  const pipe_length    = Number(inputs.pipe_length)          || 20;    // m, suction + discharge combined
  const pipe_dia_mm    = Number(inputs.pipe_diameter)        || 0;     // 0 = auto-select
  const pump_eff_pct   = Number(inputs.pump_efficiency)      || 70;    // %
  const motor_eff_pct  = Number(inputs.motor_efficiency)     || 90;    // %
  const drive_type     = (inputs.drive_type as string)       || 'Electric Motor';

  // Hazen-Williams C factor
  const C_map: Record<string, number> = { 'Steel': 120, 'Cast Iron': 100, 'Stainless Steel': 140 };
  const C = C_map[pipe_mat] || 120;

  // Convert required pressure to head (1 bar = 10.197 m H2O)
  const P_req_m = P_req_bar * 10.197;

  // Auto-select pipe diameter if not specified (target velocity 1.5–2.5 m/s)
  const std_sizes = [50, 65, 80, 100, 125, 150, 200, 250, 300]; // mm
  const Q_m3s = Q_Lmin / 1000 / 60;
  let pipe_dia = pipe_dia_mm > 0 ? pipe_dia_mm : 100;
  if (pipe_dia_mm === 0) {
    for (const d of std_sizes) {
      const A = Math.PI * Math.pow(d / 1000, 2) / 4;
      const v = Q_m3s / A;
      if (v <= 2.5) { pipe_dia = d; break; }
    }
  }

  // Pipe velocity
  const A_pipe = Math.PI * Math.pow(pipe_dia / 1000, 2) / 4;
  const velocity = Q_m3s / A_pipe;

  // Hazen-Williams friction loss (bar/m → convert to m H2O: ×10.197)
  const hL_bar_per_m = 6.05e4 * Math.pow(Q_Lmin, 1.85) / (Math.pow(C, 1.85) * Math.pow(pipe_dia, 4.87));
  const H_friction_m = hL_bar_per_m * pipe_length * 10.197;

  // Suction head contribution
  // Flooded: positive suction head reduces TDH; Suction lift: negative (adds to TDH)
  const suction_contribution = suction_type === 'Flooded Suction' ? -suction_head : suction_head;

  // Total Dynamic Head
  // TDH = Required pressure head + Static elevation + Friction loss - Suction head (if flooded)
  const TDH_m = P_req_m + elev_m + H_friction_m + suction_contribution;

  // Pump shaft power (BHP)
  // P_kW = (ρ × g × Q × H) / (η_pump × 1000) = 9.81 × Q_m3s × TDH_m / (pump_eff/100)
  const P_shaft_kW = (9.81 * Q_m3s * TDH_m) / (pump_eff_pct / 100);
  const P_shaft_HP = P_shaft_kW * 1.341;

  // Motor input power
  const P_motor_kW = P_shaft_kW / (motor_eff_pct / 100);
  const P_motor_HP = P_motor_kW * 1.341;

  // NFPA 20 motor rating requirement
  // Electric motor: rated at 115% of pump BHP; Diesel: 120%
  const nfpa_factor = drive_type === 'Diesel Engine' ? 1.20 : 1.15;
  const P_nfpa_kW   = P_shaft_kW * nfpa_factor;
  const P_nfpa_HP   = P_nfpa_kW * 1.341;

  // Select next standard fire pump HP size
  const std_HP = [5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 250, 300, 400, 500];
  let selected_HP = std_HP[std_HP.length - 1];
  for (const hp of std_HP) {
    if (hp >= P_nfpa_HP) { selected_HP = hp; break; }
  }
  const selected_kW = selected_HP / 1.341;

  // NFPA 20 overload check: pump must deliver 150% flow at 65% pressure
  const Q_overload  = Q_Lmin * 1.5;
  const P_overload  = P_req_bar * 0.65;

  // Jockey pump sizing (NFPA 20: 1% of fire pump flow, pressure + 10%)
  const Q_jockey_Lmin   = Math.ceil(Q_Lmin * 0.01);
  const P_jockey_bar    = P_req_bar * 1.10;
  const P_jockey_kW     = (9.81 * (Q_jockey_Lmin / 1000 / 60) * (P_jockey_bar * 10.197)) / 0.70;
  const P_jockey_HP     = P_jockey_kW * 1.341;
  let selected_jockey_HP = 1.0;
  for (const hp of std_HP) {
    if (hp >= P_jockey_HP) { selected_jockey_HP = hp; break; }
  }

  const round2 = (n: number) => Math.round(n * 100) / 100;

  return {
    Q_Lmin,
    P_req_bar,
    TDH_m:           round2(TDH_m),
    TDH_bar:          round2(TDH_m / 10.197),
    P_req_m:          round2(P_req_m),
    elev_m,
    H_friction_m:     round2(H_friction_m),
    suction_type,
    suction_head_m:   suction_head,
    pipe_dia,
    pipe_material:    pipe_mat,
    velocity:         round2(velocity),
    P_shaft_kW:       round2(P_shaft_kW),
    P_shaft_HP:       round2(P_shaft_HP),
    P_motor_kW:       round2(P_motor_kW),
    P_motor_HP:       round2(P_motor_HP),
    nfpa_factor,
    P_nfpa_kW:        round2(P_nfpa_kW),
    P_nfpa_HP:        round2(P_nfpa_HP),
    selected_HP,
    selected_kW:      round2(selected_kW),
    drive_type,
    Q_overload,
    P_overload:       round2(P_overload),
    Q_jockey_Lmin,
    P_jockey_bar:     round2(P_jockey_bar),
    selected_jockey_HP,
    pump_eff_pct,
    motor_eff_pct,
    inputs_used: {
      Q_Lmin, P_req_bar, elev_m, suction_type, suction_head,
      pipe_mat, pipe_dia, C, pipe_length, pump_eff_pct, motor_eff_pct, drive_type,
    },
  };
}

// ─── Fire Protection: Stairwell Pressurization (NFPA 92) ─────────────────────

function calcStairwellPressurization(inputs: Record<string, number | string>): Record<string, unknown> {
  const building_type   = (inputs.building_type as string)   || 'Sprinklered';
  const N_stairwells    = Number(inputs.n_stairwells)        || 1;
  const N_floors        = Number(inputs.n_floors)            || 5;
  const doors_per_floor = Number(inputs.doors_per_floor)     || 1;
  const door_fit        = (inputs.door_fit as string)        || 'Average';
  const delta_P_Pa      = Number(inputs.delta_P)             || (building_type === 'Sprinklered' ? 25 : 50);
  const door_W          = Number(inputs.door_width)          || 0.90;  // m
  const door_H          = Number(inputs.door_height)         || 2.10;  // m
  const fan_static_Pa   = Number(inputs.fan_static_pressure) || 400;   // Pa
  const fan_eff_pct     = Number(inputs.fan_efficiency)      || 60;    // %
  const safety_factor   = 1.20;

  // NFPA 92 Table B.1 — leakage area per door (m²)
  const door_leakage_map: Record<string, number> = {
    'Tight':   0.019,
    'Average': 0.039,
    'Loose':   0.052,
  };
  const A_door_m2 = door_leakage_map[door_fit] || 0.039;

  // Wall leakage per floor — NFPA 92 typical stairwell wall: 0.0009 m² per m² of wall
  // Assume stairwell perimeter ~12 m, floor-to-floor 3 m → wall area = 36 m² per floor
  const A_wall_per_floor = 36 * 0.0009; // ~0.032 m²

  // Total leakage area per stairwell
  const N_doors_total  = N_floors * doors_per_floor;
  const A_door_total   = N_doors_total * A_door_m2;
  const A_wall_total   = N_floors * A_wall_per_floor;
  const A_total_m2     = A_door_total + A_wall_total;

  // Pressurization airflow (NFPA 92 Eq. 6.4.1.1)
  // Q = Cd × A × sqrt(2 × ΔP / ρ)
  const Cd    = 0.65;
  const rho   = 1.20; // kg/m³ (air at ~25°C, sea level)
  const Q_m3s = Cd * A_total_m2 * Math.sqrt(2 * delta_P_Pa / rho);

  // Per stairwell and total
  const Q_per_stairwell_m3s   = Q_m3s;
  const Q_total_m3s           = Q_m3s * N_stairwells;
  const Q_design_m3s          = Q_total_m3s * safety_factor;

  // Convert to m³/h (CMH) — standard Philippine fan rating unit
  const Q_design_CMH = Q_design_m3s * 3600;
  const Q_per_CMH    = Q_per_stairwell_m3s * 3600;

  // Door opening force check (NFPA 92 max = 133 N)
  const A_door_panel = door_W * door_H; // m²
  const F_pressure_N = delta_P_Pa * A_door_panel; // simplified: ΔP × door area
  const F_closer_N   = 45; // typical door closer force (N)
  const F_total_N    = F_pressure_N + F_closer_N;
  const door_force_ok = F_total_N <= 133;

  // Fan motor power
  const P_fan_kW   = (Q_design_m3s * fan_static_Pa) / (fan_eff_pct / 100 * 1000);
  const P_fan_HP   = P_fan_kW * 1.341;

  // Select next standard HP
  const std_HP = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0, 7.5, 10.0, 15.0, 20.0, 25.0, 30.0];
  let selected_HP = std_HP[std_HP.length - 1];
  for (const hp of std_HP) {
    if (hp >= P_fan_HP) { selected_HP = hp; break; }
  }

  // NFPA 92 design pressure limits
  const delta_P_min = building_type === 'Sprinklered' ? 12.5 : 25; // Pa
  const delta_P_max = 87; // Pa (NFPA 92 — max before door becomes too hard to open)

  const round3 = (n: number) => Math.round(n * 1000) / 1000;
  const round2 = (n: number) => Math.round(n * 100) / 100;
  const round1 = (n: number) => Math.round(n * 10) / 10;

  return {
    building_type,
    N_stairwells,
    N_floors,
    doors_per_floor,
    N_doors_total,
    door_fit,
    A_door_m2,
    A_door_total:            round3(A_door_total),
    A_wall_per_floor:        round3(A_wall_per_floor),
    A_wall_total:            round3(A_wall_total),
    A_total_m2:              round3(A_total_m2),
    delta_P_Pa,
    delta_P_min,
    delta_P_max,
    delta_P_ok:              delta_P_Pa >= delta_P_min && delta_P_Pa <= delta_P_max,
    Cd,
    Q_per_stairwell_m3s:     round3(Q_per_stairwell_m3s),
    Q_per_CMH:               round1(Q_per_CMH),
    Q_total_m3s:             round3(Q_total_m3s),
    Q_design_m3s:            round3(Q_design_m3s),
    Q_design_CMH:            round1(Q_design_CMH),
    safety_factor,
    door_W,
    door_H,
    A_door_panel:            round2(A_door_panel),
    F_pressure_N:            round1(F_pressure_N),
    F_closer_N,
    F_total_N:               round1(F_total_N),
    door_force_ok,
    fan_static_Pa,
    fan_eff_pct,
    P_fan_kW:                round2(P_fan_kW),
    P_fan_HP:                round2(P_fan_HP),
    selected_HP,
    inputs_used: {
      building_type, N_stairwells, N_floors, doors_per_floor,
      door_fit, A_door_m2, delta_P_Pa, fan_static_Pa, fan_eff_pct,
    },
  };
}

// ─── Fire Protection: Fire Alarm Battery Standby (NFPA 72) ───────────────────

function calcFireAlarmBattery(inputs: Record<string, number | string>): Record<string, unknown> {
  const system_voltage   = Number(inputs.system_voltage)    || 24;   // V (12 or 24)
  const standby_hours    = Number(inputs.standby_hours)     || 24;   // 24h standard, 60h supervising
  const alarm_minutes    = Number(inputs.alarm_minutes)     || 5;    // minutes
  const safety_factor    = 1.25;                                     // NFPA 72 mandatory 25%

  // Panel currents (mA)
  const panel_standby_mA = Number(inputs.panel_standby_mA) || 50;
  const panel_alarm_mA   = Number(inputs.panel_alarm_mA)   || 200;

  // Device counts
  const n_addr_smoke   = Number(inputs.n_addr_smoke)   || 0; // addressable smoke/heat
  const n_conv_smoke   = Number(inputs.n_conv_smoke)   || 0; // conventional 4-wire smoke
  const n_heat         = Number(inputs.n_heat)         || 0; // heat detectors
  const n_pull         = Number(inputs.n_pull)         || 0; // manual pull stations
  const n_horn_strobe  = Number(inputs.n_horn_strobe)  || 0; // horn + strobe (24V)
  const n_strobe       = Number(inputs.n_strobe)       || 0; // strobe only (24V)
  const n_bell         = Number(inputs.n_bell)         || 0; // bells

  // Typical device currents (mA) per NFPA 72 / manufacturer defaults
  const DEVICE_CURRENT: Record<string, { standby: number; alarm: number }> = {
    addr_smoke:  { standby: 0.3,  alarm: 3.0   },
    conv_smoke:  { standby: 0.5,  alarm: 20.0  },
    heat:        { standby: 0.3,  alarm: 15.0  },
    pull:        { standby: 0.1,  alarm: 0.5   },
    horn_strobe: { standby: 0.0,  alarm: 100.0 },
    strobe:      { standby: 0.0,  alarm: 75.0  },
    bell:        { standby: 0.0,  alarm: 80.0  },
  };

  // Total standby current (mA)
  const I_standby_devices =
    n_addr_smoke  * DEVICE_CURRENT.addr_smoke.standby +
    n_conv_smoke  * DEVICE_CURRENT.conv_smoke.standby +
    n_heat        * DEVICE_CURRENT.heat.standby +
    n_pull        * DEVICE_CURRENT.pull.standby +
    n_horn_strobe * DEVICE_CURRENT.horn_strobe.standby +
    n_strobe      * DEVICE_CURRENT.strobe.standby +
    n_bell        * DEVICE_CURRENT.bell.standby;

  const I_standby_total_mA = panel_standby_mA + I_standby_devices;

  // Total alarm current (mA)
  const I_alarm_devices =
    n_addr_smoke  * DEVICE_CURRENT.addr_smoke.alarm +
    n_conv_smoke  * DEVICE_CURRENT.conv_smoke.alarm +
    n_heat        * DEVICE_CURRENT.heat.alarm +
    n_pull        * DEVICE_CURRENT.pull.alarm +
    n_horn_strobe * DEVICE_CURRENT.horn_strobe.alarm +
    n_strobe      * DEVICE_CURRENT.strobe.alarm +
    n_bell        * DEVICE_CURRENT.bell.alarm;

  const I_alarm_total_mA = panel_alarm_mA + I_alarm_devices;

  // Battery capacity (Ah)
  const Ah_standby = (I_standby_total_mA / 1000) * standby_hours;
  const Ah_alarm   = (I_alarm_total_mA   / 1000) * (alarm_minutes / 60);
  const Ah_calc    = Ah_standby + Ah_alarm;
  const Ah_required = Ah_calc * safety_factor;

  // Standard battery sizes (Ah) — common Philippine/ASEAN market
  const std_Ah = [1.2, 2.6, 4.5, 7, 12, 17, 18, 26, 33, 40, 55, 65, 75, 100, 120, 150, 200];
  let selected_Ah = std_Ah[std_Ah.length - 1];
  for (const ah of std_Ah) {
    if (ah >= Ah_required) { selected_Ah = ah; break; }
  }

  // Number of batteries (series for 24V system: 2× 12V; single for 12V)
  const n_batteries   = system_voltage === 24 ? 2 : 1;
  const battery_volts = system_voltage === 24 ? 12 : 12;

  // Charger current check — NFPA 72: must recharge within 48 hours
  const I_charger_min_A  = selected_Ah / 48;   // minimum charger current (A)
  const I_charger_rec_A  = selected_Ah / 10;   // recommended C/10 rate (A)

  const round3 = (n: number) => Math.round(n * 1000) / 1000;
  const round2 = (n: number) => Math.round(n * 100) / 100;

  return {
    system_voltage,
    standby_hours,
    alarm_minutes,
    panel_standby_mA,
    panel_alarm_mA,
    n_addr_smoke, n_conv_smoke, n_heat, n_pull, n_horn_strobe, n_strobe, n_bell,
    I_standby_devices:    round2(I_standby_devices),
    I_standby_total_mA:   round2(I_standby_total_mA),
    I_alarm_devices:      round2(I_alarm_devices),
    I_alarm_total_mA:     round2(I_alarm_total_mA),
    Ah_standby:           round3(Ah_standby),
    Ah_alarm:             round3(Ah_alarm),
    Ah_calc:              round3(Ah_calc),
    safety_factor,
    Ah_required:          round3(Ah_required),
    selected_Ah,
    n_batteries,
    battery_volts,
    battery_config:       system_voltage === 24 ? `2 × 12V ${selected_Ah}Ah in series` : `1 × 12V ${selected_Ah}Ah`,
    I_charger_min_A:      round2(I_charger_min_A),
    I_charger_rec_A:      round2(I_charger_rec_A),
    device_currents:      DEVICE_CURRENT,
    inputs_used: {
      system_voltage, standby_hours, alarm_minutes, panel_standby_mA, panel_alarm_mA,
      n_addr_smoke, n_conv_smoke, n_heat, n_pull, n_horn_strobe, n_strobe, n_bell,
    },
  };
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
    } else if (calc_type === "Compressed Air") {
      results = calcCompressedAir(inputs);
    } else if (calc_type === "Water Supply Pipe Sizing") {
      results = calcWaterSupplyPipeSizing(inputs);
    } else if (calc_type === "Hot Water Demand") {
      results = calcHotWaterDemand(inputs);
    } else if (calc_type === "Drainage Pipe Sizing") {
      results = calcDrainagePipeSizing(inputs);
    } else if (calc_type === "Septic Tank Sizing") {
      results = calcSepticTankSizing(inputs);
    } else if (calc_type === "Load Estimation") {
      results = calcLoadEstimation(inputs);
    } else if (calc_type === "Voltage Drop") {
      results = calcVoltageDrop(inputs);
    } else if (calc_type === "Wire Sizing") {
      results = calcWireSizing(inputs);
    } else if (calc_type === "Fire Sprinkler Hydraulic") {
      results = calcFireSprinklerHydraulic(inputs);
    } else if (calc_type === "Fire Pump Sizing") {
      results = calcFirePumpSizing(inputs);
    } else if (calc_type === "Stairwell Pressurization") {
      results = calcStairwellPressurization(inputs);
    } else if (calc_type === "Fire Alarm Battery") {
      results = calcFireAlarmBattery(inputs);
    } else if (calc_type === "Elevator Traffic Analysis") {
      results = calcElevatorTraffic(inputs);
    } else if (calc_type === "Shaft Design") {
      results = calcShaftDesign(inputs);
    } else if (calc_type === "Bearing Life (L10)") {
      results = calcBearingLife(inputs);
    } else if (calc_type === "V-Belt Drive Design") {
      results = calcVBeltDrive(inputs);
    } else if (calc_type === "Hoist Capacity") {
      results = calcHoistCapacity(inputs);
    } else if (calc_type === "Bolt Torque & Preload") {
      results = calcBoltTorque(inputs);
    } else if (calc_type === "Short Circuit") {
      results = calcShortCircuit(inputs);
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
