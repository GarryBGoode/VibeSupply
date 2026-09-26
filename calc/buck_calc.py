"""
Power-stage calculations for the USB-C PD bench supply (see PLAN.md) — 140 W USB / 10 A, fanless.

Run:   .venv/Scripts/python calc/buck_calc.py
Output: calc/results.md (overwritten every run)

All part parameters come from datasheets unless marked ASSUMPTION. The loss model is a
first-order analytic estimate (expect +-30 %); the loop section is a sanity check before LTspice,
not a replacement for it. The pre-pivot 240 W / 20 A version of this script is in git (d8d0a65).
"""

from dataclasses import dataclass
from pathlib import Path
import math

import numpy as np

OUT = Path(__file__).with_name("results.md")
lines: list[str] = []


def out(s: str = "") -> None:
    lines.append(s)


def table(header: list[str], rows: list[list]) -> None:
    out("| " + " | ".join(header) + " |")
    out("|" + "|".join("---" for _ in header) + "|")
    for r in rows:
        out("| " + " | ".join(str(c) for c in r) + " |")
    out()


# --------------------------------------------------------------------------------------------
# Parts
# --------------------------------------------------------------------------------------------

@dataclass
class Fet:
    name: str
    pkg: str
    rds_max: float      # ohm @ 25 C, at the gate drive actually used (4.5 V for the buck, 10 V for static switches)
    qg: float           # C, total at that gate drive (typ)
    qgd: float          # C
    qgs: float          # C
    qg_th: float        # C
    qoss: float         # C
    qrr_hi: float       # C, body-diode Qrr at ~1000 A/us (what a hard-switched buck sees), see QRR NOTE
    rg: float           # ohm internal (typ)
    rth_jc: float       # K/W (bottom/case)
    vpl: float          # V, gate plateau


# QRR NOTE: Qrr depends strongly on the test di/dt. Infineon's ISC030N10NM6 lists 56 nC @100 A/us and 266 nC @1000 A/us
# (x4.75 per decade -> exponent ~0.68). In this buck the top FET's current rises in a few ns, so the bottom FET's diode
# recovers at >=1000 A/us. TI specifies Qrr at 300 A/us; it is scaled with the same exponent (ASSUMPTION).
def qrr_scale(q, didt):
    return q * (1000 / didt) ** 0.68


# TI 60 V NexFET, SON 5x6 (datasheets/csd185*.pdf). Rds(on) max and Qg at VGS = 4.5 V (the LTC7803 drives 5 V).
# rth_jc ~1 K/W and the ~2.8 V plateau are read off typical curves (ASSUMPTION).
FETS = {
    "CSD18540Q5B": Fet("CSD18540Q5B", "SON5x6", 3.3e-3, 20e-9, 6.7e-9, 8.8e-9, 6.3e-9, 83e-9, qrr_scale(145e-9, 300), 0.8, 1.0, 2.8),
    "CSD18532Q5B": Fet("CSD18532Q5B", "SON5x6", 4.3e-3, 22e-9, 6.9e-9, 10e-9, 6.3e-9, 52e-9, qrr_scale(111e-9, 300), 1.2, 1.0, 2.8),
    "CSD18531Q5A": Fet("CSD18531Q5A", "SON5x6", 5.8e-3, 18e-9, 5.9e-9, 6.9e-9, 5.2e-9, 32e-9, qrr_scale(100e-9, 300), 1.2, 1.0, 2.9),
    "CSD18563Q5A": Fet("CSD18563Q5A", "SON5x6", 10.8e-3, 7.3e-9, 2.9e-9, 3.3e-9, 2.3e-9, 36e-9, qrr_scale(63e-9, 300), 1.5, 1.6, 3.0),
    "CSD18534Q5A": Fet("CSD18534Q5A", "SON5x6", 12.4e-3, 8.5e-9, 3.5e-9, 3.2e-9, 2.6e-9, 19e-9, qrr_scale(54e-9, 300), 1.5, 1.6, 3.0),
    # static-only use (output switch, input paths; ~8-10 V gate from VOM1271 / LM74800 charge pump): only Rds matters.
    "CSD18540Q5B@10V": Fet("CSD18540Q5B@10V", "SON5x6", 2.2e-3, 41e-9, 0, 0, 0, 0, 0, 0.8, 1.0, 2.8),
}

RDS_HOT = 1.45        # Rds(on) multiplier at Tj ~ 100 C (normalized-Rds curves)
K_QRR = 0.5           # ASSUMPTION: fraction of the ~1000 A/us Qrr actually recovered (short ~30 ns dead time)

