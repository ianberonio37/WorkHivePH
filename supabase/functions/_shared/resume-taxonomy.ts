/**
 * resume-taxonomy.ts - Deterministic resume lexicons vendored from open sources.
 *
 * The Resume Builder's quality levers that should NOT depend on a probabilistic
 * model live here as static data (WAT: deterministic execution, not LLM judgement).
 * Curated (NOT dumped wholesale) from public, openly-licensed sources:
 *   - O*NET / O*NET-SOC (US Dept. of Labor, public domain) industrial-maintenance
 *     task + skill vocabulary - https://www.onetonline.org
 *   - ESCO (EU, CC-BY) skills + occupations - https://esco.ec.europa.eu
 *   - open-resume + common resume-parser projects: section-header synonyms and
 *     action-verb lists - https://github.com/xitanggg/open-resume
 *
 * A FOCUSED maintenance/industrial lexicon beats a 10k-term dump for both token
 * cost and precision. Used by resume-extract (section-aware chunk splitting,
 * skill canonicalization, project-verb mining). The MAINTENANCE_SKILLS list is
 * mirrored into resume.html's offline JD dictionary (no build step in this repo,
 * so the mirror is intentional - keep the two in sync; validate_resume.py guards it).
 *
 * No em dashes anywhere in this file (they garble as 3 chars under Windows-1252).
 */

// Canonical CASING for skills/acronyms. Key = the lowercased form the source text
// may use; value = how it should read on a resume. This is normalization ONLY: it
// never invents a skill, it only fixes the case of one already extracted, so
// "plc"/"Plc"/"PLC" all collapse to "PLC" and dedupe + JD-match line up.
export const SKILL_CANON: Record<string, string> = {
  plc: "PLC", vfd: "VFD", hmi: "HMI", scada: "SCADA", dcs: "DCS", io: "I/O",
  cmms: "CMMS", erp: "ERP", sap: "SAP", "sap pm": "SAP PM", maximo: "Maximo",
  oee: "OEE", mtbf: "MTBF", mttr: "MTTR", mtta: "MTTA", fmea: "FMEA", fmeca: "FMECA",
  rca: "RCA", rcm: "RCM", tpm: "TPM", "5s": "5S", "6s": "6S", kaizen: "Kaizen",
  loto: "LOTO", ptw: "PTW", jsa: "JSA", "lockout tagout": "Lockout/Tagout",
  hvac: "HVAC", "ac/dc": "AC/DC", "p&id": "P&ID", "pid": "PID", ddc: "DDC",
  tesda: "TESDA", "nc i": "NC I", "nc ii": "NC II", "nc iii": "NC III", "nc iv": "NC IV",
  iso: "ISO", "iso 9001": "ISO 9001", "iso 14001": "ISO 14001", "iso 45001": "ISO 45001",
  "iso 50001": "ISO 50001", "iso 55000": "ISO 55000", gmp: "GMP", haccp: "HACCP",
  autocad: "AutoCAD", solidworks: "SolidWorks", inventor: "Inventor", revit: "Revit",
  "ms office": "MS Office", excel: "Excel", "ms excel": "MS Excel",
  opc: "OPC", "opc-ua": "OPC-UA", mqtt: "MQTT", modbus: "Modbus", profibus: "Profibus",
  profinet: "PROFINET", ethernet: "Ethernet", ethercat: "EtherCAT",
  ups: "UPS", ats: "ATS", mcc: "MCC", mdb: "MDB", avr: "AVR", "vsd": "VSD",
  npn: "NPN", led: "LED", igbt: "IGBT", pwm: "PWM", rtd: "RTD", plc5: "PLC-5",
  cbm: "Condition-Based Maintenance", pdm: "Predictive Maintenance",
  pm: "Preventive Maintenance", spc: "SPC", kpi: "KPI", sla: "SLA", wo: "Work Order",
};

