// asset-codes.ts - "does this question name an asset code, and is it one of this hive's?" (2026-10-07)
//
// Found by the LLM layer's Grounding walk (§LM.2). Asked about an asset code that exists nowhere ("ZQX 9471"), two AI
// surfaces failed in two different ways: the asset brain described the asset its 360 view had open AS IF it were the
// code asked about (LM112, a fabrication), and the Work Assistant answered "I couldn't pull that from your hive just
// now", a retrieval excuse for a machine that simply is not registered (LM113). Both functions hold the hive's
// registered tag list a single query away, so "is this a real asset here?" is answered in CODE, never by the model.
//
// An asset code is letters + digits ("ZQX 9471", "BF-002", "FLT 9004"). Standards, bearing brands and regulations
// that share the shape ("ISO 10816", "SKF 6205", "RA 11285") are not asset codes.

export const CODE_STOP = new Set(["ISO", "IEC", "PEC", "NFPA", "ASTM", "API", "ANSI", "IEEE", "SKF", "NSK", "FAG", "NTN",
  "TIMKEN", "PSME", "DOLE", "OSHA", "NEMA", "DIN", "JIS", "AWS", "ASME", "SAE", "SMRP", "RA", "PD", "BS", "EN", "UL"]);

export const normCode = (s: string): string => String(s || "").toLowerCase().replace(/[\s_-]+/g, "");

/** The asset-code-shaped tokens a question names, de-duplicated, excluding `excludeTag` (e.g. the asset already open). */
export function mentionedAssetCodes(question: string, excludeTag = ""): string[] {
  const skip = normCode(excludeTag);
  const out: string[] = [];
  for (const m of String(question || "").matchAll(/\b([A-Za-z]{2,5})[\s-]?(\d{3,5})\b/g)) {
    if (CODE_STOP.has(m[1].toUpperCase())) continue;
    if (skip && normCode(m[0]) === skip) continue;
    if (!out.some((c) => normCode(c) === normCode(m[0]))) out.push(m[0]);
  }
  return out;
}
