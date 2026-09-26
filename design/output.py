"""
Output stage: 1 mOhm shunt + INA228 (0x41), regen clamp / down-programmer, isolated output switch
(VOM1271 + 2x IPT015N10N5 back-to-back), 30 A 58 V MINI fuse, reverse-polarity diode, XT60 + binding posts.

Regen clamp (calc §8, sim t4): LMV331 compares VOUT_SH/20.1 with DAC_V (filtered) + offset
(≈ 0.5-1.0 V at the output, falling with Vset), ~0.7 V hysteresis; UCC27511 drives a BSC040N10NS5 into a
2 Ohm LTO100 on the heatsink. MCU can disable it (CLAMP_DIS) when the energy budget runs out.
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import (C, NMOS_small, R, VOM1271, _fields, comparator, ntc, power_fet, testpoint, tvs)


@subcircuit
def output_stage():
    # ---- output shunt + meter
    rs = R("1m", "2512", lcsc="C2903470", note="3 W, Kelvin-route sense traces")
    rs[1, 2] += VOUT_INT, VOUT_SH
    ina = Part("Sensor_Energy", "INA228", footprint="Package_SO:TSSOP-10_3x3mm_P0.5mm")
    _fields(ina, "C2887910", "output power meter, I2C 0x41")
    ina["Vin+"] += VOUT_INT
    ina["Vin-"] += VOUT_SH
    ina["Vbus"] += VOUT_SH                   # not the terminal: terminal can go negative
    ina["VS"] += P3V3
    ina["GND"] += GND
    ina["A1"] += GND
    ina["A0"] += P3V3                        # 0x41
    ina["SDA"] += I2C1_SDA
    ina["SCL"] += I2C1_SCL
    ina["~{Alert}"] += INA_ALERT
    c_ina = C("100n")
    c_ina[1, 2] += P3V3, GND

    # ---- regen clamp
    cl_sns, cl_ref, cl_cmp = Net("CLAMP_SNS"), Net("CLAMP_REF"), Net("CLAMP_CMP")
    r_a, r_b, c_a = R("191k"), R("10k"), C("1n")
    VOUT_SH & r_a & cl_sns & r_b & GND
    c_a[1, 2] += cl_sns, GND
    r_ref, r_off = R("10k"), R("1M")
    DACV_F & r_ref & cl_ref
    r_off[1, 2] += P5VA, cl_ref
    cmp = comparator()
    cmp["+"] += cl_sns
    cmp["-"] += cl_ref
    cmp["V+"] += P5VA
    cmp["V-"] += GND
    cmp[4] += cl_cmp
    r_pu, r_hys = R("4.7k"), R("1M", note="hysteresis ≈ 0.7 V at the output")
    r_pu[1, 2] += P5VA, cl_cmp
    r_hys[1, 2] += cl_cmp, cl_sns
    c_cmp = C("100n")
    c_cmp[1, 2] += P5VA, GND

    drv = Part("Driver_FET", "UCC27511ADBV", footprint="Package_TO_SOT_SMD:SOT-23-6")
    drv["V_{DD}"] += P12V
    drv["GND"] += GND
    drv["IN+"] += cl_cmp
    drv["IN-"] += CLAMP_DIS
    r_dis = R("100k", note="clamp enabled by default")
    r_dis[1, 2] += CLAMP_DIS, GND
    c_drv = C("1u", "0805", note="25 V")
    c_drv[1, 2] += P12V, GND
    g = Net("CLAMP_G")
    r_on, r_off2 = R("4.7"), R("2.2")
    drv["OUTH"] & r_on & g
    drv["OUTL"] & r_off2 & g
    r_gs = R("100k")
    r_gs[1, 2] += g, GND
    q = power_fet("BSC040N10NS5")
    q["G"] += g
    q["S"] += GND
    rcl = Net("CLAMP_R")
    q["D"] += rcl
    rp = Part("Device", "R", value="2R 100W LTO100", footprint="Package_TO_SOT_THT:TO-247-2_Vertical")
    _fields(rp, "C3546229", "Vishay LTO100F2R000JTE3, bolted to the main heatsink")
    rp[1, 2] += VOUT_SH, rcl
    testpoint("CLAMP_G")[1] += g

    # ---- output switch: VOUT_SH -> Q1 -> mid <- Q2 <- VTERM (common source), VOM1271 floating drive
    mid, sg = Net("OUTSW_MID"), Net("OUTSW_G")
    q1, q2 = power_fet("IPT015N10N5"), power_fet("IPT015N10N5")
    q1["D"] += VOUT_SH
    q1["S"] += mid
    q2["D"] += VTERM
    q2["S"] += mid
    q1["G"] += sg
    q2["G"] += sg
    vom = VOM1271()
    vom["VO+"] += sg
    vom["VO-"] += mid
    led_a, led_k, oe_g = Net("OE_LED_A"), Net("OE_LED_K"), Net("OE_G")
    r_led = R("91", note="≈20 mA LED current -> ~30 uA gate current")
    r_led[1, 2] += P3V3, led_a
    vom["A"] += led_a
    vom["K"] += led_k
    q_oe, q_of = NMOS_small(), NMOS_small()
    q_oe["D", "S", "G"] += led_k, GND, oe_g
    r_oe, r_oed = R("10k"), R("100k")
    OUT_EN & r_oe & oe_g
    r_oed[1, 2] += oe_g, GND                  # off while the MCU is in reset
    q_of["D", "S", "G"] += oe_g, GND, FAULT   # hardware fault opens the switch
    testpoint("OUTSW_G")[1] += sg

    # ---- fuse, protection, connectors
    f = Part("Device", "Fuse", value="30A 58V MINI",
             footprint="Fuse:Fuseholder_Blade_Mini_Keystone_3568")
    _fields(f, "C207030", "Littelfuse 0997030.WXN; check holder accepts the 58 V rejection feature")
    f[1, 2] += VTERM, OUT_P
    d_rev = Part("Device", "D_Schottky_Dual_CommonCathode_AKA", value="MBRB40100CT",
                 footprint="Package_TO_SOT_SMD:TO-263-3_TabPin2")
    _fields(d_rev, None, "reverse-battery crowbar: conducts until the fuse opens (IFSM >= 250 A)")
    d_rev["K"] += OUT_P
    d_rev["A"] += GND
    d_tvs = tvs("SMCJ54A", lcsc="C438116")
    d_tvs["K"] += OUT_P
    d_tvs["A"] += GND
    c_out = C("100n", "0805", note="100 V")
    c_out[1, 2] += OUT_P, GND

    j = Part("Connector_Generic", "Conn_01x02", ref="J4", value="XT60PW-F OUT",
             footprint="Connector_AMASS:AMASS_XT60PW-F_1x02_P7.20mm_Horizontal")
    _fields(j, None, "pin 1 = +, pin 2 = GND")
    j[1] += OUT_P
    j[2] += GND
    for net, label in ((OUT_P, "POST+"), (GND, "POST-")):
        lug = Part("Mechanical", "MountingHole_Pad", value=label,
                   footprint="MountingHole:MountingHole_4.3mm_M4_Pad_Via")
        lug[1] += net

    # ---- temperature
    for net in (NTC_CLAMP, NTC_OUTSW):
        t, rpu, cf = ntc(), R("10k"), C("100n")
        rpu[1, 2] += P3V3A, net
        t[1, 2] += net, GND
        cf[1, 2] += net, GND