# LTC7803 (datasheets/ltc7803.pdf, Rev. B)
VDRV = 5.15           # INTVCC regulated by the EXTVCC LDO (EXTVCC from the 12 V aux rail; a 5 V feed leaves it in dropout — see sim t088)
R_TG_PU, R_TG_PD = 3.0, 1.5
R_BG_PU, R_BG_PD = 3.0, 1.5
T_DEAD = 15e-9 + 15e-9     # TG-off->BG-on + BG-off->TG-on (typ, 3.3 nF load)
TON_MIN = 40e-9
VSENSE_MAX = (45e-3, 50e-3, 55e-3)   # min/typ/max, specified at VFB = 0.7 V
# ITH->average inductor current: 17.8 A/V at 2.5 mΩ, measured on the LTC7803 LTspice model at low duty (sim t0_ith_probe).
A_CS = 1 / (17.8 * 2.5e-3)
V_BIAS = 12.0         # EXTVCC from the 12 V aux rail (must be >= ~7 V: with 5 V the boost supply sags and the LTC7803 can stall, sim/results.md)

# Inductor: Coilcraft SER2918H-103KL (LCSC C3911665): 10 µH ±10 %, DCR 2.86 mΩ max, Isat 32.1 A, Irms 28 A (40 K rise).
# Same body and footprint as the SER2918H-682KL of the 20 A design.
L_NAME = "Coilcraft SER2918H-103KL"
L = 10e-6
L_ISAT = 32.1
L_DCR = 2.86e-3 * 1.3          # max @20 C, x1.3 for ~100 C copper
L_CORE_W = 0.3                 # ASSUMPTION: core loss at 300 kHz / ~2.6 A pp, check with the Coilcraft loss calculator

R_SENSE = 2.0e-3               # controller current-sense shunt (2x 4 mΩ 2512 in parallel); 2.5 mΩ ran out of current at D ≈ 0.9 in LTspice
R_OUT_SHUNT = 1.0e-3           # output shunt (INA228 metering)
R_IN_SHUNT = 1.0e-3            # input shunt (INA228)
R_POSTL = 1.7e-3               # post-filter inductor FXL1040-R47-M: 470 nH, 1.7 mΩ, 30 A (kept from the 20 A design)
R_FUSE = 4.0e-3                # ASSUMPTION: 15 A 58 V blade fuse, cold resistance (to pick)
OUT_SWITCH = FETS["CSD18540Q5B@10V"]  # x2 back-to-back (VOM1271 photovoltaic driver, ~8 V gate)
IN_FET = FETS["CSD18540Q5B@10V"]      # x2 back-to-back per input (LM74800)
P_HOUSEKEEPING = 2.0           # W: MCU, display, INAs, isolated USB, aux bucks (no fan any more)

# --------------------------------------------------------------------------------------------
# Loss model
# --------------------------------------------------------------------------------------------

@dataclass
class Point:
    name: str
    vin: float
    vout: float
    iout: float
    src: str      # "PD" or "DC"


# USB-C: 28 V / 5 A EPR (140 W in). DC: up to 30 V, OV lockout at ~31 V; 31 V is the worst case the stage must handle.
POINTS = [
    Point("PD 28->3.3 V 10 A", 28, 3.3, 10, "PD"),
    Point("PD 28->12 V 10 A", 28, 12, 10, "PD"),
    Point("PD 28->24 V 5.2 A", 28, 24, 5.2, "PD"),
    Point("PD 28->26.5 V 4.7 A", 28, 26.5, 4.7, "PD"),
    Point("DC 31->1 V 10 A", 31, 1.0, 10, "DC"),
    Point("DC 31->15.5 V 10 A", 31, 15.5, 10, "DC"),
    Point("DC 30->27 V 10 A", 30, 27, 10, "DC"),
    Point("DC 24->12 V 10 A", 24, 12, 10, "DC"),
]


def ripple(vin, vout, f, l=L):
    d = vout / vin
    return (vin - vout) * d / (l * f), d


def switch_times(fet: Fet):
    qgs2 = fet.qgs - fet.qg_th
    i_on = (VDRV - fet.vpl) / (R_TG_PU + fet.rg)
    i_off = fet.vpl / (R_TG_PD + fet.rg)
    return (qgs2 + fet.qgd) / i_on, (qgs2 + fet.qgd) / i_off


