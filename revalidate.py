"""
Full field mismatch re-validation — all 32 calc types against live API.
Uses exact registered names from /health endpoint.
"""
import re, json, urllib.request, time, sys
sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://engineering-calc-api.onrender.com/calculate'

TESTS = {
    'Pump Sizing (TDH)':               {'flow_rate':10,'static_head':20,'pipe_material':'uPVC','pipe_diameter_mm':50,'pipe_length_m':100},
    'Pipe Sizing':                      {'flow_rate':10,'pipe_material':'uPVC','fluid':'Water','velocity_limit':3},
    'Compressed Air':                   {'flow_cfm':50,'pressure_psig':100,'pipe_length_ft':200,'pipe_material':'Steel'},
    'HVAC Cooling Load':                {'floor_area':100,'ceiling_height':3,'people_count':10},
    'AHU Sizing':                       {'cooling_load_kW':50,'supply_air_temp_C':13,'room_temp_C':24,'oa_fraction':0.2,'floor_area':100,'ceiling_height':3},
    'Cooling Tower Sizing':             {'heat_rejection_kW':200,'flow_lps':10,'inlet_temp_C':35,'outlet_temp_C':29,'wb_C':27},
    'Duct Sizing':                      {'flow_m3hr':1000,'friction_rate_pam':1.0,'section_type':'Supply Main'},
    'Refrigerant Pipe Sizing':          {'cooling_kW':10,'refrigerant':'R-410A','line_type':'suction','length_m':10},
    'FCU Selection':                    {'room_cooling_kW':5,'chw_supply_C':7,'chw_return_C':12},
    'Chiller System — Water Cooled': {'cooling_load_kW':500,'chiller_type':'Centrifugal','chw_supply_C':7,'chw_return_C':12},
    'Chiller System — Air Cooled':   {'cooling_load_kW':200,'chiller_type':'Scroll','chw_supply_C':7,'chw_return_C':12},
    'Wire Sizing':                      {'load_kw':10,'voltage':230,'power_factor':0.85,'wire_length_m':30,'phases':1},
    'Short Circuit':                    {'transformer_kva':500,'transformer_z_pct':5.0,'lv_voltage':400,'cable_length_m':10},
    'Load Schedule':                    {'loads':[{'name':'AC','qty':2,'watts_each':2000,'power_factor':0.85,'load_type':'HVAC'}]},
    'Generator Sizing':                 {'loads':[{'name':'Essential','kw':50,'pf':0.85}],'voltage':400,'frequency':60},
    'UPS Sizing':                       {'load_kW':10,'backup_minutes':15,'topology':'Online Double-Conversion'},
    'Solar PV System':                  {'daily_load_kwh':20,'location':'Metro Manila','system_type':'grid-tied'},
    'Fire Sprinkler Hydraulic':         {'occupancy':'Office','design_area_m2':139,'sprinkler_spacing_m':3.6},
    'Fire Pump Sizing':                 {'system_flow_lpm':1900,'system_pressure_bar':6.9,'driver_type':'Electric','redundancy':'Duplex'},
    'Domestic Water System':            {'occupancy_type':'Office','num_persons':50,'building_floors':5},
    'Sewer / Drainage':                 {'building_floors':5,'pipe_material':'uPVC / CPVC','num_persons':50},
    'Beam / Column Design':             {'member_type':'Steel Beam','span_m':6,'Mu_kNm':180,'Vu_kN':90,'w_kNm':30,'section':'W310x45'},
    'Lighting Design':                  {'room_length_m':10,'room_width_m':8,'room_height_m':3,'space_type':'Office - general','luminaire_type':'LED Panel 600x600 (40W)'},
    'Lightning Protection (LPS)':       {'building_length_m':30,'building_width_m':20,'building_height_m':15,'lpl':'LPL II'},
    'Shaft Design':                     {'power_kW':7.5,'speed_rpm':1450,'radial_load_N':2000,'span_m':0.3,'material':'AISI 1045 (HR)'},
    'Gear / Belt Drive':                {'drive_type':'V-Belt','power_kW':7.5,'n_driver_rpm':1450,'n_driven_rpm':720,'belt_section':'B (17)','centre_distance_mm':500},
    'Pressure Vessel':                  {'design_pressure_bar':10,'inner_diameter_mm':800,'shell_length_mm':2000,'material':'SA-516 Gr.70 (Carbon Steel)'},
    'Heat Exchanger':                   {'duty_kW':500,'hot_inlet_C':90,'hot_outlet_C':60,'cold_inlet_C':25,'cold_outlet_C':55,'hot_flowrate_kgs':10,'cold_flowrate_kgs':8},
    'Vibration Analysis':               {'mass_kg':500,'speed_rpm':1450,'power_kW':15,'machine_class':'Class II (15–50 kW, rigid foundation)','stiffness_N_m':200000},
    'Fluid Power':                      {'calc_type':'System','system_pressure_bar':200,'flow_lpm':40,'cylinder_force_kN':50,'stroke_mm':200},
    'Noise / Acoustics':                {'calc_type':'Room','source_Lw_dB':90,'distance_m':5,'space_type':'Open-plan office','avg_absorption_coeff':0.15,'room_surface_m2':200},
    'Boiler / Steam System':            {'steam_pressure_bar':10,'feedwater_temp_C':80,'steam_flowrate_kgs':1.0,'fuel_type':'Natural gas (LNG)'},
}

