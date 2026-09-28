"""
Power stage: LTC7803 synchronous buck (300 kHz), 2x CSD18531Q5A, Coilcraft SER2918H-103 10 uH, 2.0 mOhm sense,
C1 + damper, 0.47 uH post filter, C2 + polymer, INA240A3 on the sense resistor.

Values: calc/results.md, sim/results.md. The LTC7803's own error amp is parked (VFB held at ~0.7 V);
regulation happens through ITH (design/control.py). Sim-driven details:
- EXTVCC from the 12 V aux rail (>= 7 V). With 5 V the EXTVCC LDO is in dropout, the boost supply sags and the
  controller stalled after an idle period in LTspice.
- External boost diode INTVCC -> BOOST (the LTC7803 has none inside).
- 300 kHz, not 200 kHz (sub-harmonic oscillation above ~80 % duty); 2.0 mOhm so 10 A is available up to ~Vin - 3.5 V.
- VIN pin: 10 Ohm + 1 uF + 36 V zener (40 V abs max); the LM74800 OV lockouts (~31 V) keep the bus below that.
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import C, CP, LTC7803, NMOS_small, R, _fields, main_inductor, ntc, power_fet, testpoint, tvs, L


@subcircuit
def buck():
    u = LTC7803()
    intvcc = Net("BUCK_INTVCC")
    sw, boost = Net("SW"), Net("BUCK_BOOST")
    tg, bg = Net("BUCK_TG"), Net("BUCK_BG")
    senp, vc1 = Net("IL_SENSE+"), Net("VC1")
    power_net(intvcc)

    # ---- supplies
    vinc = Net("BUCK_VINC")
    power_net(vinc)
    r_vin, c_vin = R("10", "0805"), C("1u", "1206", note="100 V")
    VIN_PWR & r_vin & vinc
    c_vin[1, 2] += vinc, GND
    z_vin = tvs("BZT52C36", "Diode_SMD:D_SOD-123", lcsc="C19077420")   # VIN pin clamp (40 V abs max)
    z_vin["K"] += vinc
    z_vin["A"] += GND
    u["VIN"] += vinc
    u["EXTVCC"] += P12V                      # >= 7 V, see docstring
    c_ext = C("1u", "0805", note="25 V")
    c_ext[1, 2] += P12V, GND
    u["INTVCC"] += intvcc
    c_int = C("4.7u", "0805", note="10 V")
    c_int[1, 2] += intvcc, GND
    u["PLLIN/SPREAD"] += GND                 # fixed frequency, spread spectrum off
    u["GND"] += GND

    # ---- control pins
    u["RUN"] += RUN
    # VFB parked at ~0.715 V (above the 0.56 V foldback threshold, below the 0.88 V FB-OVP)
    vfb = Net("BUCK_VFB")
    r_f1, r_f2, c_f = R("61.9k", note="1 %"), R("10k", note="1 %"), C("1n")
    intvcc & r_f1 & vfb & r_f2 & GND
    c_f[1, 2] += vfb, GND
    u["VFB"] += vfb
    u["ITH"] += ITH
    c_ith = C("100p", note="C0G")
    c_ith[1, 2] += ITH, GND
    ss = Net("BUCK_SS")
    c_ss = C("10n")
    c_ss[1, 2] += ss, GND
    u["TRACK/SS"] += ss
    # frequency: f = 3.74e10 / RFREQ -> 124k = 300 kHz (datasheet: 374k = 100 kHz, 75k = 500 kHz)
    r_fq = R("124k", note="1 %")
    r_fq[1, 2] += u["FREQ"], GND
    # MODE (internal 100k to GND): pulse-skip for 1.2 V < MODE < INTVCC - 1.3 V, forced continuous at INTVCC.
    # 1k from INTVCC + (1k + NMOS) to GND = 2.6 V -> pulse-skip (default: BUCK_PSKIP pulled high while the MCU
    # is in reset). MCU pulls BUCK_PSKIP low -> NMOS off -> MODE ≈ INTVCC -> forced continuous.
    mode, mode_lo = Net("BUCK_MODE"), Net("BUCK_MODE_LO")
    r_m1, r_m2 = R("1k"), R("1k")
    r_m1[1, 2] += intvcc, mode
    r_m2[1, 2] += mode, mode_lo
    qm = NMOS_small()
    qm["D", "S", "G"] += mode_lo, GND, BUCK_PSKIP
    r_mp = R("100k", note="default pulse-skip while the MCU is in reset")
    r_mp[1, 2] += P3V3, BUCK_PSKIP
    u["MODE"] += mode
    testpoint("ITH")[1] += ITH
    testpoint("SW")[1] += sw

    # ---- half bridge
    u["TG"] += tg
    u["BG"] += bg
    u["SW"] += sw
    u["BOOST"] += boost
    c_bst = C("100n", "0603", note="25 V")
    c_bst[1, 2] += boost, sw
    d_bst = Part("Device", "D_Schottky", value="CMDSH-4E", footprint="Diode_SMD:D_SOD-323")
    _fields(d_bst, "C5240486", "boost diode, low leakage (500 nA @25 V): the charge pump only supplies ~65 uA")
    d_bst["A"] += intvcc
    d_bst["K"] += boost
    q_hs, q_ls = power_fet("CSD18531Q5A"), power_fet("CSD18531Q5A")
    r_gh, r_gl = R("1", "0603", note="gate R, tune for ringing"), R("0", "0603", note="gate R")
    tg & r_gh & q_hs["G"]
    bg & r_gl & q_ls["G"]
    q_hs["D"] += VIN_PWR
    q_hs["S"] += sw
    q_ls["D"] += sw
    q_ls["S"] += GND
    # switch-node RC snubber (tune at bring-up; may be DNP)
    r_sn, c_sn = R("2.2", "1206"), C("1n", "0805", note="100 V C0G")
    sw & r_sn & c_sn & GND

    # input capacitors at the half bridge: ~5 A RMS worst case (calc §5)
    for _ in range(6):
        ci = C("4.7u", "1210", lcsc="C913445", note="100 V X7S")
        ci[1, 2] += VIN_PWR, GND
    for _ in range(2):
        ch = C("100n", "0603", note="100 V")
        ch[1, 2] += VIN_PWR, GND
    cb = CP("100u 100V", "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", lcsc="C443138",
            note="LKME1402A101MF, damping ESR")
    cb[1, 2] += VIN_PWR, GND

    # ---- inductor, sense, output filter
    l1 = main_inductor()
    l1[1, 2] += sw, senp
    for _ in range(2):                        # 2x 4 mOhm = 2.0 mOhm
        rs = R("4m", "2512", lcsc="C2904236", note="3 W, Kelvin sense to SENSE+/- and INA240")
        rs[1, 2] += senp, vc1
    # LTC7803 sense inputs: 10 Ohm + 1 nF differential filter (datasheet fig. 2a; tune RF*CF = ESL/RSENSE)
    sp, sn = Net("BUCK_SENSE_P"), Net("BUCK_SENSE_N")
    r_sp, r_sn2, c_s = R("10"), R("10"), C("1n", note="C0G")
    senp & r_sp & sp
    vc1 & r_sn2 & sn
    c_s[1, 2] += sp, sn
    u["SENSE+"] += sp
    u["SENSE-"] += sn

    for _ in range(4):
        c1 = C("4.7u", "1210", lcsc="C913445", note="100 V X7S")
        c1[1, 2] += vc1, GND
    # C1 damper: 0.1 Ohm + 100 uF 63 V polymer
    dmp = Net("VC1_DAMP")
    r_d = R("0.1", "1206", note="damper, 0.25 W")
    r_d[1, 2] += vc1, dmp
    c_d = CP("100u 63V", "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", lcsc="C2691842", note="polymer, damper")
    c_d[1, 2] += dmp, GND

    lf = L("0.47uH", "Inductor_SMD:L_Changjiang_FXL1040", lcsc="C475921", note="FXL1040-R47-M 30 A")
    lf[1, 2] += vc1, VOUT_INT
    for _ in range(4):
        c2 = C("4.7u", "1210", lcsc="C913445", note="100 V X7S")
        c2[1, 2] += VOUT_INT, GND
    c_pol = CP("100u 63V", "Capacitor_SMD:CP_Elec_10x12.6", lcsc="C5154285", note="PCR1J101MCL1GS 24 mOhm")
    c_pol[1, 2] += VOUT_INT, GND

    # ---- inductor-current amplifier for the CC loop
    ina = Part("Amplifier_Current", "INA240A3PW", footprint="Package_SO:TSSOP-8_4.4x3mm_P0.65mm")
    _fields(ina, "C544538", "gain 100: 0.2 V/A with 2.0 mOhm (14.5 A = 2.9 V)")
    ina["+"] += senp
    ina["-"] += vc1
    ina["V+"] += P5VA
    ina["GND"] += GND
    ina["REF1", "REF2"] += GND, GND          # unidirectional
    ina[8] += IL_AMP                          # OUT (unnamed pin 8 in the KiCad symbol)
    c_ina = C("100n")
    c_ina[1, 2] += P5VA, GND
    # to MCU: divider 4.7k/10k (x0.68) keeps a 4.9 V fault level below 3.4 V at the pin
    r_i1, r_i2, c_i = R("4.7k"), R("10k"), C("1n")
    IL_AMP & r_i1 & IL_SNS & r_i2 & GND
    c_i[1, 2] += IL_SNS, GND

    # ---- temperature sensors (NTC to GND, 10k pull-up to +3V3A): FETs sit on the extrusion, inductor on the board
    for net in (NTC_FET, NTC_IND):
        t, rp, cf = ntc(), R("10k"), C("100n")
        rp[1, 2] += P3V3A, net
        t[1, 2] += net, GND
        cf[1, 2] += net, GND