def losses(p: Point, f: float, hs: Fet, ls: Fet, l=L) -> dict:
    di, d = ripple(p.vin, p.vout, f, l)
    i = p.iout
    i_rms2 = i**2 + di**2 / 12
    i_pk, i_val = i + di / 2, max(i - di / 2, 0.0)
    t_on, t_off = switch_times(hs)

    hs_cond = i_rms2 * hs.rds_max * RDS_HOT * d
    hs_sw = 0.5 * p.vin * (i_val * t_on + i_pk * t_off) * f
    hs_oss = 0.5 * (hs.qoss + ls.qoss) * p.vin * f
    hs_rr = K_QRR * ls.qrr_hi * p.vin * f
    ls_cond = i_rms2 * ls.rds_max * RDS_HOT * (1 - d)
    ls_dead = 0.8 * i * T_DEAD * f
    gate_drv = (hs.qg + ls.qg) * V_BIAS * f          # drawn from the 12 V aux rail via EXTVCC

    p_ind = i_rms2 * L_DCR + L_CORE_W
    p_rsense = i_rms2 * R_SENSE
    p_out_sw = i**2 * 2 * OUT_SWITCH.rds_max * 1.3
    p_outpath = i**2 * (R_OUT_SHUNT + R_POSTL + R_FUSE) + p_out_sw

    pout = p.vout * i
    p_hs = hs_cond + hs_sw + hs_oss + hs_rr
    p_ls = ls_cond + ls_dead
    stage = p_hs + p_ls + gate_drv + p_ind + p_rsense + p_outpath + P_HOUSEKEEPING
    iin = (pout + stage) / p.vin
    p_inpath = iin**2 * (R_IN_SHUNT + 2 * IN_FET.rds_max * 1.3)
    total = stage + p_inpath
    return dict(d=d, di=di, i_pk=i_pk, hs_cond=hs_cond, hs_sw=hs_sw, hs_oss=hs_oss, hs_rr=hs_rr,
                p_hs=p_hs, p_ls=p_ls, gate=gate_drv, p_ind=p_ind, p_rsense=p_rsense,
                p_outpath=p_outpath, p_out_sw=p_out_sw, p_inpath=p_inpath, total=total,
                pout=pout, pin=pout + total, iin=(pout + total) / p.vin,
                eff=pout / (pout + total) * 100, ton=d / f)


# --------------------------------------------------------------------------------------------
out("# Power-stage calculations — results")
out()
out("Generated by `calc/buck_calc.py` — do not edit by hand; change the script and re-run.")
out("First-order analytic estimates (±30 %). Values marked ASSUMPTION in the script need confirming.")
out("Design: 140 W USB-C (28 V / 5 A) or ≤ 30 V DC in, 0–27 V / 0–10 A out, LTC7803, 60 V logic-level FETs, fanless.")
out()

# ---- 1. frequency / FET comparison at the hardest points --------------------------------
out("## 1. Switching frequency and FET choice")
out()
out("Total loss (W) at the hardest points, top-FET share in brackets. hs = high-side (top) FET, ls = low-side (bottom) FET.")
out()
combos = [("CSD18540Q5B", "CSD18540Q5B"), ("CSD18532Q5B", "CSD18532Q5B"), ("CSD18531Q5A", "CSD18531Q5A"),
          ("CSD18531Q5A", "CSD18540Q5B"), ("CSD18563Q5A", "CSD18540Q5B"), ("CSD18534Q5A", "CSD18540Q5B")]
freqs = [200e3, 300e3, 400e3]
hard = [POINTS[1], POINTS[5], POINTS[6]]
rows = []
for hsn, lsn in combos:
    for f in freqs:
        r = [f"{hsn} / {lsn}", f"{f/1e3:.0f} kHz"]
        for p in hard:
            l = losses(p, f, FETS[hsn], FETS[lsn])
            r.append(f"{l['total']:.1f} ({l['p_hs']:.1f})")
        rows.append(r)
table(["hs / ls FET", "fsw"] + [p.name for p in hard], rows)

F_SW = 300e3
HS, LS = FETS["CSD18531Q5A"], FETS["CSD18531Q5A"]
out(f"**Chosen: fsw = {F_SW/1e3:.0f} kHz, hs = ls = {HS.name}** (TI 60 V NexFET, SON 5×6, specified at VGS = 4.5 V).")
out("- Lowest loss at every hard point. The bottom FET's Qoss and Qrr are dissipated in the *top* FET, so a low-charge bottom FET")
out("  (CSD18531Q5A: Qoss 32 nC, Qrr 100 nC @300 A/µs) beats a low-Rds(on) one (CSD18540Q5B: 83 nC / 145 nC). One part number for both.")
out("- LCSC stock is thin (TI original C2876524: 35 pcs); the pin-compatible-class CSD18532Q5B (302 pcs) costs ~0.2 W more.")
out("- 300 kHz, not 200 kHz: 200 kHz would save ~0.8 W, but in LTspice the LTC7803 then shows period doubling (sub-harmonic")
out("  oscillation) above ~80 % duty. Its internal slope-compensation ramp is a fixed voltage per cycle, so a lower frequency")
out("  means a slower ramp against the same inductor down-slope (sim/results.md).")
out("- 5 V gate drive (LTC7803 TG pull-up 3 Ω) makes the transitions slower than with the LTC7801's 10 V drive; Qrr and V·I switching")
out("  are the biggest top-FET terms.")
out()