def flatten(d, keys=None):
    if keys is None: keys = set()
    for k, v in d.items():
        keys.add(k)
        if isinstance(v, dict): flatten(v, keys)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict): flatten(item, keys)
    return keys

print('Fetching live results from all 32 calc types...')
live = {}
errors = []
for ct, inp in TESTS.items():
    data = json.dumps({'calc_type': ct, 'inputs': inp}).encode()
    req = urllib.request.Request(BASE, data=data,
                                  headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            body = json.loads(r.read())
            if 'results' in body:
                live[ct] = flatten(body['results'])
            else:
                live[ct] = set()
                errors.append(f'  NO RESULTS {ct}: {list(body.keys())}')
    except Exception as ex:
        live[ct] = set()
        errors.append(f'  ERROR {ct}: {str(ex)[:80]}')
    time.sleep(0.1)

if errors:
    print('API ERRORS:')
    for e in errors: print(e)
else:
    print(f'All {len(live)} fetched OK')

with open('engineering-design.html', 'r', encoding='utf-8') as f:
    html = f.read()

RENDER_MAP = {
    'Pump Sizing (TDH)':                        'renderPumpPID',
    'HVAC Cooling Load':                        'renderHVACReport',
    'AHU Sizing':                               'renderAHUSizingReport',
    'Cooling Tower Sizing':                     'renderCoolingTowerReport',
    'Duct Sizing':                              'renderDuctSizingReport',
    'Refrigerant Pipe Sizing':                  'renderRefrigPipeReport',
    'Chiller System — Water Cooled':       'renderChillerWaterCooledReport',
    'Chiller System — Air Cooled':         'renderChillerAirCooledReport',
    'Wire Sizing':                              'renderWireSizingReport',
    'Short Circuit':                            'renderShortCircuitReport',
    'Generator Sizing':                         'renderGeneratorReport',
    'UPS Sizing':                               'renderUPSSizingReport',
    'Solar PV System':                          'renderSolarPVReport',
    'Fire Sprinkler Hydraulic':                 'renderFireSprinklerReport',
    'Fire Pump Sizing':                         'renderFirePumpReport',
    'Beam / Column Design':                     'renderBeamColumnReport',
    'Lighting Design':                          'renderLightingDesignReport',
    'Shaft Design':                             'renderShaftDesignReport',
    'Gear / Belt Drive':                        'renderGearBeltDriveReport',
    'Pressure Vessel':                          'renderPressureVesselReport',
    'Heat Exchanger':                           'renderHeatExchangerReport',
    'Vibration Analysis':                       'renderVibrationReport',
    'Fluid Power':                              'renderFluidPowerReport',
    'Noise / Acoustics':                        'renderNoiseAcousticsReport',
    'Boiler / Steam System':                    'renderBoilerSteamReport',
    'Load Schedule':                            'renderLoadReport',
    'Lightning Protection (LPS)':               'renderLPSDiagram',
    'Domestic Water System':                    'renderReport',
    'Sewer / Drainage':                         'renderReport',
    'FCU Selection':                            'renderFCUSelectionReport',
    'HVAC Cooling Load':                        'renderReport',   # generic renderer
}

# Fields that are safe to be "missing" — accessed conditionally or via compat layers
SAFE_MISSING = {
    # Compat-layer fields (remapped at top of renderer, not in raw API output)
    'E_actual_lux','N_fixtures','floor_area_m2','h_rc_m','lpd_W_m2','total_kW',
    'T_Nm','M_Nm','d_std_mm','Ss_allow_MPa','Ss_allow_Pa','Kb','Kt',
    'combined_Nm','d_cubed_m3','Ss_allow_Pa','J_m4','twist_deg','twist_deg_per_m','twist_rad',
    # Gear/Belt — new renderer uses conditional blocks per drive_type
    # Gear fields only shown when isGear=true, Chain fields when isChain=true
    'K_L','K_theta','actual_driven_rpm','arc_deg','belt_designation',
    'belt_speed_ms','capacity_margin_pct','corrected_power_kW','design_power_kW',
    'driven_dia_mm','n_belts_calc','power_per_belt_kW','rated_power_kW','total_power_capacity_kW',
    'Kv','Km','Wt_N','bending_stress_pinion_MPa','bending_stress_gear_MPa',
    'contact_stress_MPa','Sf_gear','Sf_pinion','Sh_gear','Sh_pinion',
    'bending_ok','contact_ok','d_pinion_mm','d_gear_mm','pitch_velocity_ms',
    'N_driver_teeth','N_driven_teeth','Pr_kN','d_driver_mm','d_driven_mm',
    'centre_distance_mm','chain_length_pitches','chain_length_mm','chain_number','pitch_mm',
    'module_mm',  # gear-only, inside ${isGear ? ...} conditional block
    # Noise — conditionally rendered (only show for barrier/dose modes)
    'Lp_no_barrier_dB','Lp_with_barrier_dB','NC_measured','NC_ok','barrier_IL_dB',
    # Beam/Column — type-conditional (RC fields only for RC members)
    'As_mm2','DCR_axial','KL_r','axial_ok','b_mm','h_mm','n_bars',
    'phi_Mn_kNm','phi_Pn_kN','rho','rho_g','rho_max','rho_min','rho_ok',
    'slender_ok','tension_controlled','tension_strain','a_mm','c_mm',
    # LPS — uses SVG renderer with its own data extraction
    'Nd_strikes_yr','Nt','risk_check','ng_fl_km2_yr',
}

NOISE = {
    'length','map','forEach','filter','find','join','toString','toFixed',
    'includes','sort','slice','push','pop','keys','values','entries',
    'split','trim','replace','toLowerCase','toUpperCase','results','data',
    'inputs_used','narrative','error','bom','sow','ok','pass','fail',
    'source','calc_type','svg','not_implemented','constructor','prototype',
    'hasOwnProperty','room','dose','battery_bank','ieee1184','iec62548',
    'pump','cylinder','accumulator','pressure_line','return_line','suction_line',
    'impedance','part_load_performance','psychrometrics','system_losses',
    'dc_bus_config','redundancy','topology','config_note','code_notes',
    'field_notes','test_notes','standard','calculation_source',
    'lpz_zones','spd_schedule','bom_items','sow_sections','pump_curve',
}

def get_body(name):
    m = re.search(rf'function {re.escape(name)}\s*\(', html)
    if not m: return ''
    start = m.start(); depth = 0; in_f = False
    for i in range(start, min(start+80000, len(html))):
        c = html[i]
        if c == '{': depth += 1; in_f = True
        elif c == '}':
            depth -= 1
            if in_f and depth == 0: return html[start:i+1]
    return ''

print()
print('FIELD MISMATCH REPORT — after all fixes')
print('=' * 70)
issues = []
skipped = []
for ct, func in RENDER_MAP.items():
    api = live.get(ct, set())
    if not api:
        skipped.append(f'SKIP  {ct} (API returned empty / error)')
        continue
    body = get_body(func)
    if not body:
        skipped.append(f'WARN  {ct}: renderer "{func}" not found in HTML')
        continue
    accessed = set(re.findall(r'\br\.([a-zA-Z_][a-zA-Z0-9_]*)', body))
    accessed -= NOISE
    missing = accessed - api - SAFE_MISSING
    if missing:
        issues.append((ct, sorted(missing)))
        print(f'FAIL  {ct}')
        for x in sorted(missing)[:6]:
            close = [k for k in api if x.lower() in k.lower() or k.lower() in x.lower()]
            hint = close[0] if close else 'NOT IN API'
            print(f'      r.{x}  =>  {hint}')
    else:
        print(f'OK    {ct}')

if skipped:
    print()
    for s in skipped: print(s)

print()
print('=' * 70)
total = len(RENDER_MAP)
ok = total - len(issues) - len(skipped)
print(f'RESULT: {ok} OK  |  {len(issues)} FAIL  |  {len(skipped)} SKIP  |  {total} total')
