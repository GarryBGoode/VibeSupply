"""
Analog control: CV and CC error amplifiers (ADA4522-2) diode-OR'd into ITH, the fast ITH current clamp
(PNP + DAC), setpoint filters, MCU sense dividers, hardware OVP and the fault -> RUN logic.

Loop values: sim/results.md (CV: Rz 47.5k, Cf 1.3n, Cp 68p on the 91.9k/10k divider;
CC: Rin 10k, Rz 2.4k, Cf 27n, Cp 1.3n on INA240A3 at 0.2 V/A). The ITH clamp level must be duty-aware (firmware).
Anti-windup: both compensation networks return to ITH (the OR node), not to the amp outputs.
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import C, NMOS_small, PNP_small, R, _fields, comparator, schottky_small, testpoint


def rc_filter(src, dst, r, c):
    rr, cc = R(r), C(c)
    src & rr & dst
    cc[1, 2] += dst, GND


@subcircuit
def control():
    # ---- setpoint filters (MCU DAC outputs -> amps)
    dacv_f, daci_f, icl_f = DACV_F, Net("DACI_F"), Net("DACICL_F")
    rc_filter(DAC_V, dacv_f, "1k", "100n")      # tau 0.1 ms
    rc_filter(DAC_I, daci_f, "1k", "100n")
    rc_filter(DAC_ICL, icl_f, "100", "10n")     # fast: this is the cycle-by-cycle limit

    # ---- dual op-amp
    op = Part("Amplifier_Operational", "ADA4522-2", footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm")
    _fields(op, "C403697", "zero-drift, RRO; input CM to V+ - 1.5 V")
    op["V+"] += P5VA
    op["V-"] += GND
    for v in ("100n", "1u"):
        cd = C(v)
        cd[1, 2] += P5VA, GND

    # ---- CV amp (unit A: 3 = +, 2 = -, 1 = out)
    cvm, cvz, cvo = Net("CV_M"), Net("CV_Z"), Net("CV_OUT")
    r_top = R("91.9k", note="0.1 %, 25 ppm")
    r_bot = R("10k", note="0.1 %, 25 ppm")
    VOUT_INT & r_top & cvm & r_bot & GND
    op[3] += dacv_f
    op[2] += cvm
    op[1] += cvo
    rz, cf, cp = R("47.5k"), C("1.3n", note="C0G"), C("68p", note="C0G")
    cvm & rz & cvz & cf & ITH
    cp[1, 2] += cvm, ITH
    d_cv = schottky_small()
    d_cv["A"] += ITH
    d_cv["K"] += cvo

    # ---- CC amp (unit B: 5 = +, 6 = -, 7 = out)
    ccm, ccz, cco = Net("CC_M"), Net("CC_Z"), Net("CC_OUT")
    r_in = R("10k")
    IL_AMP & r_in & ccm
    op[5] += daci_f
    op[6] += ccm
    op[7] += cco
    rz2, cf2, cp2 = R("2.4k"), C("27n", note="C0G/X7R"), C("1.3n", note="C0G")
    ccm & rz2 & ccz & cf2 & ITH
    cp2[1, 2] += ccm, ITH
    d_cc = schottky_small()
    d_cc["A"] += ITH
    d_cc["K"] += cco
    testpoint("CV_OUT")[1] += cvo
    testpoint("CC_OUT")[1] += cco

    # ---- fast current clamp: PNP pulls ITH down when ITH > DAC_ICL + Vbe
    q = PNP_small()
    q["E"] += ITH
    q["B"] += icl_f
    q["C"] += GND

    # ---- MCU sense
    r_im, c_im = R("100k"), C("1n")
    ITH & r_im & ITH_MON
    c_im[1, 2] += ITH_MON, GND
    # 110k/10k (÷12): 34.8 V = 2.9 V (VREFBUF); 40 V still < 3.6 V at the pin
    r_vt, r_vb, c_vs = R("110k", note="1 %"), R("10k", note="1 %"), C("10n")
    VOUT_INT & r_vt & VOUT_SNS & r_vb & GND
    c_vs[1, 2] += VOUT_SNS, GND
    # terminal voltage (after switch + fuse): may be negative (reversed battery) -> BAT54S clamp
    r_tt, r_tb, c_ts = R("110k", note="1 %"), R("10k", note="1 %"), C("10n")
    OUT_P & r_tt & VTERM_SNS & r_tb & GND
    c_ts[1, 2] += VTERM_SNS, GND
    cl = Part("Diode", "BAT54S", footprint="Package_TO_SOT_SMD:SOT-23")
    cl["A"] += GND          # D1: GND -> COM (clamps negative)
    cl["COM"] += VTERM_SNS
    cl["K"] += P3V3A        # D2: COM -> +3V3A (clamps positive)

    # ---- hardware absolute OVP: VOUT_SNS > 2.67 V (≈ 32 V out, below the LTC7803's 40 V SENSE pins) -> HW_OVP high
    hw_ovp, ref = Net("HW_OVP"), Net("HW_OVP_REF")
    r_r1, r_r2, c_r = R("10k", note="1 %"), R("11.5k", note="1 %"), C("100n")
    P5VA & r_r1 & ref & r_r2 & GND
    c_r[1, 2] += ref, GND
    cmp = comparator()
    cmp["+"] += VOUT_SNS
    cmp["-"] += ref
    cmp["V+"] += P5VA
    cmp["V-"] += GND
    cmp[4] += hw_ovp
    r_pu = R("10k")
    r_pu[1, 2] += P3V3, hw_ovp
    c_cmp = C("100n")
    c_cmp[1, 2] += P5VA, GND

    # ---- FAULT = OVP_FLT | OCP_FLT | HW_OVP  (diode OR, 100k pull-down)
    for src in (OVP_FLT, OCP_FLT, hw_ovp):
        d = schottky_small()
        d["A"] += src
        d["K"] += FAULT
    r_fd = R("100k")
    r_fd[1, 2] += FAULT, GND
    testpoint("FAULT")[1] += FAULT

    # ---- RUN = BUCK_RUN (MCU, 10k) pulled down by FAULT; default off while the MCU is in reset
    r_run, r_rd = R("10k"), R("100k")
    BUCK_RUN & r_run & RUN
    r_rd[1, 2] += RUN, GND
    q_f = NMOS_small()
    q_f["D", "S", "G"] += RUN, GND, FAULT
    testpoint("RUN")[1] += RUN
