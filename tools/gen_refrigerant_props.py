"""Generate the refrigerant property tables for python-api/calcs/refrigerant_pipe.py from CoolProp (run locally;
the engine ships the static result). Suction at +10 K superheat; liquid saturated at T_cond (no subcooling, the
conservative case for mass flow); discharge at the compressor outlet with isentropic efficiency 0.70."""
from CoolProp.CoolProp import PropsSI
import CoolProp

NAMES = {"R-410A": "R410A", "R-32": "R32", "R-22": "R22", "R-134a": "R134a", "R-407C": "R407C"}
EVAP = [5, -10, -35]
COND = [40, 45, 50]
K = 273.15
SH = 10.0
ETA_IS = 0.70


def dpdt(cp, t):
    return (PropsSI("P", "T", t + 0.5 + K, "Q", 1, cp) - PropsSI("P", "T", t - 0.5 + K, "Q", 1, cp)) / 1000


out = [f"# generated {CoolProp.__version__} - see the comment above REFRIG_PROPS"]
lines = ["REFRIG_PROPS: dict[str, dict] = {"]
for ref, cp in NAMES.items():
    lines.append(f'    "{ref}": {{')
    lines.append('        "evap": {')
    for te in EVAP:
        P = PropsSI("P", "T", te + K, "Q", 1, cp)
        rho = PropsSI("D", "T", te + SH + K, "P", P, cp)
        hfg = (PropsSI("H", "T", te + K, "Q", 1, cp) - PropsSI("H", "T", te + K, "Q", 0, cp)) / 1000
        lines.append(f'            {te:>3}: {{"h_fg_kJkg": {hfg:6.1f}, "rho_vap": {rho:6.2f}, "dpdt_kPaK": {dpdt(cp, te):6.2f}}},')
    lines.append("        },")
    lines.append('        "cond": {')
    for tc in COND:
        rl = PropsSI("D", "T", tc + K, "Q", 0, cp)
        lines.append(f'            {tc}: {{"rho_liq": {rl:7.1f}, "dpdt_kPaK": {dpdt(cp, tc):6.2f}}},')
    lines.append("        },")
    lines.append('        "pair": {   # "evap/cond": refrigerating effect (kJ/kg) and discharge vapour density (kg/m3)')
    for te in EVAP:
        Pe = PropsSI("P", "T", te + K, "Q", 1, cp)
        h1 = PropsSI("H", "T", te + SH + K, "P", Pe, cp)
        s1 = PropsSI("S", "T", te + SH + K, "P", Pe, cp)
        for tc in COND:
            Pc = PropsSI("P", "T", tc + K, "Q", 1, cp)
            h2s = PropsSI("H", "P", Pc, "S", s1, cp)
            h2 = h1 + (h2s - h1) / ETA_IS
            rho_d = PropsSI("D", "P", Pc, "H", h2, cp)
            t_d = PropsSI("T", "P", Pc, "H", h2, cp) - K
            re = (h1 - PropsSI("H", "T", tc + K, "Q", 0, cp)) / 1000
            lines.append(f'            "{te}/{tc}": {{"RE_kJkg": {re:6.1f}, "rho_vap_dis": {rho_d:6.2f}, "t_dis_c": {t_d:5.1f}}},')
    lines.append("        },")
    lines.append("    },")
lines.append("}")
print("\n".join(out + lines))