# ---- 2. operating points ------------------------------------------------------------------
out(f"## 2. Operating points (fsw = {F_SW/1e3:.0f} kHz, {HS.name} / {LS.name}, {L*1e6:.0f} µH)")
out()
rows = []
for p in POINTS:
    l = losses(p, F_SW, HS, LS)
    rows.append([p.name, f"{p.vout*p.iout:.0f}", f"{l['d']*100:.0f} %", f"{l['di']:.1f}", f"{l['i_pk']:.1f}",
                 f"{l['p_hs']:.2f}", f"{l['p_ls']:.2f}", f"{l['p_ind']:.2f}", f"{l['p_rsense']+l['p_outpath']:.2f}",
                 f"{l['p_inpath']:.2f}", f"{l['total']:.1f}", f"{l['eff']:.1f} %", f"{l['iin']:.2f}"])
table(["Point", "Pout W", "D", "ΔIL pp A", "IL pk A", "top FET W", "bot FET W", "L W", "shunts+out path W",
       "in path W", "total W", "eff", "Iin A"], rows)

pw = POINTS[6]
l = losses(pw, F_SW, HS, LS)
out(f"Top-FET loss breakdown at {pw.name} (W): conduction {l['hs_cond']:.2f}, V·I switching {l['hs_sw']:.2f}, "
    f"Qoss {l['hs_oss']:.2f}, Qrr {l['hs_rr']:.2f} (K_QRR = {K_QRR}). "
    f"Gate drive: {(HS.qg+LS.qg)*F_SW*1e3:.0f} mA from the 12 V aux rail via EXTVCC.")
out()
pd_pts = [p for p in POINTS if p.src == "PD"]
out("Notes:")
out(f"- PD points: the input is limited to 28 V × 5 A = 140 W, so the PD points above {pd_pts[1].vout:.0f} V run at reduced current "
    f"(≈ {POINTS[2].iout} A at 24 V, {POINTS[3].iout} A at 26.5 V). The PD input current stays ≤ 5 A in all of them "
    f"({max(losses(p, F_SW, HS, LS)['iin'] for p in pd_pts):.2f} A max).")
out("- Housekeeping (2 W) is included in every total, so the buck itself is ~2 W less.")
out()

# ---- 3. thermal (fanless) ---------------------------------------------------------------------
out("## 3. Thermal — fanless, the aluminium extrusion is the heatsink")
out()
T_AMB = 30.0                   # C, bench room (ASSUMPTION)
ENCL_DIM = (0.15, 0.10, 0.06)  # m, ASSUMPTION: ~150 × 100 × 60 mm extrusion + panels
H_CONV_RAD = 9.0               # W/(m² K), natural convection + radiation, anodized/painted surface (ASSUMPTION; bare Al ≈ 5–6)
a, b, c = ENCL_DIM
A_ENCL = 2 * (a * b + a * c + b * c)
RTH_ENCL = 1 / (H_CONV_RAD * A_ENCL)
# junction -> extrusion for an SON 5x6 FET on the bottom side of the board, pressed onto the extrusion floor:
RTH_VIAS = 4.0                 # K/W, thermal-via array under the drain pad through 1.6 mm FR4 (ASSUMPTION, ~30× 0.3 mm vias)
RTH_PAD = 1.5                  # K/W, gap pad ~1 mm, ~2 × 2 cm, 3 W/mK (ASSUMPTION)
RTH_J_ENCL = HS.rth_jc + RTH_VIAS + RTH_PAD
P_CLAMP_AVG = 10.0             # W, regen clamp average limit (agreed rating, firmware-enforced)

worst = max((losses(p, F_SW, HS, LS) for p in POINTS), key=lambda x: x["total"])
worst_hs = max(losses(p, F_SW, HS, LS)["p_hs"] for p in POINTS)
worst_ls = max(losses(p, F_SW, HS, LS)["p_ls"] for p in POINTS)
out(f"Model: all heat ends up in the extrusion, which sheds it to the room: Rθ(enclosure→ambient) = 1/(h·A) = "
    f"1/({H_CONV_RAD:.0f} W/m²K × {A_ENCL:.3f} m²) ≈ **{RTH_ENCL:.1f} K/W** "
    f"(ASSUMPTION: {a*1e3:.0f}×{b*1e3:.0f}×{c*1e3:.0f} mm, anodized or painted; bare aluminium radiates poorly → ~1.5× worse).")
out(f"FET junction → extrusion ≈ {HS.rth_jc:.0f} (jc) + {RTH_VIAS:.0f} (via array) + {RTH_PAD:.1f} (gap pad) = "
    f"**{RTH_J_ENCL:.1f} K/W** (ASSUMPTION). Ambient {T_AMB:.0f} °C.")
