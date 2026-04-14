// WorkHive Skill Matrix — Training Modules + Exam Questions
// All content is static — no DB queries needed for lesson/exam data.
// Structure: SKILL_CONTENT[discipline][level] = { title, module (HTML string), exam (array of 10) }

const DISCIPLINES = ['Mechanical', 'Electrical', 'Instrumentation', 'Facilities Management', 'Production Lines'];

const DISCIPLINE_COLORS = {
  'Mechanical':            '#F7A21B',
  'Electrical':            '#FFD700',
  'Instrumentation':       '#29B6D9',
  'Facilities Management': '#A78BFA',
  'Production Lines':      '#4ade80',
};

const DISCIPLINE_ICONS = {
  'Mechanical':            'M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z',
  'Electrical':            'M13 10V3L4 14h7v7l9-11h-7z',
  'Instrumentation':       'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
  'Facilities Management': 'M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4',
  'Production Lines':      'M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z',
};

const LEVEL_LABELS = {
  1: 'Safety Awareness',
  2: 'Supervised Practice',
  3: 'Independent Technician',
  4: 'Senior / Specialist',
  5: 'Engineer / Strategist',
};

const SKILL_CONTENT = {

  // ─────────────────────────────────────────────────────────────────────────────
  // MECHANICAL
  // ─────────────────────────────────────────────────────────────────────────────
  'Mechanical': {
    1: {
      title: 'Safety, Tools, and Workplace Awareness',
      module: `
<h3>Lockout/Tagout (LOTO)</h3>
<p>Before any maintenance work on a machine, the energy source must be isolated and locked. LOTO prevents accidental machine start-up while a technician is working on it. Steps: identify all energy sources, isolate each one, apply a personal lock and tag, verify zero energy state before starting work.</p>
<h3>Personal Protective Equipment (PPE)</h3>
<p>Always wear the correct PPE for the task. For mechanical work this includes: safety shoes, hard hat, safety glasses, gloves (cut-resistant for hand work, leather for heat), and hearing protection in high-noise areas. PPE is not optional — it is your last line of defense.</p>
<h3>Basic Hand and Power Tools</h3>
<p>Know how to identify and correctly use: open-end and ring spanners, socket sets, screwdrivers (flat, Phillips, Torx), adjustable wrench, hammer and chisel, angle grinder, and electric drill. Always use the right tool for the job. Using the wrong tool damages equipment and injures the worker.</p>
<h3>Permit-to-Work (PTW)</h3>
<p>A Permit-to-Work is a written authorization to perform hazardous work. It is mandatory before starting work on electrical systems, pressure vessels, confined spaces, and elevated structures. Never start work on a PTW-required task without a signed permit.</p>
<h3>Housekeeping and 5S</h3>
<p>Sort, Set in order, Shine, Standardize, Sustain. A clean and organized workplace prevents slips, trips, and lost tools. Always clean up your work area after a job.</p>`,
      exam: [
        { q: 'What is the main purpose of Lockout/Tagout (LOTO)?', options: ['To tag equipment for maintenance scheduling', 'To prevent accidental machine start-up while working on it', 'To label which tools belong to which technician', 'To record the time a machine was shut down'], answer: 1 },
        { q: 'Which PPE is most important when working near rotating equipment?', options: ['Ear plugs only', 'Safety glasses only', 'Safety glasses, gloves, and no loose clothing', 'Hard hat and vest only'], answer: 2 },
        { q: 'Before using a power tool, you should always:', options: ['Check that it is the newest model', 'Inspect it for damage and verify it is in safe working condition', 'Ask a supervisor for permission', 'Lubricate all moving parts'], answer: 1 },
        { q: 'A Permit-to-Work is required for which type of task?', options: ['Changing a light bulb in the office', 'Lubricating a chain drive', 'Working inside a confined space', 'Cleaning a workbench'], answer: 2 },
        { q: 'What does the "S" in 5S stand for (in order)?', options: ['Safety, Standardize, Shine, Sort, Sustain', 'Sort, Set in order, Shine, Standardize, Sustain', 'Sweep, Sort, Stack, Store, Sustain', 'Set, Shine, Sort, Safety, Sustain'], answer: 1 },
        { q: 'After a LOTO lock is applied, the next step before starting work is to:', options: ['Inform the supervisor', 'Start the machine briefly to confirm it is off', 'Verify zero energy state (press start button, release stored pressure, etc.)', 'Sign the logbook'], answer: 2 },
        { q: 'Cut-resistant gloves are most appropriate when:', options: ['Working with hot surfaces', 'Handling sharp metal edges, sheet metal, or cutting tools', 'Operating electrical panels', 'Painting surfaces'], answer: 1 },
        { q: 'What is the correct action if you find a hand tool with a cracked handle?', options: ['Continue using it carefully', 'Wrap it with tape and continue', 'Remove it from service and report it', 'Use it only for light tasks'], answer: 2 },
        { q: 'Housekeeping (5S) in the maintenance area primarily helps to:', options: ['Reduce the number of workers needed', 'Prevent accidents and reduce time lost looking for tools', 'Increase machine speed', 'Reduce preventive maintenance intervals'], answer: 1 },
        { q: 'Who is responsible for personal safety in the workplace?', options: ['Only the Safety Officer', 'Only the Supervisor', 'Every individual worker', 'Only management'], answer: 2 },
      ]
    },
    2: {
      title: 'Basic Preventive Maintenance Tasks',
      module: `
<h3>Lubrication Fundamentals</h3>
<p>Lubrication reduces friction and wear between moving parts. The two main types are grease and oil. Grease is used for sealed bearings and slow-speed joints. Oil is used for gearboxes, circulating systems, and high-speed bearings. Always use the lubricant type and quantity specified on the equipment nameplate or lubrication schedule. Over-greasing is as harmful as under-greasing — excess grease overheats bearings.</p>
<h3>Belt and Chain Inspection</h3>
<p>V-belts and flat belts must be checked for: correct tension (deflection method), cracking, fraying, or glazing. A loose belt slips and overheats. A too-tight belt overloads bearings. Chains must be checked for elongation (stretch), corrosion, and lubrication. Replace when wear exceeds 3% elongation.</p>
<h3>Fastener Torque</h3>
<p>Bolts must be tightened to the specified torque. Under-torqued bolts loosen from vibration. Over-torqued bolts strip threads or fatigue the fastener. Use a calibrated torque wrench. Tighten bolts in a star or cross pattern for even clamping force.</p>
<h3>Filter Replacement</h3>
<p>Oil filters, air filters, and hydraulic filters must be replaced on schedule. A clogged filter causes pressure drop, contamination bypass, and equipment damage. Record the filter type, date replaced, and equipment ID in the logbook.</p>
<h3>Visual Inspection Routine</h3>
<p>During PM rounds, inspect for: leaks (oil, grease, water), unusual noise, abnormal heat (use back of hand near but not touching), loose guards, and abnormal vibration. Any anomaly must be reported and logged immediately.</p>`,
      exam: [
        { q: 'What is the result of over-greasing a bearing?', options: ['Better lubrication and longer life', 'Overheating and premature failure', 'No effect — more grease is always better', 'Reduced friction and noise'], answer: 1 },
        { q: 'How do you check V-belt tension?', options: ['Pull the belt until it breaks', 'Measure belt deflection at mid-span against specification', 'Listen for squealing during startup', 'Check if the belt feels warm after 1 hour of operation'], answer: 1 },
        { q: 'A chain should be replaced when elongation exceeds:', options: ['1%', '2%', '3%', '5%'], answer: 2 },
        { q: 'Bolts should be tightened in what pattern to ensure even clamping?', options: ['Clockwise from the top', 'Random order', 'Star or cross pattern', 'Left to right in sequence'], answer: 2 },
        { q: 'What happens when a hydraulic filter becomes clogged?', options: ['The system runs faster', 'Contamination bypasses the filter and damages components', 'The pump automatically compensates', 'The filter self-cleans'], answer: 1 },
        { q: 'During a visual PM inspection, you notice a small oil puddle under a gearbox. You should:', options: ['Wipe it up and ignore it', 'Add more oil to the gearbox', 'Log it, identify the source, and report to the supervisor', 'Apply a sealant immediately'], answer: 2 },
        { q: 'Which lubricant type is most appropriate for a sealed bearing in a slow-speed conveyor roller?', options: ['Light machine oil', 'Grease', 'Hydraulic fluid', 'Gear oil'], answer: 1 },
        { q: 'The torque specification for a bolt is found in:', options: ['The company safety manual', 'The equipment maintenance manual or engineering drawing', 'The purchase order for the bolt', 'The DOLE regulations'], answer: 1 },
        { q: 'What does belt "glazing" indicate?', options: ['The belt is new and properly installed', 'The belt has hardened from slipping and heat — replace it', 'The belt is correctly tensioned', 'The belt is over-tensioned'], answer: 1 },
        { q: 'During a PM round, you detect an unusual burning smell near a motor. The first action is:', options: ['Continue PM and report at end of shift', 'Stop the equipment and investigate immediately', 'Add oil to the motor', 'Increase ventilation in the area'], answer: 1 },
      ]
    },
    3: {
      title: 'Fault Diagnosis and Corrective Repair',
      module: `
<h3>Vibration and Noise Diagnosis</h3>
<p>Unusual vibration is one of the earliest indicators of mechanical failure. Common causes: imbalance (single dominant frequency at 1x RPM), misalignment (high vibration at 1x and 2x RPM, often with axial component), bearing wear (high-frequency random vibration, often heard as a rumbling), and looseness (multiple harmonics). Use a vibration meter or simply place your hand on the bearing housing to feel the trend.</p>
<h3>Bearing Failure Modes</h3>
<p>Bearings fail from: contamination (abrasive wear), insufficient lubrication (pitting, spalling), overloading (fatigue), misalignment (edge loading), and false brinelling (fretting from vibration at rest). A failed bearing produces noise, heat, and vibration. Replace using the correct fit (interference for rotating races), and use a bearing puller and press — never strike a bearing directly.</p>
<h3>Shaft Alignment</h3>
<p>Misaligned shafts cause premature bearing, seal, and coupling failure, and increase vibration and power consumption. Two types: angular (shafts at an angle) and parallel (shafts offset). Check with dial indicators or laser alignment tools. Acceptable residual misalignment is typically less than 0.05mm for flexible couplings at normal speeds.</p>
<h3>Seal and Gasket Replacement</h3>
<p>Mechanical seals and lip seals prevent fluid leakage. Replace when there is visible leakage. Before fitting a new seal: clean the shaft and housing, check for shaft scoring (rough shaft surface cuts the seal lip), lightly oil the seal lip, and press in squarely. Never reuse a seal that has been removed.</p>`,
      exam: [
        { q: 'High vibration at 1x and 2x RPM with a strong axial component most likely indicates:', options: ['Imbalance', 'Misalignment', 'Bearing wear', 'Looseness'], answer: 1 },
        { q: 'A bearing makes a rumbling noise and the housing is unusually hot. The most likely cause is:', options: ['Over-lubrication', 'Insufficient lubrication or bearing damage', 'Correct operation — this is normal', 'Belt tension is too high'], answer: 1 },
        { q: 'When installing a new bearing, you should:', options: ['Strike it with a hammer directly on the race', 'Use a bearing press or puller — never strike directly', 'Heat it to 200°C in an open flame', 'Freeze it for 30 minutes first'], answer: 1 },
        { q: 'What is the accepted maximum residual misalignment for most flexible couplings?', options: ['0.5mm', '1.0mm', '0.05mm', '2.0mm'], answer: 2 },
        { q: 'Before fitting a new lip seal, you should:', options: ['Dry-fit the seal without any lubrication', 'Check for shaft scoring and lightly oil the seal lip', 'File the shaft to fit the seal', 'Heat the seal with a torch'], answer: 1 },
        { q: 'Vibration at multiple harmonics (1x, 2x, 3x RPM and higher) is most characteristic of:', options: ['Bearing failure', 'Imbalance', 'Mechanical looseness', 'Misalignment'], answer: 2 },
        { q: 'False brinelling on a bearing is caused by:', options: ['Over-lubrication', 'Vibration while the bearing is at rest', 'Running at too high a speed', 'Incorrect lubricant type'], answer: 1 },
        { q: 'Angular misalignment means:', options: ['The two shafts are parallel but offset', 'The two shafts are at an angle to each other', 'One shaft is spinning faster than the other', 'The coupling is worn'], answer: 1 },
        { q: 'A scoring on the shaft where a seal runs will:', options: ['Have no effect on the new seal', 'Quickly cut through the new seal lip, causing immediate leakage', 'Improve the seal grip', 'Reduce friction'], answer: 1 },
        { q: 'Bearing contamination typically causes:', options: ['Fatigue spalling at the contact zone', 'Abrasive wear visible as scratches and pitting on races', 'Edge loading on one side of the bearing', 'Excessive heat only, no visible damage'], answer: 1 },
      ]
    },
    4: {
      title: 'Precision Alignment and Condition Monitoring',
      module: `
<h3>Laser Shaft Alignment</h3>
<p>Laser alignment tools provide faster and more accurate results than dial indicators. The system measures both angular and parallel misalignment simultaneously. Shim corrections are calculated by the tool software. Always check for soft foot (one machine foot not making full contact) before alignment — soft foot causes the frame to distort when bolts are tightened, making precise alignment impossible.</p>
<h3>Vibration Analysis Basics</h3>
<p>A vibration spectrum (FFT) shows vibration amplitude vs. frequency. Each fault has a characteristic frequency signature: 1x = imbalance or misalignment, 2x = misalignment, ball pass frequencies = bearing defects, gear mesh frequency = gear wear. Trending over time is more valuable than a single reading — a gradual rise in bearing frequency amplitude predicts failure weeks in advance.</p>
<h3>Ultrasonic Testing for Lubrication</h3>
<p>Ultrasonic detectors listen for the high-frequency friction sound of under-lubricated bearings. Add grease slowly while monitoring the sound level — stop when the sound level drops to its lowest point. This prevents both under and over-lubrication and extends bearing life significantly.</p>
<h3>FMEA for Mechanical Equipment</h3>
<p>Failure Mode and Effects Analysis identifies what can fail (failure mode), what effect it has on the process (effect), and how to detect it early (detection method). For a centrifugal pump example: failure mode = impeller wear, effect = reduced flow rate, detection = flow monitoring + vibration trending.</p>`,
      exam: [
        { q: 'Soft foot in a machine must be corrected before alignment because:', options: ['It makes the laser readings inaccurate', 'Tightening bolts on a soft foot distorts the frame, undoing alignment corrections', 'The machine will vibrate more after alignment', 'It is required by safety regulations only'], answer: 1 },
        { q: 'In a vibration spectrum, the Ball Pass Frequency Outer (BPFO) is associated with:', options: ['Imbalance', 'Gear mesh', 'Outer race defect in a rolling element bearing', 'Misalignment'], answer: 2 },
        { q: 'When using an ultrasonic detector to lubricate a bearing, you should stop adding grease when:', options: ['The grease purges from the seal', 'The ultrasonic sound level drops to its lowest reading', 'The bearing housing reaches 60°C', 'You have added the specified volume from the schedule'], answer: 1 },
        { q: 'What is more valuable for predictive maintenance — a single vibration reading or a trend over time?', options: ['A single reading — it gives the current state', 'A trend over time — gradual amplitude rise predicts failure weeks ahead', 'Both are equally valuable', 'Neither — vibration analysis is unreliable'], answer: 1 },
        { q: 'In FMEA, the "Detection" column records:', options: ['What failed', 'The effect of the failure on production', 'How the failure can be detected early', 'Who is responsible for the repair'], answer: 2 },
        { q: 'Gear mesh frequency in a vibration spectrum is calculated as:', options: ['RPM only', 'Number of gear teeth × RPM', 'RPM × 60', 'Bearing inner race frequency'], answer: 1 },
        { q: 'A laser alignment tool shows a large parallel offset but very small angular error. The correction required is primarily:', options: ['Shims only under the stationary machine', 'Moving the movable machine laterally (horizontally or vertically) at the feet', 'Adjusting the coupling only', 'Replacing the bearing'], answer: 1 },
        { q: 'Trending bearing vibration data over 6 months allows you to:', options: ['Know the exact date the bearing will fail', 'Plan bearing replacement before failure occurs based on the rate of amplitude increase', 'Eliminate the need for lubrication', 'Confirm the bearing brand is correct'], answer: 1 },
        { q: 'Which condition monitoring technique is best for detecting early-stage bearing defects?', options: ['Temperature monitoring alone', 'Vibration analysis (high-frequency envelope analysis)', 'Visual inspection', 'Oil level check'], answer: 1 },
        { q: 'FMEA is best described as:', options: ['A method to repair failures faster', 'A proactive analysis to identify potential failure modes and plan detection/mitigation strategies', 'A report written after a failure occurs', 'A replacement for the maintenance schedule'], answer: 1 },
      ]
    },
    5: {
      title: 'Reliability Strategy and OEE Improvement',
      module: `
<h3>Reliability-Centered Maintenance (RCM)</h3>
<p>RCM asks: what does this asset do, what are the consequences if it fails, and what is the most cost-effective way to prevent or detect each failure mode? The output is a maintenance strategy tailored to each failure mode — not a blanket PM schedule. High-consequence failures get predictive monitoring; low-consequence failures with cheap replacement get run-to-failure.</p>
<h3>OEE (Overall Equipment Effectiveness)</h3>
<p>OEE = Availability × Performance × Quality. Availability = actual run time / planned run time. Performance = actual output rate / ideal output rate. Quality = good units / total units produced. World-class OEE is 85%. Low OEE caused by maintenance issues is typically in Availability (unplanned downtime) and Performance (speed losses from equipment degradation).</p>
<h3>MTBF and MTTR as Maintenance KPIs</h3>
<p>MTBF (Mean Time Between Failures) measures reliability — higher is better. MTTR (Mean Time to Repair) measures maintainability — lower is better. Track both per asset over time. A declining MTBF signals a worsening reliability problem. A rising MTTR signals spare parts issues, skill gaps, or poor diagnostic tools.</p>
<h3>Maintenance Budget Optimization</h3>
<p>The goal is not to minimize maintenance cost — it is to minimize total cost of ownership (maintenance cost + failure cost + lost production cost). Over-maintaining wastes money; under-maintaining causes failures. RCM analysis tells you exactly where to invest to get the highest reliability return per peso spent.</p>`,
      exam: [
        { q: 'RCM (Reliability-Centered Maintenance) is best described as:', options: ['Scheduling all PM at the same interval for simplicity', 'Tailoring the maintenance strategy to each failure mode based on consequences', 'Running all assets to failure to minimize maintenance cost', 'A method to reduce the maintenance team size'], answer: 1 },
        { q: 'OEE of 72% with 100% Quality and 90% Performance means Availability is approximately:', options: ['72%', '80%', '90%', '62%'], answer: 1 },
        { q: 'A rising MTTR over 6 months most likely indicates:', options: ['Equipment is becoming more reliable', 'Spare parts issues, skill gaps, or poor diagnostic capability', 'Maintenance is being done too frequently', 'OEE is improving'], answer: 1 },
        { q: 'For a non-critical asset with cheap replacement cost and no safety consequence on failure, the best strategy is often:', options: ['Full predictive monitoring', 'Intensive PM every week', 'Run-to-failure (RTF)', 'Immediate replacement before any sign of wear'], answer: 2 },
        { q: 'Total cost of ownership in maintenance includes:', options: ['Maintenance cost only', 'Maintenance cost + failure cost + lost production cost', 'Spare parts cost only', 'Labor cost only'], answer: 1 },
        { q: 'A declining MTBF for a critical pump over 12 months signals:', options: ['The pump is running better', 'A worsening reliability trend requiring investigation', 'Normal aging — no action needed', 'Maintenance is being performed too often'], answer: 1 },
        { q: 'In RCM, a failure mode with high safety consequence should be addressed by:', options: ['Run-to-failure', 'Lower PM frequency', 'Predictive monitoring or condition-based maintenance', 'Increasing the lubrication interval'], answer: 2 },
        { q: 'The "Performance" component of OEE is reduced when:', options: ['A machine produces defective products', 'A machine runs slower than its ideal rated speed due to wear or degradation', 'A machine is shut down for scheduled maintenance', 'A machine is idle waiting for material'], answer: 1 },
        { q: 'Which metric directly measures how fast your team can restore an asset after failure?', options: ['MTBF', 'OEE', 'MTTR', 'Availability'], answer: 2 },
        { q: 'The 80/20 maintenance planning rule (80% planned, 20% reactive) means:', options: ['80% of equipment should be on PM', 'The majority of work orders should be planned in advance, not reactive emergency repairs', 'Spend 80% of the budget on spare parts', '80% of failures are caused by 20% of assets'], answer: 1 },
      ]
    },
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // ELECTRICAL
  // ─────────────────────────────────────────────────────────────────────────────
  'Electrical': {
    1: {
      title: 'Electrical Safety and Basic Concepts',
      module: `
<h3>Electrical Hazards</h3>
<p>Electricity can kill. The human body can feel current as low as 1mA and cardiac fibrillation can occur at 100mA. Voltage does not kill — current does. However, higher voltage drives more current through body resistance. In industrial plants, 240V, 415V (3-phase), and higher voltages are common. Never assume a circuit is dead without testing it.</p>
<h3>Electrical LOTO</h3>
<p>Electrical LOTO requires: open the circuit breaker or disconnect switch, apply your personal lock, test for absence of voltage using an approved voltmeter (test the meter on a known live source first, then test the de-energized circuit, then test on the live source again — this confirms the meter worked throughout). This is called "Test Before Touch."</p>
<h3>Multimeter Basics</h3>
<p>A digital multimeter (DMM) measures: voltage (AC and DC), current, and resistance. Always set to the correct range before connecting. For voltage: connect leads before turning on the circuit. For current: the meter must be in series with the circuit. Never measure current in parallel — this will blow the meter fuse or damage the meter.</p>
<h3>Basic Electrical Terms</h3>
<p>Voltage (V) = electrical pressure. Current (A) = flow of electrons. Resistance (Ω) = opposition to flow. Power (W) = V × A. Ohm's Law: V = I × R. A 415V 3-phase motor drawing 10A per phase consumes approximately 7.2kW (415 × 10 × √3 × power factor ≈ 0.85).</p>`,
      exam: [
        { q: 'Which level of current through the human body can cause cardiac fibrillation?', options: ['1 mA', '10 mA', '100 mA', '1000 mA'], answer: 2 },
        { q: 'The correct sequence for "Test Before Touch" during electrical LOTO is:', options: ['Lock out → test → verify meter works → proceed', 'Test live source → test de-energized circuit → test live source again', 'Open breaker → proceed immediately', 'Test with a lamp tester only'], answer: 1 },
        { q: 'To measure current with a multimeter, the meter must be connected:', options: ['In parallel with the load', 'In series with the load', 'Across the voltage source', 'Between neutral and earth'], answer: 1 },
        { q: 'Ohm\'s Law states:', options: ['P = V × A', 'V = I × R', 'R = V × I', 'I = V × A'], answer: 1 },
        { q: 'A circuit reads 0V on a voltmeter. You can now safely touch the conductor because:', options: ['True — 0V means no current', 'False — verify the meter worked on a known live source before trusting the 0V reading', 'True — but only if the breaker is open', 'False — always call an electrician'], answer: 1 },
        { q: 'A 3-phase 415V motor drawing 15A per phase consumes approximately how much power (assuming PF = 0.85)?', options: ['6.2 kW', '9.1 kW', '12.5 kW', '18 kW'], answer: 1 },
        { q: 'The purpose of the neutral conductor in a single-phase system is to:', options: ['Carry fault current only', 'Complete the circuit and carry the return current', 'Provide an earth path for safety', 'Balance the three phases'], answer: 1 },
        { q: 'What does high resistance in a cable connection typically cause?', options: ['Reduced voltage and heat at the connection point', 'Higher current flow', 'Lower temperature', 'No effect on operation'], answer: 0 },
        { q: 'Which PPE is mandatory when working on or near live LV electrical panels?', options: ['Hard hat and safety shoes only', 'Insulated gloves rated for the working voltage plus face shield', 'Chemical gloves and goggles', 'Standard work gloves'], answer: 1 },
        { q: 'A blown fuse in a motor starter should be replaced with:', options: ['The next larger size available', 'The same rating as specified on the panel schedule', 'Any available fuse of similar physical size', 'A wire link temporarily'], answer: 1 },
      ]
    },
    2: {
      title: 'Motor PM and Panel Inspection',
      module: `
<h3>Motor Preventive Maintenance</h3>
<p>Electric motors require: cleaning (remove dust from cooling fins and windings), insulation resistance testing (megger test), terminal tightness check, bearing lubrication, and vibration check. A motor running hot will have reduced insulation life — every 10°C above rated temperature halves insulation life (Arrhenius Rule).</p>
<h3>Megger (Insulation Resistance) Test</h3>
<p>Measures the resistance of winding insulation to earth. Apply 500V DC test voltage for LV motors. A new motor should read >1000 MΩ. A reading below 1 MΩ indicates deteriorated insulation — do not run the motor until serviced. A polarization index (PI = 10-minute reading / 1-minute reading) of >2.0 indicates healthy insulation.</p>
<h3>Panel Inspection Checklist</h3>
<p>During electrical panel PM: check for signs of overheating (discoloration, burning smell, melted insulation), torque all terminal connections (loose connections cause heat and arcing), clean interior with dry cloth or compressed air, inspect contactors and relays for pitting or burning, verify breaker handles are free to operate, and check labeling is legible.</p>
<h3>Overload Relay Setting</h3>
<p>The overload relay protects the motor from sustained overcurrent. Set the trip current to 100–110% of the motor Full Load Amperage (FLA) from the nameplate. If the motor trips repeatedly but is not overloaded, check for: single phasing, low voltage, high ambient temperature, or blocked ventilation.</p>`,
      exam: [
        { q: 'The Arrhenius Rule for motor insulation states:', options: ['Every 10°C rise in temperature doubles insulation life', 'Every 10°C rise above rated temperature halves insulation life', 'Temperature has no effect on insulation life', 'Every 20°C rise triples insulation failure rate'], answer: 1 },
        { q: 'For a standard LV motor, the megger test voltage is:', options: ['110V DC', '250V DC', '500V DC', '1000V DC'], answer: 2 },
        { q: 'A megger reading of 0.8 MΩ on a 415V motor indicates:', options: ['Excellent insulation condition', 'Acceptable — no action needed', 'Deteriorated insulation — do not run until serviced', 'Normal aging — run and monitor'], answer: 2 },
        { q: 'A Polarization Index (PI) of 1.5 indicates:', options: ['Excellent insulation', 'Questionable insulation — possible moisture or contamination', 'The motor is overloaded', 'The motor is misaligned'], answer: 1 },
        { q: 'During a panel inspection, terminal discoloration and a burning smell indicates:', options: ['Normal operation under full load', 'A loose or corroded connection causing heat and arcing', 'The panel is working efficiently', 'The ambient temperature is too high'], answer: 1 },
        { q: 'The overload relay trip current should be set at:', options: ['50% of motor FLA', '80% of motor FLA', '100–110% of motor FLA', '150% of motor FLA'], answer: 2 },
        { q: 'A motor trips the overload relay repeatedly but is not mechanically overloaded. The most likely cause is:', options: ['Correct overload relay setting', 'Single phasing (one phase lost)', 'The motor is new and needs run-in', 'The motor bearings are too large'], answer: 1 },
        { q: 'When cleaning inside a panel, which cleaning method is correct?', options: ['Wet cloth — removes dust and grease effectively', 'Dry cloth or compressed air — never use liquids near live conductors', 'Water spray', 'Solvent spray'], answer: 1 },
        { q: 'The purpose of torquing terminal connections during PM is to:', options: ['Reduce the current capacity', 'Prevent loose connections that cause heat, arcing, and eventual failure', 'Increase resistance at the terminal', 'Make disassembly easier later'], answer: 1 },
        { q: 'Motor nameplate Full Load Amperage (FLA) is used to:', options: ['Determine the motor frame size', 'Set the overload relay correctly', 'Calculate the insulation resistance required', 'Determine the correct fuse size only'], answer: 1 },
      ]
    },
    3: {
      title: 'Fault Diagnosis, VFDs, and PLC Basics',
      module: `
<h3>Electrical Fault Diagnosis</h3>
<p>Systematic fault-finding: (1) Define the fault — what exactly is not working? (2) Check power supply — is voltage present at the load? (3) Check control circuit — is the control signal present? (4) Check the load — is the motor, solenoid, or device receiving power but not operating? Use the half-split method to narrow down the fault location quickly.</p>
<h3>Variable Frequency Drives (VFDs)</h3>
<p>A VFD controls motor speed by varying the frequency and voltage supplied. Common VFD fault codes: OC (over-current — check for short circuit or ground fault), OV (over-voltage — check line voltage or deceleration ramp), OT (over-temperature — check cooling fan and ambient), GF (ground fault — check motor insulation). Always check the VFD fault history log before replacing any component.</p>
<h3>Contactor and Relay Diagnosis</h3>
<p>A contactor is a heavy-duty switch controlled by a coil. If a contactor does not close: check coil voltage (should be rated coil voltage ±10%), check for mechanical obstruction, check for burned contacts. Burned or pitted main contacts cause voltage drop and heat — replace contact tips or the full contactor depending on severity.</p>
<h3>PLC Input/Output Basics</h3>
<p>A PLC (Programmable Logic Controller) reads digital and analog inputs (sensors, switches) and controls digital and analog outputs (motors, valves, indicators). When a machine does not respond to a command, check: (1) Is the PLC input receiving the signal (check I/O indicator light)? (2) Is the PLC output energized (check output indicator)? (3) Is the output wired correctly to the field device?</p>`,
      exam: [
        { q: 'The half-split method in electrical fault-finding means:', options: ['Replace half the components at a time', 'Test at the midpoint of the circuit to determine which half contains the fault', 'Check the first and last components only', 'Use two technicians to check from both ends'], answer: 1 },
        { q: 'A VFD displays fault code "OC" (Over-Current). The most likely cause is:', options: ['Input voltage too high', 'Cooling fan failure', 'Short circuit in motor winding or earth fault in motor cable', 'Incorrect frequency setting'], answer: 2 },
        { q: 'A contactor coil draws 24VDC. You measure 12VDC at the coil terminals. The contactor:', options: ['Will operate normally', 'Will not close reliably — voltage is outside ±10% tolerance', 'Will close but may chatter', 'Will immediately burn out'], answer: 1 },
        { q: 'Burned and pitted main contacts on a contactor indicate:', options: ['Normal wear — continue using', 'Repeated arcing from frequent switching or sustained overcurrent — replace contacts', 'The coil voltage is too high', 'The contactor is oversized'], answer: 1 },
        { q: 'When checking a PLC fault, the first step is:', options: ['Replace the PLC module', 'Check if the input indicator light is ON (sensor signal present)', 'Rewrite the PLC program', 'Power cycle the entire control panel'], answer: 1 },
        { q: 'A VFD fault code "GF" (Ground Fault) most likely indicates:', options: ['The motor speed setting is wrong', 'Motor insulation has broken down — current path to earth exists', 'The DC bus capacitor has failed', 'The input fuse has blown'], answer: 1 },
        { q: 'In systematic fault diagnosis, after confirming voltage is present at the motor terminals but the motor does not run, the next check is:', options: ['Replace the motor immediately', 'Check the motor mechanically — is it seized or overloaded?', 'Check the supply fuse', 'Check the contactor coil'], answer: 1 },
        { q: 'A PLC analog input reads 2mA instead of the expected 4–20mA range minimum of 4mA. This most likely indicates:', options: ['Signal is at minimum process value', 'Open circuit in the transmitter loop (4-20mA loop powered transmitters output minimum 4mA)', 'The PLC analog module is faulty', 'The process value is normal'], answer: 1 },
        { q: 'What is the purpose of checking the VFD fault history log before replacing components?', options: ['It is required by safety regulations', 'It reveals patterns — recurring same fault points to root cause, not just the symptom', 'It resets the fault counter', 'To satisfy the maintenance schedule requirement'], answer: 1 },
        { q: 'A machine starts then immediately trips the overload. The motor megger test is good. The most likely cause is:', options: ['Motor insulation failure', 'VFD frequency set too low', 'Mechanical overload — jammed, seized, or over-tensioned load', 'Control power fuse blown'], answer: 2 },
      ]
    },
    4: {
      title: 'Protection Relays and Motor Control',
      module: `
<h3>Motor Protection Relay Functions</h3>
<p>Modern motor protection relays provide: thermal overload protection (models the motor heating), short-circuit protection, earth fault detection, phase imbalance and loss detection, undercurrent protection (detects loss of load — e.g., broken pump coupling), and thermistor input (direct motor winding temperature monitoring). Setting parameters must match the motor nameplate.</p>
<h3>Earthing and Bonding</h3>
<p>Earthing provides a safe path for fault current to flow to earth, causing the protective device (fuse or breaker) to operate and disconnect the fault. Without a proper earth, fault current flows through a person touching the faulty equipment. All metal enclosures, conduit, and equipment frames must be bonded to earth. Earth resistance should typically be less than 1Ω for industrial plants.</p>
<h3>Power Factor and Correction</h3>
<p>Power factor (PF) is the ratio of active power (kW) to apparent power (kVA). A low PF (below 0.85) increases the current drawn from the supply, causing higher line losses and capacity charges from the utility. Capacitor banks correct PF by supplying reactive current locally. Motors are the primary cause of low PF in industrial plants.</p>
<h3>Motor Starter Types</h3>
<p>Direct-On-Line (DOL): full voltage at start — highest starting torque, highest inrush current (6-8x FLA). Star-Delta: reduces starting current to 33% of DOL, but also reduces starting torque. Soft Starter: controlled voltage ramp, reduces mechanical stress. VFD: full speed and torque control throughout operation — best for variable load applications.</p>`,
      exam: [
        { q: 'A motor protection relay detects undercurrent. This most likely indicates:', options: ['Motor is overloaded', 'Loss of load — e.g., broken pump coupling or empty pipe', 'Correct operating condition', 'Phase loss'], answer: 1 },
        { q: 'Earth resistance for industrial equipment should typically be:', options: ['Less than 1 Ω', 'Between 5–10 Ω', 'Less than 100 Ω', 'Resistance does not matter'], answer: 0 },
        { q: 'Low power factor (0.7) in a plant primarily results in:', options: ['Higher voltage at the motor', 'Higher current from the supply — increasing line losses and utility charges', 'Lower motor speed', 'Reduced insulation life only'], answer: 1 },
        { q: 'Star-Delta starting reduces starting current to what percentage of DOL inrush?', options: ['50%', '33%', '70%', '10%'], answer: 1 },
        { q: 'A VFD is the best motor starter choice when:', options: ['The motor only needs to run at full speed', 'The load requires variable speed control throughout operation', 'Starting torque must be maximized', 'The motor is small and rarely used'], answer: 1 },
        { q: 'A phase imbalance of 5% in motor supply voltage causes approximately what percentage increase in motor heating?', options: ['5%', '25%', '50%', '100%'], answer: 2 },
        { q: 'The primary purpose of bonding metal enclosures to earth is:', options: ['To provide a neutral return path', 'To ensure fault current flows through the protection device, not through a person', 'To improve power factor', 'To reduce motor noise'], answer: 1 },
        { q: 'A thermistor embedded in motor windings is used to:', options: ['Measure motor speed', 'Directly monitor winding temperature and trip the motor before thermal damage occurs', 'Measure insulation resistance', 'Control the cooling fan speed'], answer: 1 },
        { q: 'DOL starting is most appropriate for:', options: ['Large motors where high inrush current could cause supply voltage dip', 'Small motors where starting current does not affect the supply', 'All motors on a VFD supply', 'Motors requiring very slow startup'], answer: 1 },
        { q: 'A capacitor bank installed near a motor primarily improves:', options: ['Motor speed stability', 'Power factor by supplying reactive current locally', 'Motor insulation life', 'Earth fault protection'], answer: 1 },
      ]
    },
    5: {
      title: 'Power Systems, Arc Flash, and Energy Efficiency',
      module: `
<h3>Industrial Power Distribution</h3>
<p>A typical Philippine industrial plant receives 69kV or 34.5kV from the grid, steps down to 6.6kV or 3.3kV for major motors and plant distribution, then to 415V (3-phase) for most equipment and 230V single-phase for lighting and small loads. Understanding the single-line diagram (SLD) is essential for safe switching operations and fault isolation.</p>
<h3>Arc Flash Hazard</h3>
<p>An arc flash is an explosive release of energy from an electrical fault — producing intense heat (up to 20,000°C), pressure wave, and molten metal. Arc flash PPE is rated in cal/cm² — always use PPE rated higher than the incident energy calculated for the specific panel. Never work on energized equipment above 50V without arc flash assessment. The safest approach: de-energize before working.</p>
<h3>Energy Efficiency in Electrical Systems</h3>
<p>Key energy saving opportunities: replace aging motors with IE3 (Premium Efficiency) motors, install VFDs on pumps and fans running at partial load (affinity laws: reducing speed by 20% reduces power by ~50%), correct power factor to 0.95+, fix compressed air leaks, and improve power factor. Energy metering at panel level identifies the highest consumers.</p>
<h3>Transformer Maintenance</h3>
<p>Oil-filled transformers require: oil sampling (dielectric strength test, dissolved gas analysis — DGA detects developing faults from gas type), Buchholz relay testing, temperature indicator calibration, and cooling fan maintenance. DGA is the most powerful predictive tool — different gases indicate different fault types (hydrogen = corona, acetylene = arcing, methane = hot spots).</p>`,
      exam: [
        { q: 'In a Philippine industrial plant, 415V 3-phase supply is typically used for:', options: ['High voltage transmission only', 'Most industrial equipment, motors, and distribution boards', 'Lighting only', 'Control panels only'], answer: 1 },
        { q: 'Arc flash PPE selection is based on:', options: ['The voltage level only', 'The incident energy calculated for that specific panel (cal/cm²)', 'Company preference', 'The age of the equipment'], answer: 1 },
        { q: 'According to the affinity laws, reducing pump speed by 20% reduces power consumption by approximately:', options: ['20%', '40%', '50%', '80%'], answer: 2 },
        { q: 'In dissolved gas analysis (DGA) of transformer oil, acetylene indicates:', options: ['Moisture contamination', 'Arcing inside the transformer', 'Normal aging', 'Overloaded cooling system'], answer: 1 },
        { q: 'An IE3 motor designation means:', options: ['The motor uses 3-phase supply', 'The motor meets Premium Efficiency standards', 'The motor has 3 poles', 'The motor is inverter-rated'], answer: 1 },
        { q: 'A Buchholz relay on an oil transformer activates on:', options: ['Overcurrent at the secondary', 'Gas accumulation or sudden oil movement inside the transformer — indicating internal fault', 'High ambient temperature', 'Low oil level only'], answer: 1 },
        { q: 'The single-line diagram (SLD) of a plant is essential for:', options: ['Motor maintenance scheduling', 'Safe switching operations and fault isolation by showing power flow paths', 'Calculating motor FLA', 'Setting overload relays'], answer: 1 },
        { q: 'The minimum safe voltage below which arc flash PPE is not required is:', options: ['24V', '50V', '110V', '230V'], answer: 1 },
        { q: 'Power factor correction to 0.95 from 0.7 reduces supply current by approximately:', options: ['5%', '15%', '26%', '50%'], answer: 2 },
        { q: 'Energy metering at distribution board level is most useful for:', options: ['Setting overload relays', 'Identifying the highest energy consumers for efficiency projects', 'Calculating motor insulation life', 'Scheduling PM intervals'], answer: 1 },
      ]
    },
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // INSTRUMENTATION
  // ─────────────────────────────────────────────────────────────────────────────
  'Instrumentation': {
    1: {
      title: 'Instrument Types and Signal Basics',
      module: `
<h3>Common Instrument Types</h3>
<p>Pressure transmitters measure gauge, absolute, or differential pressure. Temperature transmitters use thermocouples (TC) or resistance temperature detectors (RTD). Level transmitters use differential pressure, ultrasonic, radar, or float methods. Flow transmitters use orifice plates, magnetic, vortex, or Coriolis meters. Each converts a physical variable into a standardized signal.</p>
<h3>4–20mA Standard Signal</h3>
<p>The 4–20mA current loop is the industry standard for transmitting analog measurements over long distances. 4mA = 0% (minimum process value), 20mA = 100% (maximum process value). Current (not voltage) is used because current does not degrade over distance. A reading of 0mA or below 3.8mA indicates a broken loop or failed transmitter.</p>
<h3>Instrument Tags</h3>
<p>Instrument tags follow the ISA standard: first letters describe the measured variable (P=Pressure, T=Temperature, F=Flow, L=Level), second letters describe the function (T=Transmitter, I=Indicator, C=Controller, A=Alarm). Example: PIT-101 = Pressure Indicator Transmitter, tag number 101. Tags are linked to the P&ID (Process and Instrumentation Diagram).</p>
<h3>P&ID Basics</h3>
<p>The P&ID shows all process equipment, piping, instruments, and control loops. Every instrument has a tag. Every control loop shows the measurement, the controller, and the final control element (usually a control valve or motor). The P&ID is the reference document for any instrumentation work.</p>`,
      exam: [
        { q: 'A 4–20mA signal reading of 4mA represents:', options: ['50% of the process range', '0% — the minimum process value', '100% — the maximum process value', 'A fault condition'], answer: 1 },
        { q: 'Why is current (4–20mA) preferred over voltage signals for long-distance transmission?', options: ['Current is safer than voltage', 'Current does not degrade with cable resistance over distance', 'Current signals use less cable', 'Voltage signals are not accurate'], answer: 1 },
        { q: 'An instrument reading of 0mA in a 4–20mA loop indicates:', options: ['Minimum process value', 'Broken loop or failed transmitter', '25% process value', 'Normal standby condition'], answer: 1 },
        { q: 'The instrument tag "FIT-205" means:', options: ['Flow Indicator Transmitter, tag 205', 'Fault Indicator Terminal, tag 205', 'Flow Input Terminal, tag 205', 'Frequency Indicator Transmitter, tag 205'], answer: 0 },
        { q: 'An RTD (Resistance Temperature Detector) measures temperature by:', options: ['Generating a voltage proportional to temperature', 'Changing electrical resistance proportionally with temperature', 'Measuring the expansion of a liquid', 'Measuring infrared radiation'], answer: 1 },
        { q: 'On a P&ID, what does a circle with a tag (e.g., TIC-101) represent?', options: ['A manual valve', 'An instrument — in this case a Temperature Indicator Controller', 'A process pump', 'A pipeline specification break'], answer: 1 },
        { q: 'Differential pressure (DP) transmitters are commonly used to measure:', options: ['Temperature in pipes', 'Level (using the pressure difference between bottom and top of a vessel) and flow (across an orifice plate)', 'Vibration', 'Electrical current'], answer: 1 },
        { q: 'A Coriolis flow meter directly measures:', options: ['Volumetric flow only', 'Mass flow rate and fluid density', 'Differential pressure', 'Fluid temperature'], answer: 1 },
        { q: 'The first step before any instrumentation work is to:', options: ['Replace the instrument', 'Obtain the P&ID and identify the correct instrument tag and loop', 'Calibrate the instrument', 'Check the control room display'], answer: 1 },
        { q: 'In the 4–20mA standard, a reading of 12mA represents approximately:', options: ['0%', '25%', '50%', '75%'], answer: 2 },
      ]
    },
    2: {
      title: 'Loop Calibration and Transmitter PM',
      module: `
<h3>Zero and Span Calibration</h3>
<p>Calibration adjusts an instrument to ensure its output matches the true input. Zero adjustment sets the output at the minimum input value (4mA at 0% process). Span adjustment sets the output at the maximum input value (20mA at 100% process). Always adjust zero first, then span — they can interact. Repeat until both are within acceptable tolerance (typically ±0.5%).</p>
<h3>Calibration Equipment</h3>
<p>A pressure calibrator generates and measures pressure simultaneously. A loop calibrator (like a Fluke 705) both powers a 2-wire transmitter (24VDC supply) and measures its output in mA. A temperature calibrator provides precise thermocouple or RTD simulation. Always use calibrated reference equipment with a valid calibration certificate.</p>
<h3>5-Point Calibration</h3>
<p>Check accuracy at 0%, 25%, 50%, 75%, and 100% of range. Record the applied value, the transmitter output (converted to engineering units), and the error at each point. If any point exceeds the acceptable tolerance, adjust and re-check all 5 points. Document the as-found and as-left readings.</p>
<h3>Transmitter PM Checks</h3>
<p>During PM: inspect for corrosion, moisture ingress, and physical damage. Check impulse line for blockage (DP types). Verify cable gland tightness. Check terminal tightness. Clean the instrument enclosure. Verify the instrument tag matches the P&ID. Test alarm and trip setpoints if applicable.</p>`,
      exam: [
        { q: 'During zero and span calibration, which adjustment should be made first?', options: ['Span first, then zero', 'Zero first, then span', 'Both simultaneously', 'Either order is acceptable'], answer: 1 },
        { q: 'A 5-point calibration checks accuracy at:', options: ['0% and 100% only', '0%, 25%, 50%, 75%, and 100% of range', 'Random points chosen by the technician', '50% only — mid-range is most critical'], answer: 1 },
        { q: 'A loop calibrator like the Fluke 705 performs which function?', options: ['Measures resistance only', 'Supplies 24VDC to the transmitter loop and measures the mA output', 'Programs the transmitter HART configuration', 'Measures insulation resistance'], answer: 1 },
        { q: 'Acceptable calibration tolerance for most process transmitters is typically:', options: ['±5%', '±2%', '±0.5%', '±10%'], answer: 2 },
        { q: 'A blocked impulse line on a DP level transmitter will cause:', options: ['Higher than actual level reading', 'The reading to freeze at the last measured value or read incorrectly', 'Transmitter to output 4mA (zero)', 'No effect on the reading'], answer: 1 },
        { q: '"As-found" calibration data records:', options: ['The instrument settings after adjustment', 'The instrument readings before any adjustment — the starting condition', 'The manufacturer\'s factory settings', 'The expected values only'], answer: 1 },
        { q: 'What is HART (Highway Addressable Remote Transducer)?', options: ['A type of calibration standard', 'A digital communication protocol superimposed on a 4–20mA signal for configuration and diagnostics', 'A type of flow transmitter', 'A P&ID standard'], answer: 1 },
        { q: 'A transmitter output drifts slowly upward over weeks despite stable process conditions. The most likely cause is:', options: ['Normal operation', 'Process change', 'Transmitter drift or blockage in the impulse line', 'Control system adjustment'], answer: 2 },
        { q: 'When checking a thermocouple (TC) transmitter with no input connected, the output will typically go to:', options: ['4mA (burn-down protection — most TCs)', '20mA (burn-up protection)', 'Either 4 or 20mA depending on the transmitter\'s burn-out direction setting', '12mA (mid-scale)'], answer: 2 },
        { q: 'Why must calibration reference equipment itself have a valid calibration certificate?', options: ['It is required by company policy only', 'To ensure traceability — the calibration is only as accurate as the reference standard', 'To satisfy customer audits', 'It is required by the instrument manufacturer'], answer: 1 },
      ]
    },
    3: {
      title: 'PID Control and Smart Transmitter Configuration',
      module: `
<h3>PID Controller Fundamentals</h3>
<p>A PID controller maintains a process variable (e.g., temperature, pressure, flow) at a setpoint by calculating an output to a final control element (valve, VFD). P (Proportional) — responds to current error. I (Integral) — eliminates steady-state offset by accumulating error over time. D (Derivative) — responds to rate of change, reduces overshoot. Typical starting tuning for a flow loop: P=0.5, I=0.3 rep/min, D=0.</p>
<h3>Control Loop Troubleshooting</h3>
<p>A control loop that oscillates has too much P gain or too little I. A loop that responds slowly and never reaches setpoint has too little P or too much I. A loop with steady-state offset has no I action. Start diagnostics by putting the loop in manual — if the process stabilizes, the issue is in the control tuning. If it doesn't, the issue is in the process or final control element.</p>
<h3>HART Configuration</h3>
<p>Smart transmitters (HART, FOUNDATION Fieldbus, PROFIBUS) can be configured remotely. HART configuration allows: range change (LRV and URV), damping adjustment, engineering unit change, and diagnostics. Always document the configuration before and after changes. Back up the configuration to the HART communicator or field device management software.</p>
<h3>Control Valve Basics</h3>
<p>Control valves fail to a safe position: fail-open (FO) or fail-closed (FC) depending on the process safety requirement. A level control valve on a reactor drain may be fail-open to empty the vessel on air/signal failure. Valve performance checks: full stroke from 0–100% and back, check for stiction (valve sticks and moves in jumps), measure actual flow vs. position.</p>`,
      exam: [
        { q: 'The Integral (I) term in a PID controller primarily:', options: ['Responds to the rate of change of error', 'Eliminates steady-state offset by accumulating error over time', 'Provides immediate response to current error only', 'Reduces overshoot'], answer: 1 },
        { q: 'A control loop oscillates continuously. The most likely tuning issue is:', options: ['P gain too low', 'I gain too low', 'P gain too high or I gain too high', 'D gain too low'], answer: 2 },
        { q: 'If a control loop stabilizes when put in manual mode, the problem is most likely in:', options: ['The transmitter', 'The process — not the control system', 'The control tuning or the final control element', 'The power supply'], answer: 2 },
        { q: 'In HART configuration, LRV and URV refer to:', options: ['Left Range Value and Upper Right Value', 'Lower Range Value and Upper Range Value — the 4mA and 20mA calibration points', 'Loop Resistance Value and Unified Range Value', 'The alarm limits in the DCS'], answer: 1 },
        { q: 'A control valve described as "fail-closed" (FC) will:', options: ['Close when the control signal increases', 'Open when air/signal is lost', 'Close when air/signal is lost — spring returns to closed position', 'Stay in last position on signal loss'], answer: 2 },
        { q: 'Valve "stiction" refers to:', options: ['A valve that cannot be fully opened', 'A valve that sticks and moves in jumps rather than smoothly — causing poor control', 'A valve with a sticky positioner', 'A valve fully stuck in one position'], answer: 1 },
        { q: 'A flow control loop has setpoint 50% but stabilizes at 45% even with 100% output. The most likely cause is:', options: ['P gain is too high', 'A restriction in the process (e.g., partially closed manual valve, pump issue) — not a tuning problem', 'I gain is too low', 'D gain is too high'], answer: 1 },
        { q: 'Before making any changes to a smart transmitter configuration, you should:', options: ['Call the manufacturer', 'Document the current configuration', 'Put the loop in auto mode', 'Inform production'], answer: 1 },
        { q: 'The Derivative (D) term in PID control is primarily used to:', options: ['Eliminate steady-state offset', 'Reduce overshoot by responding to the rate of change of error', 'Speed up response to step changes', 'Remove measurement noise'], answer: 1 },
        { q: 'FOUNDATION Fieldbus differs from 4–20mA HART in that it:', options: ['Uses the same wiring but different protocols', 'Carries digital process values and control output on a single bus — multiple instruments on one cable', 'Is only used for temperature measurement', 'Cannot be used with PID control'], answer: 1 },
      ]
    },
    4: {
      title: 'DCS/SCADA and Safety Instrumented Systems',
      module: `
<h3>DCS Architecture</h3>
<p>A Distributed Control System (DCS) consists of: field instruments (transmitters, analyzers, valves), I/O modules (convert field signals), controllers (run control algorithms), operator workstations (HMI for monitoring and control), and historian servers (store trend data). The key difference from a PLC-based system: DCS is designed for continuous process control with high availability and redundancy.</p>
<h3>SCADA vs DCS</h3>
<p>SCADA (Supervisory Control and Data Acquisition) is typically used for geographically distributed systems (pipelines, water utilities) where the master station communicates with remote terminal units (RTUs). DCS is for co-located process plant control. Both can use Modbus, Profibus, or OPC standards for integration.</p>
<h3>Safety Instrumented Systems (SIS)</h3>
<p>A SIS is an independent layer of protection that detects abnormal conditions and takes the process to a safe state automatically (e.g., emergency shutdown). The SIS must be independent of the control DCS — same sensors should not be shared. Safety Integrity Level (SIL) defines the reliability requirement: SIL 1 = 10x risk reduction, SIL 2 = 100x, SIL 3 = 1000x.</p>
<h3>Loop Checking and Commissioning</h3>
<p>Before startup, every loop must be checked: inject a signal at the transmitter, verify the correct reading appears at the DCS, verify the control output reaches the field device, verify alarm and trip setpoints are active. Document each loop check result. A loop check found error is far cheaper to fix before startup than after.</p>`,
      exam: [
        { q: 'What distinguishes a DCS from a PLC-based system?', options: ['DCS can only control temperature', 'DCS is designed for continuous process control with high availability and redundancy', 'PLC is slower than DCS', 'DCS requires more operators'], answer: 1 },
        { q: 'In a Safety Instrumented System (SIS), the sensors must be:', options: ['Shared with the DCS to reduce cost', 'Independent of the control DCS to prevent common cause failure', 'Less accurate than DCS sensors', 'Manually checked only'], answer: 1 },
        { q: 'SIL 2 means the SIS provides a risk reduction of:', options: ['10 times', '100 times', '1000 times', '50 times'], answer: 1 },
        { q: 'OPC (OLE for Process Control) is used in industrial systems to:', options: ['Control valve positions remotely', 'Standardize data exchange between different vendor DCS, SCADA, and historian systems', 'Program PLCs', 'Set HART configurations'], answer: 1 },
        { q: 'During loop checking, the transmitter signal is injected in the field while the technician verifies:', options: ['The transmitter housing is clean', 'The correct reading and correct engineering unit appear at the DCS workstation', 'The cable insulation resistance', 'The control valve is fully open'], answer: 1 },
        { q: 'A DCS historian server is used to:', options: ['Back up the control program', 'Store process trend data for analysis, troubleshooting, and optimization', 'Configure transmitters', 'Control emergency shutdown'], answer: 1 },
        { q: 'SCADA systems are most commonly used for:', options: ['Tightly coupled process plant control', 'Geographically distributed systems with remote field sites (pipelines, utilities)', 'Replacing DCS in refineries', 'Single-loop temperature control'], answer: 1 },
        { q: 'An emergency shutdown (ESD) valve must fail to:', options: ['Last position on power loss', 'The pre-defined safe position (open or closed depending on the process hazard)', 'Full open always', 'Full closed always'], answer: 1 },
        { q: 'The purpose of a DCS redundant controller pair is:', options: ['To double the control output', 'Automatic failover — if the primary controller fails, the standby takes over without process disruption', 'To run two different control strategies simultaneously', 'Cost reduction'], answer: 1 },
        { q: 'In loop commissioning, a "loop check found" error is best addressed:', options: ['After startup — it will likely resolve itself', 'Immediately before startup — it is far cheaper to fix now', 'During the next planned shutdown', 'By modifying the DCS alarm limits to mask it'], answer: 1 },
      ]
    },
    5: {
      title: 'IEC 61511 Functional Safety and System Design',
      module: `
<h3>IEC 61511 Overview</h3>
<p>IEC 61511 is the international standard for Safety Instrumented Systems in the process industry. It defines the complete Safety Lifecycle: hazard and risk assessment, determination of required SIL, design and implementation of the SIS, verification, validation, and ongoing proof testing. Compliance is required in petrochemical, oil and gas, and chemical plants and increasingly expected in food, pharmaceutical, and power generation.</p>
<h3>Probability of Failure on Demand (PFD)</h3>
<p>PFD measures how often a safety function fails to operate when demanded. SIL 1: PFD 0.1–0.01. SIL 2: PFD 0.01–0.001. SIL 3: PFD 0.001–0.0001. PFD is reduced by: using redundant sensors (voting logic — 2oo3 is common), increasing proof test frequency, and using components with low failure rates (high MTTF).</p>
<h3>Proof Testing</h3>
<p>A proof test verifies that the safety function will operate when demanded. It must simulate an actual demand: inject a trip signal at the sensor, verify the logic solver responds, verify the final element reaches the safe position, and verify the process can be restored. Proof test interval determines the PFD — less frequent testing raises PFD (worse safety performance).</p>
<h3>Instrument System Design Principles</h3>
<p>Key design rules for a reliable measurement system: select instruments suitable for the process fluid and environment, provide adequate impulse line routing (no pockets for condensate/gas), design redundancy for critical measurements, include isolation valves for maintenance without process shutdown, and document the entire loop from sensor to final element with P&IDs and instrument data sheets.</p>`,
      exam: [
        { q: 'IEC 61511 applies to:', options: ['Electrical motor control', 'Safety Instrumented Systems in the process industry', 'Calibration procedures only', 'PLC programming standards'], answer: 1 },
        { q: 'Probability of Failure on Demand (PFD) for SIL 2 must be between:', options: ['0.1 and 0.01', '0.01 and 0.001', '0.001 and 0.0001', '0.5 and 0.1'], answer: 1 },
        { q: 'A 2oo3 voting logic on sensor inputs means:', options: ['2 out of 3 sensors must agree on a trip before action is taken', 'All 3 sensors must trip before action is taken', 'Any 1 out of 3 sensors tripping takes action', '2 sensors are primary, 1 is backup only'], answer: 0 },
        { q: 'Increasing proof test frequency (testing more often) will:', options: ['Increase PFD (worse safety)', 'Decrease PFD (better safety)', 'Have no effect on PFD', 'Increase MTTF'], answer: 1 },
        { q: 'During a proof test, the safety function is correctly verified when:', options: ['The DCS shows no alarms', 'The trip signal is injected and the final element reaches the safe position', 'The PFD calculation is updated', 'The instrument is calibrated'], answer: 1 },
        { q: 'An impulse line with a pocket (low point in a gas service line) will cause:', options: ['Accurate measurement always', 'Condensate to accumulate — blocking or dampening the pressure signal', 'Higher transmitter output', 'No effect on a smart transmitter'], answer: 1 },
        { q: 'The Safety Lifecycle defined in IEC 61511 begins with:', options: ['SIS design and specification', 'Hazard and risk assessment', 'Proof testing procedures', 'Validation testing'], answer: 1 },
        { q: 'MTTF (Mean Time to Failure) in instrument selection affects:', options: ['The calibration interval', 'The PFD — higher MTTF means lower component failure rate, lower PFD', 'The process variable range', 'The communication protocol'], answer: 1 },
        { q: 'The SIS must be independent of the BPCS (Basic Process Control System) to prevent:', options: ['Signal interference', 'Common cause failure — a single event disabling both control and safety layers', 'Redundant wiring', 'High installation cost'], answer: 1 },
        { q: 'An instrument data sheet for a transmitter must include:', options: ['Installation photos only', 'Process conditions, range, materials, connection size, signal type, and accuracy — sufficient to specify or replace the instrument', 'Calibration certificate only', 'The P&ID tag number only'], answer: 1 },
      ]
    },
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // FACILITIES MANAGEMENT
  // ─────────────────────────────────────────────────────────────────────────────
  'Facilities Management': {
    1: {
      title: 'Building Services Awareness and Fire Safety',
      module: `
<h3>Building Services Overview</h3>
<p>Facilities Management covers all systems that make a building or plant operational: electrical distribution (lighting, power), HVAC (heating, ventilation, air conditioning), plumbing and drainage, fire protection (detection and suppression), building structure (civil and architectural), and security systems. The FM team ensures these systems are safe, functional, and compliant.</p>
<h3>Fire Detection and Suppression Systems</h3>
<p>Fire detectors include: smoke detectors (optical or ionization), heat detectors (fixed temperature or rate-of-rise), and flame detectors (UV/IR). Suppression systems include: water sprinklers, CO2 (for electrical rooms — smothers fire without water damage), FM-200 (clean agent for data centers), and dry powder (chemical fires). Fire extinguisher classes: A (ordinary combustibles), B (flammable liquids), C (electrical — use CO2 or dry powder, never water).</p>
<h3>DOLE and BFP Compliance</h3>
<p>In the Philippines, facilities must comply with DOLE (Department of Labor and Employment) Occupational Safety and Health Standards and the BFP (Bureau of Fire Protection) requirements. This includes: fire exits (unlocked, clearly marked, free from obstruction), fire drills (at least twice a year), fire extinguisher inspection (monthly), and FSIC (Fire Safety Inspection Certificate) from BFP.</p>
<h3>Emergency Response</h3>
<p>Every worker must know: the location of fire exits, the fire alarm signal, the assembly point, and how to use a fire extinguisher (PASS: Pull pin, Aim at base of fire, Squeeze handle, Sweep side to side). Never use elevators during a fire emergency.</p>`,
      exam: [
        { q: 'Which fire extinguisher type should NEVER be used on an electrical fire?', options: ['CO2 extinguisher', 'Dry powder extinguisher', 'Water extinguisher', 'FM-200 extinguisher'], answer: 2 },
        { q: 'The PASS technique for fire extinguishers stands for:', options: ['Push, Aim, Spray, Sweep', 'Pull pin, Aim at base, Squeeze handle, Sweep side to side', 'Pull, Activate, Spray, Stop', 'Press, Aim, Squeeze, Sustain'], answer: 1 },
        { q: 'CO2 fire suppression is preferred for electrical rooms because:', options: ['It is the cheapest option', 'It suppresses fire without water — preventing damage to electrical equipment', 'It is required by DOLE regulations specifically for electrical rooms', 'It cools the equipment faster'], answer: 1 },
        { q: 'Fire drills in a Philippine facility must be conducted at least:', options: ['Once a year', 'Twice a year per BFP requirements', 'Monthly', 'Only when required by the insurance company'], answer: 1 },
        { q: 'During a fire alarm, the correct action regarding elevators is:', options: ['Use elevators to evacuate faster', 'Never use elevators — use stairs only', 'Use elevators only if the fire is below your floor', 'Elevators are safe for evacuation'], answer: 1 },
        { q: 'A rate-of-rise heat detector activates when:', options: ['Temperature exceeds a fixed threshold', 'Temperature rises rapidly — faster than normal ambient changes', 'Smoke density exceeds a threshold', 'Flame UV radiation is detected'], answer: 1 },
        { q: 'FSIC (Fire Safety Inspection Certificate) is issued by:', options: ['DOLE', 'BFP (Bureau of Fire Protection)', 'DPWH', 'DENR'], answer: 1 },
        { q: 'Fire exits must always be:', options: ['Locked to prevent unauthorized access', 'Clearly marked, unlocked, and free from obstruction', 'Opened only by the safety officer', 'Alarmed to notify security when opened'], answer: 1 },
        { q: 'An ionization smoke detector is most sensitive to:', options: ['Slow, smoldering fires producing visible smoke', 'Fast, flaming fires producing invisible combustion products', 'Heat from fires', 'Flame UV radiation'], answer: 1 },
        { q: 'FM-200 clean agent suppression is preferred for data centers because:', options: ['It is the least expensive option', 'It suppresses fire without leaving residue or damaging electronic equipment', 'It is required by law for all data centers', 'It works faster than CO2'], answer: 1 },
      ]
    },
    2: {
      title: 'HVAC PM and Utilities Management',
      module: `
<h3>HVAC System Components</h3>
<p>A central HVAC system includes: chillers (produce chilled water), cooling towers (reject heat from condensers), air handling units (AHUs — cool and distribute air), fan coil units (FCUs — local cooling), ductwork, and controls. The refrigeration cycle: compressor → condenser → expansion valve → evaporator → back to compressor. The refrigerant absorbs heat in the evaporator and rejects it in the condenser.</p>
<h3>HVAC PM Tasks</h3>
<p>Monthly: clean or replace air filters, check refrigerant pressures (suction and discharge), check condensate drain lines (blockage causes water overflow), inspect belts on AHU fans, record chiller operating parameters. Quarterly: clean evaporator and condenser coils (fouled coils reduce efficiency and increase power consumption by up to 30%), calibrate thermostats. Annually: full refrigerant check, drain and clean cooling towers.</p>
<h3>Utilities Management — Water, Steam, and Compressed Air</h3>
<p>Compressed air leaks are the most common energy waste in industrial facilities — a 3mm leak at 7 bar loses approximately 1.5 kW continuously. Find leaks with ultrasonic detectors. Steam trap maintenance prevents steam loss and water hammer. Water systems require periodic flushing and biocide treatment (Legionella prevention in cooling towers).</p>
<h3>Energy Monitoring</h3>
<p>Track utility consumption: kWh, m³ water, m³ compressed air, and steam. Set baselines and monitor for increases — an unexpected rise in power consumption often means equipment degradation (dirty coils, refrigerant loss, air leaks). Sub-metering by building zone or system isolates where consumption is highest.</p>`,
      exam: [
        { q: 'In the refrigeration cycle, the refrigerant absorbs heat from the process in the:', options: ['Compressor', 'Condenser', 'Expansion valve', 'Evaporator'], answer: 3 },
        { q: 'Fouled evaporator and condenser coils can increase HVAC power consumption by up to:', options: ['5%', '10%', '30%', '50%'], answer: 2 },
        { q: 'A blocked condensate drain line in an AHU will cause:', options: ['Reduced cooling capacity only', 'Water overflow from the drain pan — potential water damage and slip hazard', 'The compressor to trip', 'Lower discharge pressure'], answer: 1 },
        { q: 'A 3mm compressed air leak at 7 bar loses approximately:', options: ['0.1 kW', '0.5 kW', '1.5 kW', '5 kW'], answer: 2 },
        { q: 'Legionella bacteria is a specific concern in:', options: ['Compressed air systems', 'Cooling towers with water — warm water and aerosol create ideal conditions for growth', 'Steam boilers', 'Chilled water only systems (closed loop)'], answer: 1 },
        { q: 'An unexpected increase in chiller power consumption despite stable load most likely indicates:', options: ['Normal seasonal variation', 'Refrigerant leak or fouled heat exchangers reducing efficiency', 'The chiller has been recently serviced', 'A control system fault'], answer: 1 },
        { q: 'Ultrasonic detectors in a compressed air system are used to:', options: ['Measure flow rate', 'Detect leaks from the high-frequency hiss of escaping air', 'Check pipe thickness', 'Measure pressure at remote points'], answer: 1 },
        { q: 'Sub-metering of utilities by building zone helps to:', options: ['Replace the main utility meter', 'Isolate which zone or system is driving high consumption for targeted improvement', 'Reduce the utility bill automatically', 'Meet DOLE requirements'], answer: 1 },
        { q: 'HVAC air filter replacement frequency is primarily based on:', options: ['Manufacturer calendar schedule only', 'Pressure drop across the filter or visual inspection — replace when dirty', 'Annual schedule only', 'The number of occupants in the building'], answer: 1 },
        { q: 'The purpose of a cooling tower in a chiller system is to:', options: ['Cool the process water directly', 'Reject heat from the refrigerant condenser to the atmosphere via evaporative cooling', 'Pre-cool the supply air', 'Provide chilled water for air handling units'], answer: 1 },
      ]
    },
    3: {
      title: 'Energy Management and Contractor Management',
      module: `
<h3>Energy Management System (ISO 50001)</h3>
<p>ISO 50001 provides a framework for energy management: establish a baseline, set energy performance indicators (EnPIs), identify significant energy uses (SEUs — typically the top 80% of consumption), set targets, implement improvement projects, and monitor performance. Common SEUs in industrial facilities: compressed air, HVAC, lighting, and large process motors.</p>
<h3>Lighting Efficiency</h3>
<p>LED lighting uses 50–75% less energy than fluorescent and has a lifespan 3–5x longer. Lighting controls (occupancy sensors, daylight dimming) reduce consumption further by 20–40%. Color Rendering Index (CRI) should be 80+ for work areas. Illuminance levels: office 300–500 lux, workshop 500–1000 lux, outdoor areas 20–50 lux. Use a lux meter to verify compliance.</p>
<h3>Contractor Safety Management</h3>
<p>Contractors on site must comply with facility safety rules. Requirements: safety induction before starting work, valid permit to work, use of facility-approved PPE, competency verification for high-risk tasks (welding, electrical, working at height). The facility owner is legally responsible for contractor safety even if the contractor employs the workers — negligence claims apply to both.</p>
<h3>Condition Assessment and Asset Management</h3>
<p>Building and facility assets (structures, roofing, drainage, roads) degrade over time. Regular condition assessments score asset condition (1=new, 5=end of life) and generate a maintenance backlog. Priority = criticality × condition score. Budget allocation based on condition prevents emergency reactive repairs and extends asset life.</p>`,
      exam: [
        { q: 'ISO 50001 is the international standard for:', options: ['Quality management', 'Environmental management', 'Energy management systems', 'Occupational health and safety'], answer: 2 },
        { q: 'Significant Energy Uses (SEUs) in ISO 50001 are defined as:', options: ['All energy uses in the facility', 'The top 80% of total energy consumption — the largest consumers', 'Energy uses above 100 kW only', 'Uses identified by the CEO'], answer: 1 },
        { q: 'LED lighting compared to fluorescent uses approximately:', options: ['10% less energy', '25% less energy', '50–75% less energy', 'The same energy'], answer: 2 },
        { q: 'A workshop requires a minimum illuminance of approximately:', options: ['50 lux', '300 lux', '500–1000 lux', '2000 lux'], answer: 2 },
        { q: 'For contractor safety, the facility owner is:', options: ['Not responsible — the contractor employs the workers', 'Responsible — negligence claims apply to both facility owner and contractor', 'Responsible only if the contractor is a local company', 'Not responsible if a PTW was signed'], answer: 1 },
        { q: 'A condition score of 5 in a facility asset assessment means:', options: ['The asset is new and in perfect condition', 'The asset is at end of life and requires replacement or major repair', 'The asset has been recently serviced', 'The asset has medium priority'], answer: 1 },
        { q: 'Occupancy sensors for lighting control can reduce lighting energy consumption by:', options: ['5%', '10%', '20–40%', '60%'], answer: 2 },
        { q: 'Contractor safety induction before starting work on site is required to:', options: ['Record the contractor\'s name for invoicing', 'Ensure the contractor understands site hazards, rules, and emergency procedures before starting', 'Satisfy the auditor\'s requirement only', 'Replace the permit-to-work process'], answer: 1 },
        { q: 'Energy Performance Indicators (EnPIs) in ISO 50001 are used to:', options: ['Calculate the ISO certification fee', 'Measure and track energy performance over time relative to a baseline', 'Set contractor safety standards', 'Design the building layout'], answer: 1 },
        { q: 'Proactive facility condition assessments primarily help to:', options: ['Increase reactive emergency repairs', 'Allocate maintenance budget to highest-priority assets before failure', 'Reduce the maintenance team size', 'Satisfy customer complaints'], answer: 1 },
      ]
    },
    4: {
      title: 'DOLE/OSHA Compliance and Integrated Facility Planning',
      module: `
<h3>DOLE OSH Standards in the Philippines</h3>
<p>Republic Act 11058 (OSHS Act 2018) strengthened OSH requirements. Key obligations: appoint a Safety Officer (SO1 to SO4 depending on risk level and headcount), conduct safety training, maintain an accident/incident log, perform workplace hazard identification (HIRAC — Hazard Identification, Risk Assessment, and Control), and submit OSH reports to DOLE annually. Failure to comply results in fines and work stoppage orders.</p>
<h3>Electrical Safety Compliance</h3>
<p>The Philippine Electrical Code (PEC) governs electrical installation standards. Key requirements: all electrical work by licensed electricians, proper earthing and bonding, Arc Flash assessment for LV panels above 50V, periodic electrical inspection (PEIS) by a PEC-accredited inspector, and EPIRA compliance for power plant facilities. Fire load assessment is required for buildings above 15m height.</p>
<h3>Facilities Master Plan</h3>
<p>A Facilities Master Plan (FMP) documents the current state of all assets, identifies gaps vs. requirements, and plans capital expenditures over 5–10 years. Key components: asset register (all building systems with age and condition), space planning, capacity planning (power, water, HVAC), sustainability targets, and compliance roadmap. The FMP is presented to management for budget approval.</p>
<h3>CMMS for Facilities</h3>
<p>A Computerized Maintenance Management System (CMMS) schedules, tracks, and records all PM tasks and corrective work orders for facility assets. Key metrics to track: PM compliance rate (% of scheduled PMs completed on time), mean time to respond (reactive), and maintenance cost per square meter. Target: 90%+ PM compliance, less than 4-hour response for critical failures.</p>`,
      exam: [
        { q: 'Republic Act 11058 in the Philippines covers:', options: ['Environmental protection', 'Occupational Safety and Health standards — employer and worker OSH obligations', 'Building code for commercial structures', 'Energy efficiency for government buildings'], answer: 1 },
        { q: 'HIRAC in OSH management stands for:', options: ['Health Incident Reporting and Control', 'Hazard Identification, Risk Assessment, and Control', 'High Risk Area Compliance', 'Hazard Index, Risk Allocation, and Correction'], answer: 1 },
        { q: 'The Philippine Electrical Code (PEC) requires that all electrical installation work be done by:', options: ['Any trained maintenance technician', 'A licensed electrical engineer or master electrician', 'The building owner', 'Any TESDA-certified worker'], answer: 1 },
        { q: 'A Facilities Master Plan (FMP) with a 5–10 year horizon is used primarily for:', options: ['Daily maintenance scheduling', 'Planning capital expenditures and capacity requirements based on current asset condition and future needs', 'Setting contractor rates', 'Emergency response planning'], answer: 1 },
        { q: 'PM compliance rate in a CMMS is calculated as:', options: ['Number of emergency repairs / total repairs', 'Number of scheduled PMs completed on time / total scheduled PMs × 100%', 'Maintenance cost / asset replacement value', 'Total downtime hours / scheduled hours'], answer: 1 },
        { q: 'A work stoppage order from DOLE can be issued when:', options: ['The company misses one OSH report', 'Imminent danger to worker safety is found during inspection', 'A minor incident occurs', 'The FSIC is expired'], answer: 1 },
        { q: 'Arc Flash assessment is required for electrical panels with voltage above:', options: ['24V', '50V', '110V', '230V'], answer: 1 },
        { q: 'The target PM compliance rate for a well-managed facility is:', options: ['60%', '75%', '90% or higher', '50%'], answer: 2 },
        { q: 'A PEIS (Periodic Electrical Inspection) must be conducted by:', options: ['The company electrician', 'A PEC-accredited inspector', 'Any licensed engineer', 'The local government inspector only'], answer: 1 },
        { q: 'Space planning in a Facilities Master Plan addresses:', options: ['Maintenance task scheduling', 'Current and future space needs — identifying gaps between available and required floor area by function', 'Contractor management', 'Safety officer allocation'], answer: 1 },
      ]
    },
    5: {
      title: 'Integrated FM, Sustainability, and Strategic Planning',
      module: `
<h3>Integrated Facilities Management (IFM)</h3>
<p>IFM consolidates all facility services (maintenance, cleaning, security, catering, utilities) under a single management framework. Benefits: unified reporting, single point of accountability, coordinated vendor management, and whole-life cost optimization. The FM manager becomes a strategic business partner — demonstrating how facility performance affects production capacity, safety, and sustainability.</p>
<h3>Sustainability in Facilities</h3>
<p>Key sustainability targets for industrial facilities: carbon footprint reduction (Scope 1 = direct combustion, Scope 2 = purchased electricity, Scope 3 = supply chain), water consumption per unit output, zero waste to landfill programs, and energy intensity (kWh per unit production). Green building certifications (LEED, BERDE in Philippines) can improve property value and attract ESG-focused investors.</p>
<h3>Life-Cycle Cost Analysis</h3>
<p>Total Cost of Ownership (TCO) = capital cost + operating cost (energy, maintenance, labor) + end-of-life disposal cost. A low-capital-cost option can have a far higher TCO. Example: a cheap air conditioner costs PHP 30,000 but consumes 40% more energy — the lifetime energy cost difference far exceeds the initial savings. Always calculate 10-year TCO for major equipment procurement decisions.</p>
<h3>Digital Facilities Management</h3>
<p>Building Information Modeling (BIM) creates a digital twin of the facility for maintenance planning. IoT sensors on building systems provide real-time condition data. AI-driven analytics predict when HVAC, lifts, and building systems will fail. Integrated platforms (IBM Maximo, SAP PM, Archibus) combine asset management, work orders, and space planning in one system.</p>`,
      exam: [
        { q: 'Integrated Facilities Management (IFM) benefits include:', options: ['Higher cost from multiple vendor contracts', 'Unified reporting, single accountability, and whole-life cost optimization', 'More complex management structure', 'Reduced safety compliance requirements'], answer: 1 },
        { q: 'Scope 2 emissions in carbon accounting refer to:', options: ['Direct combustion from owned sources', 'Purchased electricity and heat — indirect emissions from energy supply', 'Supply chain emissions', 'Employee travel emissions'], answer: 1 },
        { q: 'BERDE is the Philippine equivalent of:', options: ['DOLE OSH certification', 'Green building rating system (equivalent to LEED)', 'BFP fire safety certification', 'ISO 50001 certification'], answer: 1 },
        { q: 'Total Cost of Ownership (TCO) for a 10-year equipment life includes:', options: ['Purchase price only', 'Purchase price + energy cost + maintenance cost + disposal cost over the life of the equipment', 'Annual maintenance cost × 10', 'Energy cost only'], answer: 1 },
        { q: 'A Building Information Model (BIM) digital twin is most useful for FM in:', options: ['Daily security patrol scheduling', 'Maintenance planning — locating assets, understanding system relationships, and planning modifications without physical site investigation', 'HR management', 'Financial reporting'], answer: 1 },
        { q: 'Energy intensity is measured as:', options: ['Total kWh consumed in a year', 'kWh per unit of production output — normalizes energy use against production volume', 'Peak demand in kW', 'Cost per kWh'], answer: 1 },
        { q: 'A zero waste to landfill program in facilities means:', options: ['Producing zero waste in operations', 'Diverting all waste from landfill through recycling, composting, or energy recovery', 'Reducing waste paperwork', 'Eliminating cleaning services'], answer: 1 },
        { q: 'IoT sensors on building systems primarily enable:', options: ['Remote manual control only', 'Real-time condition monitoring and predictive analytics to detect degradation before failure', 'Building access control', 'CCTV monitoring'], answer: 1 },
        { q: 'Life-cycle cost analysis for a major equipment purchase decision should cover at minimum:', options: ['1 year', '3 years', '10 years', 'Only the warranty period'], answer: 2 },
        { q: 'The FM manager as "strategic business partner" means:', options: ['The FM manager approves the business strategy', 'FM performance data (uptime, energy, cost) is used to demonstrate FM\'s impact on production capacity and sustainability goals', 'FM manages the finance department', 'The FM manager replaces the COO'], answer: 1 },
      ]
    },
  },

  // ─────────────────────────────────────────────────────────────────────────────
  // PRODUCTION LINES
  // ─────────────────────────────────────────────────────────────────────────────
  'Production Lines': {
    1: {
      title: 'Machine Guarding, Ergonomics, and OEE Awareness',
      module: `
<h3>Machine Guarding</h3>
<p>Machine guards prevent contact with hazardous moving parts: rotating shafts, gears, belts, pulleys, cutting blades, and presses. Types of guards: fixed guards (permanent, require tools to remove), interlocked guards (machine stops when guard is opened), presence-sensing devices (light curtains — machine stops if beam is broken). Never remove or bypass a guard — report missing guards immediately.</p>
<h3>Ergonomics on the Production Line</h3>
<p>Ergonomic hazards include: repetitive motion, awkward postures (bending, reaching above shoulder height), heavy lifting, and prolonged standing on hard floors. Risk reduction: rotate tasks to reduce repetitive strain, use lifting aids for loads above 10kg, position work at elbow height where possible, use anti-fatigue mats. Ergonomic injuries develop slowly but cause long-term disability.</p>
<h3>OEE — What It Means to a Line Operator</h3>
<p>OEE (Overall Equipment Effectiveness) measures how well a line is utilized vs. its ideal potential. Three losses: Availability loss (downtime — machine stopped when it should run), Performance loss (machine runs but slower than ideal), Quality loss (producing defects). A line running at 60% OEE has significant improvement opportunity. Every worker on the line affects OEE.</p>
<h3>Production Safety Rules</h3>
<p>Never reach into a moving machine. Never bypass a safety device. Report all near-misses — they are warnings of future accidents. Follow the standard operating procedure (SOP) for every task. Unauthorized changes to machine settings are prohibited. If something looks unsafe, stop the machine and report it.</p>`,
      exam: [
        { q: 'A light curtain on a press is an example of which type of guard?', options: ['Fixed guard', 'Interlocked guard', 'Presence-sensing device', 'Adjustable guard'], answer: 2 },
        { q: 'An interlocked guard on a machine means:', options: ['The guard is bolted in place permanently', 'The machine stops automatically when the guard is opened', 'The guard can only be removed by maintenance', 'The guard has a lock for the shift supervisor'], answer: 1 },
        { q: 'For manual lifting, loads above which weight should use a mechanical lifting aid?', options: ['5 kg', '10 kg', '25 kg', '50 kg'], answer: 1 },
        { q: 'Availability loss in OEE is caused by:', options: ['Machine producing defective products', 'Machine running slower than ideal rate', 'Machine stopped when it should be running (unplanned downtime)', 'Material change between products'], answer: 2 },
        { q: 'Repetitive motion injuries on a production line are best prevented by:', options: ['Working faster to finish sooner', 'Task rotation to reduce exposure to the same motion', 'Wearing gloves', 'Increasing production targets'], answer: 1 },
        { q: 'A near-miss incident should be:', options: ['Ignored — nothing actually happened', 'Reported and investigated — it is a warning of potential future accidents', 'Reported only if someone was slightly injured', 'Documented privately without reporting to the supervisor'], answer: 1 },
        { q: 'The ideal work height for most production tasks is:', options: ['Knee height', 'Elbow height — minimizes shoulder and back strain', 'Shoulder height', 'The height of the machine, regardless of worker height'], answer: 1 },
        { q: 'Performance loss in OEE occurs when:', options: ['The machine is stopped for a breakdown', 'The machine is running but producing defects', 'The machine runs at less than the ideal rated speed', 'The machine is idle between shifts'], answer: 2 },
        { q: 'Unauthorized changes to machine settings are prohibited because:', options: ['They are expensive to reverse', 'They can affect product quality, machine safety, and process stability — without proper review and documentation', 'Management approval is required for paperwork purposes', 'It is a DOLE requirement only'], answer: 1 },
        { q: 'Anti-fatigue mats on production lines primarily:', options: ['Prevent slipping on wet floors', 'Reduce musculoskeletal fatigue from prolonged standing on hard surfaces', 'Protect the floor from damage', 'Mark the work zone boundaries'], answer: 1 },
      ]
    },
    2: {
      title: 'Changeover, Troubleshooting, and Defect ID',
      module: `
<h3>SMED (Single Minute Exchange of Die)</h3>
<p>SMED is a method to reduce changeover time. It separates activities into: Internal (must be done while machine is stopped) and External (can be done while machine is still running). The goal is to convert as many internal activities to external as possible. Target: changeover in under 10 minutes. Even partial application typically reduces changeover time by 30–50%.</p>
<h3>Basic Production Line Troubleshooting</h3>
<p>When a line stops: (1) Is it mechanical (jam, broken part)? (2) Is it electrical (no power, sensor fault, motor trip)? (3) Is it a product issue (wrong material, wrong dimension)? (4) Is it an operator error (setup incorrect)? Use a structured check — don't replace parts before diagnosing the fault. Record every stoppage with root cause in the logbook.</p>
<h3>Defect Identification — 7 Types of Waste (Muda)</h3>
<p>The 7 wastes: Overproduction, Waiting, Transportation (unnecessary movement of material), Over-processing (more work than needed), Inventory (excess WIP or finished goods), Motion (unnecessary worker movement), and Defects (rework or scrap). Defects are the most visible waste — every defect was consuming resources to produce and must be reworked or scrapped.</p>
<h3>First Article Inspection and In-Process Quality</h3>
<p>At the start of every shift and after every changeover, a first article check confirms the line is producing to specification before running in volume. Check critical dimensions, appearance, and function. If first article fails, stop the line and correct before proceeding. In-process sampling at regular intervals catches drift before it becomes a large scrap event.</p>`,
      exam: [
        { q: 'In SMED, "External" activities are those that:', options: ['Must be done while the machine is stopped', 'Can be done while the machine is still running — before or after the actual changeover', 'Are done by external contractors only', 'Take the longest time'], answer: 1 },
        { q: 'The target changeover time in SMED is:', options: ['Under 1 hour', 'Under 30 minutes', 'Under 10 minutes (Single Minute = less than 10 minutes)', 'Under 2 minutes'], answer: 2 },
        { q: 'When a production line stops unexpectedly, the first step is:', options: ['Replace the most common failure part immediately', 'Diagnose systematically — mechanical, electrical, product, or operator issue', 'Call maintenance immediately and wait', 'Restart the machine to check if it happens again'], answer: 1 },
        { q: 'Which of the 7 wastes is often considered most visible and costly?', options: ['Transportation', 'Waiting', 'Defects — consuming resources with nothing to show for it', 'Motion'], answer: 2 },
        { q: 'Over-processing waste occurs when:', options: ['Too much raw material is ordered', 'More work is done on a product than the customer requires or specification demands', 'Products are transported unnecessarily', 'Workers move between workstations too often'], answer: 1 },
        { q: 'First article inspection after changeover is done to:', options: ['Satisfy the auditor\'s requirement', 'Confirm the line is producing to specification before running in volume', 'Check the machine speed', 'Count the number of defects from the previous run'], answer: 1 },
        { q: 'If a first article fails inspection, the correct action is:', options: ['Run 10 pieces and check again', 'Stop the line and correct the setup before proceeding', 'Adjust the specification to match the parts produced', 'Continue and sort defects later'], answer: 1 },
        { q: 'Inventory waste (excess WIP) is a problem because:', options: ['It makes the warehouse look untidy', 'It hides problems (defects, machine downtime), ties up capital, and can become obsolete', 'It requires more forklift operators', 'It is required by customer safety stock requirements'], answer: 1 },
        { q: 'Recording root cause for every line stoppage is important because:', options: ['DOLE requires it', 'Patterns in stoppage causes reveal the highest priority improvement opportunities', 'It satisfies the production manager', 'It reduces the MTTR automatically'], answer: 1 },
        { q: 'In-process quality sampling during a production run is used to:', options: ['Count the total production volume', 'Detect quality drift early — before a large quantity of defective product is produced', 'Replace end-of-line inspection', 'Satisfy customer visit requirements'], answer: 1 },
      ]
    },
    3: {
      title: 'OEE Calculation, 5S/Kaizen, and RCA on Stoppages',
      module: `
<h3>OEE Calculation in Detail</h3>
<p>OEE = Availability × Performance × Quality. Availability = (Planned time - Downtime) / Planned time. Performance = (Actual output × Ideal cycle time) / Available time. Quality = Good units / Total units produced. Example: Planned 8 hours, 1 hour downtime, ideal cycle 1 part/minute, actual output 380 parts, 10 defects. A = 7/8 = 0.875. P = (380 × 1min) / 420min = 0.905. Q = 370/380 = 0.974. OEE = 0.875 × 0.905 × 0.974 = 77.1%.</p>
<h3>5S Implementation</h3>
<p>5S creates a visual workplace where abnormalities are immediately obvious. Sort: remove everything not needed. Set in order: a place for everything, everything in its place (use shadow boards for tools). Shine: clean as inspection — find problems while cleaning. Standardize: document the standard condition with photos. Sustain: audit and discipline to maintain the standard. 5S is the foundation for all other improvements — you cannot improve what you cannot see clearly.</p>
<h3>Kaizen — Continuous Improvement</h3>
<p>Kaizen = small, daily improvements by the people doing the work. Not major projects — micro-improvements. Every worker can submit a Kaizen: "I noticed X problem, I tried Y solution, the result was Z improvement." Track with a Kaizen board. 50 small Kaizens per year from a team of 10 people often delivers more total improvement than 1 large engineering project.</p>
<h3>Root Cause Analysis (RCA) for Line Stoppages</h3>
<p>5 Whys applied to a line stoppage: Machine stopped (Why?) → Motor tripped (Why?) → Overload relay tripped (Why?) → Motor was running hot (Why?) → Cooling fins blocked with dust (Why?) → No PM schedule for cleaning cooling fins. Root cause: gap in PM schedule. Corrective action: add cooling fin cleaning to PM checklist. Without RCA, the motor trips again next month.</p>`,
      exam: [
        { q: 'A line runs 7 hours of an 8-hour planned shift, produces 350 parts at an ideal rate of 1 part/minute, and 15 are defective. What is OEE?', options: ['74.8%', '81.3%', '68.9%', '77.5%'], answer: 0 },
        { q: 'In 5S, "Shine" means:', options: ['Paint the floor and equipment', 'Clean as inspection — find problems (leaks, loose parts, missing guards) while cleaning', 'Polish chrome surfaces for appearance', 'Clean only before customer visits'], answer: 1 },
        { q: 'A shadow board in a 5S workplace is used to:', options: ['Block light in inspection areas', 'Show the correct storage position for each tool — missing tools are immediately obvious', 'Display production targets', 'Cover windows during night shifts'], answer: 1 },
        { q: 'Kaizen improvements are most effective when:', options: ['Implemented only by engineers and management', 'Submitted by the workers doing the work — they see the problems daily', 'Limited to large capital projects', 'Done annually during improvement campaigns only'], answer: 1 },
        { q: 'In the 5 Whys analysis for a motor stoppage, reaching "No PM schedule for cleaning cooling fins" means you have found the:', options: ['Symptom', 'Immediate cause', 'Root cause — the system gap that allowed the problem to occur', 'Contributing factor'], answer: 2 },
        { q: '5S is described as the foundation for all other improvements because:', options: ['It is the cheapest improvement method', 'A clean, organized, and visual workplace makes abnormalities obvious — you cannot improve what you cannot clearly see', 'It is required by ISO 9001', 'It reduces headcount'], answer: 1 },
        { q: 'Performance loss in OEE is calculated using:', options: ['Downtime hours / planned hours', '(Actual output × ideal cycle time) / available time', 'Good units / total units', 'Actual speed / ideal speed for the last 5 minutes only'], answer: 1 },
        { q: 'A Kaizen board in a production team is used to:', options: ['Display the shift schedule', 'Track improvement ideas submitted, in progress, and completed — creating visibility and accountability', 'List quality defects for the week', 'Show machine downtime history'], answer: 1 },
        { q: 'The "Standardize" step in 5S means:', options: ['Buy standard tools for all operators', 'Document the standard condition (photos, labels) so everyone knows what "good" looks like', 'Create a standard work procedure only', 'Apply the same 5S rules as the factory next door'], answer: 1 },
        { q: 'Without RCA, what is the typical outcome of a repeated machine stoppage?', options: ['The problem resolves itself over time', 'The same root cause repeats — fix is only to the symptom, not the underlying system gap', 'The machine becomes more reliable after each fix', 'The stoppage frequency decreases naturally'], answer: 1 },
      ]
    },
    4: {
      title: 'Line Balancing, Bottleneck Analysis, and TPM',
      module: `
<h3>Line Balancing</h3>
<p>Line balancing distributes work content evenly across workstations so no single station is overloaded (the bottleneck) or idle (wasted capacity). Takt time = available production time / customer demand rate. Each workstation's cycle time should be at or below takt time. Balance efficiency = total work content / (number of stations × takt time). Imbalanced lines have idle workers watching the bottleneck station.</p>
<h3>Bottleneck Analysis (Theory of Constraints)</h3>
<p>The bottleneck is the station or machine that limits total line throughput. Improving non-bottleneck stations does not improve total output. To increase output: (1) Identify the bottleneck, (2) Exploit it — maximize its uptime (no starvation, no blocking), (3) Subordinate everything else to the bottleneck, (4) Elevate it — invest to improve its capacity, (5) Find the new bottleneck and repeat. This is Goldratt's Theory of Constraints (TOC).</p>
<h3>Total Productive Maintenance (TPM)</h3>
<p>TPM integrates production and maintenance — operators take ownership of basic machine care. Operator responsibilities under TPM: cleaning (which is inspection), lubrication (trained and scheduled), minor adjustments, and identifying abnormalities for the maintenance team. The maintenance team focuses on complex repairs and improvements. TPM targets: zero breakdowns, zero defects, zero accidents (ZZZ).</p>
<h3>Autonomous Maintenance (AM)</h3>
<p>AM is step 2 of the TPM pillars. The AM journey: Step 1 = Initial cleaning, Step 2 = Address sources of contamination and hard-to-clean areas, Step 3 = Create cleaning and inspection standards, Step 4 = General inspection training, Step 5 = Autonomous inspection. Each step is audited before progressing. AM transfers basic care from maintenance to operators, freeing maintenance for value-added work.</p>`,
      exam: [
        { q: 'Takt time is calculated as:', options: ['Total production time / Number of workers', 'Available production time / Customer demand rate', 'Actual cycle time / Ideal cycle time', 'Shift length / Number of workstations'], answer: 1 },
        { q: 'In line balancing, a station with a cycle time much less than takt time is:', options: ['The bottleneck', 'An under-loaded station — idle time is waste', 'A correctly balanced station', 'A problem requiring more staff'], answer: 1 },
        { q: 'According to Theory of Constraints, improving the throughput of a non-bottleneck station will:', options: ['Increase total line output proportionally', 'Not increase total line output — the bottleneck still limits throughput', 'Reduce quality at the bottleneck', 'Improve line balance efficiency'], answer: 1 },
        { q: 'TPM targets are summarized as:', options: ['Zero waste, zero defects, zero overtime', 'Zero breakdowns, zero defects, zero accidents', 'Zero inventory, zero rework, zero downtime', 'Zero stoppages, zero changeovers, zero complaints'], answer: 1 },
        { q: 'Under TPM, what is the primary role of production operators?', options: ['Only operating the machine — maintenance is entirely the maintenance team\'s responsibility', 'Basic machine care — cleaning, lubrication, minor adjustments, and abnormality reporting', 'Full machine repair and overhaul', 'Quality inspection only'], answer: 1 },
        { q: 'In Autonomous Maintenance, "cleaning is inspection" means:', options: ['Operators clean only to satisfy audit requirements', 'During cleaning, operators discover abnormalities (leaks, loose parts, wear) that would otherwise be missed', 'Cleaning replaces maintenance inspection', 'Cleaning is counted as machine downtime'], answer: 1 },
        { q: '"Exploit the bottleneck" in Theory of Constraints means:', options: ['Replace the bottleneck machine immediately', 'Maximize the bottleneck\'s productive time — eliminate starvation, blocking, and unplanned downtime', 'Add workers to the bottleneck station', 'Reduce the work content at the bottleneck'], answer: 1 },
        { q: 'Line balance efficiency of 70% means:', options: ['70% of products meet quality standard', '30% of the theoretical capacity is lost to imbalance — idle time at non-bottleneck stations', '70% of workers are productive', '30% OEE improvement is needed'], answer: 1 },
        { q: 'Autonomous Maintenance Step 3 "Create cleaning and inspection standards" produces:', options: ['A list of equipment that needs replacement', 'Documented standards with photos — what, how, who, and frequency — so cleaning is consistent across all shifts', 'A training schedule for operators', 'A maintenance budget request'], answer: 1 },
        { q: 'The correct sequence in Theory of Constraints when a bottleneck is improved and capacity increases is:', options: ['Stop — the problem is solved', 'Identify the new bottleneck and repeat the improvement cycle', 'Increase production targets to consume the new capacity', 'Reduce the number of workers'], answer: 1 },
      ]
    },
    5: {
      title: 'Lean, Six Sigma, and Production System Design',
      module: `
<h3>Lean Manufacturing Principles</h3>
<p>Lean is the systematic elimination of waste (Muda) to create more value with fewer resources. The 5 Lean principles: (1) Specify value from the customer's perspective, (2) Map the value stream and identify waste, (3) Create flow — eliminate stoppages between steps, (4) Establish pull — produce only what is needed when needed, (5) Pursue perfection — continuous improvement never ends. Lean is not a tool — it is a philosophy.</p>
<h3>Six Sigma — DMAIC</h3>
<p>Six Sigma reduces process variation to achieve defect rates below 3.4 per million opportunities (6σ). The DMAIC methodology: Define (the problem and project scope), Measure (current performance — baseline data), Analyze (find root causes using statistical tools), Improve (design and implement the solution), Control (sustain the improvement with control charts and SOPs). A Six Sigma black belt leads projects; green belts support.</p>
<h3>Value Stream Mapping (VSM)</h3>
<p>VSM maps the current state of material and information flow from raw material to customer. It identifies: total cycle time, value-added time (actual transformation), non-value-added time (transport, waiting, inspection), and inventory levels between steps. The future state map shows what the process should look like after waste elimination. VSM is the diagnostic tool that prioritizes improvement projects.</p>
<h3>Production System Design for Industrial Plants</h3>
<p>Key design decisions: process layout (product layout = sequential flow for high-volume, process layout = grouped machines for low-volume high-mix), cell manufacturing (U-shaped cells for flexible one-piece flow), material handling (minimize distances, use gravity where possible), and poka-yoke (error-proofing) — design processes so mistakes are physically impossible or immediately obvious.</p>`,
      exam: [
        { q: 'The 5 Lean principles begin with:', options: ['Eliminate waste', 'Specify value from the customer\'s perspective', 'Create flow in the process', 'Map the value stream'], answer: 1 },
        { q: 'Six Sigma targets defect rates below:', options: ['1 per thousand', '100 per million', '3.4 per million opportunities', '1 per million'], answer: 2 },
        { q: 'In DMAIC, the "Analyze" phase uses statistical tools to:', options: ['Define the project scope', 'Find the root causes of the problem — not just the symptoms', 'Measure the baseline performance', 'Implement the solution'], answer: 1 },
        { q: 'Value Stream Mapping distinguishes between value-added and non-value-added time to:', options: ['Calculate total labor cost', 'Identify where waste exists — the non-value-added time is the improvement opportunity', 'Satisfy ISO 9001 requirements', 'Calculate the shift schedule'], answer: 1 },
        { q: 'Poka-yoke (error-proofing) is a design principle that:', options: ['Catches defects before they reach the customer', 'Makes mistakes physically impossible or immediately obvious — preventing defects from occurring', 'Adds an inspection step before packaging', 'Trains operators to be more careful'], answer: 1 },
        { q: 'A U-shaped manufacturing cell is designed to enable:', options: ['Maximum machine speed', 'One-piece flow with flexible operator assignment and minimum transport distance', 'Mass production of a single product', 'Separation of inspection from production'], answer: 1 },
        { q: 'A "pull" system in Lean production means:', options: ['Management pulls reports from the production team', 'Production is triggered by actual customer demand — not production forecasts', 'Materials are pulled from a central warehouse daily', 'Workers pull their own overtime approvals'], answer: 1 },
        { q: 'A Six Sigma green belt\'s role is typically:', options: ['Lead black belt projects independently', 'Support black belt projects and lead smaller focused improvement projects', 'Approve investment decisions', 'Manage the production team'], answer: 1 },
        { q: 'In Value Stream Mapping, an "inventory triangle" icon between process steps represents:', options: ['A quality hold area', 'Inventory (WIP) accumulating between steps — a sign of imbalance or push production', 'Raw material storage', 'A FIFO lane'], answer: 1 },
        { q: 'Process layout (grouped machines) is most appropriate for:', options: ['High-volume, low-mix production', 'Low-volume, high-mix production where many different products share the same machines', 'Automated assembly lines only', 'Any production regardless of volume or mix'], answer: 1 },
      ]
    },
  },

}; // end SKILL_CONTENT