// Industrial / maintenance skills lexicon (curated from O*NET 49-9041/49-9071
// Industrial + Maintenance & Repair occupations and ESCO maintenance skills).
// Lowercased; matched as whole terms by the offline JD-keyword fallback and used
// to keep skill blocks intact while splitting. KEEP IN SYNC with resume.html _JD_DICT.
export const MAINTENANCE_SKILLS: string[] = [
  // strategies / methodologies
  "preventive maintenance", "predictive maintenance", "corrective maintenance",
  "condition monitoring", "condition-based maintenance", "reliability-centered maintenance",
  "total productive maintenance", "root cause analysis", "failure analysis",
  "reliability engineering", "asset management", "planned maintenance", "shutdown maintenance",
  "turnaround maintenance", "breakdown maintenance", "autonomous maintenance",
  // condition techniques
  "vibration analysis", "thermography", "infrared thermography", "ultrasonic testing",
  "oil analysis", "tribology", "laser alignment", "balancing", "non-destructive testing",
  // mechanical
  "troubleshooting", "calibration", "alignment", "lubrication", "rigging", "fabrication",
  "machining", "welding", "brazing", "soldering", "fitting", "pipefitting", "millwright",
  "bearings", "gearbox", "couplings", "seals", "belts", "chains", "conveyor", "actuators",
  "pumps", "compressors", "blowers", "fans", "valves", "boiler", "turbine", "hydraulics",
  "pneumatics", "lubrication systems", "cooling tower", "chiller", "heat exchanger",
  // electrical / instrumentation
  "electrical", "mechanical", "instrumentation", "automation", "controls", "wiring",
  "motor controls", "switchgear", "transformers", "power distribution", "grounding",
  "plc", "vfd", "hmi", "scada", "dcs", "servo", "drives", "sensors", "transmitters",
  "control panels", "loop tuning", "panel wiring", "relay logic", "ladder logic",
  // systems / software
  "cmms", "sap", "sap pm", "maximo", "erp", "autocad", "ms office", "excel",
  // facilities / utilities
  "hvac", "refrigeration", "fire protection", "plumbing", "generator", "ups",
  "air compressor", "steam systems", "water treatment", "electrical safety",
  // metrics / quality
  "oee", "mtbf", "mttr", "fmea", "rcm", "tpm", "5s", "kaizen", "six sigma", "lean",
  "spc", "kpi", "gmp", "haccp", "iso 9001", "iso 14001", "iso 45001", "iso 50001",
  // safety / compliance
  "lockout tagout", "loto", "permit to work", "job safety analysis", "risk assessment",
  "confined space", "working at heights", "hot work", "occupational safety",
  // certs / domain
  "tesda", "electrical permit", "boiler operator", "welding certification",
  // soft / planning
  "preventive scheduling", "work order management", "spare parts management",
  "inventory management", "shift handover", "team leadership", "supervision",
  "training", "documentation", "standard operating procedures", "commissioning",
];

// Strong, past-tense resume action verbs (open-resume / standard recruiter lists).
// The subset that signals a bounded INITIATIVE (vs a routine duty) when paired
// with a project noun - this seeds the resume-extract project miner.
export const PROJECT_ACTION_VERBS: string[] = [
  "spearheaded", "led", "implemented", "deployed", "rolled out", "designed",
  "engineered", "established", "launched", "commissioned", "retrofitted", "built",
  "developed", "introduced", "drove", "piloted", "standardized", "standardised",
  "automated", "migrated", "upgraded", "overhauled", "redesigned", "modernized",
  "modernised", "reengineered", "instituted", "orchestrated", "pioneered",
  "transformed", "revamped", "consolidated", "integrated",
];

// Section-header synonyms an ATS recognizes (open-resume taxonomy + common
// variants, incl. Filipino-resume usage). Used to detect a real section boundary
// so the long-resume splitter never cuts a single job entry across two chunks.
export const SECTION_HEADERS: Record<string, string[]> = {
  summary: ["summary", "professional summary", "career summary", "profile",
    "career objective", "objective", "about me", "personal profile"],
  experience: ["experience", "work experience", "professional experience",
    "employment history", "employment", "work history", "career history",
    "relevant experience", "professional background"],
  education: ["education", "educational background", "academic background",
    "academic qualifications", "educational attainment", "qualifications"],
  skills: ["skills", "technical skills", "core competencies", "competencies",
    "key skills", "areas of expertise", "technical proficiencies", "skill set"],
  certificates: ["certificates", "certifications", "licenses", "licences",
    "certifications and licenses", "trainings", "training", "seminars",
    "professional development", "credentials", "tesda certifications"],
  projects: ["projects", "key projects", "major projects", "project experience",
    "notable projects", "engineering projects"],
  awards: ["awards", "honors", "honours", "achievements", "accomplishments",
    "recognitions", "awards and recognition", "awards and honors"],
  references: ["references", "character references", "professional references"],
};

// One line is (probably) a section header if, after trimming punctuation, it is
// short and equals a known synonym. Built once from SECTION_HEADERS.
const _ALL_HEADERS = new Set(
  Object.values(SECTION_HEADERS).flat().map((h) => h.toLowerCase()),
);
export function isSectionHeaderLine(line: string): boolean {
  const t = line.trim().toLowerCase().replace(/[:.\-_=*#>]+$/g, "").replace(/^[#>*\-=\s]+/, "").trim();
  if (!t || t.length > 40) return false;
  return _ALL_HEADERS.has(t);
}

// Canonicalize a skill's CASING only (acronyms uppercased, known terms title-cased
// via the map). Returns the input unchanged when nothing is known - never invents.
export function canonicalizeSkill(name: string): string {
  const raw = String(name || "").trim();
  if (!raw) return raw;
  const low = raw.toLowerCase().replace(/\s+/g, " ");
  if (SKILL_CANON[low]) return SKILL_CANON[low];
  // single-token, short, all letters/digits -> likely an acronym the worker typed
  // in lower/mixed case ("plc programming" stays, "plc" -> "PLC").
  if (!low.includes(" ") && low.length <= 4 && SKILL_CANON[low]) return SKILL_CANON[low];
  return raw;
}
