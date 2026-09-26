"""
Power stage: LTC7801 synchronous buck, ISC030N10NM6 x2, Coilcraft SER2918H 6.8 uH, 2.5 mOhm sense,
C1 + damper, 0.47 uH post filter, C2 + polymer, INA240A2 on the sense resistor.

Values: calc/results.md, sim/results.md. The LTC7801's own error amp is parked (VFB held at 0.70 V);
regulation happens through ITH (design/control.py).
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import C, CP, LTC7801, NMOS_small, R, _fields, main_inductor, ntc, power_fet, testpoint, L


@subcircuit
def buck():
    u = LTC7801()
    intvcc, drvcc = Net("BUCK_INTVCC"), Net("BUCK_DRVCC")
    sw, boost = Net("SW"), Net("BUCK_BOOST")
    tg, bg = Net("BUCK_TG"), Net("BUCK_BG")
    senp, vc1 = Net("IL_SENSE+"), Net("VC1")

    # ---- supplies
    vinc = Net("BUCK_VINC")
    power_net(vinc)
    r_vin, c_vin = R("10", "0805"), C("1u", "1206", note="100 V")
    VIN_PWR & r_vin & vinc
    c_vin[1, 2] += vinc, GND
    u["VIN"] += vinc
    u["EXTVCC"] += P12V                      # 12 V aux: drivers from EXTVCC, not the 48 V LDO (calc §2)
    c_ext = C("1u", "0805", note="25 V")
    c_ext[1, 2] += P12V, GND
    u["INTVCC"] += intvcc
    c_int = C("1u", "0805")
    c_int[1, 2] += intvcc, GND
    u["DRVCC"] += drvcc
    u["NDRV"] += drvcc                       # no external NDRV FET
    c_drv = C("4.7u", "0805", note="25 V")
    c_drv[1, 2] += drvcc, GND
    u["DRVSET"] += intvcc                    # 10 V gate drive
    u["DRVUV"] += intvcc                     # higher DRVCC UVLO for 10 V drive
    u["CPUMP_EN"] += intvcc                  # charge pump -> 100 % duty in dropout
    u["PLLIN"] += GND
    u["GND"] += GND
    u["EP"] += GND

    # ---- control pins
    u["RUN"] += RUN
    # VFB parked at ~0.695 V (above the 0.56 V foldback threshold, below 0.88 V FB-OVP)
    vfb = Net("BUCK_VFB")
    r_f1, r_f2, c_f = R("61.9k"), R("10k"), C("1n")
    intvcc & r_f1 & vfb & r_f2 & GND
    c_f[1, 2] += vfb, GND
    u["VFB"] += vfb
    u["ITH"] += ITH
    c_ith = C("100p")
    c_ith[1, 2] += ITH, GND
    # soft start 10 nF; 330k to INTVCC defeats REGSD (sim/results.md)
    ss = Net("BUCK_SS")
    c_ss, r_ss = C("10n"), R("330k")
    c_ss[1, 2] += ss, GND
    r_ss[1, 2] += intvcc, ss
    u["SS"] += ss
    # frequency 300 kHz
    r_fq = R("71.5k")
    r_fq[1, 2] += u["FREQ"], GND
    # MODE: 100k/100k divider = pulse-skip (default). MCU pulls BUCK_PSKIP low -> NMOS off -> MODE = INTVCC (FCM)
    mode, mode_lo = Net("BUCK_MODE"), Net("BUCK_MODE_LO")
    r_m1, r_m2 = R("100k"), R("100k")
    r_m1[1, 2] += intvcc, mode
    r_m2[1, 2] += mode, mode_lo
    qm = NMOS_small()
    qm["D", "S", "G"] += mode_lo, GND, BUCK_PSKIP
    r_mp = R("100k", note="default pulse-skip while the MCU is in reset")
    r_mp[1, 2] += P3V3, BUCK_PSKIP
    u["MODE"] += mode
    # input OV lockout ~57.6 V: 1.2 V * (470k + 10k) / 10k
    ovlo = Net("BUCK_OVLO")
    r_o1, r_o2 = R("470k"), R("10k")
    VIN_PWR & r_o1 & ovlo & r_o2 & GND
    u["OVLO"] += ovlo
    u["PGOOD"] += NC                         # meaningless with VFB parked
    testpoint("ITH")[1] += ITH
    testpoint("SW")[1] += sw

    # ---- half bridge
    u["TG"] += tg
    u["BG"] += bg
    u["SW"] += sw
    u["BOOST"] += boost
    c_bst = C("100n", "0603", note="25 V")
    c_bst[1, 2] += boost, sw
    q_hs, q_ls = power_fet("ISC030N10NM6"), power_fet("ISC030N10NM6")
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

    # input capacitors at the half bridge
    for _ in range(10):
        ci = C("4.7u", "1210", lcsc="C913445", note="100 V X7S")
        ci[1, 2] += VIN_PWR, GND
    for _ in range(2):
        ch = C("100n", "0603", note="100 V")
        ch[1, 2] += VIN_PWR, GND
    for _ in range(2):
        cb = CP("100u 100V", "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm", lcsc="C443138",
                note="LKME1402A101MF, damping ESR")
        cb[1, 2] += VIN_PWR, GND

    # ---- inductor, sense, output filter
    l1 = main_inductor()
    l1[1, 2] += sw, senp
    for _ in range(2):                        # 2x 5 mOhm = 2.5 mOhm
        rs = R("5m", "2512", lcsc="C2903482", note="3 W, Kelvin sense to SENSE+/- and INA240")
        rs[1, 2] += senp, vc1
    # LTC7801 sense inputs: 10 Ohm + 1 nF differential filter
    sp, sn = Net("BUCK_SENSE_P"), Net("BUCK_SENSE_N")
    r_sp, r_sn2, c_s = R("10"), R("10"), C("1n", note="C0G")
    senp & r_sp & sp
    vc1 & r_sn2 & sn
    c_s[1, 2] += sp, sn
    u["SENSE+"] += sp
    u["SENSE-"] += sn

    for _ in range(6):
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
    for _ in range(6):
        c2 = C("4.7u", "1210", lcsc="C913445", note="100 V X7S")
        c2[1, 2] += VOUT_INT, GND
    c_pol = CP("100u 63V", "Capacitor_SMD:CP_Elec_10x12.6", lcsc="C5154285", note="PCR1J101MCL1GS 24 mOhm")
    c_pol[1, 2] += VOUT_INT, GND

    # ---- inductor-current amplifier for the CC loop
    ina = Part("Amplifier_Current", "INA240A2PW", footprint="Package_SO:TSSOP-8_4.4x3mm_P0.65mm")
    _fields(ina, "C129949", "gain 50: 0.125 V/A with 2.5 mOhm")
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

    # ---- temperature sensors (NTC to GND, 10k pull-up to +3V3A)
    for net in (NTC_FET, NTC_IND):
        t, rp, cf = ntc(), R("10k"), C("100n")
        rp[1, 2] += P3V3A, net
        t[1, 2] += net, GND
        cf[1, 2] += net, GND