out()
rows = []
for label, p_tot in [("Worst continuous buck load, no regen", worst["total"]),
                     ("Typical heavy use (half the worst loss)", worst["total"] / 2),
                     (f"Worst buck load + clamp at its {P_CLAMP_AVG:.0f} W average", worst["total"] + P_CLAMP_AVG),
                     ("Clamp 10 W average only (regen, buck idle)", P_HOUSEKEEPING + P_CLAMP_AVG)]:
    t_encl = T_AMB + p_tot * RTH_ENCL
    tj_hs = t_encl + worst_hs * RTH_J_ENCL
    rows.append([label, f"{p_tot:.1f}", f"{t_encl:.0f}", f"{tj_hs:.0f}"])
table(["Case", "Heat W", "Extrusion °C", "Top FET Tj °C"], rows)
out(f"- Worst FET losses: top {worst_hs:.2f} W, bottom {worst_ls:.2f} W → only ~{worst_hs*RTH_J_ENCL:.0f} K above the extrusion. "
    "The FETs are not the problem; **the enclosure surface temperature is**.")
out(f"- Continuous worst-case buck load: extrusion ≈ {T_AMB + worst['total']*RTH_ENCL:.0f} °C — warm, acceptable.")
out(f"- Adding the clamp's {P_CLAMP_AVG:.0f} W average on top pushes the extrusion to ≈ {T_AMB + (worst['total']+P_CLAMP_AVG)*RTH_ENCL:.0f} °C: "
    "too hot to touch comfortably (metal surfaces ≲ 60 °C).")
out("  → Firmware should derate the clamp's average from the enclosure NTC, not a fixed 10 W (e.g. 10 W while the extrusion < 45 °C,"
    " tapering to ~3 W at 55 °C). Bursts (50 W / 10 s = 500 J) are fine: ~0.3–0.5 kg of aluminium rises only 1–2 K.")
out("- Parts that go on the extrusion side: both buck FETs, the clamp FET, the clamp resistor (TO-247, screwed directly to the extrusion)."
    " The inductor (~0.7 W) and shunts can stay on the board.")
out()

# ---- 4. inductor & current sense ------------------------------------------------------------
out("## 4. Inductor and controller current sense")
out()
di_max = max(ripple(p.vin, p.vout, F_SW)[0] for p in POINTS)
ipk_10 = 10 + di_max / 2
ilim = [v / R_SENSE for v in VSENSE_MAX]
out(f"- Inductor: {L_NAME}, {L*1e6:.0f} µH, Isat {L_ISAT} A, DCR ≤ {L_DCR/1.3*1e3:.2f} mΩ (hot ≈ {L_DCR*1e3:.2f} mΩ) → "
    f"{10**2*L_DCR:.2f} W copper at 10 A. Same body and footprint as the SER2918H-682 of the 20 A design.")
out(f"  Alternatives on LCSC: XAL1510-682MED (6.8 µH, 4.6 mΩ, Isat 36 A, 15×16 mm, C3911560); HCZC-2918HT-6R8-M (2.45 mΩ, 45 A, C53202464).")
out(f"- Worst ripple {di_max:.1f} A pp ({di_max/10*100:.0f} % of 10 A; LTC recommends ~30–40 %) → peak at 10 A output {ipk_10:.1f} A.")
out(f"- R_SENSE = {R_SENSE*1e3:.1f} mΩ (2× 4 mΩ 2512) → cycle-by-cycle peak limit at low duty "
    f"{ilim[0]:.1f} / {ilim[1]:.1f} / {ilim[2]:.1f} A (min/typ/max).")
out(f"  Min limit leaves {ilim[0]-ipk_10:.1f} A above the 10 A peak (the MCU-set ITH clamp is the working limit, this is the backstop);"
    f" max limit ({ilim[2]:.1f} A) is {'below' if ilim[2] < L_ISAT else 'ABOVE'} the inductor Isat ({L_ISAT} A).")
out(f"- R_SENSE dissipation at 10 A: {(10**2)*R_SENSE:.2f} W.")
out("- **The limit shrinks at high duty** (slope compensation): in LTspice, with ITH at its maximum, 2.5 mΩ delivered only ~9.4 A at")
out("  D ≈ 0.9 (27 V from 30 V); 2.0 mΩ holds 27 V to ~9.4 A and gives 10 A down to ~26.5 V; 1.5 mΩ holds 27 V past 11.5 A but its")
out("  low-duty limit (up to 37 A) would exceed the inductor Isat. → 2.0 mΩ: **10 A is available up to ≈ Vin − 3.5 V** (26.5 V from 30 V).")
out("  From USB-C this never matters: above ~13 V the 140 W budget limits the current first.")
out(f"- Sense-signal ripple ΔIL·R_SENSE ≈ {di_max*R_SENSE*1e3:.1f} mV (LTC suggests 10–20 mV for noise immunity): below that, so the sense")
out("  traces need a clean Kelvin layout and the datasheet's RC filter at the SENSE pins.")
d_min_ccm = TON_MIN * F_SW
out(f"- Min on-time {TON_MIN*1e9:.0f} ns → min duty {d_min_ccm*100:.1f} %: below "
    f"{31*d_min_ccm:.2f} V out (31 V in) / {28*d_min_ccm:.2f} V (28 V in) / {9*d_min_ccm:.2f} V (9 V PD in) the controller "
    "pulse-skips (higher ripple, still regulates).")
