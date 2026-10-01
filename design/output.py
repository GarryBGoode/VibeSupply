"""
Output stage: 1 mOhm shunt + INA228 (0x41), regen clamp / down-programmer, isolated output switch
(VOM1271 + 2x BSC040N10NS5 back-to-back, 100 V: the terminals face the outside world), 15 A MINI fuse,
reverse-polarity diode, wire lugs to the binding posts on the front cap.

Regen clamp (calc §8, sim t4): comparator 1 compares VOUT_SH/10.19 with DAC_V (filtered) + offset
(≈ 1.0 V at the output at Vset = 0, ≈ 0.5 V at 27 V), ~0.5 V hysteresis. Comparator 2 fires on VIN_PWR > ~33 V
(regen pushing the bus up through the top-FET body diode; protects the LTC7803's 40 V pins). Both are diode-OR'd
into a UCC27511 that drives a BSC040N10NS5 into a 2 Ohm LTO100 on the board (back on the PCB 2026-09-30 after the
board split). The MCU can disable the clamp (CLAMP_DIS) when the energy budget / enclosure temperature says so.
The LTO100 needs the extrusion as its heatsink (a few W in free air, bursts are 50 W): horizontal tab-down footprint, meant
for the power board's bottom side, tab on a gap pad on the floor, M3 from outside through the tab hole (insulated tab).
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import (C, NMOS_small, R, VOM1271, _fields, comparator, ntc, power_fet, schottky_small, testpoint, tvs)


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
    r_a, r_b, c_a = R("91.9k", note="1 %"), R("10k", note="1 %"), C("1n")
    VOUT_SH & r_a & cl_sns & r_b & GND
    c_a[1, 2] += cl_sns, GND
    r_ref, r_off = R("10k"), R("470k")
    DACV_F & r_ref & cl_ref
    r_off[1, 2] += P5VA, cl_ref
    cmp = comparator()
    cmp["+"] += cl_sns
    cmp["-"] += cl_ref
    cmp["V+"] += P5VA
    cmp["V-"] += GND
    cmp[4] += cl_cmp
    r_pu, r_hys = R("4.7k"), R("1M", note="hysteresis ≈ 0.5 V at the output")
    r_pu[1, 2] += P5VA, cl_cmp
    r_hys[1, 2] += cl_cmp, cl_sns
    c_cmp = C("100n")
    c_cmp[1, 2] += P5VA, GND

    # comparator 2: absolute bus limit VIN_PWR > ~33 V (VIN_PWR/13 > 2.54 V)
    bus_sns, bus_ref, bus_cmp = Net("CLAMP_BUS_SNS"), Net("CLAMP_BUS_REF"), Net("CLAMP_BUS_CMP")
    r_c, r_d, c_c = R("120k", note="1 %"), R("10k", note="1 %"), C("1n")
    VIN_PWR & r_c & bus_sns & r_d & GND
    c_c[1, 2] += bus_sns, GND
    r_r1, r_r2 = R("10k", note="1 %"), R("10.2k", note="1 %")
    P5VA & r_r1 & bus_ref & r_r2 & GND
    cmp2 = comparator()
    cmp2["+"] += bus_sns
    cmp2["-"] += bus_ref
    cmp2["V+"] += P5VA
    cmp2["V-"] += GND
    cmp2[4] += bus_cmp
    r_pu2, r_hys2 = R("4.7k"), R("1M", note="hysteresis ≈ 0.6 V on the bus")
    r_pu2[1, 2] += P5VA, bus_cmp
    r_hys2[1, 2] += bus_cmp, bus_sns
    c_cmp2 = C("100n")
    c_cmp2[1, 2] += P5VA, GND
    # diode-OR of both comparators into the driver input
    cl_in = Net("CLAMP_IN")
    for src in (cl_cmp, bus_cmp):
        d = schottky_small()
        d["A"] += src
        d["K"] += cl_in
    r_in = R("100k")
    r_in[1, 2] += cl_in, GND

    drv = Part("Driver_FET", "UCC27511ADBV", footprint="Package_TO_SOT_SMD:SOT-23-6")
    drv["V_{DD}"] += P12V
    drv["GND"] += GND
    drv["IN+"] += cl_in
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
    rp = Part("Device", "R", value="2R 100W LTO100", footprint="Package_TO_SOT_THT:TO-247-2_Horizontal_TabDown")
    _fields(rp, "C3546229", "Vishay LTO100F2R000JTE3; tab (insulated) on the extrusion floor via gap pad, M3 screw")
    rp[1, 2] += VOUT_SH, rcl
    testpoint("CLAMP_G")[1] += g

    # ---- output switch: VOUT_SH -> Q1 -> mid <- Q2 <- VTERM (common source), VOM1271 floating drive
    mid, sg = Net("OUTSW_MID"), Net("OUTSW_G")
    q1, q2 = power_fet("BSC040N10NS5"), power_fet("BSC040N10NS5")
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
    f = Part("Device", "Fuse", value="15A 32V MINI",
             footprint="Fuse:Fuseholder_Blade_Mini_Keystone_3568")
    _fields(f, None, "15 A MINI blade fuse (32 V is enough for <= 27 V out); LCSC part to pick")
    f[1, 2] += VTERM, OUT_P
    d_rev = Part("Device", "D_Schottky_Dual_CommonCathode_AKA", value="MBRB40100CT",
                 footprint="Package_TO_SOT_SMD:TO-263-3_TabPin2")
    _fields(d_rev, None, "reverse-battery crowbar: conducts until the fuse opens (IFSM >= 250 A)")
    d_rev["K"] += OUT_P
    d_rev["A"] += GND
    d_tvs = tvs("SMCJ54A", lcsc="C438116")   # 54 V: an external battery up to 48 V must not make it conduct
    d_tvs["K"] += OUT_P
    d_tvs["A"] += GND
    c_out = C("100n", "0805", note="100 V")
    c_out[1, 2] += OUT_P, GND

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
