"""
Power-stage calculations for the USB-C PD bench supply (see PLAN.md).

Run:   .venv/Scripts/python calc/buck_calc.py
Output: calc/results.md (overwritten every run)

All part parameters come from datasheets unless marked ASSUMPTION. The loss model is a
first-order analytic estimate (expect +-30 %); the loop section is a sanity check before LTspice,
not a replacement for it.
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
    rds_max: float      # ohm @ 25 C, VGS = 10 V
    qg: float           # C, total @ 10 V (typ)
    qgd: float          # C
    qgs: float          # C
    qg_th: float        # C
    qoss: float         # C
    qrr_hi: float       # C, body-diode Qrr at ~1000 A/us (what a hard-switched buck sees), see QRR NOTE
    rg: float           # ohm internal (typ)
    rth_jc: float       # K/W (max, bottom/case)
    vpl: float          # V, gate plateau


# QRR NOTE: Qrr depends strongly on the test di/dt. ISC030N10NM6 lists 56 nC @100 A/us and 266 nC @1000 A/us
# (x4.75 per decade -> exponent ~0.68). In this buck the top FET turns on in a few ns, so the bottom FET's diode
# recovers at >=1000 A/us. Where a datasheet gives only a lower di/dt, it is scaled with that exponent (ASSUMPTION).
def qrr_scale(q, didt):
    return q * (1000 / didt) ** 0.68


FETS = {
    # TI NexFET datasheets. Qrr specified at 300 A/us -> scaled. rth_jc, vpl: ASSUMPTION (typ. figures).
    "CSD19531Q5A": Fet("CSD19531Q5A", "SON5x6", 7.8e-3, 37e-9, 6.6e-9, 10.5e-9, 7.3e-9, 97e-9, qrr_scale(226e-9, 300), 1.3, 0.9, 3.8),
    "CSD19532Q5B": Fet("CSD19532Q5B", "SON5x6", 5.7e-3, 48e-9, 8.7e-9, 13e-9, 9.5e-9, 128e-9, qrr_scale(249e-9, 300), 1.2, 0.8, 3.8),
    "CSD19535KTT": Fet("CSD19535KTT", "D2PAK", 4.1e-3, 75e-9, 11e-9, 25e-9, 16e-9, 210e-9, qrr_scale(435e-9, 300), 1.4, 0.5, 3.8),
    "CSD19536KTT": Fet("CSD19536KTT", "D2PAK", 2.8e-3, 118e-9, 17e-9, 37e-9, 24e-9, 335e-9, qrr_scale(548e-9, 300), 1.4, 0.4, 3.8),
    # static-only use (output switch, DC-input path): only Rds matters. Values from the LCSC listing.
    "IPT015N10N5": Fet("IPT015N10N5", "TOLL", 1.5e-3, 211e-9, 0, 0, 0, 0, 0, 1.0, 0.4, 4.5),
    # Infineon OptiMOS datasheets (datasheets/). Qrr @1000 A/us straight from the datasheet where listed.
    "ISC060N10NM6": Fet("ISC060N10NM6", "SSO8 5x6", 6.0e-3, 26e-9, 4.5e-9, 8.6e-9, 5.3e-9, 48e-9, 155e-9, 1.15, 1.2, 4.6),
    "ISC030N10NM6": Fet("ISC030N10NM6", "SSO8 5x6", 3.0e-3, 55e-9, 9.1e-9, 18e-9, 11e-9, 101e-9, 266e-9, 1.05, 0.72, 4.6),
    "ISC027N10NM6": Fet("ISC027N10NM6", "SSO8 5x6", 2.7e-3, 58e-9, 9.6e-9, 19e-9, 12e-9, 107e-9, 305e-9, 1.2, 0.69, 4.5),
    "ISC040N10NM8": Fet("ISC040N10NM8", "SSO8 5x6", 4.0e-3, 49e-9, 12e-9, 13e-9, 8.7e-9, 93e-9, 247e-9, 0.8, 0.9, 4.2),
    # NM7: only Qrr @100 A/us (23 nC) given -> scaled; BSC040N10NS5 (OptiMOS 5): 90 nC @100 A/us -> scaled.
    "ISC040N10NM7": Fet("ISC040N10NM7", "SSO8 5x6", 4.0e-3, 39e-9, 6.8e-9, 13e-9, 7.9e-9, 91e-9, qrr_scale(23e-9, 100), 1.3, 0.9, 4.7),
    "BSC040N10NS5": Fet("BSC040N10NS5", "SSO8 5x6", 4.0e-3, 58e-9, 12e-9, 19e-9, 11e-9, 75e-9, qrr_scale(90e-9, 100), 1.3, 0.9, 4.6),
}

RDS_HOT = 1.45        # Rds(on) multiplier at Tj ~ 100 C (normalized-Rds curves)
K_QRR = 0.5           # ASSUMPTION: fraction of the ~1000 A/us Qrr actually recovered (short ~50 ns dead time)

# LTC7801 (datasheet Rev. B)
VDRV = 10.0           # DRVSET = INTVCC
R_TG_PU, R_TG_PD = 2.2, 1.0
R_BG_PU, R_BG_PD = 2.0, 1.0
T_DEAD = (55e-9 + 50e-9)   # TG-off->BG-on + BG-off->TG-on
TON_MIN = 80e-9
VSENSE_MAX = (66e-3, 75e-3, 84e-3)   # min/typ/max
A_CS = 1 / (26.2 * 2.5e-3)   # ITH->VSENSE slope, measured in LTspice (sim/out/ith_probe.cir: 26.2 A/V at 2.5 mΩ)
V_EXTVCC = 12.0

# Inductor: Würth WE-HCF 2818 7443640680B (datasheet)
# Coilcraft SER2918H-682KL (LCSC C3911802): 6.8 µH ±10 %, DCR 2.86 mΩ max, Isat 45.9 A, Irms 25 A (40 K rise).
# (Würth 7443640680B has lower DCR but is not stocked at LCSC.)
L_NAME = "Coilcraft SER2918H-682KL"
L = 6.8e-6
L_ISAT10, L_ISAT30 = 45.9, 45.9   # Coilcraft quotes a single Isat figure
L_DCR = 2.86e-3 * 1.3          # max @20 C, x1.3 for ~100 C copper
L_CORE_W = 1.0                 # ASSUMPTION: core loss, check with the Coilcraft loss calculator

R_SENSE = 2.5e-3               # controller current-sense shunt (2x 5 mΩ 2512 3 W in parallel)
R_OUT_SHUNT = 1.0e-3           # output shunt (INA240 + INA228)
R_IN_SHUNT = 1.0e-3            # input shunt (INA228)
R_POSTL = 1.7e-3               # post-filter inductor FXL1040-R47-M / FAUL1040-R47MT: 470 nH, 1.7 mΩ, 30 A
R_FUSE = 1.85e-3               # Littelfuse 0997030.WXN: 30 A, 58 V DC blade fuse, 1.85 mΩ
OUT_SWITCH = FETS["IPT015N10N5"]  # x2 back-to-back (VOM1271 photovoltaic driver)
DCIN_FET = FETS["IPT015N10N5"]    # x2 back-to-back (LM74800)
USB_FET = FETS["CSD19532Q5B"]     # x2 back-to-back (LM74800), 5 A path
P_HOUSEKEEPING = 3.0           # W: MCU, display, INAs, isolated USB, fan, LDO/buck losses

T_AMB_BOX = 45.0               # C inside the enclosure (ASSUMPTION)
RTH_OPTIONS = {                # junction->ambient-in-box, ASSUMPTIONS for comparison
    "SON5x6 on PCB only": 25.0,
    "SON5x6 + via array + bottom heatsink + fan": 6.0,
    "D2PAK + via array + bottom heatsink + fan": 4.0,
}


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


POINTS = [
    Point("PD 48->12 V 20 A", 48, 12, 20, "PD"),
    Point("PD 48->24 V 9.4 A", 48, 24, 9.4, "PD"),
    Point("PD 48->46 V 4.9 A", 48, 46, 4.9, "PD"),
    Point("PD 28->24 V 5 A", 28, 24, 5.0, "PD"),
    Point("DC 48->3.3 V 20 A", 48, 3.3, 20, "DC"),
    Point("DC 48->24 V 20 A", 48, 24, 20, "DC"),
    Point("DC 48->46 V 20 A", 48, 46, 20, "DC"),
    Point("DC 55->50 V 20 A", 55, 50, 20, "DC"),
]


def ripple(vin, vout, f):
    d = vout / vin
    return (vin - vout) * d / (L * f), d


def switch_times(fet: Fet):
    qgs2 = fet.qgs - fet.qg_th
    i_on = (VDRV - fet.vpl) / (R_TG_PU + fet.rg)
    i_off = fet.vpl / (R_TG_PD + fet.rg)
    return (qgs2 + fet.qgd) / i_on, (qgs2 + fet.qgd) / i_off


def losses(p: Point, f: float, hs: Fet, ls: Fet) -> dict:
    di, d = ripple(p.vin, p.vout, f)
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
    gate_drv = (hs.qg + ls.qg) * V_EXTVCC * f          # drawn from 12 V EXTVCC

    p_ind = i_rms2 * L_DCR + L_CORE_W
    p_rsense = i_rms2 * R_SENSE
    p_outpath = i**2 * (R_OUT_SHUNT + R_POSTL + R_FUSE + 2 * OUT_SWITCH.rds_max * 1.3)
    p_out_sw = i**2 * 2 * OUT_SWITCH.rds_max * 1.3

    pout = p.vout * i
    p_hs = hs_cond + hs_sw + hs_oss + hs_rr
    p_ls = ls_cond + ls_dead
    stage = p_hs + p_ls + gate_drv + p_ind + p_rsense + p_outpath + P_HOUSEKEEPING
    pin_guess = pout + stage
    iin = pin_guess / p.vin
    fet_in = USB_FET if p.src == "PD" else DCIN_FET
    p_inpath = iin**2 * (R_IN_SHUNT + 2 * fet_in.rds_max * 1.3)
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
out()

# ---- 1. frequency / FET comparison at the two hardest points --------------------------------
out("## 1. Switching frequency and FET choice")
out()
out("Total loss (W) at the hardest points. hs = high-side (top) FET, ls = low-side (bottom) FET.")
out()
combos = [("CSD19532Q5B", "CSD19532Q5B"), ("CSD19535KTT", "CSD19535KTT"),
          ("BSC040N10NS5", "BSC040N10NS5"), ("ISC030N10NM6", "ISC030N10NM6"), ("ISC060N10NM6", "ISC030N10NM6"),
          ("ISC060N10NM6", "ISC027N10NM6"), ("ISC040N10NM8", "ISC040N10NM8"), ("ISC040N10NM7", "ISC040N10NM7"),
          ("ISC040N10NM7", "ISC030N10NM6")]
freqs = [200e3, 300e3]
hard = [POINTS[0], POINTS[6], POINTS[5]]
rows = []
for hsn, lsn in combos:
    for f in freqs:
        r = [f"{hsn} / {lsn}", f"{f/1e3:.0f} kHz"]
        for p in hard:
            l = losses(p, f, FETS[hsn], FETS[lsn])
            r.append(f"{l['total']:.1f} (hs {l['p_hs']:.1f})")
        rows.append(r)
table(["hs / ls FET", "fsw"] + [p.name for p in hard], rows)

F_SW = 300e3
HS, LS = FETS["ISC030N10NM6"], FETS["ISC030N10NM6"]
out(f"**Chosen: fsw = {F_SW/1e3:.0f} kHz, hs = ls = {HS.name}** (Infineon OptiMOS 6, 3.0 mΩ, SuperSO8 5×6).")
out("- All its numbers are from the datasheet, including Qrr at 1000 A/µs; one part number for both positions.")
out("- vs. the TI CSD19532Q5B: top-FET worst case ~7.5 W instead of ~11 W, mostly from lower Qrr and Rds(on).")
out("- ISC040N10NM7 looks even better, but its Qrr is only given at 100 A/µs (scaled here) — a candidate if the NM6 runs hot.")
out("- 200 kHz would save ~2 W more but raises ripple 1.5× (peak current closer to the 26 A minimum limit). Staying at 300 kHz.")
out("- Qrr in the table is taken at ~1000 A/µs, the speed this buck really switches at; datasheet headline values")
out("  at 100 A/µs are 4–7× lower and not comparable between vendors.")
out()

# ---- 2. operating points ------------------------------------------------------------------
out(f"## 2. Operating points (fsw = {F_SW/1e3:.0f} kHz, {HS.name} / {LS.name})")
out()
rows = []
for p in POINTS:
    l = losses(p, F_SW, HS, LS)
    rows.append([p.name, f"{p.vout*p.iout:.0f}", f"{l['d']*100:.0f} %", f"{l['di']:.1f}", f"{l['i_pk']:.1f}",
                 f"{l['p_hs']:.1f}", f"{l['p_ls']:.1f}", f"{l['p_ind']:.1f}", f"{l['p_rsense']+l['p_outpath']:.1f}",
                 f"{l['p_inpath']:.1f}", f"{l['total']:.1f}", f"{l['eff']:.1f} %", f"{l['iin']:.1f}"])
table(["Point", "Pout W", "D", "ΔIL pp A", "IL pk A", "top FET W", "bot FET W", "L W", "shunts+out path W",
       "in path W", "total W", "eff", "Iin A"], rows)

l = losses(POINTS[6], F_SW, HS, LS)
out("Top-FET loss breakdown at DC 48->46 V 20 A (W): "
    f"conduction {l['hs_cond']:.2f}, V·I switching {l['hs_sw']:.2f}, Qoss {l['hs_oss']:.2f}, "
    f"Qrr {l['hs_rr']:.2f} (K_QRR = {K_QRR}).")
out(f"Gate drive from 12 V EXTVCC: {(HS.qg+LS.qg)*F_SW*1e3:.0f} mA "
    f"(from the 48 V internal LDO instead it would burn {(HS.qg+LS.qg)*F_SW*(48-VDRV):.2f} W in the LTC7801 → EXTVCC required).")
out()
out("Notes:")
out("- PD points: full 240 W needs the 48 V PDO, because the PD current limit is 5 A — P_in = V_in · 5 A.")
out("  So the \"lowest input voltage\" policy is `V_in ≥ max(V_out + headroom, P_needed / 5 A)`; AVS helps efficiency only at part load.")
out("- Worst heat is at 20 A, and it's nearly independent of output voltage (see PLAN §1).")
out()

# ---- 3. thermal ---------------------------------------------------------------------------
out("## 3. Thermal (top FET, worst point)")
out()
worst = max((losses(p, F_SW, HS, LS) for p in POINTS), key=lambda x: x["p_hs"])
rows = []
for k, rth in RTH_OPTIONS.items():
    tj = T_AMB_BOX + worst["p_hs"] * rth
    rows.append([k, f"{rth:.0f}", f"{worst['p_hs']:.1f}", f"{tj:.0f}", "OK" if tj < 125 else "too hot"])
table(["Mounting (ASSUMPTION Rθ)", "Rθja K/W", "P top W", "Tj °C", ""], rows)
out("→ SON5x6 FETs need the via array + bottom-side heatsink + fan. PCB copper alone is not enough at 20 A.")
worst_total = max(losses(p, F_SW, HS, LS)["total"] for p in POINTS)
out(f"Total heat to remove from the power stage (worst point): **{worst_total:.0f} W** (+ clamp, see §8).")
out()

# ---- 4. inductor & current sense ------------------------------------------------------------
out("## 4. Inductor and controller current sense")
out()
di_max = max(ripple(p.vin, p.vout, F_SW)[0] for p in POINTS)
ipk_20 = 20 + di_max / 2
ilim = [v / R_SENSE for v in VSENSE_MAX]
out(f"- Inductor: {L_NAME}, {L*1e6:.1f} µH, Isat {L_ISAT10} A, DCR ≤ {L_DCR/1.3*1e3:.2f} mΩ (hot ≈ {L_DCR*1e3:.2f} mΩ).")
out(f"- Worst ripple {di_max:.1f} A pp → peak at 20 A output {ipk_20:.1f} A.")
out(f"- R_SENSE = {R_SENSE*1e3:.1f} mΩ → cycle-by-cycle peak limit {ilim[0]:.1f} / {ilim[1]:.1f} / {ilim[2]:.1f} A (min/typ/max).")
out(f"  Min limit leaves {ilim[0]-ipk_20:.1f} A headroom above the 20 A peak (the MCU-set ITH clamp is the working limit, this is the backstop); max limit ({ilim[2]:.1f} A) is "
    f"{'below' if ilim[2] < L_ISAT10 else 'ABOVE'} the inductor Isat ({L_ISAT10} A).")
out(f"- R_SENSE dissipation at 20 A: {(20**2)*R_SENSE:.2f} W → 2512 metal-strip, ≥2 W, Kelvin-connected.")
d_min_ccm = TON_MIN * F_SW
out(f"- Min on-time {TON_MIN*1e9:.0f} ns → min duty {d_min_ccm*100:.1f} %: below "
    f"{48*d_min_ccm:.2f} V out (48 V in) / {15*d_min_ccm:.2f} V (15 V in) the controller pulse-skips "
    "(higher ripple, still regulates). Lower V_in via PD helps; not possible on a 48 V DC input.")
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
CIN_MLCC_N, CIN_MLCC_EFF = 10, 2.0e-6   # 10x 4.7 uF 100 V X7S 1210, ~2 uF each at 48 V (ASSUMPTION)
cin = CIN_MLCC_N * CIN_MLCC_EFF
dv = 20 * 0.5 * 0.5 / (F_SW * cin)
out(f"- Worst ~10 A RMS at D≈0.5. Proposal: {CIN_MLCC_N}× 4.7 µF 100 V X7S/X7R 1210 (≈{cin*1e6:.0f} µF effective at 48 V,"
    f" ~1 A RMS each) right at the half-bridge + bulk 100 V aluminium electrolytic (≥100 µF, ESR 0.1–0.3 Ω) for damping.")
out(f"- Input ripple (ceramics only, 20 A, D=0.5): ≈ {dv:.2f} V pp.")
z_cable = math.sqrt(1e-6 / cin)
out(f"- Damping vs. ~1 µH of source cable: Z0 = √(L/C) ≈ {z_cable:.2f} Ω → bulk cap ESR in that range damps the input resonance.")
out("- PD rule: keep ≤10 µF on raw VBUS *before* the sink switch (TPS26750 recommends 1–10 µF); bulk sits after the LM74800.")
out()

# ---- 6. output filter ---------------------------------------------------------------------
out("## 6. Output capacitors and post-filter")
out()
C1_EFF, C2_EFF = 11e-6, 11e-6         # 6x 4.7 uF 100 V 1210 each node, ~40 % left at 46 V (ASSUMPTION)
LF = 0.47e-6
C_EL, ESR_EL = 100e-6, 0.024          # PCR1J101MCL1GS: 100 µF 63 V polymer, 24 mΩ
CD, RD = 100e-6, 0.1                  # C1 damper: 100 µF 63 V polymer + 0.1 Ω series resistor
ESR_MLCC = 1.5e-3


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
out(f"- C1 (after main L): 6× 4.7 µF 100 V 1210 (≈{C1_EFF*1e6:.0f} µF eff. at 46 V).")
out(f"- C1 damper: {CD*1e6:.0f} µF, ESR/series R ≈ {RD} Ω.")
out(f"- Post filter: {LF*1e6:.2f} µH (≥25 A, {R_POSTL*1e3:.1f} mΩ) → C2: 6× 4.7 µF 100 V 1210 + {C_EL*1e6:.0f} µF 63 V polymer ({ESR_EL*1e3:.0f} mΩ).")
out(f"- Ripple (fundamental, worst ΔIL {di:.1f} A pp): at C1 ≈ {v1*1e3:.0f} mV pp, at the output ≈ **{v2*1e3:.1f} mV pp** (target ≤ 20 mV).")
out(f"- Post-filter resonance ≈ {f0/1e3:.1f} kHz (with the electrolytic); CV-loop crossover must stay well below → see §9.")
e_out = 0.5 * (C1_EFF + C2_EFF + C_EL) * 50**2
out(f"- Energy in output caps at 50 V ≈ {e_out:.2f} J (dumped into a short before CC takes over — small vs. a DP100-class supply).")
out()

# ---- 7. sensing and DAC scaling -------------------------------------------------------------
out("## 7. Sensing and setpoint scaling")
out()
VREF = 2.9                                 # STM32G474 VREFBUF 2.9 V setting
k_div = 2.5 / 50
out(f"- CV divider 1/{1/k_div:.0f} (e.g. 190 k / 10 k, 0.1 %, 25 ppm): 50 V → {50*k_div:.2f} V.")
out(f"  STM32G474 12-bit DAC on VREFBUF {VREF} V → {VREF/4096/k_div*1e3:.1f} mV per LSB at the output.")
g_ina240 = 100
h_cc = 50 * R_SENSE
out(f"- CC: INA240A2 (gain 50) across the {R_SENSE*1e3:.1f} mΩ inductor shunt (see §9 for why) → {h_cc:.3f} V/A; "
    f"20 A → {20*h_cc:.2f} V = DAC full scale, {VREF/4096/h_cc*1e3:.1f} mA per LSB.")
out(f"  INA240 offset ±25 µV max → ±{25e-6/R_SENSE*1e3:.0f} mA error; firmware trims the setpoint from the INA228 reading.")
out(f"- Metering: INA228 on the same {R_OUT_SHUNT*1e3:.0f} mΩ shunt; ±40.96 mV range (ADCRANGE=1) → up to 40 A, "
    f"LSB ≈ {25/2**19*1e6:.0f} µA with CURRENT_LSB = 25 A/2^19; bus voltage 195 µV/LSB.")
out(f"- Shunt dissipation at 20 A: output {20**2*R_OUT_SHUNT:.2f} W, input {20**2*R_IN_SHUNT:.2f} W → 2512 4-terminal (Kelvin) 1 mΩ, ≥1 W.")
out("- Option for later: external dual 16-bit DAC (e.g. DAC80502) → 0.76 mV / 0.4 mA resolution. Leave a footprint.")
out()

# ---- 8. regen clamp ---------------------------------------------------------------------------
out("## 8. Regen clamp / down-programmer")
out()
R_CLAMP = 2.0   # Vishay LTO100F2R000JTE3 (LCSC stock); 3.3 Ω is not stocked
rows = []
for v in [5, 12, 24, 36, 50]:
    rows.append([v, f"{v/R_CLAMP:.1f}", f"{v*v/R_CLAMP:.0f}"])
table(["Vout V", "clamp I A (on)", "max absorb W (100 % on)"], rows)
out(f"- R = {R_CLAMP} Ω thick-film power resistor (Vishay LTO100, TO-247, 100 W) switched by a 100 V FET, hysteretic on "
    "Vout > Vset + margin; firmware integrates energy and derates on the NTC.")
out(f"- Can absorb 50 W down to √(50·{R_CLAMP}) ≈ {math.sqrt(50*R_CLAMP):.1f} V; below that less (V²/R), which matches smaller regen at low voltage.")
E_BURST = 50 * 10     # J: 50 W for 10 s
M_HS, C_AL = 150, 0.9  # g, J/(g K): ASSUMPTION ~150 g aluminium heatsink shared with the power stage
out(f"- **Rating (agreed): burst-only.** 50 W for up to ~10 s (≈{E_BURST} J), then firmware limits to ~10 W average")
out("  and turns the output off with a warning if regen keeps coming. It's a safety net, not a brake resistor.")
out(f"- The resistor (TO-247 thick film, e.g. Vishay LTO100 class) bolts to the main heatsink: {E_BURST} J into "
    f"~{M_HS} g of aluminium ≈ {E_BURST/(M_HS*C_AL):.0f} K rise, so no separate clamp heatsink is needed.")
out("- Firmware: integrate clamp energy (V²/R × duty), track heatsink NTC, enforce the budget; hardware comparator does the switching.")
out()

# ---- 9. loop sanity check -------------------------------------------------------------------------
out("## 9. Loop sanity check (frequency domain)")
out()
out("Model: current-mode modulator as a transconductance Gi = 1/(A_cs·R_SENSE) with the Ridley sampling double pole at fsw/2")
out("(Q = 0.64, i.e. adequate slope compensation), feeding C1 (+ damper) → post-filter L → C2 ∥ electrolytic ∥ load.")
out("External amps: type-II (integrator + zero + HF pole). Starting values only.")
out()
Gi = 1 / (A_CS * R_SENSE)
out(f"- Gi ≈ {Gi:.1f} A/V (A_cs ≈ {A_CS:.1f}, measured on the LTC7801 LTspice model).")
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

# CV loop, with and without damper
cv_fc = 10e3                      # sweep in sim/ notes: 10 kHz gives PM >= 75°, GM >= 11 dB
for damper in (False, True):
    k_cv, fz_cv, fp_cv = design(plant(2.3, damper)[0], k_div, cv_fc)
    rows = [row(rl, plant(rl, damper)[0] * k_div * type2(fz_cv, fp_cv, k_cv)) for rl in [1000, 10, 2.3, 0.6]]
    tag = f"with C1 damper ({CD*1e6:.0f} µF + {RD} Ω)" if damper else "without C1 damper"
    out(f"**CV loop, {tag}** — sense at C2, divider 1/{1/k_div:.0f}; type-II zero {fz_cv/1e3:.2f} kHz, "
        f"pole {fp_cv/1e3:.0f} kHz, k = {k_cv:.0f} /s (R_in 10 kΩ → C_f from the divider top 95.3 kΩ ≈ {1/(95.3e3/20.06*k_cv)*1e9:.2f} nF):")
    out()
    table(HDR, rows)

# CC loop: output-shunt sense (after the post filter) vs. inductor-current sense
h_out = g_ina240 * R_OUT_SHUNT
k1, fz1, fp1 = design(plant(0.01)[1], h_out, 5e3)
rows = [row(rl, plant(rl)[1] * h_out * type2(fz1, fp1, k1)) for rl in [2.3, 0.6, 0.1, 0.01, 0.001]]
out(f"**CC loop sensing the OUTPUT shunt** (after the post filter, INA240A3, {h_out:.2f} V/A) — for comparison:")
out()
table(HDR, rows)

G_IL = 50                                   # INA240A2 across R_SENSE
h_il = G_IL * R_SENSE
k2, fz2, fp2 = design(plant(0.6)[2], h_il, 10e3)
rows = [row(rl, plant(rl)[2] * h_il * type2(fz2, fp2, k2)) for rl in [2.3, 0.6, 0.1, 0.01, 0.001]]
out(f"**CC loop sensing the INDUCTOR current** (INA240A2 across R_SENSE, {h_il:.3f} V/A → 20 A = {20*h_il:.1f} V) — chosen; "
    f"zero {fz2/1e3:.1f} kHz, pole {fp2/1e3:.0f} kHz, k = {k2:.0f} /s (R_in 10 kΩ → C_i ≈ {1/(k2*10e3)*1e9:.1f} nF):")
out()
table(HDR, rows)
out("Reading:")
out("- Sensing the load current *after* the post filter puts the lightly damped L_f–C1 series resonance inside the CC loop;")
out("  near a short it's unstable. Sensing the inductor current gives a load-independent, well-behaved plant.")
out("  The CC loop then regulates the average inductor current = DC output current; the 1 mΩ output shunt (INA228)")
out("  stays for metering and a slow firmware trim of the CC setpoint.")
out("- The C1 damper (RC across C1) tames the post-filter resonance for the CV loop.")
out("- LTspice time-domain verification: see sim/results.md (the sim uses C_f = 1.8 nF, i.e. fc ≈ 8 kHz).")
out()

OUT.write_text("\n".join(lines), encoding="utf-8")
print(f"wrote {OUT}")