out("- Path drops alone would allow ~27.7 V at 10 A from 28 V, but the LTC7803 does not reach 100 % duty under load: slope")
out("  compensation caps the current near dropout. LTspice: 30 V → 10 A up to 26.5 V; 28 V PD → ≈ 26.5 V at ≈ 4.3 A (sim/results.md t5, t7).")
out()

# ---- 5. input capacitors ------------------------------------------------------------------
out("## 5. Input capacitors")
out()
rows = []
for p in POINTS:
    di, d = ripple(p.vin, p.vout, F_SW)
    irms = math.sqrt(p.iout**2 * d * (1 - d) + d * di**2 / 12)
    rows.append([p.name, f"{irms:.1f}"])
table(["Point", "Cin RMS A"], rows)
CIN_MLCC_N, CIN_MLCC_EFF = 6, 3.0e-6   # 6x 4.7 uF 100 V X7S 1210, ~3 uF each at 30 V (ASSUMPTION, DC-bias derating)
cin = CIN_MLCC_N * CIN_MLCC_EFF
dv = 10 * 0.5 * 0.5 / (F_SW * cin)
out(f"- Worst ~5 A RMS at D≈0.5. Proposal: {CIN_MLCC_N}× 4.7 µF 100 V X7S 1210 (≈{cin*1e6:.0f} µF effective at 30 V,"
    " < 1 A RMS each) right at the half-bridge + ≥ 100 µF electrolytic (ESR 0.1–0.3 Ω) for damping.")
out("  100 V MLCCs instead of 50 V: at 30 V a 4.7 µF/100 V part keeps about as much capacitance as a 10 µF/50 V one, with more voltage margin.")
out(f"- Input ripple (ceramics only, 10 A, D=0.5): ≈ {dv:.2f} V pp.")
z_cable = math.sqrt(1e-6 / cin)
out(f"- Damping vs. ~1 µH of source cable: Z0 = √(L/C) ≈ {z_cable:.2f} Ω → bulk cap ESR in that range damps the input resonance.")
out("- PD rule: keep ≤ 10 µF on raw VBUS *before* the sink switch; the bulk sits after the LM74800.")
out("- LTC7803 VIN pin: RC filter (≈ 10 Ω + 1 µF) + ~36 V zener/TVS at the pin (40 V abs max); see calc/ic_reshop.md.")
out()

# ---- 6. output filter ---------------------------------------------------------------------
out("## 6. Output capacitors and post-filter")
out()
C1_EFF, C2_EFF = 4 * 3.0e-6, 4 * 3.0e-6   # 4x 4.7 uF 100 V 1210 per node, ~3 uF each at 27 V (ASSUMPTION)
LF = 0.47e-6
C_EL, ESR_EL = 100e-6, 0.024          # PCR1J101MCL1GS: 100 µF 63 V polymer, 24 mΩ
CD, RD = 100e-6, 0.1                  # C1 damper: 100 µF 63 V polymer + 0.1 Ω series resistor
ESR_MLCC = 2e-3


def z_c(c, esr, w):
    return esr + 1 / (1j * w * c)


def par(*z):
    return 1 / sum(1 / x for x in z)


w = 2 * math.pi * F_SW
di = max(ripple(p.vin, p.vout, F_SW)[0] for p in POINTS)
z1 = par(z_c(C1_EFF, ESR_MLCC, w), z_c(CD, RD, w))
z2 = par(z_c(C2_EFF, ESR_MLCC, w), z_c(C_EL, ESR_EL, w))
v1 = di * abs(par(z1, 1j * w * LF + z2))
v2 = v1 * abs(z2 / (1j * w * LF + z2))
f0 = 1 / (2 * math.pi * math.sqrt(LF * (C2_EFF + C_EL)))
out(f"- C1 (after the main L): 4× 4.7 µF 100 V 1210 (≈{C1_EFF*1e6:.0f} µF eff. at 27 V) + damper {CD*1e6:.0f} µF polymer with {RD} Ω in series.")
out(f"- Post filter: {LF*1e6:.2f} µH FXL1040-R47 (kept; 30 A, {R_POSTL*1e3:.1f} mΩ) → C2: 4× 4.7 µF 100 V 1210 + {C_EL*1e6:.0f} µF 63 V polymer ({ESR_EL*1e3:.0f} mΩ).")
out(f"- Ripple (fundamental, worst ΔIL {di:.1f} A pp): at C1 ≈ {v1*1e3:.0f} mV pp, at the output ≈ **{v2*1e3:.1f} mV pp** (target ≤ 20 mV).")
out(f"- Post-filter resonance ≈ {f0/1e3:.1f} kHz (with the polymer cap); CV-loop crossover must stay well below → see §9.")
e_out = 0.5 * (C1_EFF + C2_EFF + C_EL + CD) * 27**2
out(f"- Energy in the output caps at 27 V ≈ {e_out*1e3:.0f} mJ (dumped into a short before CC takes over).")
out()

