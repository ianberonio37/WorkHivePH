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

// ASHRAE design solar irradiance by orientation: Manila latitude ~14.6°N
// Source: ASHRAE 2021 Fundamentals Ch. 18, peak design values for tropical latitudes.
// "Mixed" preserves the original 200 W/m² default for unknown or multi-orientation facades.
const SOLAR_IRRADIANCE_BY_ORIENTATION: Record<string, number> = {
  "North":      90,
  "South":      130,
  "East":       700,
  "West":       700,
  "Horizontal": 950,
  "Mixed":      200,
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
  const persons       = Number(inputs.persons)      || 0;
  const equipKW       = Number(inputs.equipment_kw) || 0;
  const outdoorTemp   = Number(inputs.outdoor_temp)  || 35;
  const indoorTemp    = Number(inputs.indoor_temp)   || 24;
  const insulation        = String(inputs.insulation         || "Standard");
  const glassType         = String(inputs.glass_type         || "Standard");
  const windowOrientation = String(inputs.window_orientation || "Mixed");
  const roomFunction      = String(inputs.room_function      || "Office");

  const deltaT = outdoorTemp - indoorTemp;

  const uWall  = U_VALUES[insulation]      || 0.45;
  const qWalls = uWall * (wallArea - glassArea) * deltaT;

  const roofArea = floorArea;
  const uRoof  = ROOF_U_VALUES[insulation] || 0.50;
  const qRoof  = uRoof * roofArea * deltaT * 1.15;

  const shgc           = GLASS_SHGC[glassType] || 0.87;
  const solarIrradiance = SOLAR_IRRADIANCE_BY_ORIENTATION[windowOrientation] ?? 200;
  const qGlass          = (0.57 * glassArea * deltaT) + (glassArea * shgc * solarIrradiance);

  const heatPP          = HEAT_PER_PERSON[roomFunction] || { sensible: 75, latent: 55 };
  const qPeopleSensible = persons * heatPP.sensible;  // sensible portion only: goes into sensible sub-total
  const qPeopleLatent   = persons * heatPP.latent;    // latent portion: tracked separately

  const qEquipment = equipKW * 1000 * 0.85;

  const litWpm2   = LIGHTING_WPM2[roomFunction] || 12;
  const qLighting = litWpm2 * floorArea;

  const volume        = floorArea * ceilingHeight;
  const qInfiltration = 0.5 * volume * 0.35 * deltaT;

  // ASHRAE Cooling Load: sensible sub-total uses occupant SENSIBLE heat only.
  // Latent heat (occupant moisture) is added separately: not as a % of combined people heat.
  const qSensibleTotal = qWalls + qRoof + qGlass + qPeopleSensible + qEquipment + qLighting + qInfiltration;
  const qLatent        = qPeopleLatent;
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
      q_people:       Math.round(qPeopleSensible),
      q_people_latent: Math.round(qPeopleLatent),
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
      shgc:               shgc,
      window_orientation: windowOrientation,
      solar_irradiance:   solarIrradiance,
      delta_t:            deltaT,
      lighting_wpm2:      litWpm2,
      heat_per_person:    heatPP,
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

// ─── Water Kinematic Viscosity (temperature-dependent) ────────────────────────
// ASHRAE 2021 Fundamentals Table 2: Water Properties
function kinematicViscosityWater(T_C: number): number {
  const table: [number, number][] = [
    [0,  1.787e-6], [5,  1.519e-6], [10, 1.307e-6], [15, 1.139e-6],
    [20, 1.004e-6], [25, 0.893e-6], [30, 0.801e-6], [35, 0.727e-6],
    [40, 0.658e-6], [50, 0.553e-6], [60, 0.475e-6], [70, 0.413e-6],
    [80, 0.365e-6], [90, 0.326e-6], [100, 0.295e-6],
  ];
  if (T_C <= table[0][0]) return table[0][1];
  if (T_C >= table[table.length - 1][0]) return table[table.length - 1][1];
  for (let i = 0; i < table.length - 1; i++) {
    if (T_C >= table[i][0] && T_C <= table[i + 1][0]) {
      const t = (T_C - table[i][0]) / (table[i + 1][0] - table[i][0]);
      return table[i][1] + t * (table[i + 1][1] - table[i][1]);
    }
  }
  return 0.801e-6;
}

// Default fluid temperature (°C) by pipe service type
function defaultFluidTempC(serviceType: string): number {
  const defaults: Record<string, number> = {
    'Chilled Water Supply': 7,  'Chilled Water Return': 12,
    'Hot Water Supply':     80, 'Condenser Water':      35,
    'Cold Water Supply':    20, 'Fire Protection':      20,
    'General Water':        20,
  };
  return defaults[serviceType] ?? 20;
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
  const vaporPressure = 0.43; // m at 30°C water: IAPWS-IF97: Pvap(30°C)=4.243 kPa = 0.432 m water head
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

  const fluidTempC = Number(inputs.fluid_temp_c ?? defaultFluidTempC(serviceType));
  const C_base     = PIPE_C_VALUES[pipeMaterial] || 150;
  // Hazen-Williams temperature correction (ASHRAE 2021 Fundamentals Ch.22):
  // C_T = C_base × (1 + 0.01 × (T − 15.5))   where T in °C
  const C          = Math.round(C_base * (1 + 0.01 * (fluidTempC - 15.5)) * 100) / 100;
  const limits     = VELOCITY_LIMITS[serviceType] || VELOCITY_LIMITS["General Water"];
  const g          = 9.81;

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

  // Reynolds number: temperature-dependent kinematic viscosity (ASHRAE 2021 Table 2)
  const nu = kinematicViscosityWater(fluidTempC);
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
      fluid_temp_c:   fluidTempC,
      C_base:         C_base,
      C_factor:       C,
      fittings_pct:   fittingsPct,
      equiv_length:   Math.round(equivLength * 10) / 10,
      velocity_limits: limits,
    }
  };
}

// ─── Chiller System — Water Cooled Calculation ───────────────────────────────
// Method: Q_design = load × SF, P = Q/COP, Q_rejection = Q+P (first law)
// CW flow via Q_rejection, CHW flow via Q_design, ASHRAE 90.1 COP by chiller type
function calcChillerWaterCooled(inputs: Record<string, number | string>) {
  const Q_input_kW   = Number(inputs.cooling_load_kW)  || 0;
  const chillerType  = String(inputs.chiller_type      || 'Centrifugal');
  const chwSupply    = Number(inputs.chw_supply_C)     || 7;
  const chwReturn    = Number(inputs.chw_return_C)     || 12;
  const cwSupply     = Number(inputs.cw_supply_C)      || 29;
  const cwReturn     = Number(inputs.cw_return_C)      || 35;
  const cop          = Number(inputs.cop)              || 5.5;
  const safetyFactor = Number(inputs.safety_factor)    || 1.10;
  const nUnits       = Math.max(1, Math.round(Number(inputs.n_units) || 2));

  // 1. Design load
  const Q_design_kW = Q_input_kW * safetyFactor;
  const Q_design_TR = Q_design_kW / 3.517;

  // 2. Compressor power
  const P_total_kW    = Q_design_kW / cop;
  const P_per_unit_kW = P_total_kW / nUnits;

  // 3. Heat rejection to condenser water (first law)
  const Q_rejection_kW = Q_design_kW + P_total_kW;
  const Q_rejection_TR = parseFloat((Q_rejection_kW / 3.517).toFixed(2));

  // 4. Per-unit capacity
  const Q_per_unit_kW = Q_design_kW / nUnits;
  const Q_per_unit_TR = Q_per_unit_kW / 3.517;

  // 5. Nominal chiller size
  const STD_SIZES_TR = [10,15,20,25,30,40,50,60,75,100,125,150,200,250,300,350,400,500,600,800,1000];
  const nominal_TR_each = STD_SIZES_TR.find(s => s >= Q_per_unit_TR) || Math.ceil(Q_per_unit_TR / 50) * 50;
  const nominal_kW_each = parseFloat((nominal_TR_each * 3.517).toFixed(1));
  const nominal_total_TR = nominal_TR_each * nUnits;

  // 6. CW flow rate
  const dT_cw      = Math.max(1, cwReturn - cwSupply);
  const Q_cw_lps   = Q_rejection_kW / (4.187 * dT_cw);
  const Q_cw_m3h   = Q_cw_lps * 3.6;
  const Q_cw_GPM   = Q_cw_lps * 15.8508;

  // 7. CHW flow rate
  const dT_chw     = Math.max(1, chwReturn - chwSupply);
  const Q_chw_lps  = Q_design_kW / (4.187 * dT_chw);
  const Q_chw_m3h  = Q_chw_lps * 3.6;
  const Q_chw_GPM  = Q_chw_lps * 15.8508;

  // 8. ASHRAE 90.1 minimum COP and IPLV by chiller type and size
  // Water-cooled minimums (ASHRAE 90.1-2019 Table 6.8.1-3)
  let ashrae_min_cop: number;
  let ashrae_min_iplv: number;
  const type = chillerType.toLowerCase();
  if (type.includes('centrifugal')) {
    if (Q_design_kW < 528)       { ashrae_min_cop = 5.00; ashrae_min_iplv = 6.28; }  // < 150 TR
    else if (Q_design_kW < 1055) { ashrae_min_cop = 5.55; ashrae_min_iplv = 7.19; }  // 150–300 TR
    else                          { ashrae_min_cop = 6.10; ashrae_min_iplv = 8.27; }  // > 300 TR
  } else if (type.includes('screw')) {
    if (Q_design_kW < 528) { ashrae_min_cop = 4.45; ashrae_min_iplv = 5.32; }
    else                    { ashrae_min_cop = 4.90; ashrae_min_iplv = 5.86; }
  } else if (type.includes('scroll')) {
    ashrae_min_cop = 4.45; ashrae_min_iplv = 5.32;
  } else {
    ashrae_min_cop = 3.80; ashrae_min_iplv = 4.32; // reciprocating / other
  }
  const cop_check  = cop >= ashrae_min_cop ? 'PASS' : 'FAIL';
  const cop_margin = parseFloat((cop - ashrae_min_cop).toFixed(3));

  // IPLV check (user-supplied from AHRI 550/590 chiller datasheet)
  const iplv: number | null = inputs.iplv !== undefined && inputs.iplv !== '' ? Number(inputs.iplv) : null;
  const iplv_check  = iplv !== null ? (iplv >= ashrae_min_iplv ? 'PASS' : 'FAIL') : null;
  const iplv_margin = iplv !== null ? parseFloat((iplv - ashrae_min_iplv).toFixed(3)) : null;

  // 9. Electrical
  const total_kVA        = parseFloat((P_total_kW / 0.85).toFixed(1));
  const total_A_at_400V  = parseFloat((total_kVA * 1000 / (Math.sqrt(3) * 400)).toFixed(1));

  // 10. Refrigerant (water-cooled: R-134a large centrifugal, R-1234ze new, R-32 screw/scroll)
  const refrigerant = type.includes('centrifugal')
    ? 'R-134a or R-1234ze(E) (low-GWP, preferred for new centrifugal installations)'
    : 'R-32 or R-410A (screw/scroll: verify per manufacturer specification)';

  return {
    inputs_used: { cooling_load_kW: Q_input_kW, chiller_type: chillerType, chw_supply_C: chwSupply, chw_return_C: chwReturn, cw_supply_C: cwSupply, cw_return_C: cwReturn, cop, safety_factor: safetyFactor, n_units: nUnits },
    Q_input_kW:          parseFloat(Q_input_kW.toFixed(2)),
    Q_design_kW:         parseFloat(Q_design_kW.toFixed(2)),
    Q_design_TR:         parseFloat(Q_design_TR.toFixed(2)),
    safety_factor:       safetyFactor,
    P_total_kW:          parseFloat(P_total_kW.toFixed(2)),
    P_per_unit_kW:       parseFloat(P_per_unit_kW.toFixed(2)),
    cop_used:            cop,
    Q_rejection_kW:      parseFloat(Q_rejection_kW.toFixed(2)),
    Q_rejection_TR,
    n_units:             nUnits,
    Q_per_unit_kW:       parseFloat(Q_per_unit_kW.toFixed(2)),
    Q_per_unit_TR:       parseFloat(Q_per_unit_TR.toFixed(2)),
    nominal_TR_each,
    nominal_kW_each,
    nominal_total_TR,
    dT_cw_C:             parseFloat(dT_cw.toFixed(1)),
    Q_cw_lps:            parseFloat(Q_cw_lps.toFixed(2)),
    Q_cw_m3h:            parseFloat(Q_cw_m3h.toFixed(2)),
    Q_cw_GPM:            parseFloat(Q_cw_GPM.toFixed(1)),
    dT_chw_C:            parseFloat(dT_chw.toFixed(1)),
    Q_chw_lps:           parseFloat(Q_chw_lps.toFixed(2)),
    Q_chw_m3h:           parseFloat(Q_chw_m3h.toFixed(2)),
    Q_chw_GPM:           parseFloat(Q_chw_GPM.toFixed(1)),
    ashrae_min_cop,
    cop_check,
    cop_margin,
    iplv,
    ashrae_min_iplv,
    iplv_check,
    iplv_margin,
    total_kVA,
    total_A_at_400V,
    refrigerant,
    chiller_type:        chillerType,
  };
}

// ─── Chiller System — Air Cooled Calculation ─────────────────────────────────
// Method: Heat balance: Q_design = load × safety, P = Q/COP, Q_rejection = Q + P
// Standards: ASHRAE 90.1 (min COP), ASHRAE 15 (safety), PSME Code
function calcChillerAirCooled(inputs: Record<string, number | string>) {
  const Q_input_kW   = Number(inputs.cooling_load_kW)  || 0;   // building cooling load
  const ambientTemp  = Number(inputs.ambient_temp_C)    || 35;  // design ambient °C
  const chwSupply    = Number(inputs.chw_supply_C)      || 7;   // CHW supply temp °C
  const chwReturn    = Number(inputs.chw_return_C)      || 12;  // CHW return temp °C
  const cop          = Number(inputs.cop)               || 3.0; // COP (dimensionless)
  const safetyFactor = Number(inputs.safety_factor)     || 1.15;
  const nUnits       = Math.max(1, Math.round(Number(inputs.n_units) || 1));

  // 1. Design cooling load (with safety/diversity margin)
  const Q_design_kW  = Q_input_kW * safetyFactor;
  const Q_design_TR  = Q_design_kW / 3.517;

  // 2. Compressor power input (first law: P = Q / COP)
  const P_total_kW   = Q_design_kW / cop;

  // 3. Heat rejection to condenser (first law: Q_rej = Q + W)
  const Q_rejection_kW = Q_design_kW + P_total_kW;

  // 4. Per-unit capacity and power
  const Q_per_unit_kW  = Q_design_kW  / nUnits;
  const Q_per_unit_TR  = Q_per_unit_kW / 3.517;
  const P_per_unit_kW  = P_total_kW   / nUnits;

  // 5. Nominal chiller size: round up to nearest standard tonnage
  const STD_SIZES_TR = [5,7.5,10,15,20,25,30,40,50,60,75,100,125,150,200,250,300,350,400,450,500];
  const nominal_TR_each = STD_SIZES_TR.find(s => s >= Q_per_unit_TR) || Math.ceil(Q_per_unit_TR / 25) * 25;
  const nominal_kW_each = nominal_TR_each * 3.517;
  const nominal_total_TR = nominal_TR_each * nUnits;

  // 6. Condenser airflow: air-cooled rejection
  // Q_airflow (m³/s) = Q_rejection / (rho × cp × delta_T_cond)
  // rho=1.2 kg/m³, cp=1.005 kJ/(kg·K), delta_T_cond=15°C (typ. for air-cooled)
  const rho = 1.2; const cp = 1.005; const dT_cond = 15;
  const Q_airflow_m3s  = Q_rejection_kW / (rho * cp * dT_cond);
  const Q_airflow_CMH  = Q_airflow_m3s * 3600;                // m³/h
  const Q_airflow_CFM  = Q_airflow_m3s * 2118.88;             // CFM

  // Per unit condenser airflow
  const Q_airflow_CMH_per_unit = Q_airflow_CMH / nUnits;

  // 7. Chilled water flow rate
  // Q_flow (L/s) = Q_design_kW / (cp_water × delta_T_chw)
  // cp_water = 4.187 kJ/(kg·K), rho_water = 1.0 kg/L
  const dT_chw       = Math.max(1, chwReturn - chwSupply);    // °C delta-T
  const Q_flow_lps   = Q_design_kW / (4.187 * dT_chw);       // L/s
  const Q_flow_m3h   = Q_flow_lps * 3.6;                      // m³/h
  const Q_flow_GPM   = Q_flow_lps * 15.8508;                  // US GPM

  // 8. ASHRAE 90.1 COP and IPLV check
  // Air-cooled minimums (ASHRAE 90.1-2019 Table 6.8.1-7)
  // Min COP: 2.84 (<528 kW / <150 TR), 2.80 (≥528 kW / ≥150 TR)
  // Min IPLV: 3.50 (<528 kW), 3.45 (≥528 kW)
  const ashrae_min_cop  = Q_design_kW >= 528 ? 2.80 : 2.84;
  const ashrae_min_iplv = Q_design_kW >= 528 ? 3.45 : 3.50;
  const cop_check       = cop >= ashrae_min_cop ? 'PASS' : 'FAIL';
  const cop_margin      = parseFloat((cop - ashrae_min_cop).toFixed(3));

  // IPLV check (user-supplied from AHRI 550/590 chiller datasheet)
  const iplv: number | null = inputs.iplv !== undefined && inputs.iplv !== '' ? Number(inputs.iplv) : null;
  const iplv_check  = iplv !== null ? (iplv >= ashrae_min_iplv ? 'PASS' : 'FAIL') : null;
  const iplv_margin = iplv !== null ? parseFloat((iplv - ashrae_min_iplv).toFixed(3)) : null;

  // 9. Electrical supply estimate (kVA at PF=0.85)
  const total_kVA = P_total_kW / 0.85;
  const total_A_at_400V = (total_kVA * 1000) / (Math.sqrt(3) * 400);  // 3-phase 400V

  // 10. Refrigerant note (R-32 / R-410A at 35°C ambient typical)
  const refrigerant = ambientTemp >= 35 ? 'R-32 or R-410A (verified at 35°C ambient per ASHRAE 15)' : 'R-32 or R-410A';

  return {
    // Inputs echoed back
    inputs_used: {
      cooling_load_kW: Q_input_kW,
      ambient_temp_C: ambientTemp,
      chw_supply_C: chwSupply,
      chw_return_C: chwReturn,
      cop,
      safety_factor: safetyFactor,
      n_units: nUnits,
    },
    // Design load
    Q_input_kW:        parseFloat(Q_input_kW.toFixed(2)),
    Q_design_kW:       parseFloat(Q_design_kW.toFixed(2)),
    Q_design_TR:       parseFloat(Q_design_TR.toFixed(2)),
    safety_factor:     safetyFactor,
    // Compressor
    P_total_kW:        parseFloat(P_total_kW.toFixed(2)),
    P_per_unit_kW:     parseFloat(P_per_unit_kW.toFixed(2)),
    cop_used:          cop,
    // Heat rejection
    Q_rejection_kW:    parseFloat(Q_rejection_kW.toFixed(2)),
    // Per-unit sizing
    n_units:           nUnits,
    Q_per_unit_kW:     parseFloat(Q_per_unit_kW.toFixed(2)),
    Q_per_unit_TR:     parseFloat(Q_per_unit_TR.toFixed(2)),
    nominal_TR_each,
    nominal_kW_each:   parseFloat(nominal_kW_each.toFixed(1)),
    nominal_total_TR,
    // Condenser airflow
    Q_airflow_m3s:     parseFloat(Q_airflow_m3s.toFixed(3)),
    Q_airflow_CMH:     parseFloat(Q_airflow_CMH.toFixed(0)),
    Q_airflow_CFM:     parseFloat(Q_airflow_CFM.toFixed(0)),
    Q_airflow_CMH_per_unit: parseFloat(Q_airflow_CMH_per_unit.toFixed(0)),
    dT_cond_C:         dT_cond,
    // CHW system
    dT_chw_C:          parseFloat(dT_chw.toFixed(1)),
    Q_flow_lps:        parseFloat(Q_flow_lps.toFixed(2)),
    Q_flow_m3h:        parseFloat(Q_flow_m3h.toFixed(2)),
    Q_flow_GPM:        parseFloat(Q_flow_GPM.toFixed(1)),
    // Electrical
    total_kVA:         parseFloat(total_kVA.toFixed(1)),
    total_A_at_400V:   parseFloat(total_A_at_400V.toFixed(1)),
    // Compliance
    ashrae_min_cop,
    cop_check,
    cop_margin,
    iplv,
    ashrae_min_iplv,
    iplv_check,
    iplv_margin,
    refrigerant,
    // Ambient correction note
    ambient_note: ambientTemp >= 35
      ? 'High ambient (≥35°C). Verify chiller performance data is rated at 35°C ambient: not default 30°C/32°C catalog conditions.'
      : 'Ambient below 35°C. Standard catalog data typically applicable.',
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
  // Note: Floor Drain is a drainage fixture: it has no water supply WFU per UPC/PPC.
  // A trap primer supply connection is a small metered line, not sized by WFU method.
  // Do not include Floor Drain in water supply pipe sizing calculations.
  "Mop Sink":                    { wfu: 3,  pfr_lpm: 11.4, label: "Mop Sink",                      type: "both" },
  "Custom":                      { wfu: 0,  pfr_lpm: 0,    label: "Custom Fixture",                 type: "both" },
};

// Hunter's curve: WFU → peak flow (L/s): piecewise interpolation
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

// ─── Electrical: Load Estimation: PEC Article 2.10 / 2.20 ──────────────────
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
    total_connected_kw:   Math.round(breakdown.reduce((s, l) => s + l.qty * l.watts_each, 0) / 1000 * 100) / 100,
    total_demand_va:      Math.round(totalDemVA),
    total_demand_kva:     Math.round(totalDemVA / 1000 * 100) / 100,
    total_demand_kw:      Math.round(breakdown.reduce((s, l) => s + l.qty * l.watts_each * l.demand_factor, 0) / 1000 * 100) / 100,
    computed_ampacity:    Math.round(computedA * 100) / 100,
    ampacity_with_spare:  Math.round(withSpare * 100) / 100,
    recommended_breaker_A: recBreaker,
    load_breakdown:       breakdown,
  };
}

// ─── Electrical: Voltage Drop: PEC Article 2.10.19 / 2.20 ──────────────────
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

// ─── Electrical: Wire Sizing: PEC Table 3.10.1 ──────────────────────────────
// Copper THHN/THWN-2 at 75°C: table ampacities
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

// ─── Septic Tank Sizing: Occupancy-Based Method (PPC / DOH) ─────────────────
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

// ─── Drainage Pipe Sizing: DFU Method (Philippine Plumbing Code / UPC) ─────
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

// UPC Table 7-5: Horizontal branches at 1%, 2%, 4% slope (mm → max DFU)
const HORIZ_DRAIN_TABLE: Record<string, Record<number, number>> = {
  "1%": { 75: 21, 100: 96,  125: 216, 150: 384,  200: 864,  250: 1584, 300: 2520 },
  "2%": { 50: 21, 75: 42,  100: 180, 125: 390,  150: 700,  200: 1600, 250: 2900, 300: 4600 },
  "4%": { 40: 3,  50: 21,  75: 42,  100: 180,  125: 390,  150: 700,  200: 1600 },
};

// UPC Table 7-5: Stacks (total DFU on stack)
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
  let recommended = sortedSizes.find(d => tableRaw[d] >= totalDFU) || sortedSizes[sortedSizes.length - 1];

  // UPC/PPC hard rule: 75mm horizontal branch cannot serve water closets
  const hasWC      = fixtures.some(f => f.fixture_type === "Water Closet");
  const wcOverride = !isStack && hasWC && recommended < 100;
  if (wcOverride) recommended = 100;

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
    wc_override:         wcOverride,
    fixture_breakdown:   fixtureBreakdown,
    size_comparison:     comparison,
  };
}

// ─── Hot Water Demand: ASHRAE Use Rate Method ───────────────────────────────
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

// ─── Report Narrative: Groq 5-model fallback chain ─────────────────────────
// On 429 (rate limit) or 413 (prompt too large): skip to next model silently.
// On auth/server error: bail fast. Only reaches hardcoded fallback when all models fail.
const GROQ_NARRATIVE_CHAIN = [
  "llama-3.3-70b-versatile",                   // 1st: best quality
  "meta-llama/llama-4-scout-17b-16e-instruct",  // 2nd: 500K TPD, fast
  "qwen/qwen3-32b",                             // 3rd: 500K TPD, 60 RPM
  "llama-3.1-8b-instant",                       // 4th: high TPM, lightweight
  "openai/gpt-oss-20b",                         // 5th: strict JSON schema
];

async function generateReportNarrative(
  calcType: string,
  inputs: Record<string, number | string>,
  results: Record<string, unknown>
): Promise<{ objective: string; assumptions: string; recommendations: string }> {

  const GROQ_API_KEY = Deno.env.get("GROQ_API_KEY");
  if (!GROQ_API_KEY) {
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

  for (const model of GROQ_NARRATIVE_CHAIN) {
    try {
      const res = await fetch(
        "https://api.groq.com/openai/v1/chat/completions",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${GROQ_API_KEY}`,
          },
          body: JSON.stringify({
            model,
            messages: [{ role: "user", content: prompt }],
            temperature: 0.3,
            max_tokens: 512,
            response_format: { type: "json_object" },
          }),
        }
      );

      // Rate-limited or prompt too large: try next model silently
      if (res.status === 429 || res.status === 413) {
        const errText = await res.text();
        console.warn(`Narrative model ${model} skipped (${res.status}): ${errText.slice(0, 80)}`);
        continue;
      }
      if (!res.ok) break; // Auth/server error: bail to hardcoded fallback

      const json = await res.json();
      const text = json?.choices?.[0]?.message?.content || "";
      const cleaned = text.replace(/```json\n?/g, "").replace(/```\n?/g, "").trim();
      const parsed = JSON.parse(cleaned);
      if (parsed.objective && parsed.assumptions && parsed.recommendations) {
        console.log(`Narrative generated by: ${model}`);
        return parsed;
      }
    } catch {
      continue; // JSON parse error: try next model
    }
  }

  // All models exhausted or auth/server error: build hardcoded fallback from results directly
  {
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
    } else if (calcType === "Wastewater Treatment (STP)") {
      const flow   = rec.flow_m3_day   ?? '';
      const aVol   = rec.aeration_vol_m3 ?? '';
      const bod    = rec.effluent_bod   ?? '';
      const sludge = rec.sludge_kg_day  ?? '';
      const denr   = rec.denr_status    ?? 'REVIEW';
      recommendations = `The activated sludge STP is sized for ${flow} m³/day average daily flow with an aeration tank volume of ${aVol} m³. Projected effluent BOD is ${bod} mg/L: DENR DAO 2016-08 status: ${denr}. Sludge production is ${sludge} kg dry solids/day: engage a DOH/DENR-licensed septage hauler for removal. Secure DENR Environmental Compliance Certificate (ECC) and DOH Sanitation Permit before construction. Provide minimum 2× duty+standby blowers with VFD. Verify actual wastewater BOD and flow by site measurement before finalizing detailed design.`;
    } else if (calcType === "Water Treatment System") {
      const filterDia  = rec.selected_filter_dia_mm ?? '';
      const trainSteps = Array.isArray(rec.train_steps) ? (rec.train_steps as string[]).join(' → ') : '';
      const cl2        = rec.cl2_dose_mg_L ?? '';
      const storage    = rec.storage_tank_m3 ?? '';
      const pns        = rec.pns_1998_status ?? '';
      recommendations  = `Install the treatment train: ${trainSteps}. Multimedia/sand filter: ${filterDia} mm pressure vessel. Chlorination dose: ${cl2} mg/L NaOCl; provide a calibrated dosing pump and contact tank. Treated water storage: ${storage} m³ (1-day demand). Projected outlet quality: ${pns}. Conduct water quality testing (turbidity, iron, pH, coliform, residual chlorine) after commissioning and every 6 months per DOH/LWUA requirements.`;
    } else if (calcType === "Roof Drain Sizing") {
      const D    = rec.drain_size_mm      ?? '';
      const HL   = rec.horiz_leader_mm   ?? '';
      const Q    = rec.q_total_ls        ?? '';
      const n    = rec.n_drains          ?? '';
      const slp  = rec.leader_slope_pct  ?? '';
      const ovr  = rec.overflow_drain_mm ? `, with ${rec.overflow_drain_mm} mm overflow drains set at +50 mm above primary invert (IPC §1101.7)` : '';
      const mat  = rec.pipe_material     ?? 'uPVC';
      recommendations = `Provide ${n} × ${D} mm primary roof drain bodies with ${D} mm vertical leaders and ${HL} mm horizontal ${mat} leaders at ${slp}% slope${ovr}. Total design flow is ${Q} L/s. Install strainer domes on all drain bodies and verify positive fall to every drain. Conduct a roof flood test per IPC §1109 after installation. Provide accessible cleanouts at all changes of direction.`;
    } else if (calcType === "Storm Drain / Stormwater") {
      const D    = rec.d_selected_mm ?? '';
      const Q    = rec.design_flow_lps ?? '';
      const V    = rec.full_pipe_vel_ms ?? '';
      const chk  = rec.velocity_check ?? '';
      const rp   = rec.return_period_yr ?? '';
      const mat  = rec.pipe_material ?? '';
      recommendations = `Provide ${D} mm ${mat} storm drain pipe for the design catchment. Design flow is ${Q} L/s (${rp}-year return period, Rational Method). Full-pipe velocity is ${V} m/s: velocity check: ${chk}. Maintain minimum 0.6 m/s self-cleaning velocity and maximum slope per DPWH Drainage Design Guidelines. Install cleanouts at every junction and at 50 m maximum intervals. Verify catchment area and runoff coefficient with as-built site grading plans before finalising.`;
    } else if (calcType === "Grease Trap Sizing") {
      const pdi     = rec.pdi_gpm         ?? '';
      const capL    = rec.liquid_cap_l    ?? '';
      const gretKg  = rec.grease_ret_kg   ?? '';
      const days    = rec.clean_interval_days ?? '';
      const qgpm    = rec.q_design_gpm    ?? '';
      recommendations = `Install a PDI-rated ${pdi} GPM hydro-mechanical grease interceptor (PDI G-101). Design flow is ${qgpm} GPM. Liquid holding capacity: ${capL} L; grease retention: ${gretKg} kg. Clean every ${days} days (or when fill exceeds 25% of liquid capacity) using a DENR DAO 2016-08 accredited hauler. Locate the interceptor inside the kitchen, as close as possible to the grease-laden discharge fixtures, with accessible maintenance cover. Secure LGU Sanitary Permit before installation.`;
    } else if (calcType === "Boiler System") {
      const bhp   = rec.q_boiler_bhp ?? '';
      const qkw   = rec.q_boiler_kw ?? '';
      const fuel  = rec.fuel_consumption_kg_hr ?? '';
      const fuelT = String(inputs.fuel_type || 'fuel');
      const n     = inputs.num_boilers ?? 1;
      if (String(inputs.boiler_type) === 'Hot Water') {
        const svKw  = rec.safety_valve_min_kw ?? '';
        const ts    = inputs.supply_temp_c ?? '';
        const tr    = inputs.return_temp_c ?? '';
        const fl    = inputs.flow_rate_lhr ?? '';
        recommendations = `Provide ${n} × ${qkw} kW (${bhp} BHP) hot water boiler(s) fired on ${fuelT}. System: ${ts}°C supply / ${tr}°C return at ${fl} L/hr. Fuel consumption: ${fuel} kg/hr per boiler. Install safety relief valve(s) rated minimum ${svKw} kW per ASME BPVC Sec IV / PD 8. Provide closed-loop chemical treatment (inhibited water, pH 7.5–9.0) and expansion tank. Annual statutory inspection by a DOLE-accredited boiler inspector is mandatory.`;
      } else {
        const bd    = rec.blowdown_pct ?? '';
        const sv    = rec.safety_valve_min_kg_hr ?? '';
        recommendations = `Provide ${n} × ${qkw} kW (${bhp} BHP) steam boiler(s) fired on ${fuelT}. Fuel consumption: ${fuel} kg/hr per boiler. Maintain continuous blowdown at ${bd}% to control total dissolved solids within allowable limits. Install safety relief valve(s) with minimum rated capacity of ${sv} kg/hr per ASME BPVC / PD 8. Boiler installation requires DOLE-accredited Third Party Inspector certification and annual statutory inspection under PD 8.`;
      }
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
      recommendations = `Specify ${d} mm diameter ${mat} solid shaft. Calculated minimum: ${rec.d_min_mm ?? ''} mm. Angle of twist: ${twist}°/m (ASME limit: 1.0°/m). Verify critical speed: operating speed must be below 50% of first critical speed. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "Bearing Life (L10)") {
      const life = rec.L10h_adj ?? rec.L10h ?? '';
      const pass = rec.life_check ?? '';
      const creq = rec.C_required_kN ?? '';
      recommendations = `Adjusted bearing life (Lna): ${life} hours: ${pass}. ${pass === 'FAIL' ? 'Select a bearing with C ≥ ' + creq + ' kN.' : 'Bearing is adequate for the application.'} Verify static rating C0 against peak shock loads. Specify sealed bearing (2RS) for humid/dusty Philippine plant environments. Establish lubrication intervals per manufacturer. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
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
    } else if (calcType === "Lighting Design") {
      const n   = rec.N_fixtures ?? '';
      const lux = rec.E_actual_lux ?? '';
      const lpd = rec.lpd_W_m2 ?? '';
      const fix = (inputs.fixture_type as string) || '';
      recommendations = `Provide ${n} units of ${fix} luminaires to achieve ${lux} lux maintained average illuminance. Arrange fixtures in a uniform grid for even distribution: calculate spacing-to-height ratio (SHR) and verify it does not exceed the fixture's maximum SHR per photometric data. Add 10-15% spare fixtures to the bill of materials to account for layout adjustments. Lighting power density: ${lpd} W/m²: verify against ASHRAE 90.1 or PEC limits for the space type. Provide dimming or occupancy sensors for energy compliance where required. A PRC-licensed Electrical Engineer must sign and seal this document.`;
    } else if (calcType === "Short Circuit") {
      const isc  = rec.Isc_kA ?? '';
      const chk  = rec.ic_check ?? '';
      const ic   = (inputs.breaker_ic_kA as number) ?? '';
      const recIC = rec.ic_min_recommended ?? '';
      recommendations = `Available fault current at panel: ${isc} kA (3-phase symmetrical). Breaker IC check: ${chk}. ${chk === 'FAIL' ? `Installed IC of ${ic} kA is insufficient: replace with minimum ${recIC} kA interrupting capacity breaker immediately. This is a critical safety deficiency.` : `Installed IC of ${ic} kA is adequate for ${isc} kA available fault.`} Verify IC rating of every branch breaker in this panel: fault current is the same at all points in the same panel. Request utility confirmation of available fault current at the point of delivery for final documentation. A PRC-licensed Electrical Engineer must sign and seal this document.`;
    } else if (calcType === "Generator Sizing") {
      const sel  = rec.selected_kva ?? '';
      const selKW = rec.selected_kw ?? '';
      const fuel  = rec.fuel_100pct_lhr ?? '';
      const tank  = rec.tank_8hr_litres ?? '';
      const load  = rec.loading_pct ?? '';
      const app   = (inputs.application as string) || 'Standby (ESP)';
      const start = rec.start_method ?? '';
      const startKVA = rec.starting_kva ?? 0;
      const runKVA   = rec.running_kva ?? 0;
      const ctrl = Number(startKVA) > Number(runKVA) ? `Motor starting surge (${startKVA} kVA, ${start}) is the controlling factor: not running load.` : `Running demand (${runKVA} kVA) is the controlling factor.`;
      recommendations = `Provide a ${sel} kVA (${selKW} kW) diesel generator set rated for ${app} duty per ISO 8528-1. ${ctrl} Operating loading at running demand: ${load}%: within the 75-80% recommended loading range for diesel generators. Design fuel tank for minimum 8-hour full-load operation: ${tank} liters. Connect to an Automatic Transfer Switch (ATS) per PEC Article 7: transfer time must not exceed 10 seconds for emergency loads. Submit generator installation plans to LGU / DPWH for building permit endorsement. A PRC-licensed Electrical Engineer must sign and seal this document.`;
    } else if (calcType === "Power Factor Correction") {
      const kvar    = rec.selected_kvar        ?? '';
      const pfT     = rec.pf_target            ?? '';
      const curRed  = rec.current_reduction    ?? '';
      const curPct  = rec.current_reduction_pct ?? '';
      const kvaRed  = rec.kva_reduction        ?? '';
      const surcharge = rec.meralco_penalty
        ? ` Installation eliminates the Meralco PF surcharge currently incurred: correction to PF ${pfT} brings the system above the 0.85 threshold.`
        : '';
      recommendations = `Install a ${kvar} kVAR capacitor bank (IEEE 18 / IEC 60831-1) at the main distribution board. This reduces feeder current by ${curRed} A (${curPct}%) and kVA demand by ${kvaRed} kVA.${surcharge} Protect with a dedicated MCCB sized at 135% of capacitor rated current per PEC 2017 Article 4.60.14. Include factory-installed discharge resistors (terminal voltage < 50V within 5 minutes per IEEE 18). If VFDs or other harmonic loads are present, specify a 7% series detuning reactor. Verify achieved PF with a power analyzer under full load before project closeout. A PRC-licensed Electrical Engineer must sign and seal this document.`;
    } else if (calcType === "Cable Tray Sizing") {
      const selW    = rec.selected_width_mm  ?? '';
      const depth   = (inputs.depth_mm as number) || 75;
      const tType   = (inputs.tray_type as string) || 'Ladder';
      const fill    = rec.fill_actual_pct    ?? '';
      const fillChk = rec.fill_check         ?? '';
      const nema    = rec.nema_load_class    ?? '';
      const span    = (inputs.span_m as number) || 1.5;
      const df      = rec.derating_factor    ?? 1.0;
      const derate  = Number(df) < 1.0;
      recommendations = `Provide a ${selW} mm wide × ${depth} mm deep ${tType} cable tray (NEMA VE 1 Load Class ${nema}, hot-dip galvanized steel for industrial use). Support at ${span} m centres. Actual cable fill: ${fill}%: Fill Check: ${fillChk} per NEC 392.22. ${derate ? `Fill exceeds 30% derating threshold: apply 80% derating factor to all power conductor ampacities per NEC 392.80 (NEC 310.15). Verify each conductor's derated ampacity equals or exceeds its design current.` : `Actual fill does not exceed 30%: no ampacity derating required for ${tType} tray.`} Separate power cables from control and instrumentation cables using a tray divider or a separate adjacent tray per NEMA VE 2 to minimize electromagnetic interference. Provide covers for outdoor sections or where physical protection is needed. A PRC-licensed Electrical Engineer must sign and seal this calculation for building permit submission.`;
    } else if (calcType === "UPS Sizing") {
      const selKVA   = rec.selected_kva        ?? '';
      const loadPct  = rec.loading_pct         ?? '';
      const bCfg     = rec.battery_config      ?? '';
      const bMin     = rec.actual_runtime_min  ?? '';
      const brkA     = rec.input_breaker_a     ?? '';
      const topo     = (inputs.topology as string) || 'Online (Double-Conversion)';
      const backup   = (inputs.backup_min as number) || 30;
      const iecClass = topo === 'Online (Double-Conversion)' ? 'VFI-SS-111' : topo === 'Line Interactive' ? 'VI-SS-111' : 'VFD-SS-111';
      recommendations = `Install a ${selKVA} kVA ${topo} UPS (IEC 62040-3 ${iecClass}) at the proposed location. System loading is ${loadPct}%: within the IEEE 446 recommended ≤ 80% limit for thermal headroom and future load additions. Battery bank: ${bCfg}, rated backup ${bMin} minutes at design load (required: ${backup} min). Provide a static bypass module to allow UPS maintenance without interrupting supply to critical loads. Input supply shall be from a dedicated ${brkA}A MCCB circuit: do not share with non-critical loads. Commission with a full-load battery discharge test per IEC 62040-3 and verify actual runtime ≥ ${backup} minutes before handover. Plan VRLA battery replacement at Year 3 for unconditioned rooms or Year 5 for air-conditioned spaces per IEEE 1184. A PRC-licensed Electrical Engineer must sign and seal this calculation for building permit submission.`;
    } else if (calcType === "Earthing / Grounding System") {
      const rEff     = rec.r_parallel_ohm ?? rec.r_single_ohm ?? '';
      const rLim     = rec.r_limit_ohm    ?? '';
      const passLbl  = rec.pass_label     || (rec.pass ? 'PASS' : 'FAIL');
      const eType    = (inputs.electrode_type as string) || 'Rod';
      const nElec    = (inputs.num_electrodes as number) || 1;
      const sSys     = (inputs.system_type as string) || 'Residential / Commercial';
      const gecSz    = rec.gec_mm2 ?? '';
      const limitBasis = sSys === 'Substation / HV'
        ? 'IEEE 80-2013'
        : sSys === 'Industrial'
        ? 'IEEE 142-2007'
        : 'PEC 2017 Art. 2.50';
      recommendations = `The earthing system uses ${nElec} ${eType.toLowerCase()} electrode${nElec > 1 ? 's' : ''} in ${sSys} configuration. Measured/calculated resistance: ${rEff} Ohm: ${passLbl} against the ${rLim} Ohm limit per ${limitBasis}. ${rec.pass ? 'The installation is compliant. Proceed with construction and conduct site acceptance testing using a four-pole Wenner or fall-of-potential method.' : `Ground resistance exceeds the ${rLim} Ohm limit. Increase electrodes, apply soil treatment (bentonite or GEM compound), or use deeper/longer electrodes before proceeding.`} GEC minimum size per PEC 2017 Table 2.50.66: ${gecSz} mm2 copper. All earthing conductors must be protected from mechanical damage per PEC 2017 Section 2.50.16. Bonding jumpers must achieve full electrical continuity per IEEE 80 bonding requirements. A PRC-licensed Electrical Engineer must sign and seal this calculation for building permit submission.`;
    } else if (calcType === "Duct Sizing (Equal Friction)") {
      const hp     = rec.fan_motor_hp_std  ?? '';
      const kw     = rec.fan_motor_kw      ?? '';
      const fanPa  = rec.fan_static_pa     ?? '';
      const dpPa   = rec.total_dp_pa       ?? '';
      const flow   = rec.max_flow_lps      ?? '';
      const shape  = (inputs.duct_shape   as string) || 'Circular';
      const mat    = (inputs.duct_material as string) || 'Galvanized Steel';
      const fr     = inputs.friction_rate ?? 1.0;
      const segs   = Array.isArray(rec.segments) ? rec.segments as Array<{vel_check: string}> : [];
      const velWarn = segs.some(s => s.vel_check !== 'OK');
      recommendations = `Provide ${shape} ${mat} ductwork sized at ${fr} Pa/m friction rate per ASHRAE 2021 Fundamentals Chapter 21 Equal Friction Method. Total straight-run ΔP: ${dpPa} Pa; required fan static pressure including 50% SMACNA fittings allowance: ${fanPa} Pa. Size supply fan at maximum segment flow ${flow} L/s; specify a ${hp} HP (${kw} kW) centrifugal fan motor per the standard size schedule. ${velWarn ? 'WARNING: one or more duct segments exceed the ASHRAE 62.1 / SMACNA velocity limit: review those segments and increase duct size or reduce airflow before finalising.' : 'All segments are within ASHRAE 62.1 / SMACNA velocity limits.'} Add AHU internal resistance (cooling coil, filters: typically 200–500 Pa) and terminal device resistance (50–150 Pa each) to the fan static pressure when specifying the fan. A Testing, Adjusting, and Balancing (TAB) report confirming design airflows at all diffusers within ±10% is mandatory before building acceptance. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "Refrigerant Pipe Sizing") {
      const refrig   = (inputs.refrigerant as string) || 'R-410A';
      const capKw    = rec.capacity_kw  ?? (inputs.capacity_kw ?? '');
      const app      = (inputs.application as string) || 'AC';
      const evapT    = rec.evap_temp_c  ?? '';
      const condT    = rec.cond_temp_c  ?? (inputs.cond_temp_c ?? 40);
      const lineArr  = Array.isArray(rec.lines) ? rec.lines as Array<{name:string;line_type:string;selected_od_mm:number;velocity_ms:number;vel_check:string;delta_t_k:number}> : [];
      const anyWarn  = lineArr.some(l => l.vel_check !== 'OK');
      const lineSummary = lineArr.map(l => `${l.name} (${l.line_type}): ${l.selected_od_mm}mm OD, v=${l.velocity_ms}m/s ${l.vel_check}, ΔT=${l.delta_t_k}K`).join('; ');
      recommendations = `Procure ASTM B280 ACR copper tubing for all ${refrig} refrigerant line sets: capacity ${capKw}kW, ${app} service, evaporating ${evapT}°C / condensing ${condT}°C. Line schedule: ${lineSummary}. ${anyWarn ? 'WARNING: one or more lines have velocity outside the ASHRAE recommended range: re-size before procurement.' : 'All lines are within ASHRAE velocity limits.'} Insulate all suction lines with minimum 19mm closed-cell elastomeric foam (ASTM C534) before pressure testing. Install oil traps at all suction vertical riser bases. All brazed joints shall use OFN (nitrogen purge brazing). Pressure test at 1.1× MAWP with dry nitrogen; evacuate to ≤500 microns before refrigerant charge. Refrigerant charge by weight per manufacturer specification adjusted for actual line length. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "Expansion Tank Sizing") {
      const sysType   = (inputs.system_type as string) || 'Chilled Water';
      const tankL     = rec.selected_tank_L   ?? '';
      const reqL      = rec.required_volume_L ?? '';
      const alpha     = rec.acceptance_factor ?? '';
      const pPrech    = rec.precharge_kpa_g   ?? '';
      const pFill     = rec.fill_pressure_kpa_g ?? '';
      const pMax      = rec.max_pressure_kpa_g  ?? (inputs.max_pressure_kpa_g ?? '');
      const Ew        = rec.expansion_ratio    ?? '';
      const Vexp      = rec.V_expansion_L      ?? '';
      const sysVol    = rec.system_volume_L    ?? '';
      const passAlpha = Number(alpha) >= 0.25;
      recommendations = `Install a ${tankL}L pre-pressurised bladder/diaphragm expansion tank (ASME VIII-listed) on the ${sysType} closed-loop system. Required acceptance volume: ${reqL}L; acceptance factor α = ${alpha} (ASHRAE min 0.25: ${passAlpha ? 'PASS' : 'FAIL: increase system maximum pressure or reduce fill pressure'}). Set factory pre-charge to ${pPrech} kPa g; confirm system fill pressure at ${pFill} kPa g before commissioning. System expansion volume: ${Vexp}L (E_w = ${Ew} for system volume ${sysVol}L). System maximum allowable working pressure: ${pMax} kPa g. ${!passAlpha ? `WARNING: Acceptance factor ${alpha} is below ASHRAE minimum of 0.25: specify a larger tank or increase maximum pressure setting. ` : ''}Use EPDM bladder for CHW/HHW service. Install isolation valve, pressure gauge, and manual drain between the tank connection and the main pipe. Locate tank on the suction side of the primary pump at the point of no pressure change. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "FCU Selection") {
      const rooms      = Array.isArray(rec.rooms) ? rec.rooms as Array<{room_name:string; selected_model:string; qty:number; selected_kw:number}> : [];
      const totalDesKW = rec.total_design_kw  ?? '';
      const totalDesTR = rec.total_design_tr  ?? '';
      const totalChw   = rec.total_chw_lps    ?? '';
      const mainNps    = rec.main_pipe_nps_mm ?? '';
      const velCheck   = rec.vel_check        ?? '';
      const totalUnits = rec.total_units      ?? '';
      const divF       = rec.diversity_factor ?? (inputs.diversity_factor ?? 0.85);
      const pipeSys    = (inputs.pipe_system  as string) || '2-Pipe (Cooling Only)';
      const mount      = (inputs.mounting_type as string) || 'Ceiling Cassette';
      const roomSummary = rooms.slice(0, 5).map(r => `${r.room_name}: ${r.qty}× ${r.selected_model} (${r.selected_kw}kW)`).join('; ');
      recommendations = `Install ${totalUnits} fan coil units (${mount}) on a ${pipeSys} chilled water system. Design load: ${totalDesKW} kW / ${totalDesTR} TR after applying diversity factor ${divF}. Total CHW flow: ${totalChw} L/s: size main at ${mainNps} mm NPS Black Steel SCH40 (velocity ${velCheck}). FCU summary: ${roomSummary}${rooms.length > 5 ? ` and ${rooms.length - 5} more rooms` : ''}. Verify CHW branch pipe sizes per ASHRAE at 0.6–2.5 m/s. Balance each FCU with a circuit balancing valve (PICV) for equal CHW distribution. Specify EER ≥ 3.5 per ASHRAE 90.1. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "Bolt Torque & Preload") {
      const torque = rec.torque_Nm ?? '';
      const size   = (inputs.bolt_size as string) || '';
      const grade  = (inputs.bolt_grade as string) || '';
      const sf     = rec.separation_sf ?? '';
      const jchk   = rec.joint_check ?? '';
      recommendations = `Tighten ${size} Grade ${grade} bolts to ${torque} N·m using a calibrated torque wrench. Use the 3-pass cross-torquing method: 30% → 70% → 100% of target torque. Joint separation SF = ${sf} (${jchk}). Never reuse torque-to-yield bolts (Grade 10.9 / 12.9 one-time use). Apply thread lubricant (K=${(inputs.nut_factor as number) ?? ''}) consistently: dry/lubricated torque differs by up to 30%. A PRC-licensed Mechanical Engineer must sign and seal this document.`;
    } else if (calcType === "Lightning Protection System (LPS)") {
      const lpl   = (inputs.lpl as string) || 'LPL II';
      const rchk  = rec.risk_check ?? '';
      const ndc   = rec.n_down_conductors ?? '';
      const nat   = rec.n_air_terminals_est ?? '';
      const nel   = rec.n_electrodes ?? '';
      const elLen = rec.min_electrode_length_m ?? '';
      const R     = rec.rolling_sphere_R_m ?? '';
      const mesh  = rec.mesh_size_m ?? '';
      const eff   = rec.efficiency_pct ?? '';
      recommendations = `Install an external LPS complying with IEC 62305-3 for ${lpl} (rolling sphere radius ${R} m, mesh ${mesh} m, efficiency ${eff}%). Risk assessment: ${rchk}. Air termination: ${nat} air terminals (Franklin rods or horizontal conductors) arranged per the rolling sphere / mesh method: all roof edges, corners, and ridges within protection radius. Down conductors: ${ndc} runs of ${(inputs.dc_material as string) || 'copper'} conductors at ${rec.dc_spacing_m ?? ''} m spacing along the building perimeter: route straight and vertical, minimum 0.2 m from doors and windows. Earth termination: ${nel} electrodes (minimum ${elLen} m each), Type ${(inputs.earth_type as string) || 'A'} per IEC 62305-3: measure and verify earth resistance ≤ 10 Ω before commissioning. Bond all metal building elements (roof structure, pipes, conduits, HVAC) to the down conductor network per IEC 62305-3 Section 6. Provide SPDs at main panel per IEC 62305-4. A PRC-licensed Electrical Engineer must sign and seal this document. Submit LPS design drawings and earthing test results to the Building Official / BFP for permit clearance.`;
    }
    return {
      objective: `To determine the required ${calcType} design parameters for the subject project in accordance with applicable Philippine and international engineering standards.`,
      assumptions: "Standard Philippine tropical climate and code conditions applied. Safety factors as specified in the applicable standard have been applied to all computed values.",
      recommendations,
    };
  }
}

// ─── Electrical: Lightning Protection System (LPS): IEC 62305 / NFPA 780 ────

function calcLightningProtection(inputs: Record<string, number | string>): Record<string, unknown> {
  const round2 = (v: number) => Math.round(v * 100) / 100;
  const round4 = (v: number) => Math.round(v * 10000) / 10000;

  const L  = Number(inputs.building_length_m  ?? 20);
  const W  = Number(inputs.building_width_m   ?? 15);
  const H  = Number(inputs.building_height_m  ?? 10);
  const lpl = (inputs.lpl as string) || 'LPL II';
  const ng_loc = (inputs.ng_location as string) || 'Metro Manila';
  const ng_custom = Number(inputs.ng_custom ?? 10);
  const dc_material = (inputs.dc_material as string) || 'Copper';
  const earth_type  = (inputs.earth_type  as string) || 'Type A: Radial / Vertical Electrodes';
  const struct_type = (inputs.structure_type as string) || 'Residential';
  const air_method  = (inputs.air_term_method as string) || 'Rolling Sphere';

  // Philippine Ng lookup (flashes/km²/yr, approximate PAGASA data)
  const NG_TABLE: Record<string, number> = {
    "Metro Manila / NCR":      10,
    "Baguio / Cordillera":     12,
    "Ilocos Region":            8,
    "Cagayan Valley":          12,
    "Central Luzon":           10,
    "CALABARZON":              10,
    "Bicol Region":            14,
    "Western Visayas":         10,
    "Central Visayas (Cebu)":  10,
    "Eastern Visayas":         12,
    "Zamboanga Peninsula":     12,
    "Northern Mindanao":       14,
    "Davao Region":            14,
    "SOCCSKSARGEN":            16,
    "CARAGA":                  14,
    "ARMM / BARMM":            14,
    "Custom":                  ng_custom,
  };
  const Ng = NG_TABLE[ng_loc] ?? ng_custom;

  // IEC 62305-3 Table 1: LPL parameters
  const LPL_TABLE: Record<string, { R: number; mesh: number; angle_base: number; dc_spacing: number; I_min: number; eff: number }> = {
    "LPL I":   { R: 20, mesh: 5,  angle_base: 25, dc_spacing: 10, I_min: 3,  eff: 99 },
    "LPL II":  { R: 30, mesh: 10, angle_base: 35, dc_spacing: 10, I_min: 5,  eff: 97 },
    "LPL III": { R: 45, mesh: 15, angle_base: 45, dc_spacing: 15, I_min: 10, eff: 91 },
    "LPL IV":  { R: 60, mesh: 20, angle_base: 55, dc_spacing: 20, I_min: 16, eff: 80 },
  };
  const lplP = LPL_TABLE[lpl] ?? LPL_TABLE["LPL II"];

  // Collection area: IEC 62305-2 Annex A Eq. A.1
  const Ad = L * W + 6 * H * (L + W) + 9 * Math.PI * H * H;

  // Annual strike frequency
  const Nd = round4(Ng * Ad * 1e-6);

  // Tolerable annual strikes (simplified IEC 62305-2)
  const Cd: Record<string, number> = {
    "Residential": 1, "Commercial": 1, "Industrial": 2,
    "Healthcare": 2,  "Critical Infrastructure": 2, "Explosive / Flammable": 5,
  };
  const cd = Cd[struct_type] ?? 1;
  const Nt = parseFloat((1e-5 / cd).toFixed(8));

  const risk_ratio = round2(Nd / Nt);
  // IEC 62305-2 §4.1: if Nd > Nt (ratio > 1), protection is required.
  // "RECOMMENDED" zone: 0.5 < ratio ≤ 1 (approaching threshold: prudent to install).
  const risk_check = risk_ratio > 1 ? "LPS REQUIRED" : risk_ratio > 0.5 ? "LPS RECOMMENDED" : "LPS NOT REQUIRED";

  // Down conductors
  const perimeter = 2 * (L + W);
  const n_dc = Math.max(2, Math.ceil(perimeter / lplP.dc_spacing));

  // Protection angle (IEC 62305-3 Table 2, simplified: angle reduces linearly to 0° at H=60m for LPL I)
  const alpha_base = lplP.angle_base;
  const h_ref = lplP.R; // height at which angle reaches 0
  const prot_angle = Math.max(0, Math.round(alpha_base * (1 - Math.min(H, h_ref) / (h_ref * 2))));

  // Air terminal estimate
  let n_at: number;
  if (air_method === "Mesh") {
    const rows_L = Math.ceil(L / lplP.mesh) + 1;
    const rows_W = Math.ceil(W / lplP.mesh) + 1;
    n_at = rows_L + rows_W;
  } else {
    // Rolling sphere / protection angle: corners + edge intervals
    n_at = 4 + 2 * Math.floor(L / lplP.dc_spacing) + 2 * Math.floor(W / lplP.dc_spacing);
    n_at = Math.max(4, n_at);
  }

  // Earth termination (IEC 62305-3 Table 7: Type A minimum electrode length)
  const min_el = Math.max(5, round2(0.5 * H));

  // Cable lengths (indicative)
  const down_cond_length_m = Math.round(n_dc * H * 1.15); // 15% extra for routing
  const earth_ring_m = Math.round(perimeter + 20);        // ring + bonding

  // SPD recommendation
  const spd_class = lpl === "LPL I" || lpl === "LPL II" ? "Class I + II combination" : "Class II";

  return {
    // Risk assessment
    Ad_m2:            Math.round(Ad),
    ng_fl_km2_yr:     Ng,
    Nd_strikes_yr:    Nd,
    Cd:               cd,
    Nt:               Nt,
    risk_ratio:       risk_ratio,
    risk_check:       risk_check,

    // LPL parameters
    lpl_label:            lpl,
    efficiency_pct:       lplP.eff,
    I_min_kA:             lplP.I_min,

    // Air termination
    air_term_method:      air_method,
    rolling_sphere_R_m:   lplP.R,
    mesh_size_m:          lplP.mesh,
    protection_angle_deg: prot_angle,
    n_air_terminals_est:  n_at,

    // Down conductors
    perimeter_m:      Math.round(perimeter),
    dc_spacing_m:     lplP.dc_spacing,
    n_down_conductors: n_dc,
    dc_material:      dc_material,
    down_cond_length_m: down_cond_length_m,

    // Earth termination
    earth_type:              earth_type,
    min_electrode_length_m:  min_el,
    n_electrodes:            n_dc,
    earth_resistance_target_ohm: 10,
    earth_ring_length_m:     earth_ring_m,

    // SPD
    spd_class: spd_class,
  };
}

// ─── Electrical: Lighting Design: Lumen Method (IES / PEC 2017) ─────────────

function calcLightingDesign(inputs: Record<string, number | string>): Record<string, unknown> {
  const round2 = (v: number) => Math.round(v * 100) / 100;
  const round1 = (v: number) => Math.round(v * 10) / 10;

  const room_len    = Number(inputs.room_len_m      ?? 10);
  const room_wid    = Number(inputs.room_wid_m      ?? 8);
  const ceiling_ht  = Number(inputs.ceiling_ht_m    ?? 3.0);
  const target_lux  = Number(inputs.target_lux      ?? 500);
  const lumens      = Number(inputs.lumens_per_fix  ?? 3200);
  const watts       = Number(inputs.watts_per_fix   ?? 36);
  const llf         = Number(inputs.llf             ?? 0.80);

  // Floor area
  const floor_area_m2 = round2(room_len * room_wid);

  // Step 1: Room Cavity Ratio
  const work_plane = 0.85; // m (standard desk height)
  const h_rc_m     = round2(ceiling_ht - work_plane);
  const RCR        = round2(5 * h_rc_m * (room_len + room_wid) / (room_len * room_wid));

  // Step 2: Coefficient of Utilization (IES typical, 80/50/20 reflectance)
  // RCR → CU lookup (deep groove ball bearing equivalent for lighting)
  const CU_TABLE: [number, number][] = [
    [1, 0.75], [2, 0.72], [3, 0.66], [4, 0.62],
    [5, 0.57], [6, 0.54], [7, 0.50], [8, 0.46], [9, 0.43], [10, 0.40],
  ];
  let CU = 0.72; // default RCR 1-2
  for (const [rcr, cu] of CU_TABLE) {
    if (RCR <= rcr) { CU = cu; break; }
    CU = cu; // fallback to last entry
  }
  CU = round2(CU);

  // Step 3: Number of luminaires
  const N_exact    = round2((target_lux * floor_area_m2) / (lumens * CU * llf));
  const N_fixtures = Math.ceil(N_exact);

  // Step 4: Achieved illuminance
  const E_actual_lux = round1((N_fixtures * lumens * CU * llf) / floor_area_m2);

  // Step 5: Electrical load
  const total_watts = N_fixtures * watts;
  const total_kW    = round2(total_watts / 1000);
  const lpd_W_m2    = round2(total_watts / floor_area_m2);

  return {
    floor_area_m2,
    h_rc_m,
    RCR,
    CU,
    N_exact,
    N_fixtures,
    E_actual_lux,
    total_watts,
    total_kW,
    lpd_W_m2,
  };
}

// ─── Electrical: Short Circuit Analysis (PEC 2017 / IEC 60909 / IEEE 141) ────

// Cable reactance at 50 Hz (Ω/km): typical 4-core XLPE/PVC LV cable
const CABLE_REACTANCE_OHM_KM: Array<[number, number]> = [
  [14, 0.085], [22, 0.083], [30, 0.082], [38, 0.080],
  [60, 0.079], [100, 0.077], [150, 0.076], [250, 0.074],
];
function cableReactance(mm2: number): number {
  const t = Math.max(14, Math.min(250, mm2));
  for (let i = 0; i < CABLE_REACTANCE_OHM_KM.length - 1; i++) {
    const [s0, x0] = CABLE_REACTANCE_OHM_KM[i];
    const [s1, x1] = CABLE_REACTANCE_OHM_KM[i + 1];
    if (t >= s0 && t <= s1) return x0 + (x1 - x0) * (t - s0) / (s1 - s0);
  }
  return CABLE_REACTANCE_OHM_KM[CABLE_REACTANCE_OHM_KM.length - 1][1];
}

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

  // Step 3: Cable resistance (copper resistivity 0.0175 Ω·mm²/m at 75°C)
  const R_cable_ohm = round4((0.0175 / cable_mm2) * cable_len_m);

  // Step 3b: Cable reactance at 50 Hz (per XLPE/PVC LV cable table)
  const X_cable_ohm = round4(cableReactance(cable_mm2) * cable_len_m / 1000);

  // Step 3c: Cable impedance magnitude Z_cable = √(R² + X²)
  const Z_cable_ohm = round4(Math.sqrt(R_cable_ohm ** 2 + X_cable_ohm ** 2));

  // Step 4: Total impedance: Z_xfmr in series with Z_cable
  const Z_total_ohm = round4(Z_xfmr_ohm + Z_cable_ohm);

  // Step 5: 3-phase symmetrical fault current (IEC 60909 §4.2)
  // c = 1.05 voltage factor for LV systems (Un ≤ 1 kV), max fault calculation: IEC 60909 Table 1
  const c_factor = voltage_ll <= 1000 ? 1.05 : 1.10;
  const Isc_A = (c_factor * voltage_ll) / (Math.sqrt(3) * Z_total_ohm);
  const Isc_kA = round2(Isc_A / 1000);

  // Step 6: Asymmetrical peak current: IEC 60909 §4.3: ip = κ × √2 × Isc
  // κ = 1.8 for typical LV distribution (R/X governed); ip = 1.8 × √2 × Isc ≈ 2.55 × Isc
  const Ipeak_kA = round2(1.8 * Math.sqrt(2) * Isc_kA);

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
    X_cable_ohm,
    Z_cable_ohm,
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

  // Proof strength (Sp) in MPa per grade: ISO 898-1:2013
  // Grade 8.8: 580 MPa for M10/M12 (Table 3, ≤16mm thread); 600 MPa for M16 and above (Table 4)
  // Grade 4.8: 310 MPa (ISO 898-1 under investigation; commonly cited: verify against ISO 898-1:2013 Table 4)
  const SP_MAP: Record<string, number> = {
    '4.6':  225,
    '4.8':  310,   // ⚠️ UNVERIFIED: confirm against ISO 898-1:2013 Table 4
    '8.8':  600,   // size-dependent; overridden below for M10/M12
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
  let Sp_MPa = SP_MAP[bolt_grade] ?? 600;
  // ISO 898-1:2013: Grade 8.8 Sp = 580 MPa for M5–M14; 600 MPa for M16 and above
  if (bolt_grade === '8.8' && d_mm <= 14) Sp_MPa = 580;

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

  // Material tensile and yield strengths (MPa): AISI annealed/normalized typical values
  const Sut_map: Record<string, number> = {
    'AISI 1020': 380,
    'AISI 1045': 570,
    'AISI 4140': 655,
    'AISI 4340': 1035,
  };
  // Sy (yield strength) per material: ASME B106.1M requires min(0.30×Sy, 0.18×Sut)
  const Sy_map: Record<string, number> = {
    'AISI 1020': 210,
    'AISI 1045': 310,
    'AISI 4140': 415,
    'AISI 4340': 470,
  };
  const Sut_MPa = Sut_map[material] || 570;
  const Sy_MPa  = Sy_map[material]  || 310;

  // ASME B106.1M allowable shear stress:
  //   Ss_allow (no keyway) = min(0.30 × Sy, 0.18 × Sut)
  //   Ss_allow (with keyway) = 0.75 × min(0.30 × Sy, 0.18 × Sut)
  const Ss_no_keyway_MPa = Math.min(0.30 * Sy_MPa, 0.18 * Sut_MPa);
  const Ss_allow_MPa = round1(keyway === 'Yes' ? 0.75 * Ss_no_keyway_MPa : Ss_no_keyway_MPa);
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

  // Bending moment: simply supported, point load at midspan
  const M_Nm = round1(transverse_load_N * (span_mm / 1000) / 4);

  // Combined load term (ASME elliptic)
  const combined_Nm = round1(Math.sqrt(Math.pow(Kb * M_Nm, 2) + Math.pow(Kt * T_Nm, 2)));

  // Minimum diameter (m)
  const d_cubed_m3 = (16 / Math.PI) * combined_Nm / Ss_allow_Pa;
  const d_min_m    = Math.pow(d_cubed_m3, 1/3);
  const d_min_mm   = round1(d_min_m * 1000);

  // Standard shaft diameters (mm): PH market
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
    Sy_MPa,
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
      // Roller bearing: ISO 281: for combined radial + axial load:
      // X=0.4, Y=0.4×cot(α); contact angle α=15° typical → cot(15°)≈3.73, Y≈1.5
      X = 0.4; Y = 1.5; // conservative estimate (15° contact angle); use manufacturer data for exact Y
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

  // Belt designation: RMA standard lengths per section (datum length in inches, label in mm)
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

  // Total rise (m): ground floor to highest floor
  const H_m = Math.round((n_floors - 1) * floor_height * 10) / 10;

  // Flight time (round trip, no acceleration correction for standard speeds)
  const t_flight_s = Math.round((2 * H_m / speed) * 10) / 10;

  // Average number of stops (S): CIBSE Guide D formula:
  // S = n * [1 - (1 - 1/n)^P]  where n = floors-1 (excluding ground), P = effective_pax
  const n = n_floors - 1;
  const S_raw = n * (1 - Math.pow(1 - 1 / n, effective_pax));
  const avg_stops = Math.round(S_raw * 10) / 10;

  // Stop time = (dwell + door open + door close) × avg_stops
  const t_per_stop = t_dwell + t_door_open + t_door_close;
  const t_stops_s  = Math.round(t_per_stop * avg_stops * 10) / 10;

  // Loading/unloading time: estimated as 0.8 s per passenger (CIBSE typical)
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
  // NFPA 13 Table 19.3.3.1.2 hose stream allowances (combined):
  //   Light Hazard = 100 gpm = 379 L/min
  //   Ordinary Hazard = 250 gpm = 946 L/min
  //   Extra Hazard = 500 gpm = 1893 L/min
  const hazardTable: Record<string, { density: number; area: number; coverage: number; hose: number; duration: number }> = {
    'Light Hazard':       { density: 4.1,  area: 139, coverage: 18.6, hose: 379,  duration: 30  },
    'Ordinary Group 1':   { density: 6.1,  area: 139, coverage: 12.1, hose: 946,  duration: 60  },
    'Ordinary Group 2':   { density: 8.1,  area: 139, coverage: 12.1, hose: 946,  duration: 60  },
    'Extra Hazard Grp 1': { density: 12.2, area: 232, coverage: 9.3,  hose: 1893, duration: 90  },
    'Extra Hazard Grp 2': { density: 16.3, area: 279, coverage: 9.3,  hose: 1893, duration: 120 },
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

  // NFPA 92 Table B.1: leakage area per door (m²)
  const door_leakage_map: Record<string, number> = {
    'Tight':   0.019,
    'Average': 0.039,
    'Loose':   0.052,
  };
  const A_door_m2 = door_leakage_map[door_fit] || 0.039;

  // Wall leakage per floor: NFPA 92 typical stairwell wall: 0.0009 m² per m² of wall
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

  // Convert to m³/h (CMH): standard Philippine fan rating unit
  const Q_design_CMH = Q_design_m3s * 3600;
  const Q_per_CMH    = Q_per_stairwell_m3s * 3600;

  // Door opening force check (NFPA 92 §6.5.1.1 max = 133 N / 30 lbf)
  // Correct formula: F = F_dc + (ΔP × A × W) / (2 × (W - d))
  // Pressure acts at door centroid (W/2 from hinge); force applied at handle (W - d from hinge).
  // d = handle setback from latch edge = 0.076 m (3 in), per NFPA 92.
  const A_door_panel     = door_W * door_H; // m²
  const d                = 0.076; // m: handle setback from latch edge (NFPA 92, 3 in)
  const lever_arm_factor = door_W / (2 * (door_W - d)); // moment arm correction
  const F_pressure_N     = delta_P_Pa * A_door_panel * lever_arm_factor;
  const F_closer_N       = 45; // typical door closer force (N)
  const F_total_N        = F_pressure_N + F_closer_N;
  const door_force_ok    = F_total_N <= 133;

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
  const delta_P_max = 87; // Pa: NFPA 92 §6.4.1.4 code maximum (independent of door force check)

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
    d,
    lever_arm_factor:        round3(lever_arm_factor),
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

  // Standard battery sizes (Ah): common Philippine/ASEAN market
  const std_Ah = [1.2, 2.6, 4.5, 7, 12, 17, 18, 26, 33, 40, 55, 65, 75, 100, 120, 150, 200];
  let selected_Ah = std_Ah[std_Ah.length - 1];
  for (const ah of std_Ah) {
    if (ah >= Ah_required) { selected_Ah = ah; break; }
  }

  // Number of batteries (series for 24V system: 2× 12V; single for 12V)
  const n_batteries   = system_voltage === 24 ? 2 : 1;
  const battery_volts = system_voltage === 24 ? 12 : 12;

  // Charger current check: NFPA 72: must recharge within 48 hours
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

// ─── Cooling Tower Sizing ─────────────────────────────────────────────────────
// Method: Heat rejection + Merkel-based approach/range; ASHRAE GRP-214 water loss
// Standards: ASHRAE 90.1 cooling-tower efficiency, CTI Std-201, PSME Code
// Outputs: water flow, evaporation/drift/blowdown/makeup, fan airflow & motor, approach check

// Standard fan motor sizes (kW) for cooling tower duty
const CT_FAN_MOTOR_KW = [0.37, 0.55, 0.75, 1.1, 1.5, 2.2, 3.0, 3.7, 5.5, 7.5, 11, 15, 18.5, 22, 30, 37, 45, 55, 75, 90, 110];

function roundUpToCTFanKW(kw: number): number {
  return CT_FAN_MOTOR_KW.find(s => s >= kw) || Math.ceil(kw / 10) * 10;
}

function calcCoolingTowerSizing(inputs: Record<string, number | string>) {
  const loadSource    = String(inputs.load_source || 'direct');
  // Accept canonical keys (ewt/lwt) or alias keys (hot_water_temp_c / cold_water_temp_c)
  const ewt           = Number(inputs.ewt || inputs.hot_water_temp_c)  || 37;   // entering water temp °C
  const lwt           = Number(inputs.lwt || inputs.cold_water_temp_c) || 32;   // leaving water temp °C
  const wbt           = Number(inputs.wbt)            || 27;   // design wet-bulb temp °C
  const coc           = Math.max(2, Number(inputs.coc) || 4);  // cycles of concentration
  const nCells        = Math.max(1, Math.round(Number(inputs.n_cells) || 1));
  const lgRatio       = Math.max(0.8, Math.min(2.0, Number(inputs.lg_ratio) || 1.2));
  const chillerCOP    = Math.max(2.0, Number(inputs.chiller_cop) || 4.5);

  // ── 1. Heat rejection load ─────────────────────────────────────────────────
  let qRejKW: number;
  if (loadSource === 'chiller') {
    const chillerTR = Number(inputs.chiller_cap_tr) || 0;
    if (chillerTR <= 0) return { error: "Chiller capacity must be greater than zero." };
    const chillerKW = chillerTR * 3.517;
    // Heat rejection = chiller capacity + compressor work = Q_evap × (1 + 1/COP)
    qRejKW = chillerKW * (1 + 1 / chillerCOP);
  } else {
    // Accept q_rejection_kw (canonical) or derive from condenser flow × delta-T
    const flowLpm = Number(inputs.condenser_water_flow_lpm) || 0;
    qRejKW = Number(inputs.q_rejection_kw)
      || (flowLpm > 0 ? flowLpm / 60 * 4.187 * (ewt - lwt) : 0);
    if (qRejKW <= 0) return { error: "Heat rejection load must be greater than zero." };
  }

  // ── 2. Temperature checks ─────────────────────────────────────────────────
  const range    = ewt - lwt;
  const approach = lwt - wbt;
  if (range    <= 0) return { error: "Entering water temp must be greater than leaving water temp." };
  if (approach <= 0) return { error: "Leaving water temp must be greater than wet-bulb temp. Reduce LWT or check design WBT." };
  if (approach < 2) return { error: `Approach of ${approach.toFixed(1)}°C is below 2°C minimum (CTI Std-201). Increase LWT or reduce WBT.` };

  const qRejTR = qRejKW / 3.517;

  // ── 3. Circulation water flow rate ────────────────────────────────────────
  // Q_w = Q_rejection / (Cp × ΔT_range)  [Cp = 4.187 kJ/kg·°C, density ≈ 1 kg/L]
  const Cp_water  = 4.187;
  const qW_lps    = qRejKW / (Cp_water * range);        // L/s
  const qW_m3hr   = qW_lps * 3.6;                       // m³/hr
  const qW_lpm    = qW_lps * 60;                        // L/min
  const qW_GPM    = qW_lps * 15.8508;                   // US GPM

  // ── 4. Water losses (ASHRAE GRP-214 / CTI method) ─────────────────────────
  // Evaporation: ~0.85% of circ flow per °C of range
  const evap_lhr      = 0.00085 * range * qW_m3hr * 1000;   // L/hr
  // Drift: 0.02% of circ flow (modern film fill with drift eliminators)
  const drift_lhr     = 0.0002 * qW_m3hr * 1000;            // L/hr
  // Blowdown: E / (CoC - 1): maintains cycles of concentration
  const blowdown_lhr  = evap_lhr / (coc - 1);               // L/hr
  // Makeup = evaporation + drift + blowdown
  const makeup_lhr    = evap_lhr + drift_lhr + blowdown_lhr;
  const makeup_m3day  = makeup_lhr * 24 / 1000;

  // ── 5. Fan airflow (air side) ─────────────────────────────────────────────
  // L/G ratio = water mass flow / air mass flow
  // m_air (kg/s) = qW_lps × ρ_water / L/G ≈ qW_lps / L/G (ρ_water ≈ 1 kg/L)
  const rho_air       = 1.15;   // kg/m³ at ~27°C WBT, typical Philippine conditions
  const mAir_kgs      = qW_lps / lgRatio;                   // kg/s air
  const fanFlow_m3s   = mAir_kgs / rho_air;                 // m³/s
  const fanFlow_CMH   = fanFlow_m3s * 3600;                 // m³/hr total
  const fanFlow_CMH_cell = fanFlow_CMH / nCells;

  // ── 6. Fan motor power ────────────────────────────────────────────────────
  // Typical cooling tower: 0.035–0.045 kW per kW heat rejection
  // Use 0.040 (mid range, axial fan, good fills)
  const fanKW_total    = qRejKW * 0.040;
  const fanKW_per_cell = fanKW_total / nCells;
  const fanKW_std      = roundUpToCTFanKW(fanKW_per_cell);

  // ── 7. Tower capacity per cell ────────────────────────────────────────────
  const qCell_kW = qRejKW / nCells;
  const qCell_TR = qRejTR / nCells;

  // ── 8. Approach check (CTI Std-201 minimum 2°C) ──────────────────────────
  const approach_check = approach >= 3 ? "PASS" : approach >= 2 ? "MARGINAL (2–3°C: verify with tower manufacturer)" : "FAIL";
  const approach_min   = 2;  // °C per CTI Std-201

  // ── 9. ASHRAE 90.1 cooling tower efficiency check ────────────────────────
  // ASHRAE 90.1-2019 metric: water flow rate (L/s) / fan power (kW) ≥ 3.23 L/s/kW
  // (equivalent to 38.2 gpm/hp per ASHRAE 90.1 Table 6.8.1-7 for open cooling towers)
  const ashrae_ct_efficiency = qW_lps / fanKW_total;          // L/s per kW of fan power
  const ashrae_ct_check = ashrae_ct_efficiency >= 3.23
    ? `PASS: ${ashrae_ct_efficiency.toFixed(2)} L/s/kW (≥ 3.23 L/s/kW per ASHRAE 90.1-2019)`
    : `FAIL: ${ashrae_ct_efficiency.toFixed(2)} L/s/kW (< 3.23 L/s/kW per ASHRAE 90.1-2019 Table 6.8.1-7)`;

  // ── 10. Chiller tie-in data (if from chiller) ────────────────────────────
  const chillerTR_input  = loadSource === 'chiller' ? Number(inputs.chiller_cap_tr) : null;
  const chillerKW_input  = chillerTR_input !== null ? chillerTR_input * 3.517 : null;

  return {
    // Load
    load_source:         loadSource,
    q_rejection_kw:      parseFloat(qRejKW.toFixed(2)),
    q_rejection_tr:      parseFloat(qRejTR.toFixed(2)),
    chiller_tr_input:    chillerTR_input,
    chiller_kw_input:    chillerKW_input !== null ? parseFloat(chillerKW_input.toFixed(2)) : null,
    chiller_cop:         loadSource === 'chiller' ? chillerCOP : null,
    // Design temps
    ewt, lwt, wbt,
    range_c:             parseFloat(range.toFixed(1)),
    approach_c:          parseFloat(approach.toFixed(1)),
    approach_check,
    approach_min,
    // Water flow
    q_w_lps:             parseFloat(qW_lps.toFixed(2)),
    q_w_m3hr:            parseFloat(qW_m3hr.toFixed(2)),
    q_w_lpm:             parseFloat(qW_lpm.toFixed(1)),
    q_w_GPM:             parseFloat(qW_GPM.toFixed(1)),
    // Water losses
    coc,
    evap_lhr:            parseFloat(evap_lhr.toFixed(1)),
    drift_lhr:           parseFloat(drift_lhr.toFixed(2)),
    blowdown_lhr:        parseFloat(blowdown_lhr.toFixed(1)),
    makeup_lhr:          parseFloat(makeup_lhr.toFixed(1)),
    makeup_m3day:        parseFloat(makeup_m3day.toFixed(2)),
    // Fan / air side
    lg_ratio:            lgRatio,
    fan_flow_CMH:        parseFloat(fanFlow_CMH.toFixed(0)),
    fan_flow_CMH_cell:   parseFloat(fanFlow_CMH_cell.toFixed(0)),
    fan_kw_total:        parseFloat(fanKW_total.toFixed(2)),
    fan_kw_per_cell:     parseFloat(fanKW_per_cell.toFixed(2)),
    fan_kw_std:          fanKW_std,
    // Cells
    n_cells:             nCells,
    q_cell_kw:           parseFloat(qCell_kW.toFixed(2)),
    q_cell_tr:           parseFloat(qCell_TR.toFixed(2)),
    // Compliance
    ashrae_ct_lps_per_kw: parseFloat(ashrae_ct_efficiency.toFixed(2)),
    ashrae_ct_check,
  };
}

// ─── Main Handler ─────────────────────────────────────────────────────────────

// ─── AHU Sizing Calculation ───────────────────────────────────────────────────
// Method: Psychrometric supply-air approach (sensible heat method)
// Standards: ASHRAE 62.1 (ventilation), ASHRAE 90.1 (fan power), PSME Code
// Outputs: supply airflow (CMH/CFM), cooling coil capacity (kW/TR),
//          CHW flow (L/s), fan power (kW/HP), ACH, OA compliance.

// Standard nominal AHU sizes (CMH): common Philippine market offerings
const AHU_STD_SIZES_CMH = [
  1000, 1500, 2000, 3000, 4000, 5000, 6000, 8000, 10000,
  12000, 15000, 20000, 25000, 30000, 40000, 50000, 60000,
];

// Standard fan motor HP sizes
const FAN_MOTOR_HP = [0.5, 0.75, 1, 1.5, 2, 3, 5, 7.5, 10, 15, 20, 25, 30, 40, 50, 60, 75, 100];

function roundUpToAHUSize(cmh: number): number {
  return AHU_STD_SIZES_CMH.find(s => s >= cmh) || Math.ceil(cmh / 5000) * 5000;
}
function roundUpToFanHP(kw: number): number {
  const hp = kw / 0.7457;
  return FAN_MOTOR_HP.find(s => s >= hp) || Math.ceil(hp / 10) * 10;
}

function calcAHUSizing(inputs: Record<string, number | string>) {
  const Q_input_kW    = Number(inputs.cooling_load_kW) || 0;    // zone total cooling load (kW)
  const shr           = Math.min(1.0, Math.max(0.5, Number(inputs.shr) || 0.75)); // sensible heat ratio
  const T_room        = Number(inputs.room_temp_C)     || 24;   // design room dry-bulb (°C)
  const T_supply      = Number(inputs.supply_temp_C)   || 14;   // supply air temp (°C)
  const oa_pct        = Math.min(100, Math.max(0, Number(inputs.oa_pct) || 20)) / 100; // OA fraction
  const chwSupply     = Number(inputs.chw_supply_C)    || 7;    // CHW supply (°C)
  const chwReturn     = Number(inputs.chw_return_C)    || 12;   // CHW return (°C)
  const fan_static_Pa = Number(inputs.fan_static_Pa)   || 400;  // total fan static pressure (Pa)
  const eta_fan       = Math.min(0.95, Math.max(0.30, Number(inputs.eta_fan) || 0.65)); // fan+motor combined
  const safetyFactor  = Number(inputs.safety_factor)   || 1.10;
  const nUnits        = Math.max(1, Math.round(Number(inputs.n_units) || 1));
  const floorArea     = Number(inputs.floor_area)      || 0;    // m² (for ACH check)
  const ceilingHeight = Number(inputs.ceiling_height)  || 3.0;  // m
  const persons       = Number(inputs.persons)         || 0;    // occupants (for OA check)
  const spaceType     = String(inputs.space_type || 'Office');

  // 1. Design cooling load (with safety factor)
  const Q_design_kW   = Q_input_kW * safetyFactor;
  const Q_design_TR   = Q_design_kW / 3.517;

  // 2. Sensible and latent split
  const Q_sensible_kW = Q_design_kW * shr;
  const Q_latent_kW   = Q_design_kW * (1 - shr);

  // 3. Supply air quantity (sensible heat method)
  //    Q_sa (m³/s) = Q_sensible / (ρ × Cp × ΔT_sa)
  //    ρ = 1.2 kg/m³, Cp = 1.005 kJ/(kg·K)
  const rho   = 1.2;
  const cp    = 1.005;
  const dT_sa = Math.max(1, T_room - T_supply);   // supply temperature differential
  const Q_sa_m3s    = Q_sensible_kW / (rho * cp * dT_sa);  // m³/s
  const Q_sa_CMH    = Q_sa_m3s * 3600;                     // m³/h
  const Q_sa_CFM    = Q_sa_m3s * 2118.88;                  // CFM

  // Per-unit values
  const Q_sa_CMH_each = Q_sa_CMH / nUnits;

  // 4. Outside air quantity (ASHRAE 62.1)
  const Q_oa_m3s  = Q_sa_m3s * oa_pct;
  const Q_oa_CMH  = Q_oa_m3s * 3600;
  const Q_oa_lps  = Q_oa_m3s * 1000;
  const Q_ra_CMH  = Q_sa_CMH - Q_oa_CMH;   // return/recirculation air

  // ASHRAE 62.1-2019 Ventilation Rate Procedure (VRP): Sec 6.2.2
  // Vbz = Rp × P + Ra × A  (breathing zone outdoor airflow)
  // Per Table 6-1: Office: Rp=2.5 L/s/person, Ra=0.30 L/s/m²
  // Conference: Rp=2.5 L/s/person, Ra=0.30 L/s/m²
  // Use spaceType to select Rp / Ra; default to office if unrecognised
  const oa_vrp: Record<string, { Rp: number; Ra: number }> = {
    'Office':      { Rp: 2.5, Ra: 0.30 },
    'Conference':  { Rp: 2.5, Ra: 0.30 },
    'Classroom':   { Rp: 3.8, Ra: 0.36 },
    'Reception':   { Rp: 2.5, Ra: 0.30 },
    'Retail':      { Rp: 1.7, Ra: 0.25 },
    'Restaurant':  { Rp: 3.8, Ra: 0.90 },
    'Gymnasium':   { Rp: 5.0, Ra: 0.30 },
    'Hotel Room':  { Rp: 2.5, Ra: 0.30 },
  };
  const vrp = oa_vrp[spaceType] || oa_vrp['Office'];
  const Vbz_lps = vrp.Rp * persons + vrp.Ra * floorArea;  // ASHRAE 62.1-2019 §6.2.2
  const oa_per_person_lps = persons > 0 ? Q_oa_lps / persons : null;
  const oa_check = persons > 0 || floorArea > 0
    ? (Q_oa_lps >= Vbz_lps
        ? `PASS: ${Q_oa_lps.toFixed(1)} L/s ≥ Vbz ${Vbz_lps.toFixed(1)} L/s (ASHRAE 62.1-2019 VRP)`
        : `FAIL: ${Q_oa_lps.toFixed(1)} L/s < Vbz ${Vbz_lps.toFixed(1)} L/s (ASHRAE 62.1-2019 VRP: increase OA%)`)
    : 'N/A (enter persons and/or floor area)';

  // 5. Mixed air temperature (mass balance, no latent correction)
  const T_outside = 35;  // design ambient dry-bulb for PH
  const T_mixed   = (oa_pct * T_outside) + ((1 - oa_pct) * T_room);

  // 6. Cooling coil capacity (coil must handle mixed→supply)
  //    Sensible coil load = ρ × Cp × Q_sa × (T_mixed − T_supply)
  const Q_coil_sensible_kW = rho * cp * Q_sa_m3s * (T_mixed - T_supply);
  const Q_coil_total_kW    = Q_coil_sensible_kW / shr;  // gross coil capacity (incl. latent)
  const Q_coil_TR          = Q_coil_total_kW / 3.517;
  const Q_coil_latent_kW   = Q_coil_total_kW - Q_coil_sensible_kW;

  // 7. Chilled water flow rate
  const dT_chw       = Math.max(1, chwReturn - chwSupply);
  const Q_chw_lps    = Q_coil_total_kW / (4.187 * dT_chw);   // L/s
  const Q_chw_m3h    = Q_chw_lps * 3.6;                       // m³/h
  const Q_chw_GPM    = Q_chw_lps * 15.8508;                   // US GPM

  // 8. Fan motor power
  //    P_fan (kW) = Q_sa_m3s × ΔP_fan / η_combined
  const P_fan_kW      = (Q_sa_m3s * fan_static_Pa) / (eta_fan * 1000);  // kW
  const P_fan_kW_each = P_fan_kW / nUnits;
  const fan_hp_std    = roundUpToFanHP(P_fan_kW_each);
  const fan_hp_total  = fan_hp_std * nUnits;

  // ASHRAE 90.1 fan power limitation: max 0.82 W/(L/s) at design airflow
  const fan_power_W_lps    = (P_fan_kW * 1000) / (Q_sa_m3s * 1000);   // W/(L/s)
  const ashrae_fan_max     = 0.82;
  const fan_power_check    = fan_power_W_lps <= ashrae_fan_max ? 'PASS' : 'FAIL (exceed 0.82 W/L·s limit: reduce static or increase fan efficiency)';

  // 9. ACH check
  const zone_volume       = floorArea * ceilingHeight;  // m³
  const ach_actual        = zone_volume > 0 ? (Q_sa_CMH / zone_volume) : null;

  // 10. Nominal AHU selection (round up to standard size per unit)
  const nominal_AHU_CMH_each = roundUpToAHUSize(Q_sa_CMH_each);
  const nominal_AHU_CMH_total = nominal_AHU_CMH_each * nUnits;

  // 11. Electrical supply estimate (fan only: coil is hydronic)
  const total_fan_kVA     = P_fan_kW / 0.85;  // kVA (PF=0.85)
  const total_fan_A_400V  = (total_fan_kVA * 1000) / (Math.sqrt(3) * 400);

  return {
    // Design load
    Q_input_kW:              parseFloat(Q_input_kW.toFixed(2)),
    Q_design_kW:             parseFloat(Q_design_kW.toFixed(2)),
    Q_design_TR:             parseFloat(Q_design_TR.toFixed(2)),
    Q_sensible_kW:           parseFloat(Q_sensible_kW.toFixed(2)),
    Q_latent_kW:             parseFloat(Q_latent_kW.toFixed(2)),
    shr,
    safety_factor:           safetyFactor,
    // Air side
    T_room,
    T_supply,
    T_mixed:                 parseFloat(T_mixed.toFixed(1)),
    dT_sa:                   parseFloat(dT_sa.toFixed(1)),
    Q_sa_m3s:                parseFloat(Q_sa_m3s.toFixed(3)),
    Q_sa_CMH:                parseFloat(Q_sa_CMH.toFixed(0)),
    Q_sa_CFM:                parseFloat(Q_sa_CFM.toFixed(0)),
    Q_sa_CMH_each:           parseFloat(Q_sa_CMH_each.toFixed(0)),
    Q_oa_CMH:                parseFloat(Q_oa_CMH.toFixed(0)),
    Q_ra_CMH:                parseFloat(Q_ra_CMH.toFixed(0)),
    oa_pct_used:             Math.round(oa_pct * 100),
    // OA compliance
    oa_per_person_lps:       oa_per_person_lps !== null ? parseFloat(oa_per_person_lps.toFixed(2)) : null,
    Vbz_lps:                 parseFloat(Vbz_lps.toFixed(2)),
    oa_check,
    // Cooling coil
    Q_coil_sensible_kW:      parseFloat(Q_coil_sensible_kW.toFixed(2)),
    Q_coil_latent_kW:        parseFloat(Q_coil_latent_kW.toFixed(2)),
    Q_coil_total_kW:         parseFloat(Q_coil_total_kW.toFixed(2)),
    Q_coil_TR:               parseFloat(Q_coil_TR.toFixed(2)),
    // CHW system
    dT_chw_C:                parseFloat(dT_chw.toFixed(1)),
    Q_chw_lps:               parseFloat(Q_chw_lps.toFixed(2)),
    Q_chw_m3h:               parseFloat(Q_chw_m3h.toFixed(2)),
    Q_chw_GPM:               parseFloat(Q_chw_GPM.toFixed(1)),
    chw_supply_C:            chwSupply,
    chw_return_C:            chwReturn,
    // Fan
    fan_static_Pa,
    eta_fan,
    P_fan_kW:                parseFloat(P_fan_kW.toFixed(2)),
    P_fan_kW_each:           parseFloat(P_fan_kW_each.toFixed(2)),
    fan_hp_std,
    fan_hp_total,
    fan_power_W_lps:         parseFloat(fan_power_W_lps.toFixed(3)),
    fan_power_check,
    ashrae_fan_max,
    // Selected AHU
    n_units:                 nUnits,
    nominal_AHU_CMH_each,
    nominal_AHU_CMH_total,
    // Zone data
    floor_area:              floorArea,
    ceiling_height:          ceilingHeight,
    zone_volume:             parseFloat(zone_volume.toFixed(1)),
    ach_actual:              ach_actual !== null ? parseFloat(ach_actual.toFixed(1)) : null,
    persons,
    space_type:              spaceType,
    // Electrical (fan motors)
    total_fan_kVA:           parseFloat(total_fan_kVA.toFixed(1)),
    total_fan_A_400V:        parseFloat(total_fan_A_400V.toFixed(1)),
  };
}

// ─── Water Softener Sizing ───────────────────────────────────────────────────

const SOFTENER_TANK_SIZES: [number, number, number][] = [
  // [dia_in, ht_in, resin_L]
  [8,  44,  25], [9,  48,  35], [10, 54,  50], [12, 52,  70],
  [13, 54,  85], [14, 65, 120], [16, 65, 160], [18, 65, 200],
  [21, 62, 270], [24, 72, 400], [30, 72, 600], [36, 72, 900],
];

function selectSoftenerTank(resinL: number): { dia_in: number; ht_in: number; resin_L: number } {
  for (const [d, h, r] of SOFTENER_TANK_SIZES) {
    if (r >= resinL) return { dia_in: d, ht_in: h, resin_L: r };
  }
  const last = SOFTENER_TANK_SIZES[SOFTENER_TANK_SIZES.length - 1];
  return { dia_in: last[0], ht_in: last[1], resin_L: last[2] };
}

const BRINE_TANK_SIZES = [100, 150, 200, 300, 500, 750, 1000, 1500, 2000];

function selectBrineTank(minL: number): number {
  return BRINE_TANK_SIZES.find(s => s >= minL) ?? BRINE_TANK_SIZES[BRINE_TANK_SIZES.length - 1];
}

function calcWaterSoftenerSizing(inputs: Record<string, number | string>): Record<string, unknown> {
  const demandSource = String(inputs.demand_source || 'direct');
  const nPeople      = Number(inputs.n_people) || 0;
  const perCapita    = Number(inputs.per_capita_lpd) || 200;

  let demandLpd: number;
  if (demandSource === 'people') {
    if (nPeople <= 0) return { error: "Number of people must be greater than 0." };
    demandLpd = nPeople * perCapita;
  } else {
    // Accept demand_lpd (canonical), daily_demand_L, or daily_demand_m3 (alias m³/day → L/day)
    demandLpd = Number(inputs.demand_lpd)
      || Number(inputs.daily_demand_L)
      || (inputs.daily_demand_m3 ? Number(inputs.daily_demand_m3) * 1000 : 0)
      || 0;
    if (demandLpd <= 0) return { error: "Daily water demand must be greater than 0." };
  }

  const inletHardness  = Math.max(1,   Number(inputs.inlet_hardness)   || 200); // mg/L as CaCO3
  const targetHardness = Math.max(0,   Number(inputs.target_hardness)  || 17);  // mg/L
  const regenInterval  = Math.max(1, Math.min(7, Number(inputs.regen_interval) || 3)); // days
  const saltDose       = Math.max(40, Math.min(150, Number(inputs.salt_dose_gL) || 80)); // g NaCl/L resin
  const nUnits         = Math.max(1, Math.round(Number(inputs.n_units) || 1));
  const safetyFactor   = 1.2;

  if (inletHardness <= targetHardness) {
    return { error: `Inlet hardness (${inletHardness} mg/L) must be greater than target hardness (${targetHardness} mg/L).` };
  }

  // Hardness in grains per gallon (reference)
  const inletGpg  = parseFloat((inletHardness  / 17.1).toFixed(2));
  const targetGpg = parseFloat((targetHardness / 17.1).toFixed(2));

  // Hardness classification
  const hardnessClass =
    inletHardness < 60  ? 'Slightly Hard'   :
    inletHardness < 120 ? 'Moderately Hard' :
    inletHardness < 180 ? 'Hard'            :
    inletHardness < 300 ? 'Very Hard'       : 'Extremely Hard';

  // PNS 1998 / WHO check
  const pnsCheck = inletHardness <= 300
    ? `WITHIN PNS 1998 limit (≤300 mg/L): softening recommended for equipment protection`
    : `EXCEEDS PNS 1998 limit (300 mg/L): softening mandatory`;

  // Step 1: Daily hardness load
  const removalMgL  = inletHardness - targetHardness;
  const dailyLoadG  = parseFloat((demandLpd * removalMgL / 1000).toFixed(1)); // g CaCO3/day

  // Step 2: Load per regen cycle (all units combined, with safety factor)
  const loadPerCycleG = parseFloat((dailyLoadG * regenInterval * safetyFactor).toFixed(0));

  // Step 3: Resin exchange capacity (empirical, based on salt dose)
  const exchCapacityGperL =
    saltDose <= 40  ? 35 :
    saltDose <= 60  ? 40 :
    saltDose <= 80  ? 45 :
    saltDose <= 120 ? 50 : 55;

  // Step 4: Resin volume per unit
  const resinLperUnit  = parseFloat((loadPerCycleG / exchCapacityGperL / nUnits).toFixed(1));
  const resinFt3       = parseFloat((resinLperUnit / 28.317).toFixed(2));

  // Step 5: Select standard tank (per unit)
  const tank           = selectSoftenerTank(resinLperUnit);
  const selectedResinL = tank.resin_L;
  const tankDiaMm      = Math.round(tank.dia_in * 25.4);
  const tankHtMm       = Math.round(tank.ht_in  * 25.4);

  // Step 6: Service flow rates based on selected resin volume
  const minFlowLpm    = parseFloat((selectedResinL * 6  / 60).toFixed(1)); // 6 BV/hr
  const maxFlowLpm    = parseFloat((selectedResinL * 25 / 60).toFixed(1)); // 25 BV/hr
  const designFlowLpm = parseFloat((demandLpd / (8 * 60)).toFixed(1));     // 8 hr/day peak operation basis
  const flowCheck     = designFlowLpm >= minFlowLpm && designFlowLpm <= maxFlowLpm
    ? `PASS: Design flow ${designFlowLpm} L/min is within ${minFlowLpm}–${maxFlowLpm} L/min`
    : designFlowLpm < minFlowLpm
      ? `LOW: Design flow ${designFlowLpm} L/min is below minimum ${minFlowLpm} L/min; consider smaller tank or shorter regen interval`
      : `HIGH: Design flow ${designFlowLpm} L/min exceeds maximum ${maxFlowLpm} L/min; add units or increase tank size`;

  // Step 7: Backwash flow rate (5 GPM/ft² of tank cross-section = ~204 L/min/m²)
  const tankDiaM     = tank.dia_in * 0.0254;
  const tankAreaM2   = Math.PI / 4 * tankDiaM * tankDiaM;
  const backwashLpm  = parseFloat((tankAreaM2 * 204).toFixed(0));

  // Step 8: Salt consumption
  const saltPerRegenKg  = parseFloat((selectedResinL * saltDose / 1000).toFixed(1));
  const monthlySaltKg   = parseFloat((saltPerRegenKg * nUnits * 30 / regenInterval).toFixed(1));

  // Step 9: Brine tank sizing (hold 3 months of salt; NaCl bulk density ~1.2 kg/L)
  const brineTankMinL = Math.ceil(monthlySaltKg * 3 / 1.2);
  const brineTankL    = selectBrineTank(brineTankMinL);

  // Step 10: Regeneration water waste (backwash + brine rinse + slow rinse ≈ 5 BV per regen)
  const rinseWaterL    = parseFloat((selectedResinL * 5).toFixed(0));
  const monthlyRinseM3 = parseFloat((rinseWaterL * nUnits * 30 / regenInterval / 1000).toFixed(2));
  const efficiencyPct  = parseFloat((100 - (rinseWaterL * nUnits / (demandLpd * regenInterval)) * 100).toFixed(1));

  return {
    // Input summary
    demand_lpd:          parseFloat(demandLpd.toFixed(0)),
    demand_m3day:        parseFloat((demandLpd / 1000).toFixed(3)),
    inlet_hardness_mgL:  inletHardness,
    inlet_hardness_gpg:  inletGpg,
    target_hardness_mgL: targetHardness,
    target_hardness_gpg: targetGpg,
    hardness_class:      hardnessClass,
    pns_check:           pnsCheck,
    removal_mgL:         removalMgL,
    regen_interval_days: regenInterval,
    salt_dose_gL:        saltDose,
    n_units:             nUnits,
    exch_capacity_gL:    exchCapacityGperL,
    safety_factor:       safetyFactor,
    // Loads
    daily_load_g:        dailyLoadG,
    load_per_cycle_g:    loadPerCycleG,
    // Resin
    resin_L_per_unit:    resinLperUnit,
    resin_ft3_per_unit:  resinFt3,
    // Tank (per unit)
    tank_dia_in:         tank.dia_in,
    tank_ht_in:          tank.ht_in,
    tank_dia_mm:         tankDiaMm,
    tank_ht_mm:          tankHtMm,
    selected_resin_L:    selectedResinL,
    // Flow
    min_flow_lpm:        minFlowLpm,
    max_flow_lpm:        maxFlowLpm,
    design_flow_lpm:     designFlowLpm,
    flow_check:          flowCheck,
    backwash_lpm:        backwashLpm,
    // Salt & brine
    salt_per_regen_kg:   saltPerRegenKg,
    monthly_salt_kg:     monthlySaltKg,
    brine_tank_min_L:    brineTankMinL,
    brine_tank_L:        brineTankL,
    // Rinse water
    rinse_water_L_per_regen: rinseWaterL,
    monthly_rinse_m3:    monthlyRinseM3,
    efficiency_pct:      efficiencyPct,
  };
}

// ─── Water Treatment System ───────────────────────────────────────────────────

function calcWaterTreatmentSystem(inputs: Record<string, number | string>): Record<string, unknown> {

  // ── Inputs ──────────────────────────────────────────────────────────────────
  const demandSource  = String(inputs.demand_source || 'direct');
  const nPeople       = Number(inputs.n_people)     || 0;
  const perCapita     = Number(inputs.per_capita_lpd) || 200;

  let demandLpd: number;
  if (demandSource === 'people') {
    if (nPeople <= 0) return { error: "Number of people must be greater than 0." };
    demandLpd = nPeople * perCapita;
  } else {
    // Accept demand_lpd (canonical), daily_demand_L, or daily_demand_m3 (alias m³/day → L/day)
    demandLpd = Number(inputs.demand_lpd)
      || Number(inputs.daily_demand_L)
      || (inputs.daily_demand_m3 ? Number(inputs.daily_demand_m3) * 1000 : 0)
      || 0;
    if (demandLpd <= 0) return { error: "Daily water demand must be greater than 0." };
  }

  const rawSource     = String(inputs.raw_source    || 'Deep Well / Bore');
  const turbidityNTU  = Math.max(0, Number(inputs.turbidity_ntu)   || 10);
  const ironMgL       = Math.max(0, Number(inputs.iron_mg)         || 0.3);
  const bacteriaConcern = String(inputs.bacteria_concern || 'yes') === 'yes';
  const intendedUse   = String(inputs.intended_use  || 'Potable');
  const peakFactor    = Math.max(1.1, Math.min(3.0, Number(inputs.peak_factor) || 1.5));

  // ── Derived flows ────────────────────────────────────────────────────────────
  const demandM3d     = demandLpd / 1000;
  const peakFlowM3hr  = parseFloat(((demandM3d * peakFactor) / 24).toFixed(3));
  const avgFlowM3hr   = parseFloat((demandM3d / 24).toFixed(3));
  const avgFlowLpm    = parseFloat((demandLpd / (24 * 60)).toFixed(2));

  // ── Treatment train selection ────────────────────────────────────────────────
  const needsCoagFloc    = turbidityNTU > 25;
  const needsSedimentation = turbidityNTU > 50;
  const needsIronRemoval  = ironMgL > 0.3;
  const needsDisinfection = bacteriaConcern || rawSource === 'Surface Water' || rawSource === 'Rainwater';
  const disinfMethod      = bacteriaConcern && demandLpd > 50000 ? 'Chlorination' : bacteriaConcern ? 'UV + Chlorination' : 'Chlorination';
  const needsSoftener     = intendedUse === 'Boiler Makeup' || intendedUse === 'Cooling Tower Makeup';
  const needsRO           = intendedUse === 'Boiler Makeup (High Pressure)';

  // Treatment train sequence
  const trainSteps: string[] = [];
  if (needsCoagFloc)     trainSteps.push('Coagulation / Flocculation (Alum dosing)');
  if (needsSedimentation) trainSteps.push('Sedimentation / Clarifier');
  trainSteps.push(needsIronRemoval ? 'Iron Removal Filter (Greensand + Aeration)' : 'Multimedia Filter (Quartz sand + Anthracite)');
  if (turbidityNTU > 5)  trainSteps.push('Activated Carbon Filter (Taste / Odor / Chlorine)');
  if (needsDisinfection) trainSteps.push(disinfMethod === 'UV + Chlorination' ? 'UV Disinfection + Chlorination' : 'Chlorination (Sodium Hypochlorite dosing)');
  if (needsSoftener)     trainSteps.push('Water Softener (Ion exchange: refer to Water Softener Sizing calc)');
  if (needsRO)           trainSteps.push('Reverse Osmosis (RO: for high-pressure boiler makeup)');
  trainSteps.push('Treated Water Storage Tank');

  // ── PNS 1998 source quality check ────────────────────────────────────────────
  const turbidityCheck  = turbidityNTU <= 5   ? 'WITHIN PNS 1998 limit (≤5 NTU) post-filtration achievable' : turbidityNTU <= 25  ? 'Filtration required to achieve PNS 1998 ≤5 NTU' : 'Coagulation + Filtration required for PNS 1998 compliance';
  const ironCheck       = ironMgL <= 0.3 ? 'Within PNS 1998 limit (≤0.3 mg/L)' : ironMgL <= 1.0 ? 'EXCEEDS PNS 1998 limit: iron removal required' : 'Severely elevated: aeration + greensand filtration required';

  // ── Turbidity classification ─────────────────────────────────────────────────
  const turbidClass = turbidityNTU < 5   ? 'Clear'    : turbidityNTU < 25  ? 'Slightly Turbid'  : turbidityNTU < 100 ? 'Moderately Turbid' : 'Highly Turbid';

  // ── 1. Multimedia / Sand Filter Sizing ────────────────────────────────────────
  // Filtration rate: 8 m/hr (sand), 10 m/hr (multimedia)
  const filtRate       = needsIronRemoval ? 8.0 : 10.0; // m/hr
  const filterAreaM2   = parseFloat((peakFlowM3hr / filtRate).toFixed(3));
  const filterDiaM     = parseFloat((Math.sqrt(filterAreaM2 * 4 / Math.PI)).toFixed(3));
  // Select standard pressure filter diameter (mm): 400,500,600,700,800,900,1000,1200,1400,1600,1800,2000,2400
  const STD_FILTER_DIA = [400,500,600,700,800,900,1000,1200,1400,1600,1800,2000,2400];
  const reqDiaMm = filterDiaM * 1000;
  const selFilterDiaMm = STD_FILTER_DIA.find(d => d >= reqDiaMm) ?? 2400;
  const selFilterAreaM2 = parseFloat((Math.PI / 4 * (selFilterDiaMm / 1000) ** 2).toFixed(4));
  const actualFiltRate  = parseFloat((peakFlowM3hr / selFilterAreaM2).toFixed(2));
  // Backwash: 25 m/hr
  const backwashFlowM3hr  = parseFloat((selFilterAreaM2 * 25).toFixed(2));
  const backwashFlowLpm   = parseFloat((backwashFlowM3hr / 60 * 1000).toFixed(0));
  const bedDepthMm        = needsIronRemoval ? 900 : 750; // mm
  const filterTankHtMm    = bedDepthMm + 400 + 300; // media + freeboard + underdrain

  // ── 2. Iron Removal (if needed) ─────────────────────────────────────────────
  // Aeration: simple cascade or pressure aerator at 4:1 air:water
  const aerationAirM3hr   = needsIronRemoval ? parseFloat((peakFlowM3hr * 4).toFixed(1)) : 0;
  // Greensand media: ~3.5 kg/m²
  const greensandKg        = needsIronRemoval ? parseFloat((selFilterAreaM2 * 3.5 * (bedDepthMm / 750)).toFixed(1)) : 0;
  // KMnO4 regenerant dose: 0.25 g / g Fe removed
  const ironRemovedGhr     = needsIronRemoval ? parseFloat((peakFlowM3hr * 1000 / 60 * (ironMgL - 0.1)).toFixed(1)) : 0;
  const kmno4DoseGhr       = needsIronRemoval ? parseFloat((ironRemovedGhr * 0.25).toFixed(1)) : 0;
  const kmno4DailyKg       = needsIronRemoval ? parseFloat((kmno4DoseGhr * 24 / 1000).toFixed(2)) : 0;

  // ── 3. Coagulant dosing (if needed) ─────────────────────────────────────────
  // Typical alum dose: 10-50 mg/L depending on turbidity
  const alumDoseMgL        = needsCoagFloc
    ? (turbidityNTU < 50 ? 10 : turbidityNTU < 100 ? 25 : 40) : 0;
  const alumDailyKg        = needsCoagFloc
    ? parseFloat((alumDoseMgL * demandM3d / 1000).toFixed(2)) : 0;

  // ── 4. Chlorine disinfection dosing ──────────────────────────────────────────
  // Cl2 dose by source quality
  const cl2DoseMgL =
    rawSource === 'Municipal Supply' ? 0.5 :
    rawSource === 'Deep Well / Bore' ? 1.0 :
    rawSource === 'Surface Water'    ? (turbidityNTU > 50 ? 5.0 : 3.0) :
    rawSource === 'Rainwater'        ? 2.0 : 1.0;
  const cl2DailyKg         = parseFloat((cl2DoseMgL * demandM3d / 1000).toFixed(3));
  // NaOCl (12% liquid hypochlorite): 1 kg Cl2 ≈ 8.3 L of 12% NaOCl
  const naoclDailyL        = parseFloat((cl2DailyKg * 8.3).toFixed(2));
  // Contact tank sizing: CT ≥ 36 mg·min/L for 3-log Giardia at pH 7, 25°C: EPA Guidance Manual Table 3-1
  const ctRequired         = 36; // mg·min/L  (EPA 3-log Giardia, free chlorine, pH 7, 25°C)
  const contactTimeMin     = parseFloat((ctRequired / cl2DoseMgL).toFixed(1));
  const contactTankM3      = parseFloat((peakFlowM3hr / 60 * contactTimeMin).toFixed(2));
  // CT achieved check
  const ctAchieved         = parseFloat((cl2DoseMgL * contactTimeMin).toFixed(1));
  const ctCheck            = ctAchieved >= ctRequired ? `PASS: CT ${ctAchieved} mg·min/L ≥ required ${ctRequired} mg·min/L` : `FAIL: CT ${ctAchieved} mg·min/L < required ${ctRequired} mg·min/L`;

  // ── 5. UV (if applicable) ────────────────────────────────────────────────────
  // UV dose for 3-log reduction: 40 mJ/cm² (EPA UV Guidance)
  const uvDoseMJcm2        = disinfMethod.includes('UV') ? 40 : 0;
  const uvFlowM3hr         = disinfMethod.includes('UV') ? peakFlowM3hr : 0;

  // ── 6. Storage tank ──────────────────────────────────────────────────────────
  const storageTankM3      = parseFloat((demandM3d * 1.0).toFixed(1)); // 1 day storage
  const storageTankL       = Math.round(storageTankM3 * 1000);

  // ── 7. Activated carbon filter (if needed) ───────────────────────────────────
  // Same diameter as main filter, empty bed contact time 10 min
  const acFilterDiaMm     = turbidityNTU > 5 ? selFilterDiaMm : 0;
  const acFiltAreaM2       = acFilterDiaMm > 0 ? selFilterAreaM2 : 0;
  const acEBCT_min         = 10; // minutes
  const acBedVolumeM3      = parseFloat((peakFlowM3hr / 60 * acEBCT_min).toFixed(3));
  const acBedDepthMm       = acFilterDiaMm > 0 ? Math.round((acBedVolumeM3 / acFiltAreaM2) * 1000) : 0;

  // ── 8. Treated water quality projection ──────────────────────────────────────
  const projTurbidityNTU   = parseFloat((turbidityNTU * (needsCoagFloc ? 0.02 : needsSedimentation ? 0.05 : 0.1)).toFixed(2));
  const projIronMgL        = needsIronRemoval ? parseFloat((ironMgL * 0.05).toFixed(3)) : ironMgL;
  const projClResidualMgL  = needsDisinfection ? parseFloat((cl2DoseMgL * 0.3).toFixed(2)) : 0; // residual after contact
  const meetsPN1998        = projTurbidityNTU <= 5 && projIronMgL <= 0.3 && (!bacteriaConcern || projClResidualMgL >= 0.2);
  const pns1998Status      = meetsPN1998 ? 'MEETS PNS 1998 / PNSDW' : 'REVIEW required: check residual disinfectant or turbidity';

  return {
    // Input summary
    demand_lpd:           parseFloat(demandLpd.toFixed(0)),
    demand_m3d:           parseFloat(demandM3d.toFixed(3)),
    peak_flow_m3hr:       peakFlowM3hr,
    avg_flow_m3hr:        avgFlowM3hr,
    avg_flow_lpm:         avgFlowLpm,
    raw_source:           rawSource,
    turbidity_ntu:        turbidityNTU,
    turbidity_class:      turbidClass,
    iron_mg:              ironMgL,
    bacteria_concern:     bacteriaConcern,
    intended_use:         intendedUse,
    peak_factor:          peakFactor,

    // PNS checks
    turbidity_check:      turbidityCheck,
    iron_check:           ironCheck,

    // Treatment train
    train_steps:          trainSteps,
    needs_coag_floc:      needsCoagFloc,
    needs_sedimentation:  needsSedimentation,
    needs_iron_removal:   needsIronRemoval,
    needs_disinfection:   needsDisinfection,
    disinfection_method:  disinfMethod,
    needs_softener_note:  needsSoftener,
    needs_ro_note:        needsRO,

    // Filter sizing
    filtration_rate_mhr:  filtRate,
    filter_area_req_m2:   filterAreaM2,
    filter_dia_req_mm:    parseFloat(reqDiaMm.toFixed(0)),
    selected_filter_dia_mm: selFilterDiaMm,
    selected_filter_area_m2: selFilterAreaM2,
    actual_filtration_rate: actualFiltRate,
    backwash_flow_m3hr:   backwashFlowM3hr,
    backwash_flow_lpm:    backwashFlowLpm,
    filter_bed_depth_mm:  bedDepthMm,
    filter_tank_height_mm: filterTankHtMm,

    // Iron removal
    iron_removal_air_m3hr: aerationAirM3hr,
    greensand_media_kg:   greensandKg,
    kmno4_daily_kg:       kmno4DailyKg,

    // Coagulant
    alum_dose_mg_L:       alumDoseMgL,
    alum_daily_kg:        alumDailyKg,

    // Disinfection
    cl2_dose_mg_L:        cl2DoseMgL,
    cl2_daily_kg:         cl2DailyKg,
    naocl_daily_L:        naoclDailyL,
    contact_time_min:     contactTimeMin,
    contact_tank_m3:      contactTankM3,
    ct_achieved:          ctAchieved,
    ct_required:          ctRequired,
    ct_check:             ctCheck,
    uv_dose_mj_cm2:       uvDoseMJcm2,
    uv_flow_m3hr:         uvFlowM3hr,

    // AC filter
    ac_filter_dia_mm:     acFilterDiaMm,
    ac_bed_volume_m3:     acBedVolumeM3,
    ac_bed_depth_mm:      acBedDepthMm,
    ac_ebct_min:          acEBCT_min,

    // Storage
    storage_tank_m3:      storageTankM3,
    storage_tank_L:       storageTankL,

    // Projected output quality
    proj_turbidity_ntu:   projTurbidityNTU,
    proj_iron_mg_L:       projIronMgL,
    proj_cl_residual_mg_L: projClResidualMgL,
    pns_1998_status:      pns1998Status,
  };
}

// ─── Wastewater Treatment (STP): Activated Sludge Method ───────────────────

function calcWastewaterSTP(inputs: Record<string, number | string>): Record<string, unknown> {
  const flowSource   = String(inputs.flow_source    || 'population');
  const population   = Number(inputs.population     || 200);
  const perCapLpd    = Number(inputs.per_capita_lpd || 150);
  const flowDirectM3 = Number(inputs.flow_direct_m3d || 30);
  const bodIn        = Number(inputs.bod_influent   || 220);
  const bodOut       = Number(inputs.bod_effluent   || 30);
  const srtDays      = Number(inputs.srt_days       || 8);
  const mlssMgL      = Number(inputs.mlss_mg_l      || 3000);
  const disinfection = String(inputs.disinfection   || 'Chlorination');

  // Design flow
  const flowM3Day  = flowSource === 'population' ? population * perCapLpd / 1000 : flowDirectM3;
  const flowM3Hr   = flowM3Day / 24;
  const peakFactor = 1.5;
  const peakFlowM3Hr = flowM3Hr * peakFactor;
  const peakFlowLps  = peakFlowM3Hr * 1000 / 3600;

  // BOD loading
  const bodLoadKgDay     = bodIn * flowM3Day / 1000;
  const bodRemovedKgDay  = (bodIn - bodOut) * flowM3Day / 1000;
  const bodRemovalPct    = Math.round((bodIn - bodOut) / bodIn * 100 * 10) / 10;

  // Activated sludge parameters
  const Y   = 0.60;  // yield coefficient, kg VSS/kg BOD
  const kd  = 0.06;  // endogenous decay, /day
  const mlvssRatio = 0.80; // VSS/TSS
  const mlvssMgL   = mlssMgL * mlvssRatio;

  // Aeration tank volume: SRT method: V = Q × Y × SRT × (S0-Se) / (X × (1 + kd×SRT))
  const aerVolM3Raw = (flowM3Day * Y * srtDays * (bodIn - bodOut)) / (mlvssMgL * (1 + kd * srtDays));
  const aerVolM3    = Math.ceil(aerVolM3Raw * 10) / 10;
  const aerHrtHr    = Math.round(aerVolM3 / flowM3Hr * 10) / 10;

  // Tank dimensions: L:W:D = 2:1:4 typical, depth 4m
  const depth   = 4.0;
  const planArea = aerVolM3 / depth;
  const width   = Math.ceil(Math.sqrt(planArea / 2) * 10) / 10;
  const length  = Math.ceil(width * 2 * 10) / 10;
  const aerDims = `${length} m × ${width} m × ${depth} m`;

  // MLVSS in tank
  const mlvssKg = Math.round(mlvssMgL * aerVolM3 / 1000 * 10) / 10;
  const fmRatio = Math.round(bodRemovedKgDay / mlvssKg * 1000) / 1000;

  // Oxygen demand: O2 = a×BOD_removed + b×MLVSS×V (kg/day)
  const a = 0.50; const b = 0.10;
  const o2Synthesis    = Math.round(a * bodRemovedKgDay * 10) / 10;
  const o2Endogenous   = Math.round(b * mlvssMgL * aerVolM3 / 1000 * 10) / 10;
  const o2TotalKgDay   = Math.round((o2Synthesis + o2Endogenous) * 10) / 10;

  // Blower: O2 demand kg/day → m3/min air (STE 8%, air density 1.2 kg/m3, O2 fraction 0.232)
  // kg O2/day ÷ (0.232 × 1.2 kg/m3 × 0.08 STE × 1440 min/day)
  const blowerM3Min    = Math.round(o2TotalKgDay / (0.232 * 1.2 * 0.08 * 1440) * 100) / 100;
  const blowerRecM3Min = Math.round(blowerM3Min * 1.2 * 100) / 100; // 20% safety
  const blowerKw       = Math.ceil(blowerRecM3Min * 0.55 * 10) / 10; // ~0.55 kW per m3/min

  // Primary clarifier: SOR = 28 m3/m2/day
  const primSor     = 28;
  const primAreaM2  = Math.round(flowM3Day / primSor * 100) / 100;
  const primDiaM    = Math.round(Math.sqrt(primAreaM2 * 4 / Math.PI) * 10) / 10;
  const primDepthM  = 3.5;
  const primHdtHr   = Math.round(primAreaM2 * primDepthM / flowM3Hr * 10) / 10;

  // Secondary clarifier: SOR = 20 m3/m2/day
  const secSor    = 20;
  const secAreaM2 = Math.round(flowM3Day / secSor * 100) / 100;
  const secDiaM   = Math.round(Math.sqrt(secAreaM2 * 4 / Math.PI) * 10) / 10;
  const secDepthM = 4.0;

  // Sludge production: Px = Y_obs × BOD_removed, Y_obs = Y/(1+kd×SRT)
  const yObs         = Y / (1 + kd * srtDays);
  const sludgeKgDay  = Math.round(yObs * bodRemovedKgDay * 10) / 10;
  const sludgeM3Day  = Math.round(sludgeKgDay / 10 * 100) / 100; // at 1% DS (10 kg/m3)
  const wasM3Day     = Math.round(sludgeM3Day * 100) / 100;
  const desludgeDays = Math.round(20 / sludgeM3Day * 10) / 10; // assume 20 m3 sludge holding
  const desludgeFreq = `Every ${desludgeDays} days (at ${sludgeM3Day} m³/day production, 20 m³ holding tank)`;

  // Disinfection
  const cl2DoseMgL   = 5.0; // mg/L for secondary effluent
  const naoclLpd     = Math.round(cl2DoseMgL * flowM3Day * 0.083 * 10) / 10; // 10% NaOCl, 0.083 L per gram
  const contactTankM3 = Math.round(peakFlowM3Hr / 60 * 30 * 10) / 10; // 30-min contact at peak flow

  // Projected effluent quality
  const effluentBod  = bodOut;
  const effluentTss  = Math.round(mlssMgL * 0.005 * 10) / 10; // ~0.5% carryover from secondary clarifier, typ 10-20 mg/L
  const effluentTssAdj = Math.max(effluentTss, 10); // minimum 10 mg/L realistic

  const denrStatus = effluentBod <= 30 && effluentTssAdj <= 50 ? 'COMPLIANT' : 'REVIEW';

  return {
    flow_source:         flowSource,
    flow_m3_day:         Math.round(flowM3Day * 10) / 10,
    flow_m3_hr:          Math.round(flowM3Hr * 100) / 100,
    peak_flow_m3_hr:     Math.round(peakFlowM3Hr * 100) / 100,
    peak_flow_lps:       Math.round(peakFlowLps * 10) / 10,
    bod_load_kg_day:     Math.round(bodLoadKgDay * 10) / 10,
    bod_removed_kg_day:  Math.round(bodRemovedKgDay * 10) / 10,
    bod_removal_pct:     bodRemovalPct,
    // Aeration tank
    aeration_vol_m3:     aerVolM3,
    aeration_hrt_hr:     aerHrtHr,
    aeration_dims:       aerDims,
    mlvss_mg_l:          mlvssMgL,
    mlvss_kg:            mlvssKg,
    fm_ratio:            fmRatio,
    // O2 and blower
    o2_synthesis_kg_day:   o2Synthesis,
    o2_endogenous_kg_day:  o2Endogenous,
    o2_total_kg_day:       o2TotalKgDay,
    blower_m3_min:         blowerM3Min,
    blower_recommended_m3_min: blowerRecM3Min,
    blower_kw:             blowerKw,
    // Primary clarifier
    prim_sor:       primSor,
    prim_area_m2:   primAreaM2,
    prim_dia_m:     primDiaM,
    prim_depth_m:   primDepthM,
    prim_hdt_hr:    primHdtHr,
    // Secondary clarifier
    sec_sor:        secSor,
    sec_area_m2:    secAreaM2,
    sec_dia_m:      secDiaM,
    sec_depth_m:    secDepthM,
    // Sludge
    sludge_kg_day:  sludgeKgDay,
    sludge_m3_day:  sludgeM3Day,
    was_m3_day:     wasM3Day,
    desludge_freq:  desludgeFreq,
    // Disinfection
    cl2_dose_mg_l:   cl2DoseMgL,
    naocl_lpd:       naoclLpd,
    contact_tank_m3: contactTankM3,
    // Effluent quality
    effluent_bod:   effluentBod,
    effluent_tss:   effluentTssAdj,
    denr_status:    denrStatus,
  };
}

// ─── Grease Trap Sizing: PDI G-101 Flow Rate Method ──────────────────────────

const PDI_STANDARD_GPM = [4, 6, 7, 10, 15, 20, 25, 35, 50, 75, 100];

function calcGreaseTrapSizing(inputs: Record<string, unknown>): Record<string, unknown> {
  const fixtures  = (inputs.fixtures as Array<{fixture_type: string; flow_lpm: number; qty: number}>) || [];
  const suf       = Number(inputs.suf        || 0.75);
  const mealsDay  = Number(inputs.meals_per_day || 0);

  // Total connected flow
  const totalFlowLPM = fixtures.reduce((sum, fx) => sum + Number(fx.flow_lpm) * Number(fx.qty), 0);

  // Design flow with SUF
  const qDesignLPM = totalFlowLPM * suf;
  // Convert to GPM (1 L/min = 0.26417 GPM)
  const qDesignGPM = qDesignLPM * 0.26417;

  // Select next standard PDI GPM size >= q_design
  const pdiGPM = PDI_STANDARD_GPM.find(g => g >= qDesignGPM) || PDI_STANDARD_GPM[PDI_STANDARD_GPM.length - 1];

  // Liquid capacity: PDI GPM × 2 gal converted to litres
  const liquidCapL = pdiGPM * 2 * 3.78541;

  // Grease retention: PDI GPM × 0.4536 kg (1 lb per GPM)
  const greaseRetKg = pdiGPM * 0.4536;

  // Cleaning interval: greaseRetKg / (meals/day × 0.06 kg/meal × 0.5 fill limit)
  let cleanIntervalDays = 0;
  if (mealsDay > 0) {
    const fogPerDay = mealsDay * 0.06;  // kg FOG/day
    // Clean when 50% of grease retention is filled
    cleanIntervalDays = Math.floor((greaseRetKg * 0.5) / fogPerDay);
    if (cleanIntervalDays < 1) cleanIntervalDays = 1;
    if (cleanIntervalDays > 90) cleanIntervalDays = 90;
  } else {
    cleanIntervalDays = 30; // default recommendation
  }

  return {
    total_flow_lpm:        +totalFlowLPM.toFixed(2),
    q_design_lpm:          +qDesignLPM.toFixed(2),
    q_design_gpm:          +qDesignGPM.toFixed(2),
    pdi_gpm:               pdiGPM,
    liquid_cap_l:          +liquidCapL.toFixed(1),
    grease_ret_kg:         +greaseRetKg.toFixed(2),
    clean_interval_days:   cleanIntervalDays,
    suf_used:              suf,
  };
}

// ─── Roof Drain Sizing: IPC §1106 / Philippine Plumbing Code ────────────────

// Roof drain body capacities (L/s): IPC 2018 Table 1106.2 / ASPE Vol. 2
// At 100 mm head above drain invert, C = 1.0 (impervious roof)
const RD_DRAIN_SIZES_MM    = [75,   100,  125,  150,  200 ];
const RD_DRAIN_CAP_LS      = [0.76, 1.51, 2.65, 4.16, 8.83];

// Horizontal leader capacity at 1% slope (L/s): Manning n = 0.011, half-full flow
// Scales to other slopes: Cap_s = Cap_1% × √(slope_pct / 1.0)
const RD_LEADER_SIZES_MM   = [75,   100,  125,  150,  200  ];
const RD_LEADER_CAP_1PCT   = [0.95, 1.89, 3.31, 5.20, 11.04];

function calcRoofDrainSizing(inputs: Record<string, number | string>): Record<string, unknown> {
  const roofArea       = Number(inputs.roof_area        || 0);
  const nDrains        = Math.max(1, Math.round(Number(inputs.n_drains       || 2)));
  const intensityMmhr  = Number(inputs.intensity_mmhr   || 100);
  const slopePct       = Number(inputs.leader_slope_pct || 1.0);
  const hasParapet     = String(inputs.has_parapet || "Yes") === "Yes";
  const pipeMaterial   = String(inputs.pipe_material    || "uPVC");

  // Manning n by material
  const manningN = (pipeMaterial === "Cast Iron" || pipeMaterial === "Galv. Steel") ? 0.013 : 0.011;

  // Design flow: Rational Method, C = 1.0 for impervious roof (IPC §1101)
  // Q (L/s) = I (mm/hr) × A (m²) / 3600
  const Q_total_ls = (intensityMmhr * roofArea) / 3600;
  const Q_each_ls  = nDrains > 0 ? Q_total_ls / nDrains : Q_total_ls;

  // Primary roof drain body: first size whose capacity ≥ Q_each
  let drainSizeMm = RD_DRAIN_SIZES_MM[RD_DRAIN_SIZES_MM.length - 1];
  let drainCapLs  = RD_DRAIN_CAP_LS[RD_DRAIN_CAP_LS.length - 1];
  for (let i = 0; i < RD_DRAIN_SIZES_MM.length; i++) {
    if (RD_DRAIN_CAP_LS[i] >= Q_each_ls) {
      drainSizeMm = RD_DRAIN_SIZES_MM[i];
      drainCapLs  = RD_DRAIN_CAP_LS[i];
      break;
    }
  }

  // Vertical leader (conductor): same diameter as drain body per IPC §1106.3
  const leaderSizeMm = drainSizeMm;

  // Horizontal leader: capacity scales with √(slope_pct / 1.0)
  const slopeFactor = Math.sqrt(Math.max(slopePct, 0.1) / 1.0);
  let horizLeaderSizeMm = RD_LEADER_SIZES_MM[RD_LEADER_SIZES_MM.length - 1];
  let horizLeaderCapLs  = parseFloat((RD_LEADER_CAP_1PCT[RD_LEADER_SIZES_MM.length - 1] * slopeFactor).toFixed(2));
  for (let i = 0; i < RD_LEADER_SIZES_MM.length; i++) {
    const capAtSlope = RD_LEADER_CAP_1PCT[i] * slopeFactor;
    if (capAtSlope >= Q_each_ls) {
      horizLeaderSizeMm = RD_LEADER_SIZES_MM[i];
      horizLeaderCapLs  = parseFloat(capAtSlope.toFixed(2));
      break;
    }
  }

  // Overflow drain: required when parapet walls present (IPC §1101.7)
  // Same size as primary drain, invert +50 mm above primary invert
  const overflowDrainMm: number | null = hasParapet ? drainSizeMm : null;

  // Compliance
  const drainCapOk     = drainCapLs >= Q_each_ls;
  const minDrainsCheck = nDrains >= 2 ? "PASS" : "FAIL: minimum 2 primary roof drains required per IPC §1106.3";
  const drainCapCheck  = drainCapOk
    ? "PASS"
    : `FAIL: Q_each (${Q_each_ls.toFixed(2)} L/s) exceeds maximum 200 mm drain capacity (8.83 L/s). Add more drains or split into zones.`;
  const overflowCheck  = hasParapet
    ? "Required: overflow drains specified at +50 mm above primary invert (IPC §1101.7)"
    : "Not required: no parapet walls";
  const overallStatus  = (nDrains >= 2 && drainCapOk) ? "PASS" : "FAIL";

  return {
    roof_area_m2:        parseFloat(roofArea.toFixed(1)),
    n_drains:            nDrains,
    intensity_mmhr:      intensityMmhr,
    leader_slope_pct:    slopePct,
    has_parapet:         hasParapet,
    pipe_material:       pipeMaterial,
    manning_n:           manningN,
    q_total_ls:          parseFloat(Q_total_ls.toFixed(2)),
    q_each_ls:           parseFloat(Q_each_ls.toFixed(2)),
    drain_size_mm:       drainSizeMm,
    drain_cap_ls:        drainCapLs,
    leader_size_mm:      leaderSizeMm,
    horiz_leader_mm:     horizLeaderSizeMm,
    horiz_leader_cap_ls: horizLeaderCapLs,
    overflow_drain_mm:   overflowDrainMm,
    min_drains_check:    minDrainsCheck,
    drain_cap_check:     drainCapCheck,
    overflow_check:      overflowCheck,
    overall_status:      overallStatus,
  };
}

// ─── Storm Drain / Stormwater: Rational Method + Manning's Pipe Sizing ───────

const SD_STANDARD_DIAMETERS_MM = [300, 375, 450, 525, 600, 675, 750, 900, 1050, 1200, 1350, 1500];

function calcStormDrain(inputs: Record<string, number | string>): Record<string, unknown> {
  const areaMode       = String(inputs.area_mode       || 'single');
  const intensityMmhr  = Number(inputs.intensity_mmhr  || 75);
  const tcMin          = Number(inputs.tc_min          || 15);
  const returnPeriod   = Number(inputs.return_period   || 10);
  const slopePct       = Number(inputs.slope_pct       || 0.5);
  const pipeMaterial   = String(inputs.pipe_material   || 'uPVC');
  const manningN       = Number(inputs.manning_n       || 0.011);

  // Determine catchment area and runoff coefficient
  let totalAreaHa = Number(inputs.area_ha || 0.5);
  let compositeC  = Number(inputs.c_value || 0.80);
  let zoneTable: { zone: string; area_ha: number; c: number; weight: number }[] = [];

  if (areaMode === 'composite') {
    const z1a = Number(inputs.z1_area || 0);
    const z1c = Number(inputs.z1_c   || 0.90);
    const z2a = Number(inputs.z2_area || 0);
    const z2c = Number(inputs.z2_c   || 0.35);
    const z3a = Number(inputs.z3_area || 0);
    const z3c = Number(inputs.z3_c   || 0.60);

    const zones = [
      { zone: 'Zone 1', area_ha: z1a, c: z1c },
      { zone: 'Zone 2', area_ha: z2a, c: z2c },
      { zone: 'Zone 3', area_ha: z3a, c: z3c },
    ].filter(z => z.area_ha > 0);

    totalAreaHa = zones.reduce((s, z) => s + z.area_ha, 0) || 0.5;
    const sumCA = zones.reduce((s, z) => s + z.c * z.area_ha, 0);
    compositeC  = totalAreaHa > 0 ? Math.round((sumCA / totalAreaHa) * 1000) / 1000 : 0.80;

    zoneTable = zones.map(z => ({
      zone:    z.zone,
      area_ha: z.area_ha,
      c:       z.c,
      weight:  Math.round((z.c * z.area_ha / totalAreaHa) * 1000) / 1000,
    }));
  }

  // Rational Method: Q = C × i × A / 360  (m³/s, i in mm/hr, A in ha)
  const Q_m3s = compositeC * intensityMmhr * totalAreaHa / 360;

  // Pipe sizing: D_req = (Q × n / (0.3117 × sqrt(S)))^(3/8) in metres
  const S = slopePct / 100;
  const sqrtS = Math.sqrt(S);
  const D_req_m   = Math.pow((Q_m3s * manningN) / (0.3117 * sqrtS), 3 / 8);
  const D_req_mm  = D_req_m * 1000;

  // Round up to next DPWH standard diameter (minimum 300 mm)
  const D_sel_mm = SD_STANDARD_DIAMETERS_MM.find(d => d >= D_req_mm) || SD_STANDARD_DIAMETERS_MM[SD_STANDARD_DIAMETERS_MM.length - 1];

  // Full-pipe capacity of selected pipe
  const D_sel_m   = D_sel_mm / 1000;
  const Q_cap_m3s = (0.3117 / manningN) * Math.pow(D_sel_m, 8 / 3) * sqrtS;

  // Full-pipe velocity
  const A_pipe    = Math.PI / 4 * D_sel_m * D_sel_m;
  const V_m_s     = Q_cap_m3s / A_pipe;

  // Velocity limits per material
  const maxVel = (pipeMaterial === 'uPVC' || pipeMaterial === 'HDPE') ? 5.0 : 3.0;
  const velocityCheck = V_m_s >= 0.6 && V_m_s <= maxVel ? 'PASS' : 'FAIL';
  const velocityNote  = V_m_s < 0.6
    ? `Low velocity (${Math.round(V_m_s * 100) / 100} m/s < 0.6 m/s minimum): increase slope or verify flow.`
    : V_m_s > maxVel
    ? `High velocity (${Math.round(V_m_s * 100) / 100} m/s > ${maxVel} m/s max for ${pipeMaterial}): increase pipe diameter or reduce slope.`
    : `Velocity ${Math.round(V_m_s * 100) / 100} m/s is within acceptable range (0.6–${maxVel} m/s).`;

  const flowRatioPct = Math.round((Q_m3s / Q_cap_m3s) * 1000) / 10; // %

  return {
    area_mode:         areaMode,
    total_area_ha:     Math.round(totalAreaHa * 1000) / 1000,
    composite_c:       Math.round(compositeC * 1000) / 1000,
    return_period_yr:  returnPeriod,
    intensity_mmhr:    intensityMmhr,
    tc_min:            tcMin,
    slope_pct:         slopePct,
    pipe_material:     pipeMaterial,
    manning_n:         manningN,
    // Rational Method results
    design_flow_m3s:   Math.round(Q_m3s * 100000) / 100000,
    design_flow_lps:   Math.round(Q_m3s * 1000 * 10) / 10,
    // Pipe sizing
    d_required_mm:     Math.round(D_req_mm * 10) / 10,
    d_selected_mm:     D_sel_mm,
    q_capacity_m3s:    Math.round(Q_cap_m3s * 100000) / 100000,
    q_capacity_lps:    Math.round(Q_cap_m3s * 1000 * 10) / 10,
    full_pipe_vel_ms:  Math.round(V_m_s * 100) / 100,
    flow_ratio_pct:    flowRatioPct,
    velocity_check:    velocityCheck,
    velocity_note:     velocityNote,
    max_velocity_ms:   maxVel,
    zone_table:        zoneTable,
  };
}

// ─── Boiler System Calculation ───────────────────────────────────────────────
//
// Steam tables (saturation): pressure → hg, hf, T_sat
// Interpolated from IAPWS-IF97 saturation curve (0.1–50 bar abs)
// P_abs (bar a) = P_gauge (bar g) + 1.01325
//
// Outputs: Q_boiler (kW), BHP, fuel consumption, blowdown %, makeup water,
//          safety valve minimum capacity
//
// Standards: PD 8, ASME BPVC Sec I/IV, PSME Code, DOLE OSH
// ─────────────────────────────────────────────────────────────────────────────

// Steam saturation table [P_bara, T_sat_C, hg_kJ_kg, hf_kJ_kg]
const STEAM_TABLE: [number, number, number, number][] = [
  [0.006113, 0.01, 2500.9, 0.0],
  [0.1,      45.8, 2584.7, 191.8],
  [0.5,      81.3, 2645.4, 340.5],
  [1.0,      99.6, 2675.0, 417.5],
  [1.5,     111.4, 2693.1, 467.2],
  [2.0,     120.2, 2706.3, 504.7],
  [3.0,     133.5, 2724.9, 561.2],
  [4.0,     143.6, 2738.1, 604.7],
  [5.0,     151.8, 2748.1, 640.1],
  [6.0,     158.8, 2756.4, 670.4],
  [7.0,     165.0, 2763.2, 697.2],
  [8.0,     170.4, 2769.0, 721.0],
  [9.0,     175.4, 2773.8, 742.8],
  [10.0,    179.9, 2777.8, 762.6],
  [12.0,    187.9, 2784.3, 798.4],
  [15.0,    198.3, 2791.5, 844.6],
  [20.0,    212.4, 2798.7, 908.4],
  [25.0,    223.9, 2802.0, 962.0],
  [30.0,    233.8, 2803.0, 1008.3],
  [40.0,    250.4, 2800.3, 1087.4],
  [50.0,    263.9, 2794.2, 1154.2],
];

function interpolateSteamTable(p_bara: number): { t_sat: number; hg: number; hf_sat: number } {
  const tbl = STEAM_TABLE;
  if (p_bara <= tbl[0][0]) return { t_sat: tbl[0][1], hg: tbl[0][2], hf_sat: tbl[0][3] };
  if (p_bara >= tbl[tbl.length - 1][0]) {
    const last = tbl[tbl.length - 1];
    return { t_sat: last[1], hg: last[2], hf_sat: last[3] };
  }
  for (let i = 0; i < tbl.length - 1; i++) {
    const [p0, t0, hg0, hf0] = tbl[i];
    const [p1, t1, hg1, hf1] = tbl[i + 1];
    if (p_bara >= p0 && p_bara <= p1) {
      const f = (p_bara - p0) / (p1 - p0);
      return {
        t_sat:   Math.round((t0  + f * (t1  - t0))  * 10) / 10,
        hg:      Math.round((hg0 + f * (hg1 - hg0)) * 10) / 10,
        hf_sat:  Math.round((hf0 + f * (hf1 - hf0)) * 10) / 10,
      };
    }
  }
  return { t_sat: 100, hg: 2675, hf_sat: 418 };
}

// Feedwater enthalpy approximation: hf_fw ≈ Cp_water × T_fw (kJ/kg), Cp = 4.187 kJ/kg·K
function fwEnthalpy(t_fw_c: number): number {
  return Math.round(4.187 * t_fw_c * 10) / 10;
}

// Fuel LHV (kJ/kg) and density (kg/L) where applicable
const FUEL_LHV: Record<string, number> = {
  'LPG':         46100,
  'Diesel':      42700,
  'Bunker C':    40200,
  'Natural Gas': 50000,
  'Biomass':     15000,
};
// kg/L for liquid fuels (Natural Gas and Biomass don't use volume)
const FUEL_DENSITY: Record<string, number> = {
  'LPG':    0.54,
  'Diesel': 0.84,
  'Bunker C': 0.96,
};

function calcBoiler(inputs: Record<string, number | string>): Record<string, unknown> {
  const boilerType = String(inputs.boiler_type || 'Steam');

  // ── HOT WATER BRANCH ────────────────────────────────────────────────────────
  if (boilerType === 'Hot Water') {
    const supplyTempC   = Number(inputs.supply_temp_c      || 80);
    const returnTempC   = Number(inputs.return_temp_c      || 60);
    const flowRateLhr   = Number(inputs.flow_rate_lhr      || 0);
    const numBoilers    = Math.max(1, Number(inputs.num_boilers || 1));
    const sysPressureG  = Number(inputs.system_pressure_barg || 3);
    const fuelType      = String(inputs.fuel_type          || 'LPG');
    const effPct        = Number(inputs.efficiency_pct     || 82);
    const safetyFactor  = Number(inputs.safety_factor      || 1.25);

    const deltaT        = supplyTempC - returnTempC;  // °C (= K for ΔT)
    const avgTempC      = (supplyTempC + returnTempC) / 2;
    // Water density at average temp: least-squares fit of IAPWS data (40–95°C)
    // ρ ≈ 1.0184 − 0.000619 × T  (kg/L), error ±0.3% vs IAPWS in range
    const waterDensity  = Math.round((1.0184 - 0.000619 * avgTempC) * 10000) / 10000;  // kg/L, 4dp
    // Compute Q directly from L/hr to avoid rounding cascade through flowRateKgS
    // Q = (L/hr × ρ kg/L / 3600 s/hr) × Cp kJ/kg·K × ΔT K  (kW)
    const flowRateKgS   = Math.round(flowRateLhr * waterDensity / 3600 * 10000) / 10000;  // kg/s, 4dp
    const q_raw_kw      = flowRateLhr * waterDensity / 3600 * 4.187 * deltaT;  // unrounded

    // Q = ṁ × Cp × ΔT (kW),  Cp = 4.187 kJ/kg·K
    const q_net_kw      = Math.round(q_raw_kw * 10) / 10;
    const q_net_bhp     = Math.round(q_net_kw / 9.8095 * 10) / 10;
    const q_boiler_kw   = Math.round(q_net_kw * safetyFactor * 10) / 10;
    const q_boiler_bhp  = Math.round(q_boiler_kw / 9.8095 * 10) / 10;
    const total_kw      = Math.round(q_boiler_kw  * numBoilers * 10) / 10;
    const total_bhp     = Math.round(q_boiler_bhp * numBoilers * 10) / 10;

    // Fuel consumption
    const lhv           = FUEL_LHV[fuelType] || 42700;
    const eta           = effPct / 100;
    const fuel_kg_hr    = lhv > 0 && eta > 0
      ? Math.round(q_boiler_kw / (lhv / 3600 * eta) * 100) / 100
      : 0;
    const densityKgL    = FUEL_DENSITY[fuelType];
    const fuel_l_hr     = densityKgL
      ? Math.round(fuel_kg_hr / densityKgL * 10) / 10
      : null;

    // Safety relief valve: min capacity per ASME Sec IV = 1.1 × design output
    const safety_valve_min_kw = Math.round(q_boiler_kw * 1.1 * 10) / 10;

    return {
      boiler_type:              'Hot Water',
      supply_temp_c:            supplyTempC,
      return_temp_c:            returnTempC,
      delta_t_c:                deltaT,
      avg_temp_c:               Math.round(avgTempC * 10) / 10,
      water_density_kg_l:       waterDensity,
      flow_rate_kgs:            flowRateKgS,
      q_net_kw:                 q_net_kw,
      q_net_bhp:                q_net_bhp,
      q_boiler_kw:              q_boiler_kw,
      q_boiler_bhp:             q_boiler_bhp,
      total_capacity_kw:        total_kw,
      total_capacity_bhp:       total_bhp,
      fuel_lhv_kj_kg:           lhv,
      fuel_consumption_kg_hr:   fuel_kg_hr,
      fuel_consumption_lhr:     fuel_l_hr,
      safety_valve_min_kw:      safety_valve_min_kw,
      system_pressure_barg:     sysPressureG,
    };
  }

  // ── STEAM BRANCH ────────────────────────────────────────────────────────────
  const loadMode        = String(inputs.load_mode        || 'Steam Demand (kg/hr)');
  const steamDemandIn   = Number(inputs.steam_demand_kg_hr || 0);
  const heatLoadKW      = Number(inputs.heat_load_kw     || 0);
  const numBoilers      = Math.max(1, Number(inputs.num_boilers || 1));
  const pGauge          = Number(inputs.steam_pressure_barg || 7);
  const fwTempC         = Number(inputs.fw_temp_c        || 80);
  const fuelType        = String(inputs.fuel_type        || 'LPG');
  const effPct          = Number(inputs.efficiency_pct   || 82);
  const safetyFactor    = Number(inputs.safety_factor    || 1.25);
  const tdsMakeup       = Number(inputs.tds_makeup_ppm   || 200);
  const tdsMax          = Math.max(tdsMakeup + 1, Number(inputs.tds_max_ppm || 3000));

  // Steam properties
  const p_bara = pGauge + 1.01325;
  const { t_sat, hg, hf_sat } = interpolateSteamTable(p_bara);
  const hf_fw  = fwEnthalpy(fwTempC);
  const delta_h = Math.round((hg - hf_fw) * 10) / 10;  // kJ/kg

  // Steam demand
  let steamDemandKgHr: number;
  if (loadMode.includes('Heat Load')) {
    // Back-calculate steam demand from heat load
    // Q_kW = steam_demand × delta_h / 3600 → steam_demand = Q_kW × 3600 / delta_h
    steamDemandKgHr = delta_h > 0 ? Math.round(heatLoadKW * 3600 / delta_h * 10) / 10 : 0;
  } else {
    steamDemandKgHr = steamDemandIn;
  }

  // Design demand with safety factor (per boiler)
  const designSteamKgHr = Math.round(steamDemandKgHr * safetyFactor * 10) / 10;

  // Boiler heat output
  const q_boiler_kw = delta_h > 0
    ? Math.round(designSteamKgHr * delta_h / 3600 * 10) / 10
    : 0;
  const q_boiler_bhp = Math.round(q_boiler_kw / 9.8095 * 10) / 10;

  // Total installed
  const total_kw  = Math.round(q_boiler_kw  * numBoilers * 10) / 10;
  const total_bhp = Math.round(q_boiler_bhp * numBoilers * 10) / 10;

  // Fuel consumption (per boiler)
  const lhv = FUEL_LHV[fuelType] || 42700;
  const eta = effPct / 100;
  const fuel_kg_hr = lhv > 0 && eta > 0
    ? Math.round(q_boiler_kw / (lhv / 3600 * eta) * 100) / 100
    : 0;
  // Volumetric (L/hr) for liquid fuels
  const densityKgL = FUEL_DENSITY[fuelType];
  const fuel_l_hr  = densityKgL
    ? Math.round(fuel_kg_hr / densityKgL * 10) / 10
    : null;

  // Blowdown
  const blowdownPct = tdsMax > tdsMakeup
    ? Math.round(tdsMakeup / (tdsMax - tdsMakeup) * 1000) / 10  // 1 decimal %
    : 0;
  const blowdownKgHr    = Math.round(designSteamKgHr * blowdownPct / 100 * 10) / 10;
  const makeupWaterKgHr = Math.round((designSteamKgHr + blowdownKgHr) * 10) / 10;

  // Safety valve minimum
  const safetyValveMinKgHr = Math.round(designSteamKgHr * 1.1 * 10) / 10;

  return {
    boiler_type:              boilerType,
    steam_pressure_bara:      Math.round(p_bara * 1000) / 1000,
    t_sat_c:                  t_sat,
    hg_kj_kg:                 hg,
    hf_fw_kj_kg:              hf_fw,
    delta_h_kj_kg:            delta_h,
    steam_demand_kg_hr:       steamDemandKgHr,
    design_steam_demand_kg_hr:designSteamKgHr,
    q_boiler_kw:              q_boiler_kw,
    q_boiler_bhp:             q_boiler_bhp,
    total_capacity_kw:        total_kw,
    total_capacity_bhp:       total_bhp,
    fuel_lhv_kj_kg:           lhv,
    fuel_consumption_kg_hr:   fuel_kg_hr,
    fuel_consumption_lhr:     fuel_l_hr,
    blowdown_pct:             blowdownPct,
    blowdown_kg_hr:           blowdownKgHr,
    makeup_water_kg_hr:       makeupWaterKgHr,
    safety_valve_min_kg_hr:   safetyValveMinKgHr,
  };
}

// ─── Electrical: Generator Sizing: ISO 8528-1 / PEC Art. 7 / NFPA 110 ───────
const STD_GEN_KVA = [10,15,20,25,30,40,50,62.5,75,87.5,100,125,150,175,200,250,300,350,400,450,500,600,750,875,1000,1250,1500,2000];

function calcGeneratorSizing(inputs: Record<string, unknown>): Record<string, unknown> {
  const round2 = (v: number) => Math.round(v * 100) / 100;

  const loads = (inputs.loads as Array<{ load_type: string; quantity: number; watts_each: number; power_factor: number }>) || [];
  const overallPF    = Number(inputs.overall_pf)    || 0.85;
  const safetyFactor = Number(inputs.safety_factor) || 1.25;
  const motorHP      = Number(inputs.motor_hp)      || 0;
  const startMethod  = String(inputs.start_method || "DOL");
  const application  = String(inputs.application  || "Standby (ESP)");

  // Step 1: Running demand
  const breakdown = loads.map(l => {
    const qty = Number(l.quantity) || 1;
    const w   = Number(l.watts_each) || 0;
    const pf  = Number(l.power_factor) || 0.85;
    const df  = LOAD_DEMAND_FACTOR[l.load_type] || 1.0;
    const connVA = qty * w / pf;
    const demVA  = connVA * df;
    return { load_type: l.load_type, qty, watts_each: w, pf, demand_factor: df,
             connected_va: Math.round(connVA), demand_va: Math.round(demVA) };
  });

  const totalDemandVA  = breakdown.reduce((s, l) => s + l.demand_va, 0);
  const totalDemandKVA = round2(totalDemandVA / 1000);
  const runningKW      = round2(totalDemandKVA * overallPF);
  const runningKVA     = round2(totalDemandKVA);

  // Step 2: Starting kVA (largest motor DOL surge)
  const motorKW = round2(motorHP * 0.7457); // HP to kW
  let startMultiplier = 1.0;
  if (startMethod === "DOL")          startMultiplier = 3.5; // 6-7× FLA ≈ 3-4× kVA (conservative 3.5)
  else if (startMethod === "Soft Starter") startMultiplier = 1.75;
  else if (startMethod === "VFD")     startMultiplier = 1.25;
  const startingKVA = round2(motorHP > 0 ? (motorKW / 0.85) * startMultiplier : 0);

  // Step 3: Design kVA
  const controllingKVA = Math.max(runningKVA, startingKVA);
  const designKVA      = round2(controllingKVA * safetyFactor);

  // Step 4: Select standard generator size
  const selectedKVA = STD_GEN_KVA.find(s => s >= designKVA) || STD_GEN_KVA[STD_GEN_KVA.length - 1];
  const selectedKW  = round2(selectedKVA * 0.8); // standard alternator PF 0.8
  const loadingPct  = round2((runningKVA / selectedKVA) * 100);

  // Step 5: Fuel consumption (diesel)
  // SFC at 100% load ~0.30 L/kWh; at 75% load ~0.27 L/kWh (ISO 3046-1 / manufacturer data)
  const fuel100LHr   = round2(selectedKW * 0.30);
  const fuel75LHr    = round2(selectedKW * 0.75 * 0.27);
  const tank8hrL     = Math.ceil(fuel100LHr * 8);

  return {
    phase_config:        inputs.phase_config,
    application,
    load_breakdown:      breakdown,
    total_demand_va:     Math.round(totalDemandVA),
    total_demand_kva:    totalDemandKVA,
    overall_pf:          overallPF,
    running_kw:          runningKW,
    running_kva:         runningKVA,
    motor_hp:            motorHP,
    motor_kw:            motorKW,
    start_method:        startMethod,
    start_multiplier:    startMultiplier,
    starting_kva:        startingKVA,
    controlling_kva:     round2(controllingKVA),
    safety_factor:       safetyFactor,
    design_kva:          designKVA,
    selected_kva:        selectedKVA,
    selected_kw:         selectedKW,
    loading_pct:         loadingPct,
    fuel_75pct_lhr:      fuel75LHr,
    fuel_100pct_lhr:     fuel100LHr,
    tank_8hr_litres:     tank8hrL,
  };
}

// ─── Electrical: Solar PV System: IEC 62548 / PEC Art. 6 / DOE Net Metering ─
const PH_PSH: Record<string, number> = {
  "Metro Manila": 4.5, "Cebu": 4.8, "Davao": 4.9, "Iloilo": 4.7,
  "Baguio": 4.2, "CDO": 4.6, "Zamboanga": 4.9, "Batangas": 4.6,
  "Legazpi": 4.4, "Tacloban": 4.5,
};
// Minimum recorded ambient temperature per Philippine location (°C): PAGASA data
// Used for IEC 62548 worst-case string Voc check (Voc increases at low temperature)
const T_MIN_BY_LOCATION: Record<string, number> = {
  "Metro Manila": 18, "Cebu": 20, "Davao": 20, "Iloilo": 20,
  "Baguio": 8,  "CDO": 19, "Zamboanga": 21, "Batangas": 18,
  "Legazpi": 17, "Tacloban": 19,
};

function calcSolarPV(inputs: Record<string, unknown>): Record<string, unknown> {
  const round2 = (v: number) => Math.round(v * 100) / 100;

  const systemType    = String(inputs.system_type   || "Grid-Tied");
  const location      = String(inputs.location      || "Metro Manila");
  const dailyEnergy   = Number(inputs.daily_energy_kwh)  || 50;
  const panelWp       = Number(inputs.panel_wp)          || 450;
  const panelVoc      = Number(inputs.panel_voc)         || 49.5;
  const panelAreaM2   = Number(inputs.panel_area_m2)     || 1.7;
  const deratingPct   = Number(inputs.derating_pct)      || 80;
  const inverterEffPct = Number(inputs.inverter_eff_pct) || 96;
  const autonomyDays  = Number(inputs.autonomy_days)     || 1;
  const dodPct        = Number(inputs.dod_pct)           || 80;
  const battVoltage   = Number(inputs.battery_voltage)   || 48;
  // IEC 62548 Voc temperature derating: Voc increases at low ambient temp
  const tempCoeffVoc  = Number(inputs.temp_coeff_voc     ?? -0.29); // %/°C (negative for monocrystalline)
  const tMinC         = Number(inputs.t_min_c            ?? T_MIN_BY_LOCATION[location] ?? 18);

  // Step 1: Peak Sun Hours
  const psh = PH_PSH[location] ?? Number(inputs.psh_hr) ?? 4.5;

  // Step 2: System efficiency
  const derating    = deratingPct / 100;
  const inverterEff = inverterEffPct / 100;
  const sysEff      = round2(derating * inverterEff);

  // Step 3: Required array power
  const requiredArrayKWp = round2(dailyEnergy / (psh * sysEff));

  // Step 4: Panel count (ceil to next whole panel)
  const panelQty = Math.ceil(requiredArrayKWp * 1000 / panelWp);

  // Step 5: Actual array kWp
  const actualArrayKWp = round2(panelQty * panelWp / 1000);

  // Step 6: String sizing: IEC 62548, 1000 V DC max
  // Voc increases at low ambient temperature; use worst-case cold-temp Voc for safe string limit
  const Voc_max         = round2(panelVoc * (1 + (tempCoeffVoc / 100) * (tMinC - 25)));
  const panelsPerString = Math.floor(1000 / Voc_max);
  const numStrings      = Math.ceil(panelQty / panelsPerString);

  // Step 7: Inverter capacity (1:1 DC/AC ratio, standard)
  const inverterKW = round2(actualArrayKWp);

  // Step 8: Annual energy yield
  const annualYieldKWh = round2(actualArrayKWp * psh * 365 * sysEff);

  // Step 9: Roof area
  const roofAreaM2 = round2(panelQty * panelAreaM2);

  // Step 10: CO2 reduction (Philippine grid emission factor 0.72 kg CO2/kWh)
  const co2ReductionKg = round2(annualYieldKWh * 0.72);

  // Step 11: Battery bank (Off-Grid / Hybrid only)
  const isOffGrid = systemType.includes("Off-Grid") || systemType.includes("Hybrid");
  const batteryKWh = isOffGrid ? round2(dailyEnergy * autonomyDays / (dodPct / 100)) : 0;
  const batteryAh  = isOffGrid ? Math.ceil(batteryKWh * 1000 / battVoltage) : 0;

  return {
    system_type:         systemType,
    location,
    psh_hr:              psh,
    daily_energy_kwh:    dailyEnergy,
    derating_pct:        deratingPct,
    inverter_eff_pct:    inverterEffPct,
    system_efficiency:   sysEff,
    required_array_kwp:  requiredArrayKWp,
    panel_wp:            panelWp,
    panel_qty:           panelQty,
    actual_array_kwp:    actualArrayKWp,
    temp_coeff_voc:      tempCoeffVoc,
    t_min_c:             tMinC,
    voc_max:             Voc_max,
    panels_per_string:   panelsPerString,
    num_strings:         numStrings,
    panel_area_m2:       panelAreaM2,
    total_roof_area_m2:  roofAreaM2,
    inverter_kw:         inverterKW,
    annual_yield_kwh:    annualYieldKWh,
    co2_reduction_kg:    co2ReductionKg,
    battery_kwh:         batteryKWh,
    battery_ah:          batteryAh,
    battery_voltage:     battVoltage,
  };
}

// ─── Electrical: Power Factor Correction: IEEE 18 / IEEE 1036 / PEC Art. 4.60 ─

function calcPFC(inputs: Record<string, unknown>): Record<string, unknown> {
  const round2 = (v: number) => Math.round(v * 100) / 100;
  const round4 = (v: number) => Math.round(v * 10000) / 10000;

  const kw         = Number(inputs.load_kw)      || 100;
  const pfExisting = Number(inputs.pf_existing)  || 0.75;
  const pfTarget   = Number(inputs.pf_target)    || 0.95;
  const voltageV   = Number(inputs.voltage_v)    || 400;
  const phases     = Number(inputs.phases)       || 3;
  const monthlyKwh = Number(inputs.monthly_kwh)  || 0;
  const meralcoRate= Number(inputs.meralco_rate) || 0;

  // Step 1: angles
  const phi1Rad = Math.acos(pfExisting);
  const phi2Rad = Math.acos(pfTarget);
  const phi1Deg = round2((phi1Rad * 180) / Math.PI);
  const phi2Deg = round2((phi2Rad * 180) / Math.PI);
  const tanPhi1 = round4(Math.tan(phi1Rad));
  const tanPhi2 = round4(Math.tan(phi2Rad));

  // Step 2: required kVAR
  const kvarRequired = round2(kw * (tanPhi1 - tanPhi2));

  // Step 3: select standard size
  const stdSizes = [5,10,15,20,25,30,40,50,60,75,100,150,200,300,400,500];
  const selectedKvar = stdSizes.find(s => s >= kvarRequired) ?? Math.ceil(kvarRequired / 50) * 50;

  // Step 4: kVA before and after
  const kvaBefore = round2(kw / pfExisting);
  const kvaAfter  = round2(kw / pfTarget);
  const kvaReduction = round2(kvaBefore - kvaAfter);

  // Step 5: feeder current
  const divisor = phases === 3 ? (Math.sqrt(3) * voltageV) : voltageV;
  const currentBefore    = round2((kvaBefore * 1000) / divisor);
  const currentAfter     = round2((kvaAfter  * 1000) / divisor);
  const currentReduction = round2(currentBefore - currentAfter);
  const currentRedPct    = round2((currentReduction / currentBefore) * 100);

  // Step 6: Meralco PF surcharge (threshold 0.85)
  const meralcoPenalty = pfExisting < 0.85;
  const surchargePct   = meralcoPenalty ? round2((0.85 - pfExisting) / 0.85 * 100) : 0;

  // Optional: monthly savings estimate
  // Meralco PF surcharge applies to the Distribution Charge only (~18% of total rate)
  const MERALCO_DIST_CHARGE_FRACTION = 0.18;
  let monthlySavingsPhp = 0;
  if (meralcoPenalty && monthlyKwh > 0 && meralcoRate > 0) {
    const distChargePerKwh = meralcoRate * MERALCO_DIST_CHARGE_FRACTION;
    const monthlyDistCharge = monthlyKwh * distChargePerKwh;
    monthlySavingsPhp = round2(monthlyDistCharge * (surchargePct / 100));
  }

  return {
    kw,
    pf_existing:          pfExisting,
    pf_target:            pfTarget,
    phi1_deg:             phi1Deg,
    phi2_deg:             phi2Deg,
    tan_phi1:             tanPhi1,
    tan_phi2:             tanPhi2,
    kvar_required:        kvarRequired,
    selected_kvar:        selectedKvar,
    kva_before:           kvaBefore,
    kva_after:            kvaAfter,
    kva_reduction:        kvaReduction,
    current_before:       currentBefore,
    current_after:        currentAfter,
    current_reduction:    currentReduction,
    current_reduction_pct: currentRedPct,
    meralco_penalty:      meralcoPenalty,
    surcharge_pct:        surchargePct,
    monthly_savings_php:  monthlySavingsPhp > 0 ? monthlySavingsPhp : undefined,
  };
}

// ─── Electrical: Cable Tray Sizing: NEMA VE 1 / NEC 392 / PEC 2017 Art. 3.92 ─

function calcCableTray(inputs: Record<string, unknown>): Record<string, unknown> {
  const round2 = (v: number) => Math.round(v * 100) / 100;

  const trayType      = String(inputs.tray_type      || 'Ladder');
  const depthMm       = Number(inputs.depth_mm       || 75);
  const fillRatioPct  = Number(inputs.fill_ratio_pct || 40);
  const spanM         = Number(inputs.span_m         || 1.5);
  const runLengthM    = Number(inputs.run_length_m   || 30);
  const cables        = (inputs.cables as Array<{ cable_type: string; od_mm: number; qty: number; weight_kg_m?: number | null }>) || [];

  // Standard tray widths (NEMA VE 1, mm)
  const stdWidths = [100, 150, 200, 300, 450, 600, 750, 900];

  // NEMA VE 1 load classes: [class label, max kg/m]
  const nemaClasses: Array<[string, number]> = [
    ['8A',  11.9],
    ['12A', 17.9],
    ['16A', 23.8],
    ['20A', 29.8],
    ['24A', 35.7],
    ['32A', 47.6],
  ];

  // Step 1: per-cable fill area and weight
  let totalFillArea = 0;
  let totalWeightKgM = 0;

  for (const cable of cables) {
    const od  = Number(cable.od_mm)  || 0;
    const qty = Number(cable.qty)    || 1;
    // Weight: use provided value, else estimate 0.01 kg/m per mm of OD (rule-of-thumb)
    const wtKgM = (cable.weight_kg_m != null && Number(cable.weight_kg_m) > 0)
      ? Number(cable.weight_kg_m)
      : od * 0.01;

    const areaPerCable = (Math.PI / 4) * od * od;
    totalFillArea  += areaPerCable * qty;
    totalWeightKgM += wtKgM * qty;
  }
  totalFillArea  = round2(totalFillArea);
  totalWeightKgM = round2(totalWeightKgM);

  // Step 2: required tray width
  const fillDecimal  = fillRatioPct / 100;
  const reqWidthRaw  = depthMm > 0 ? totalFillArea / (fillDecimal * depthMm) : 0;
  const reqWidthMm   = round2(reqWidthRaw);
  const selWidthMm   = stdWidths.find(w => w >= reqWidthRaw) ?? 900;

  // Step 3: actual fill %
  const trayArea     = selWidthMm * depthMm;
  const fillActualPct= trayArea > 0 ? round2((totalFillArea / trayArea) * 100) : 0;
  const fillCheck    = fillActualPct <= fillRatioPct ? 'PASS' : 'FAIL';

  // Step 4: load per span and NEMA class
  const loadPerSpan  = round2(totalWeightKgM * spanM);
  let nemaClass = 'Custom (> 32A)';
  for (const [label, maxKgM] of nemaClasses) {
    if (totalWeightKgM <= maxKgM) { nemaClass = label; break; }
  }

  // Step 5: derating factor (NEC 392.80)
  // Ladder / Ventilated Trough: derate if fill > 30%
  // Solid Bottom: derate if fill > 40% of inside tray cross-section (stricter)
  const deratingThreshold = trayType === 'Solid Bottom' ? 40 : 30;
  const deratingFactor    = fillActualPct > deratingThreshold ? 0.80 : 1.0;

  return {
    tray_type:           trayType,
    depth_mm:            depthMm,
    fill_ratio_pct:      fillRatioPct,
    span_m:              spanM,
    run_length_m:        runLengthM,
    total_fill_area_mm2: totalFillArea,
    required_width_mm:   reqWidthMm,
    selected_width_mm:   selWidthMm,
    fill_actual_pct:     fillActualPct,
    fill_check:          fillCheck,
    total_weight_kg_m:   totalWeightKgM,
    load_per_span_kg:    loadPerSpan,
    nema_load_class:     nemaClass,
    derating_factor:     deratingFactor,
    derating_applies:    deratingFactor < 1.0,
  };
}

// ─── Electrical: UPS Sizing: IEC 62040-3 / IEEE 446 / IEEE 1184 / PEC Art. 7 ─

function calcUPS(inputs: Record<string, unknown>): Record<string, unknown> {
  const round2 = (v: number) => Math.round(v * 100) / 100;

  const topology     = String(inputs.topology    || 'Online (Double-Conversion)');
  const phase        = String(inputs.phase       || '3-Phase');
  const backupMin    = Number(inputs.backup_min  || 30);
  const growthFactor = Number(inputs.growth_factor || 1.20);
  const upsEff       = Number(inputs.ups_eff     || 0.96);
  const loads        = (inputs.loads as Array<{ description: string; va_per_unit: number; power_factor: number; qty: number }>) || [];

  // Step 1: Total connected VA and weighted W
  let totalConnectedVA = 0;
  let totalConnectedW  = 0;
  for (const load of loads) {
    const loadVA = Number(load.va_per_unit) * Number(load.qty);
    const loadW  = loadVA * Number(load.power_factor || 0.9);
    totalConnectedVA += loadVA;
    totalConnectedW  += loadW;
  }
  totalConnectedVA = round2(totalConnectedVA);
  totalConnectedW  = round2(totalConnectedW);
  const avgPF = totalConnectedVA > 0 ? round2(totalConnectedW / totalConnectedVA) : 0.90;

  // Step 2: Design VA / kW with growth factor
  const designVA = round2(totalConnectedVA * growthFactor);
  const designKW = round2(totalConnectedW  * growthFactor);

  // Step 3: Select standard UPS kVA (at 80% loading recommendation per IEEE 446)
  const minKVA = designVA / 1000 / 0.8;
  const stdSizes = [1,2,3,5,6,8,10,15,20,25,30,40,50,60,80,100,120,160,200,250,300,400,500];
  const selectedKVA = stdSizes.find(s => s >= minKVA) ?? Math.ceil(minKVA / 50) * 50;
  const loadingPct  = round2((designVA / (selectedKVA * 1000)) * 100);

  // Step 4: Battery DC bus voltage auto-selection
  let batteryV: number;
  let cellsInSeries: number;
  if      (selectedKVA <= 10)  { batteryV = 96;  cellsInSeries = 8;  }
  else if (selectedKVA <= 40)  { batteryV = 192; cellsInSeries = 16; }
  else if (selectedKVA <= 100) { batteryV = 240; cellsInSeries = 20; }
  else                         { batteryV = 480; cellsInSeries = 40; }

  // Step 5: Battery Ah required
  // Ah = (kW_design × t_h) / (V_dc × DOD × η_UPS × η_wire)
  const DOD      = 0.80;
  const wireEff  = 0.98;
  const ahRequired = round2(
    (designKW * (backupMin / 60)) / (batteryV / 1000 * DOD * upsEff * wireEff)
  );

  // Step 6: Select standard Ah
  const stdAh = [7,9,12,17,26,38,40,65,100,150,200,250,300,400,500];
  const selectedAh = stdAh.find(a => a >= ahRequired) ?? Math.ceil(ahRequired / 50) * 50;
  const batteryConfig = `${cellsInSeries} × 12V ${selectedAh}Ah VRLA (sealed lead-acid)`;

  // Step 7: Actual runtime verification
  const actualRuntimeMin = round2(
    (selectedAh * (batteryV / 1000) * DOD * upsEff * wireEff) / designKW * 60
  );

  // Step 8: Input power and current
  const inputVA = round2(designVA / upsEff);
  const inputKW = round2(designKW / upsEff);
  const voltageIn = phase === '3-Phase' ? 415 : 230;
  const inputCurrentA = phase === '3-Phase'
    ? round2(inputVA / (Math.sqrt(3) * voltageIn))
    : round2(inputVA / voltageIn);

  // Step 9: Input breaker at 125% per PEC Art. 7
  const stdBreakers = [16,20,25,32,40,50,63,80,100,125,160,200,250,315,400,500,630,800,1000,1250];
  const inputBreakerA = stdBreakers.find(b => b >= inputCurrentA * 1.25) ?? Math.ceil(inputCurrentA * 1.25 / 100) * 100;

  // Step 10: Output current
  const voltageOut = phase === '3-Phase' ? 415 : 230;
  const outputCurrentA = phase === '3-Phase'
    ? round2(designVA / (Math.sqrt(3) * voltageOut))
    : round2(designVA / voltageOut);

  return {
    topology,
    phase,
    total_connected_va:  totalConnectedVA,
    total_connected_kw:  totalConnectedW,
    avg_pf:              avgPF,
    design_va:           designVA,
    design_kw:           designKW,
    growth_factor:       growthFactor,
    selected_kva:        selectedKVA,
    loading_pct:         loadingPct,
    battery_voltage_v:   batteryV,
    cells_in_series:     cellsInSeries,
    ah_required:         ahRequired,
    selected_ah:         selectedAh,
    battery_config:      batteryConfig,
    actual_runtime_min:  actualRuntimeMin,
    input_va:            inputVA,
    input_kw:            inputKW,
    input_current_a:     inputCurrentA,
    input_breaker_a:     inputBreakerA,
    output_current_a:    outputCurrentA,
  };
}

// ─── Earthing / Grounding System (PEC 2017 Art.2.50 / IEEE 80 / IEC 62305) ───

function calcEarthing(inputs: Record<string, unknown>): Record<string, unknown> {
  const elecType  = String(inputs.electrode_type   || "Rod");
  const soilRho   = Number(inputs.soil_resistivity || 100);   // Ohm·m
  const numElec   = Math.max(1, Math.round(Number(inputs.num_electrodes || 1)));
  const sysType   = String(inputs.system_type      || "Residential / Commercial");

  // Resistance limit per system type
  const R_LIMIT   = sysType === "Substation / HV" ? 1.0
                  : sysType === "Industrial"       ? 5.0
                  :                                  10.0;  // residential/commercial

  let rSingle = 0;
  let platArea = 0;
  let platRadius = 0;

  if (elecType === "Rod") {
    // Dwight (1936): R = (rho / 2*pi*L) * [ln(4L/d) - 1]
    const L = Number(inputs.rod_length_m  || 3.0);
    const d = Number(inputs.rod_dia_mm    || 16) / 1000;  // convert mm to m
    rSingle = (soilRho / (2 * Math.PI * L)) * (Math.log(4 * L / d) - 1);
  } else if (elecType === "Plate") {
    // R = rho / (4 * r),  r = sqrt(A / pi)
    const W = Number(inputs.plate_width_m  || 0.6);
    const H = Number(inputs.plate_height_m || 0.6);
    platArea   = W * H;
    platRadius = Math.sqrt(platArea / Math.PI);
    rSingle    = soilRho / (4 * platRadius);
  } else {
    // Ring/Loop: Sunde (1968): R = (rho / 2*pi^2*D) * [ln(8D/d) - 2]
    const D = Number(inputs.ring_dia_m       || 10);
    const d = Number(inputs.ring_cond_dia_mm || 10) / 1000;  // mm to m
    rSingle = (soilRho / (2 * Math.PI * Math.PI * D)) * (Math.log(8 * D / d) - 2);
  }

  // Parallel electrodes (simplified: adequate spacing assumed)
  const rParallel = rSingle / numElec;
  const effectiveR = numElec > 1 ? rParallel : rSingle;
  const pass = effectiveR <= R_LIMIT;

  // GEC sizing per PEC 2017 Table 2.50.66 (service conductor mm² → GEC mm²)
  const svcCond = Number(inputs.service_cond_mm2 || 35);
  let gecMm2 = 6;
  let gecLabel = "min";
  if (svcCond <= 35)       { gecMm2 = 6;   gecLabel = "min 6 mm2"; }
  else if (svcCond <= 50)  { gecMm2 = 10;  gecLabel = "min 10 mm2"; }
  else if (svcCond <= 95)  { gecMm2 = 16;  gecLabel = "min 16 mm2"; }
  else if (svcCond <= 185) { gecMm2 = 35;  gecLabel = "min 35 mm2"; }
  else if (svcCond <= 300) { gecMm2 = 50;  gecLabel = "min 50 mm2"; }
  else                     { gecMm2 = 70;  gecLabel = "min 70 mm2"; }

  const round3 = (v: number) => Math.round(v * 1000) / 1000;

  return {
    r_single_ohm:  round3(rSingle),
    r_parallel_ohm: round3(rParallel),
    r_limit_ohm:   R_LIMIT,
    pass,
    pass_label:    pass ? "PASS" : "FAIL",
    gec_mm2:       gecMm2,
    gec_label:     gecLabel,
    plate_area_m2:  elecType === "Plate" ? Math.round(platArea * 10000) / 10000 : null,
    plate_radius_m: elecType === "Plate" ? Math.round(platRadius * 10000) / 10000 : null,
  };
}

// ─── HVAC: Duct Sizing: Equal Friction Method (ASHRAE Ch.21 / SMACNA) ────────

function calcDuctSizing(inputs: Record<string, unknown>): Record<string, unknown> {
  const round2 = (v: number) => Math.round(v * 100) / 100;

  const ductShape    = String(inputs.duct_shape    || "Circular");
  const frictionRate = Number(inputs.friction_rate || 1.0);   // Pa/m
  const rho          = Number(inputs.air_density   || 1.20);  // kg/m³
  const aspectRatio  = Number(inputs.aspect_ratio  || 2);     // max W/H for rectangular
  const segments     = (inputs.segments as Array<{
    name: string; flow_lps: number; length_m: number; seg_type: string;
  }>) || [];

  // Dynamic viscosity: 1.81e-5 Pa·s at 20°C (standard); 1.90e-5 Pa·s at 35°C (tropical)
  // Per ASHRAE 2021 Ch.21 / maintenance-expert skill: ρ<1.175 signals tropical selection
  const mu = rho < 1.175 ? 1.90e-5 : 1.81e-5;
  const nu = mu / rho;       // kinematic viscosity m²/s

  // Standard circular duct diameters (mm)
  const CIRC_STD_MM = [100,125,150,175,200,225,250,300,350,400,450,500,550,600,650,700,750,800,900,1000,1100,1200];
  // Standard motor HP sizes
  const STD_HP = [0.5,0.75,1.0,1.5,2.0,3.0,5.0,7.5,10,15,20,25,30,40,50,60,75,100,125,150,200];

  // ASHRAE 62.1 / SMACNA velocity limits (m/s)
  const VEL_LIMITS: Record<string, number> = {
    "Supply Main":   8.0,
    "Supply Branch": 5.0,
    "Return Main":   6.0,
    "Return Branch": 4.0,
  };

  // Equal friction formula (Darcy-Weisbach + Blasius):
  // fr = K × Q^1.75 / D^4.75   where K = 8×0.3164×ρ×(π×ν)^0.25 / (π²×4^0.25)
  const K = 8 * 0.3164 * rho * Math.pow(Math.PI * nu, 0.25) /
            (Math.PI * Math.PI * Math.pow(4, 0.25));

  const segResults = segments.map(seg => {
    const Qm3s = Number(seg.flow_lps) / 1000;
    if (Qm3s <= 0) return null;

    // Theoretical D for circular duct
    const D_calc_m = Math.pow(K * Math.pow(Qm3s, 1.75) / frictionRate, 1 / 4.75);

    let D_h_m: number;   // hydraulic diameter used for Re and ΔP
    let area_m2: number;
    let dim: string;

    if (ductShape === "Circular") {
      const D_calc_mm = D_calc_m * 1000;
      const D_std_mm  = CIRC_STD_MM.find(s => s >= D_calc_mm) ??
                        Math.ceil(D_calc_mm / 50) * 50;
      D_h_m   = D_std_mm / 1000;
      area_m2 = Math.PI * D_h_m * D_h_m / 4;
      dim     = `Ø${D_std_mm} mm`;
    } else {
      // Rectangular: ASHRAE De = 1.30 × (a×b)^0.625 / (a+b)^0.25 = D_calc_m
      // With b = r×a:  De = 1.30 × r^0.625 × a / (1+r)^0.25
      // → a = De × (1+r)^0.25 / (1.30 × r^0.625)
      const r   = aspectRatio;
      const a_m = D_calc_m * Math.pow(1 + r, 0.25) / (1.30 * Math.pow(r, 0.625));
      const b_m = r * a_m;
      // Round up to nearest 50 mm
      const a_mm = Math.ceil(a_m * 1000 / 50) * 50;
      const b_mm = Math.ceil(b_m * 1000 / 50) * 50;
      area_m2 = (a_mm / 1000) * (b_mm / 1000);
      // Hydraulic diameter for pressure drop: D_h = 4A/P = 2ab/(a+b)
      D_h_m   = 2 * (a_mm / 1000) * (b_mm / 1000) / ((a_mm + b_mm) / 1000);
      const wMm = Math.max(a_mm, b_mm);
      const hMm = Math.min(a_mm, b_mm);
      dim = `${wMm} × ${hMm} mm`;
    }

    // Velocity at standard size
    const v = Qm3s / area_m2;

    // Reynolds number
    const Re = v * D_h_m / nu;

    // Friction factor
    let f: number;
    if (Re < 4000) {
      f = 64 / Re;  // laminar (rare in HVAC)
    } else if (Re <= 100000) {
      f = 0.3164 / Math.pow(Re, 0.25);  // Blasius smooth
    } else {
      // Swamee-Jain (smooth approximation, ε = 0.09 mm for galvanized steel)
      const eps = 0.00009;
      const term = eps / (3.7 * D_h_m) + 5.74 / Math.pow(Re, 0.9);
      f = 0.25 / Math.pow(Math.log10(term), 2);
    }

    // Segment pressure drop (Pa)
    const dp_pa = round2(f * rho * v * v * Number(seg.length_m) / (2 * D_h_m));

    // Velocity check
    const velLimit = VEL_LIMITS[seg.seg_type] ?? 6;
    const velCheck = v <= velLimit ? "OK" : v <= velLimit * 1.2 ? "WARNING" : "HIGH";

    return {
      name:         seg.name,
      seg_type:     seg.seg_type,
      flow_lps:     Number(seg.flow_lps),
      length_m:     Number(seg.length_m),
      dim,
      velocity_ms:  round2(v),
      Re:           Math.round(Re),
      f:            Math.round(f * 10000) / 10000,
      dp_pa,
      vel_check:    velCheck,
      vel_limit_ms: velLimit,
    };
  }).filter(Boolean);

  // System totals
  const totalDpPa     = round2(segResults.reduce((s, r) => s + (r?.dp_pa ?? 0), 0));
  const fanStaticPa   = round2(totalDpPa * 1.5);
  const totalLengthM  = round2(segments.reduce((s, seg) => s + Number(seg.length_m), 0));
  const maxFlowLps    = segments.reduce((m, seg) => Math.max(m, Number(seg.flow_lps)), 0);
  const totalFlowM3s  = maxFlowLps / 1000;

  // Fan motor kW = Q × ΔP_fan / (η_fan × η_motor × 1000)
  const fanMotorKw      = round2(totalFlowM3s * fanStaticPa / (0.65 * 0.85 * 1000));
  const fanMotorHpCalc  = round2(fanMotorKw / 0.746);
  const fanMotorHpStd   = STD_HP.find(h => h >= fanMotorHpCalc) ??
                          Math.ceil(fanMotorHpCalc * 10) / 10;

  return {
    segments:            segResults,
    total_dp_pa:         totalDpPa,
    fittings_factor:     1.5,
    fan_static_pa:       fanStaticPa,
    total_length_m:      totalLengthM,
    max_flow_lps:        maxFlowLps,
    fan_motor_kw:        fanMotorKw,
    fan_motor_hp_calc:   fanMotorHpCalc,
    fan_motor_hp_std:    fanMotorHpStd,
    duct_shape:          ductShape,
    friction_rate:       frictionRate,
    air_density:         rho,
    duct_material:       String(inputs.duct_material || "Galvanized Steel"),
  };
}

// ─── Transformer Sizing: IEC 60076-1 / IEEE C57.12.00 / PEC 2017 ────────────

function calcTransformerSizing(inputs: Record<string, unknown>): Record<string, unknown> {
  const r2 = (v: number) => Math.round(v * 100) / 100;
  const loadKva      = Number(inputs.load_kva          || 80);
  const primaryV     = Number(inputs.primary_voltage   || 13800);
  const secondaryV   = Number(inputs.secondary_voltage || 400);
  const phases       = Number(inputs.phases            || 3);
  const impedancePct = Number(inputs.impedance_pct     || 5.0);
  const sparePct     = Number(inputs.spare_capacity_pct|| 25);
  const loadPf       = Number(inputs.load_power_factor || 0.85);
  const numUnits     = Math.max(1, Math.round(Number(inputs.num_units || 1)));
  const winding      = String(inputs.winding_connection|| 'Delta-Star (Dyn11)');

  const STD_KVA = [5,10,15,25,37.5,50,75,100,112.5,150,167,200,225,250,300,333,400,500,750,1000,1500,2000,2500,3000];
  const requiredKva  = loadKva * (1 + sparePct / 100);
  const ratedKva     = STD_KVA.find(s => s >= requiredKva) ?? Math.ceil(requiredKva / 100) * 100;

  const sqrt3 = Math.sqrt(3);
  const I1 = (ratedKva * 1000) / (phases === 3 ? sqrt3 * primaryV   : primaryV);
  const I2 = (ratedKva * 1000) / (phases === 3 ? sqrt3 * secondaryV : secondaryV);
  const Isc = I2 * 100 / impedancePct;

  // IEC 60076-1 typical loss fractions
  const nlFrac = ratedKva <= 100 ? 0.0022 : ratedKva <= 500 ? 0.0018 : 0.0014;
  const llFrac = ratedKva <= 100 ? 0.014  : ratedKva <= 500 ? 0.012  : 0.010;
  const coreLoss = ratedKva * nlFrac;
  const cuLoss   = ratedKva * llFrac;
  const pOut     = ratedKva * loadPf;
  const etaFl    = pOut / (pOut + coreLoss + cuLoss) * 100;
  const eta75    = (pOut * 0.75) / (pOut * 0.75 + coreLoss + cuLoss * 0.5625) * 100;

  const er  = (cuLoss / ratedKva) * 100;
  const ex  = Math.sqrt(Math.max(0, impedancePct ** 2 - er ** 2));
  const sinf = Math.sqrt(Math.max(0, 1 - loadPf * loadPf));
  const VR  = er * loadPf + ex * sinf;

  return {
    load_kva: r2(loadKva), spare_capacity_pct: sparePct,
    required_kva: r2(requiredKva), rated_kva: ratedKva,
    num_units: numUnits, total_installed_kva: ratedKva * numUnits,
    loading_pct: r2(loadKva / ratedKva * 100),
    primary_voltage: primaryV, secondary_voltage: secondaryV,
    phases, winding_connection: winding, cooling_type: 'ONAN',
    I1_full_load_A: r2(I1), I2_full_load_A: r2(I2),
    impedance_pct: impedancePct,
    Isc_secondary_A: r2(Isc), Isc_secondary_kA: r2(Isc / 1000),
    core_loss_kW: r2(coreLoss), copper_loss_kW: r2(cuLoss),
    total_loss_fl_kW: r2(coreLoss + cuLoss),
    total_loss_75pct_kW: r2(coreLoss + cuLoss * 0.5625),
    efficiency_fl_pct: r2(etaFl), efficiency_75pct: r2(eta75),
    voltage_regulation_pct: r2(VR), load_power_factor: loadPf,
  };
}

// ─── Harmonic Distortion: IEEE 519-2022 / IEC 61000-3-2 ─────────────────────

function calcHarmonicDistortion(inputs: Record<string, unknown>): Record<string, unknown> {
  const r2 = (v: number) => Math.round(v * 100) / 100;
  const I1  = Number(inputs.fundamental_current_a   || 100);
  const IL  = Number(inputs.max_demand_current_a    || 0) || I1;
  const Isc = Number(inputs.short_circuit_current_a || 0);
  const harmonics = (inputs.harmonics as Array<{ order: number; current_pct: number }>) || [];

  const iscIl = (Isc > 0 && IL > 0) ? Isc / IL : 20;
  // IEEE 519-2022 Table 2 TDD limits by ISC/IL
  const tddLimit = iscIl < 20 ? 5 : iscIl < 50 ? 8 : iscIl < 100 ? 12 : iscIl < 1000 ? 15 : 20;
  // Individual harmonic scale factor per ISC/IL tier
  const indvScale = iscIl < 20 ? 1.0 : iscIl < 50 ? 2.0 : iscIl < 100 ? 3.0 : iscIl < 1000 ? 3.5 : 5.0;

  let sumSq = 0;
  const harmonicTable = harmonics.map(h => {
    const Ih  = I1 * h.current_pct / 100;
    sumSq += Ih * Ih;
    const basePct = h.order < 11 ? 4.0 : h.order < 17 ? 2.0 : h.order < 23 ? 1.5 : h.order < 35 ? 0.6 : 0.3;
    const limPct  = basePct * indvScale;
    const limA    = IL * limPct / 100;
    return { order: h.order, current_pct: h.current_pct, current_A: r2(Ih), limit_pct_of_IL: r2(limPct), limit_A: r2(limA), pass: Ih <= limA };
  });

  const THD = IL > 0 ? Math.sqrt(sumSq) / I1 * 100 : 0;
  const TDD = IL > 0 ? Math.sqrt(sumSq) / IL * 100 : 0;
  const kFactor = harmonics.reduce((s, h) => s + (h.current_pct / 100) ** 2 * h.order ** 2, 0) + 1;
  const allIndvPass = harmonicTable.every(h => h.pass);

  return {
    fundamental_current_A: I1, max_demand_current_A: IL,
    system_voltage_V: Number(inputs.system_voltage_v || 400),
    isc_il_ratio: Math.round(iscIl * 10) / 10,
    THD_I_pct: r2(THD), TDD_pct: r2(TDD),
    TDD_limit_pct: tddLimit, TDD_pass: TDD <= tddLimit,
    TDD_status: TDD <= tddLimit ? 'PASS' : `FAIL: TDD ${r2(TDD)}% > limit ${tddLimit}%`,
    K_factor: r2(kFactor),
    individual_harmonics: harmonicTable,
    all_individuals_pass: allIndvPass,
    overall_pass: TDD <= tddLimit && allIndvPass,
  };
}

// ─── Clean Agent Suppression: NFPA 2001:2022 / ISO 14520:2015 ────────────────

function calcCleanAgentSuppression(inputs: Record<string, unknown>): Record<string, unknown> {
  const r2 = (v: number) => Math.round(v * 100) / 100;
  const agentKey = String(inputs.agent_type       || 'FK-5-1-12');
  const vol      = Number(inputs.hazard_volume_m3 || 100);
  const tempC    = Number(inputs.temperature_c    || 20);
  const alt      = Number(inputs.altitude_m       || 15);
  const sf       = Number(inputs.safety_factor    || 1.10);
  const nZones   = Math.max(1, Math.round(Number(inputs.num_zones || 1)));

  const AGENTS: Record<string, { s1: number; s2: number; c_design: number; c_min: number; label: string; noael: number; type: string; gwp: number }> = {
    'FK-5-1-12': { s1: 0.0664,  s2: 0.0002738, c_design: 5.0,  c_min: 4.0,  label: 'FK-5-1-12 (Novec 1230)', noael: 10, type: 'halocarbon', gwp: 1 },
    'FM-200':    { s1: 0.1269,  s2: 0.0005007, c_design: 7.0,  c_min: 6.25, label: 'FM-200 / HFC-227ea',     noael: 9,  type: 'halocarbon', gwp: 3220 },
    'Inergen':   { s1: 0.6598,  s2: 0.0024475, c_design: 38.0, c_min: 35.0, label: 'Inergen (IG-541)',       noael: 43, type: 'inert_gas',  gwp: 0 },
    'CO2':       { s1: 0.5541,  s2: 0.002031,  c_design: 34.0, c_min: 30.0, label: 'CO2',                   noael: 5,  type: 'inert_gas',  gwp: 1 },
  };
  const agent    = AGENTS[agentKey] ?? AGENTS['FK-5-1-12'];
  const cDesign  = Number(inputs.design_concentration_pct || 0) || agent.c_design;

  const S        = agent.s1 + agent.s2 * tempC;
  const altFactor= Math.pow(1 - 2.2558e-5 * alt, 5.2559);
  const Vadj     = vol * altFactor;
  const W        = (Vadj / S) * (cDesign / (100 - cDesign));
  const Wdesign  = W * sf;

  const STD_CYL = [16, 32, 50, 80, 100, 150, 200];
  const selCyl  = STD_CYL.find(c => c >= Wdesign) ?? 200;
  const selQty  = Math.ceil(Wdesign / selCyl);
  const safe    = cDesign <= agent.noael;

  return {
    agent_type: agentKey, agent_label: agent.label, agent_class: agent.type, gwp: agent.gwp,
    hazard_volume_m3: vol, altitude_m: alt,
    altitude_correction: Math.round(altFactor * 10000) / 10000,
    adjusted_volume_m3: r2(Vadj), temperature_c: tempC,
    specific_vol_m3_kg: Math.round(S * 1000000) / 1000000,
    design_concentration_pct: cDesign, c_min_pct: agent.c_min,
    W_calculated_kg: r2(W), W_design_kg: r2(Wdesign),
    safety_factor: sf, flooding_factor: 1.0, num_zones: nZones,
    recommended_cylinder_kg: selCyl, recommended_qty: selQty,
    total_agent_kg: selCyl * selQty,
    discharge_time_req: agent.type === 'halocarbon' ? '≤ 10 s' : '≤ 60 s',
    noael_pct: agent.noael, safe_for_occupied_spaces: safe,
    safety_note: safe ? 'Safe for occupied spaces' : `EVACUATE before discharge — ${cDesign}% > NOAEL ${agent.noael}%`,
    cylinder_options: STD_CYL.map(c => ({ cylinder_kg: c, qty: Math.ceil(Wdesign / c), total_kg: c * Math.ceil(Wdesign / c) })),
  };
}

// ─── Expansion Tank Sizing: ASHRAE Acceptance Ratio Method / ASME VIII ──────

// Water specific volume table (ASHRAE/IAPWS, L/kg) at key temperatures (°C)
const WATER_SPEC_VOL: Array<[number, number]> = [
  [0,  1.00013], [4,  1.00000], [10, 1.00030], [20, 1.00177],
  [30, 1.00435], [40, 1.00786], [50, 1.01207], [60, 1.01705],
  [70, 1.02277], [80, 1.02900], [90, 1.03601], [95, 1.03996], [99, 1.04305],
];

function waterSpecVol(tempC: number): number {
  // Linear interpolation between table points; clamp to range
  const t = Math.max(0, Math.min(99, tempC));
  for (let i = 0; i < WATER_SPEC_VOL.length - 1; i++) {
    const [t0, v0] = WATER_SPEC_VOL[i];
    const [t1, v1] = WATER_SPEC_VOL[i + 1];
    if (t >= t0 && t <= t1) {
      return v0 + (v1 - v0) * (t - t0) / (t1 - t0);
    }
  }
  return WATER_SPEC_VOL[WATER_SPEC_VOL.length - 1][1];
}

// Standard bladder/diaphragm expansion tank sizes (L)
const EXP_TANK_SIZES = [8, 12, 18, 24, 35, 50, 60, 80, 100, 150, 200, 300, 400, 500, 750, 1000, 1500, 2000];

function calcExpansionTank(inputs: Record<string, unknown>): Record<string, unknown> {
  const r3 = (v: number) => Math.round(v * 1000) / 1000;
  const r2 = (v: number) => Math.round(v * 100) / 100;

  const systemType    = (inputs.system_type   as string) || 'Chilled Water';
  const volumeMethod  = (inputs.volume_method as string) || 'Direct Entry';
  const systemKw      = Number(inputs.system_kw      ?? 0);
  const fillTempC     = Number(inputs.fill_temp_c    ?? 20);
  const maxTempC      = Number(inputs.max_temp_c     ?? 18);
  const staticHeadM   = Number(inputs.static_head_m  ?? 10);
  const maxPressKpaG  = Number(inputs.max_pressure_kpa_g ?? 400);

  // Determine system volume (L)
  const KW_TO_VOL: Record<string, number> = {
    'Chilled Water':     8,
    'Heating Hot Water': 10,
    'Condenser Water':   6,
  };
  let systemVolumeL = Number(inputs.system_volume_L ?? 0);
  if (volumeMethod === 'Estimate from kW' && systemKw > 0) {
    systemVolumeL = systemKw * (KW_TO_VOL[systemType] ?? 8);
  }

  // ASHRAE expansion factor: always computed between the higher and lower temperature.
  // For HHW/CW: fill is ambient (cold), max is hot operating temp → normal case.
  // For CHW:    fill is ambient (warm, e.g. 20°C), max is CHW supply (cold, e.g. 7°C) →
  //             water CONTRACTS when system starts; we still size for the thermal swing.
  //             Using T_high and T_low ensures E_w is always positive regardless of system type.
  const T_high = Math.max(fillTempC, maxTempC);
  const T_low  = Math.min(fillTempC, maxTempC);
  const vHigh  = waterSpecVol(T_high);   // L/kg at the higher temperature
  const vLow   = waterSpecVol(T_low);    // L/kg at the lower temperature (reference)

  // Net expansion ratio (ASHRAE 2023 Handbook HVAC Systems & Equipment Ch.12)
  const E_w = (vHigh - vLow) / vLow;

  // Net expansion volume (L)
  const V_expansion = systemVolumeL * E_w;

  // Pre-charge pressure (gauge, kPa): cover static head + safety margin
  // Pre-charge = max(30, ceil(9.81 × h / 10) × 10) kPa g (round up to nearest 10)
  const prechargeCalc = (9.81 * staticHeadM * 1000) / 1000; // kPa from head
  const prechargeKpaG = Math.max(30, Math.ceil(prechargeCalc / 10) * 10);

  // Fill pressure = pre-charge + 15 kPa safety margin
  const fillPressureKpaG = prechargeKpaG + 15;

  // Convert pressures to absolute (add 101.3 kPa atm)
  const P_atm        = 101.3;
  const P_fill_abs   = fillPressureKpaG  + P_atm;
  const P_max_abs    = maxPressKpaG      + P_atm;

  // Acceptance factor α (ASHRAE minimum = 0.25)
  const alpha = 1 - P_fill_abs / P_max_abs;
  const alphaCheck = alpha >= 0.25 ? 'PASS' : 'FAIL: increase Pmax or reduce fill pressure';

  // Required tank volume (L): ASME VIII acceptance ratio method
  // V_tank = V_expansion / α
  const requiredVolumeL = alpha > 0 ? V_expansion / alpha : 9999;

  // Select standard tank size
  const selectedTankL = EXP_TANK_SIZES.find(s => s >= requiredVolumeL) ?? EXP_TANK_SIZES[EXP_TANK_SIZES.length - 1];

  // Pressure check: fill pressure must be < max pressure
  const pressureCheck = fillPressureKpaG < maxPressKpaG ? 'PASS' : 'FAIL: fill pressure exceeds max system pressure';

  return {
    system_type:           systemType,
    volume_method:         volumeMethod,
    system_volume_L:       r2(systemVolumeL),
    fill_temp_c:           fillTempC,
    max_temp_c:            maxTempC,
    v_fill:                Math.round(waterSpecVol(fillTempC) * 100000) / 100000,
    v_max:                 Math.round(waterSpecVol(maxTempC)  * 100000) / 100000,
    expansion_ratio:       Math.round(E_w * 100000) / 100000,  // 5dp so report formula multiplies correctly
    V_expansion_L:         r2(V_expansion),
    static_head_m:         staticHeadM,
    precharge_kpa_g:       prechargeKpaG,
    fill_pressure_kpa_g:   fillPressureKpaG,
    max_pressure_kpa_g:    maxPressKpaG,
    acceptance_factor:     r3(alpha),
    acceptance_check:      alphaCheck,
    required_volume_L:     r2(requiredVolumeL),
    selected_tank_L:       selectedTankL,
    pressure_check:        pressureCheck,
  };
}

// ─── FCU Selection: ASHRAE HVAC Systems and Equipment Handbook ───────────────

// Standard FCU capacity tiers (manufacturer-agnostic, kW nominal at 7°C CHW / 27°C DB room)
const FCU_CATALOG = [
  { model: 'FCU-06', kw: 1.76,  tr: 0.50, cmh: 340  },
  { model: 'FCU-09', kw: 2.64,  tr: 0.75, cmh: 510  },
  { model: 'FCU-12', kw: 3.52,  tr: 1.00, cmh: 680  },
  { model: 'FCU-18', kw: 5.28,  tr: 1.50, cmh: 1020 },
  { model: 'FCU-24', kw: 7.03,  tr: 2.00, cmh: 1360 },
  { model: 'FCU-30', kw: 8.79,  tr: 2.50, cmh: 1700 },
  { model: 'FCU-36', kw: 10.55, tr: 3.00, cmh: 2040 },
  { model: 'FCU-42', kw: 12.31, tr: 3.50, cmh: 2380 },
  { model: 'FCU-48', kw: 14.07, tr: 4.00, cmh: 2720 },
  { model: 'FCU-60', kw: 17.58, tr: 5.00, cmh: 3400 },
];

// CHW pipe: Black Steel Schedule 40 nominal pipe sizes (NPS mm, ID mm)
const CHW_PIPES = [
  { nps_mm:  15, id_mm:  15.80 },
  { nps_mm:  20, id_mm:  21.34 },
  { nps_mm:  25, id_mm:  26.64 },
  { nps_mm:  32, id_mm:  35.05 },
  { nps_mm:  40, id_mm:  40.89 },
  { nps_mm:  50, id_mm:  52.50 },
  { nps_mm:  65, id_mm:  62.71 },
  { nps_mm:  80, id_mm:  77.93 },
  { nps_mm: 100, id_mm: 102.26 },
  { nps_mm: 125, id_mm: 128.19 },
  { nps_mm: 150, id_mm: 154.05 },
  { nps_mm: 200, id_mm: 202.72 },
];

function calcFCUSelection(inputs: Record<string, unknown>): Record<string, unknown> {
  const chwSup        = Number(inputs.chw_supply_c  ?? 7);
  const chwRet        = Number(inputs.chw_return_c  ?? 12);
  const divFactor     = Number(inputs.diversity_factor ?? 0.85);
  const dT_chw        = chwRet - chwSup;                       // °C
  const CP_WATER      = 4.187;                                  // kJ/(kg·K)
  const V_TARGET_MS   = 1.5;                                    // m/s CHW main design velocity

  const roomInputs = (inputs.rooms as Array<{room_name:string; area_m2:number; cooling_load_kw:number; qty:number}>) || [];

  let totalRequiredKW = 0;
  let totalConnectedKW = 0;
  let totalConnectedTR = 0;
  let totalUnits = 0;

  const roomResults = roomInputs.map(r => {
    const loadPerUnit = Number(r.cooling_load_kw ?? 0);
    const qty         = Number(r.qty ?? 1);

    // Select smallest FCU tier that meets the per-unit load
    const selected = FCU_CATALOG.find(f => f.kw >= loadPerUnit) ?? FCU_CATALOG[FCU_CATALOG.length - 1];

    const totalRoomKW      = loadPerUnit * qty;
    const selectedTotalKW  = selected.kw  * qty;
    const selectedTotalTR  = selected.tr  * qty;
    const chw_flow_per_unit = dT_chw > 0 ? selected.kw / (CP_WATER * dT_chw) : 0;  // L/s
    const chw_flow_total    = chw_flow_per_unit * qty;

    totalRequiredKW  += totalRoomKW;
    totalConnectedKW += selectedTotalKW;
    totalConnectedTR += selectedTotalTR;
    totalUnits       += qty;

    return {
      room_name:          r.room_name || 'Room',
      area_m2:            r.area_m2 || 0,
      cooling_load_kw:    loadPerUnit,
      qty,
      selected_model:     selected.model,
      selected_kw:        Number(selected.kw.toFixed(2)),
      selected_tr:        Number(selected.tr.toFixed(2)),
      airflow_cmh:        selected.cmh * qty,
      chw_flow_lps_unit:  Number(chw_flow_per_unit.toFixed(3)),
      chw_flow_lps_total: Number(chw_flow_total.toFixed(3)),
    };
  });

  const totalDesignKW  = totalRequiredKW  * divFactor;
  const totalDesignTR  = totalDesignKW / 3.517;
  const totalChwLps    = dT_chw > 0 ? totalDesignKW / (CP_WATER * dT_chw) : 0;

  // CHW main pipe selection (velocity method at V_TARGET_MS)
  const totalChwM3s = totalChwLps / 1000;
  const dReqM       = Math.sqrt(4 * totalChwM3s / (Math.PI * V_TARGET_MS));
  const dReqMm      = dReqM * 1000;
  const selectedPipe = CHW_PIPES.find(p => p.id_mm >= dReqMm) ?? CHW_PIPES[CHW_PIPES.length - 1];
  const actualVelMs  = totalChwM3s > 0
    ? totalChwM3s / (Math.PI * Math.pow(selectedPipe.id_mm / 2000, 2))
    : 0;

  return {
    rooms:              roomResults,
    total_required_kw:  Number(totalRequiredKW.toFixed(2)),
    total_connected_kw: Number(totalConnectedKW.toFixed(2)),
    total_connected_tr: Number(totalConnectedTR.toFixed(2)),
    total_design_kw:    Number(totalDesignKW.toFixed(2)),
    total_design_tr:    Number(totalDesignTR.toFixed(2)),
    total_chw_lps:      Number(totalChwLps.toFixed(3)),
    total_units:        totalUnits,
    chw_supply_c:       chwSup,
    chw_return_c:       chwRet,
    dT_chw_c:           Number(dT_chw.toFixed(1)),
    main_pipe_nps_mm:   selectedPipe.nps_mm,
    main_pipe_id_mm:    selectedPipe.id_mm,
    main_pipe_vel_ms:   Number(actualVelMs.toFixed(2)),
    vel_check:          actualVelMs >= 1.0 && actualVelMs <= 2.0 ? 'OK' : actualVelMs < 1.0 ? 'Low: check stratification' : 'High: upsize pipe',
    diversity_factor:   divFactor,
  };
}

// ─── Refrigerant Pipe Sizing: ASHRAE Velocity Method / ASTM B280 ────────────

// ASTM B280 ACR copper tube standard sizes: OD mm, wall mm, ID mm
const ACR_TUBES = [
  { od_mm:  6.35, wall_mm: 0.813, id_mm:  4.724 },
  { od_mm:  9.52, wall_mm: 0.813, id_mm:  7.894 },
  { od_mm: 12.70, wall_mm: 0.813, id_mm: 11.074 },
  { od_mm: 15.88, wall_mm: 0.889, id_mm: 14.102 },
  { od_mm: 19.05, wall_mm: 0.889, id_mm: 17.272 },
  { od_mm: 22.22, wall_mm: 1.016, id_mm: 20.188 },
  { od_mm: 28.58, wall_mm: 1.016, id_mm: 26.548 },
  { od_mm: 34.93, wall_mm: 1.016, id_mm: 32.898 },
  { od_mm: 41.28, wall_mm: 1.143, id_mm: 38.994 },
  { od_mm: 53.98, wall_mm: 1.270, id_mm: 51.440 },
  { od_mm: 66.68, wall_mm: 1.270, id_mm: 64.140 },
  { od_mm: 79.38, wall_mm: 1.524, id_mm: 76.332 },
];

// Refrigerant properties: pre-computed from ASHRAE/NIST at Philippine operating conditions
// Key: [refrigerant][evap_temp_c] → suction props | [refrigerant][cond_temp_c] → cond props
type EvapProps = { h_fg: number; rho_suc: number; mu_suc: number; dpdt_suc: number; };
type CondProps = { rho_dis: number; rho_liq: number; mu_dis: number; dpdt_dis: number; };

const REFRIG_EVAP: Record<string, Record<string, EvapProps>> = {
  "R-410A": {
    "5":   { h_fg: 197, rho_suc: 27.7, mu_suc: 1.20e-5, dpdt_suc: 44 },
    "-10": { h_fg: 204, rho_suc: 19.5, mu_suc: 1.15e-5, dpdt_suc: 36 },
    "-35": { h_fg: 213, rho_suc:  8.9, mu_suc: 1.08e-5, dpdt_suc: 22 },
  },
  "R-32": {
    "5":   { h_fg: 352, rho_suc: 23.7, mu_suc: 1.20e-5, dpdt_suc: 49 },
    "-10": { h_fg: 364, rho_suc: 17.0, mu_suc: 1.15e-5, dpdt_suc: 39 },
    "-35": { h_fg: 379, rho_suc:  8.0, mu_suc: 1.08e-5, dpdt_suc: 25 },
  },
  "R-22": {
    "5":   { h_fg: 204, rho_suc: 18.0, mu_suc: 1.18e-5, dpdt_suc: 29 },
    "-10": { h_fg: 210, rho_suc: 13.7, mu_suc: 1.13e-5, dpdt_suc: 23 },
    "-35": { h_fg: 217, rho_suc:  5.7, mu_suc: 1.07e-5, dpdt_suc: 12 },
  },
  "R-407C": {
    "5":   { h_fg: 202, rho_suc: 22.5, mu_suc: 1.20e-5, dpdt_suc: 38 },
    "-10": { h_fg: 209, rho_suc: 15.0, mu_suc: 1.14e-5, dpdt_suc: 30 },
    "-35": { h_fg: 218, rho_suc:  7.0, mu_suc: 1.07e-5, dpdt_suc: 18 },
  },
  "R-134a": {
    "5":   { h_fg: 194, rho_suc: 17.0, mu_suc: 1.12e-5, dpdt_suc: 17 },
    "-10": { h_fg: 197, rho_suc:  9.8, mu_suc: 1.07e-5, dpdt_suc: 12 },
    "-35": { h_fg: 200, rho_suc:  3.2, mu_suc: 0.98e-5, dpdt_suc:  5 },
  },
};

const REFRIG_COND: Record<string, Record<number, CondProps>> = {
  "R-410A": {
    40: { rho_dis: 100, rho_liq: 1055, mu_dis: 1.60e-5, dpdt_dis: 65 },
    45: { rho_dis: 117, rho_liq: 1015, mu_dis: 1.65e-5, dpdt_dis: 73 },
    50: { rho_dis: 137, rho_liq:  975, mu_dis: 1.70e-5, dpdt_dis: 82 },
  },
  "R-32": {
    40: { rho_dis: 102, rho_liq:  990, mu_dis: 1.60e-5, dpdt_dis: 70 },
    45: { rho_dis: 121, rho_liq:  950, mu_dis: 1.65e-5, dpdt_dis: 79 },
    50: { rho_dis: 144, rho_liq:  906, mu_dis: 1.70e-5, dpdt_dis: 88 },
  },
  "R-22": {
    40: { rho_dis:  77, rho_liq: 1125, mu_dis: 1.50e-5, dpdt_dis: 44 },
    45: { rho_dis:  90, rho_liq: 1090, mu_dis: 1.55e-5, dpdt_dis: 50 },
    50: { rho_dis: 104, rho_liq: 1052, mu_dis: 1.60e-5, dpdt_dis: 56 },
  },
  "R-407C": {
    40: { rho_dis:  87, rho_liq: 1050, mu_dis: 1.55e-5, dpdt_dis: 55 },
    45: { rho_dis: 103, rho_liq: 1010, mu_dis: 1.60e-5, dpdt_dis: 63 },
    50: { rho_dis: 122, rho_liq:  968, mu_dis: 1.65e-5, dpdt_dis: 71 },
  },
  "R-134a": {
    40: { rho_dis:  57, rho_liq: 1147, mu_dis: 1.30e-5, dpdt_dis: 29 },
    45: { rho_dis:  67, rho_liq: 1113, mu_dis: 1.35e-5, dpdt_dis: 33 },
    50: { rho_dis:  80, rho_liq: 1077, mu_dis: 1.40e-5, dpdt_dis: 38 },
  },
};

// Application → evaporating temperature mapping (Philippine practice)
const APP_EVAP_TEMP: Record<string, number> = {
  "AC":                      5,
  "Air Conditioning":        5,   // form submits this value
  "Low-Temp Refrigeration": -10,
  "Freezer":                -35,
};

// Velocity limits [min, max] m/s by line type
const VEL_LIMITS: Record<string, { min: number; max: number }> = {
  "Suction: Horizontal":      { min: 4,   max: 10  },
  "Suction: Vertical Riser":  { min: 6,   max: 12  },
  "Discharge":                 { min: 5,   max: 15  },
  "Liquid":                    { min: 0.5, max: 1.5  },
};

function calcRefrigPipeSizing(inputs: Record<string, unknown>): Record<string, unknown> {
  const r2  = (v: number) => Math.round(v * 100) / 100;
  const r3  = (v: number) => Math.round(v * 1000) / 1000;

  // Normalize refrigerant name: "R410A" → "R-410A", "R134a" → "R-134a", etc.
  const rawRefrig = String(inputs.refrigerant || "R-410A");
  const refrigerant = rawRefrig.replace(/^R(\d)/i, "R-$1");
  const capacity_kw  = Number(inputs.capacity_kw  || 10);
  const application  = String(inputs.application  || "AC");
  const cond_temp_c  = Number(inputs.cond_temp_c  || 40);
  const lines        = (inputs.lines as Array<{ name: string; line_type: string; equiv_length_m: number }>) || [];

  // Clamp cond_temp to nearest table key
  const condKeys = [40, 45, 50];
  const condKey  = condKeys.reduce((a, b) => Math.abs(b - cond_temp_c) < Math.abs(a - cond_temp_c) ? b : a);
  const evapTemp = APP_EVAP_TEMP[application] ?? 5;
  const evapKey  = [-35, -10, 5].reduce((a, b) => Math.abs(b - evapTemp) < Math.abs(a - evapTemp) ? b : a);

  const evapProps = REFRIG_EVAP[refrigerant]?.[String(evapKey)];
  const condProps = REFRIG_COND[refrigerant]?.[condKey];

  if (!evapProps || !condProps) {
    return { error: `Property data not available for ${refrigerant} at evap ${evapKey}°C / cond ${condKey}°C` };
  }

  const h_fg     = evapProps.h_fg;       // kJ/kg
  const mass_flow = capacity_kw / h_fg;  // kg/s  (ṁ = Q_kW / h_fg)
  const eps_m    = 1.5e-9;               // copper roughness (m): essentially smooth

  const lineResults = lines.map(line => {
    const lineType   = line.line_type || "Suction: Horizontal";
    const lengthM    = Number(line.equiv_length_m) || 1;

    // Select density, viscosity, and dpdt based on line type
    let rho: number, mu: number, dpdt_kpa_k: number;
    if (lineType === "Discharge") {
      rho        = condProps.rho_dis;
      mu         = condProps.mu_dis;
      dpdt_kpa_k = condProps.dpdt_dis;
    } else if (lineType === "Liquid") {
      rho        = condProps.rho_liq;
      mu         = condProps.mu_dis;  // liquid viscosity approx
      dpdt_kpa_k = condProps.dpdt_dis;
    } else {
      // Suction (Horizontal or Vertical Riser)
      rho        = evapProps.rho_suc;
      mu         = evapProps.mu_suc;
      dpdt_kpa_k = evapProps.dpdt_suc;
    }

    const nu = mu / rho;  // kinematic viscosity (m²/s)
    const qv = mass_flow / rho; // volume flow (m³/s)

    const limits = VEL_LIMITS[lineType] || { min: 1, max: 10 };

    // Select smallest ASTM B280 tube where velocity is within limits
    let selected = ACR_TUBES[ACR_TUBES.length - 1]; // fallback to largest
    for (const tube of ACR_TUBES) {
      const id_m = tube.id_mm / 1000;
      const area = Math.PI * (id_m / 2) ** 2;
      const v    = qv / area;
      if (v >= limits.min && v <= limits.max) {
        selected = tube;
        break;
      }
    }

    const id_m    = selected.id_mm / 1000;
    const area    = Math.PI * (id_m / 2) ** 2;
    const velocity = qv / area;

    // Darcy-Weisbach friction factor
    const re = velocity * id_m / nu;
    let f: number;
    if (re < 2300) {
      f = 64 / re; // laminar
    } else if (re < 100000) {
      f = 0.3164 / Math.pow(re, 0.25); // Blasius
    } else {
      // Swamee-Jain (copper: near smooth, eps/D ≈ 0)
      const log_arg = eps_m / (3.7 * id_m) + 5.74 / Math.pow(re, 0.9);
      f = 0.25 / Math.pow(Math.log10(log_arg), 2);
    }

    const dp_pa_m   = f * rho * velocity ** 2 / (2 * id_m);   // Pa/m
    const dp_total  = dp_pa_m * lengthM;                        // Pa total
    const delta_t_k = dp_total / (dpdt_kpa_k * 1000);          // K equiv

    // Velocity check
    let vel_check: string;
    if (velocity > limits.max) {
      vel_check = "HIGH";
    } else if (velocity < limits.min) {
      vel_check = lineType.includes("Vertical") ? "LOW (oil return risk)" : "LOW";
    } else {
      vel_check = "OK";
    }

    return {
      name:            line.name,
      line_type:       lineType,
      equiv_length_m:  r2(lengthM),
      selected_od_mm:  r2(selected.od_mm),
      selected_id_mm:  r2(selected.id_mm),
      velocity_ms:     r2(velocity),
      vel_check,
      re:              Math.round(re),
      f:               r3(f),
      dp_pa_m:         r2(dp_pa_m),
      dp_total_pa:     Math.round(dp_total),
      delta_t_k:       r3(delta_t_k),
      rho_used:        r2(rho),
    };
  });

  const anyWarn = lineResults.some(l => l.vel_check !== "OK");

  return {
    refrigerant,
    capacity_kw:    r2(capacity_kw),
    application,
    evap_temp_c:    evapKey,
    cond_temp_c:    condKey,
    h_fg_kj_kg:     r2(h_fg),
    mass_flow_kgs:  r3(mass_flow),
    lines:          lineResults,
    any_velocity_warning: anyWarn,
  };
}

// ─────────────────────────────────────────────────────────────────────────────

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

    // ─── Python API proxy (Phase 0+) ─────────────────────────────────────────
    // Try the Python microservice first. If it handles the calc_type it returns
    // { results: {...} }. If not yet implemented it returns { not_implemented: true }
    // and we fall through to the TypeScript handlers below. Network errors or
    // timeouts also fall through silently: zero user-facing disruption.
    const PYTHON_API_URL = Deno.env.get("PYTHON_API_URL");
    if (PYTHON_API_URL) {
      try {
        const pyRes = await fetch(`${PYTHON_API_URL}/calculate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ calc_type, inputs }),
          signal: AbortSignal.timeout(60000), // 60s: covers Render free-tier cold-start (~50s)
        });
        if (pyRes.ok) {
          const pyData = await pyRes.json();
          if (!pyData.not_implemented && pyData.results) {
            // Python handled it: run Groq narrative (stays in Deno) and return
            const narrative = await generateReportNarrative(calc_type, inputs, pyData.results);
            return new Response(
              JSON.stringify({ results: pyData.results, narrative, source: "python" }),
              { headers: { ...corsHeaders, "Content-Type": "application/json" } }
            );
          }
          // not_implemented: true: fall through to TypeScript handlers below
        }
      } catch (_pyErr) {
        // Network error, timeout, or cold-start: fall through silently
        console.warn("Python API unavailable, falling back to TypeScript:", String(_pyErr));
      }
    }
    // ─────────────────────────────────────────────────────────────────────────

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
    } else if (calc_type === "Lighting Design") {
      results = calcLightingDesign(inputs);
    } else if (calc_type === "Short Circuit") {
      results = calcShortCircuit(inputs);
    } else if (calc_type === "Chiller System — Water Cooled") {
      results = calcChillerWaterCooled(inputs);
    } else if (calc_type === "Chiller System — Air Cooled") {
      results = calcChillerAirCooled(inputs);
    } else if (calc_type === "AHU Sizing") {
      results = calcAHUSizing(inputs);
    } else if (calc_type === "Cooling Tower Sizing") {
      results = calcCoolingTowerSizing(inputs);
    } else if (calc_type === "Water Softener Sizing") {
      results = calcWaterSoftenerSizing(inputs);
    } else if (calc_type === "Water Treatment System") {
      results = calcWaterTreatmentSystem(inputs);
    } else if (calc_type === "Wastewater Treatment (STP)") {
      results = calcWastewaterSTP(inputs);
    } else if (calc_type === "Roof Drain Sizing") {
      results = calcRoofDrainSizing(inputs);
    } else if (calc_type === "Storm Drain / Stormwater") {
      results = calcStormDrain(inputs);
    } else if (calc_type === "Grease Trap Sizing") {
      results = calcGreaseTrapSizing(inputs);
    } else if (calc_type === "Boiler System") {
      results = calcBoiler(inputs);
    } else if (calc_type === "Generator Sizing") {
      results = calcGeneratorSizing(inputs);
    } else if (calc_type === "Solar PV System") {
      results = calcSolarPV(inputs);
    } else if (calc_type === "Power Factor Correction") {
      results = calcPFC(inputs);
    } else if (calc_type === "Cable Tray Sizing") {
      results = calcCableTray(inputs);
    } else if (calc_type === "Lightning Protection System (LPS)") {
      results = calcLightningProtection(inputs);
    } else if (calc_type === "UPS Sizing") {
      results = calcUPS(inputs);
    } else if (calc_type === "Earthing / Grounding System") {
      results = calcEarthing(inputs);
    } else if (calc_type === "Duct Sizing (Equal Friction)") {
      results = calcDuctSizing(inputs);
    } else if (calc_type === "Refrigerant Pipe Sizing") {
      results = calcRefrigPipeSizing(inputs);
    } else if (calc_type === "FCU Selection") {
      results = calcFCUSelection(inputs);
    } else if (calc_type === "Expansion Tank Sizing") {
      results = calcExpansionTank(inputs);
    } else if (calc_type === "Transformer Sizing") {
      results = calcTransformerSizing(inputs);
    } else if (calc_type === "Harmonic Distortion") {
      results = calcHarmonicDistortion(inputs);
    } else if (calc_type === "Clean Agent Suppression") {
      results = calcCleanAgentSuppression(inputs);
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