# ---- 7. sensing and DAC scaling -------------------------------------------------------------
out("## 7. Sensing and setpoint scaling")
out()
VREF = 2.9                                 # STM32G474 VREFBUF 2.9 V setting
k_div = 1 / 10.2                           # e.g. 92 k / 10 k
out(f"- CV divider 1/{1/k_div:.1f} (e.g. 91.9 k / 10 k, 0.1 %, 25 ppm): DAC full scale {VREF} V → {VREF/k_div:.1f} V out; "
    f"27 V → {27*k_div:.2f} V. 12-bit DAC → {VREF/4096/k_div*1e3:.1f} mV per LSB at the output.")
G_IL = 100                                 # INA240A3 across R_SENSE (gain 200 would cap the range at 7 A)
h_il = G_IL * R_SENSE
out(f"- CC: INA240A3 (gain 100, LCSC C2060584) across the {R_SENSE*1e3:.1f} mΩ inductor shunt → {h_il:.3f} V/A; "
    f"DAC full scale {VREF} V → {VREF/h_il:.1f} A, {VREF/4096/h_il*1e3:.1f} mA per LSB.")
out(f"  INA240 offset ±25 µV max → ±{25e-6/R_SENSE*1e3:.0f} mA error; firmware trims the setpoint from the INA228 reading.")
out(f"- Metering: INA228 on the {R_OUT_SHUNT*1e3:.0f} mΩ output shunt; ±40.96 mV range (ADCRANGE=1) → up to 40 A, "
    f"LSB ≈ {12.5/2**19*1e6:.0f} µA with CURRENT_LSB = 12.5 A/2^19; bus voltage 195 µV/LSB.")
out(f"- Shunt dissipation at 10 A: output {10**2*R_OUT_SHUNT:.2f} W, input {10**2*R_IN_SHUNT:.2f} W.")
out("- Option for later: external dual 16-bit DAC (e.g. DAC80502) → ~0.4 mV / 0.2 mA resolution. Leave a footprint.")
out()

# ---- 8. regen clamp ---------------------------------------------------------------------------
out("## 8. Regen clamp / down-programmer")
out()
R_CLAMP = 2.0   # Vishay LTO100F2R000JTE3 (LCSC stock)
rows = []
for v in [5, 12, 20, 27, 33]:
    rows.append([v, f"{v/R_CLAMP:.1f}", f"{v*v/R_CLAMP:.0f}"])
table(["Vout V", "clamp I A (on)", "max absorb W (100 % on)"], rows)
out(f"- Unchanged (agreed): R = {R_CLAMP} Ω thick film (Vishay LTO100, TO-247, 100 W) screwed to the extrusion, switched by a 60 V FET, "
    "hysteretic on Vout > Vset + margin **and** on an absolute ~33 V (protects the LTC7803's 40 V SENSE/SW pins); "
    "a second comparator input watches VIN_BUS > ~33 V (regen through the top-FET body diode).")
out(f"- Can absorb 50 W down to √(50·{R_CLAMP}) ≈ {math.sqrt(50*R_CLAMP):.0f} V; at 27 V it can take up to {27**2/R_CLAMP:.0f} W peak.")
out("- Rating: burst 50 W for ~10 s (500 J), average derated from the enclosure NTC (see §3); output off + warning beyond that.")
out()

# ---- 9. loop sanity check -------------------------------------------------------------------------
out("## 9. Loop sanity check (frequency domain)")
out()
out("Model: current-mode modulator as a transconductance Gi = 1/(A_cs·R_SENSE) with the Ridley sampling double pole at fsw/2")
out("(Q = 0.64, i.e. adequate slope compensation), feeding C1 (+ damper) → post-filter L → C2 ∥ polymer ∥ load.")
out("External amps: type-II (integrator + zero + HF pole). Starting values only; LTspice with the LTC7803 model is the real check.")
out()
Gi = 1 / (A_CS * R_SENSE)
out(f"- Gi ≈ {Gi:.1f} A/V (A_cs ≈ {A_CS:.1f}, scaled from the LTC7801 measurement — ASSUMPTION, measure on the LTC7803 model).")
freq = np.logspace(1, 6, 4000)
s = 2j * np.pi * freq
wn, Q_S = math.pi * F_SW, 0.64
He = 1 / (1 + s / (wn * Q_S) + (s / wn) ** 2)     # sampling double pole


def plant(rload, damper=True):
    """Returns (V at C2 per V of ITH, load current per V of ITH, inductor current per V of ITH)."""
    zc1 = ESR_MLCC + 1 / (s * C1_EFF)
    if damper:
        zc1 = 1 / (1 / zc1 + 1 / (RD + 1 / (s * CD)))
    zl = s * LF + R_POSTL
    z2 = 1 / (1 / (ESR_MLCC + 1 / (s * C2_EFF)) + 1 / (ESR_EL + 1 / (s * C_EL)) + 1 / rload)
    zbr = zl + z2
    il = Gi * He
    v1 = il / (1 / zc1 + 1 / zbr)
    v2 = v1 * z2 / zbr
    return v2, v2 / rload, il


def type2(fz, fp, k):
    # G(s) = k*(1+s/wz)/(s*(1+s/wp))
    return k * (1 + s / (2 * np.pi * fz)) / (s * (1 + s / (2 * np.pi * fp)))


def margins(T):
    """Crossover, phase margin, gain margin (worst |T| above fc where the phase is at or beyond -180 deg)."""
    mag = np.abs(T)
    ph = np.degrees(np.unwrap(np.angle(T)))
    idx = np.where((mag[:-1] >= 1) & (mag[1:] < 1))[0]
    if len(idx) == 0:
        return None, None, None, 0
    i = idx[-1]
    fc, pm = freq[i], 180 + ph[i]
    above = slice(i + 1, None)
    bad = ph[above] <= -180
    gm = -20 * np.log10(mag[above][bad].max()) if bad.any() else None
    return fc, pm, gm, len(idx)


def design(pl, h, fc_target, fz_ratio=4, fp_ratio=5):
    fz, fp = fc_target / fz_ratio, fc_target * fp_ratio
    i = np.argmin(np.abs(freq - fc_target))
    k = 1 / np.abs(pl[i] * h * type2(fz, fp, 1.0)[i])
    return k, fz, fp


def row(rl, T):
    fc, pm, gm, n = margins(T)
    return [f"{rl} Ω", f"{fc/1e3:.1f}" if fc else "-", f"{pm:.0f}°" if pm is not None else "-",
            f"{gm:.0f} dB" if gm is not None else "n/a (phase > -180°)", n]


HDR = ["Load", "fc kHz", "phase margin", "gain margin", "0 dB crossings"]
R_TOP = 91.9e3

cv_fc = 10e3
k_cv, fz_cv, fp_cv = design(plant(2.7)[0], k_div, cv_fc)
rows = [row(rl, plant(rl)[0] * k_div * type2(fz_cv, fp_cv, k_cv)) for rl in [1000, 27, 2.7, 0.5]]
out(f"**CV loop, with C1 damper** — sense at C2, divider 1/{1/k_div:.1f}; type-II zero {fz_cv/1e3:.2f} kHz, "
    f"pole {fp_cv/1e3:.0f} kHz, k = {k_cv:.0f} /s (C_f from the divider top {R_TOP/1e3:.1f} kΩ ≈ {1/(R_TOP*k_div*k_cv)*1e9:.2f} nF):")
out()
table(HDR, rows)

k2, fz2, fp2 = design(plant(1.0)[2], h_il, 10e3)
rows = [row(rl, plant(rl)[2] * h_il * type2(fz2, fp2, k2)) for rl in [2.7, 1.0, 0.1, 0.01, 0.001]]
out(f"**CC loop sensing the INDUCTOR current** (INA240A3 across R_SENSE, {h_il:.2f} V/A) — "
    f"zero {fz2/1e3:.1f} kHz, pole {fp2/1e3:.0f} kHz, k = {k2:.0f} /s (R_in 10 kΩ → C_i ≈ {1/(k2*10e3)*1e9:.1f} nF):")
out()
table(HDR, rows)
out("Reading:")
out("- Same structure as the 20 A design: the CC loop regulates the average inductor current (load-independent plant);")
out("  the 1 mΩ output shunt (INA228) is for metering and a slow firmware trim of the CC setpoint.")
out("- The C1 damper (RC across C1) tames the post-filter resonance for the CV loop.")
out("- Gi is roughly 2/3 of the LTC7801 design's (lower VSENSE(MAX)), and C1/C2 are smaller: the compensation values change,")
out("  the margins should not. To confirm in LTspice (sim/, LTC7803 model).")
out()

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {OUT}")
