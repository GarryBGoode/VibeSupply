"""
Input power: USB-C PD sink (TPD4S480 + TPS26750 + EEPROM + LM74800 sink switch),
XT60 DC input (LM74800 ideal diode), input shunt + INA228, VIN sense divider.

References: TPS26750 datasheet SLVSH67 (fig. 8-4 EPR implementation, fig. 8-5 POWER_PATH_EN buffer,
table 7-6 SafeMode strap), TPD4S480 datasheet, LM7480-Q1 datasheet SNOSD95C.
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import (B0505S, C, CP, LM74800, NMOS_small, R, TPD4S480, TPS26750, _fields, power_fet, testpoint, tvs)


@subcircuit
def lm74800_path(v_in, v_out, en, name, fet_model, ov_top="453k", ov_bot="10k"):
    """Back-to-back common-drain N-FETs: Q_A = ideal diode (DGATE), Q_B = on/off + OV cut-off (HGATE).
    OV cut-off ≈ 1.23 V * (1 + top/bot) = 57 V with 453k/10k."""
    u = LM74800()
    qa, qb = power_fet(fet_model), power_fet(fet_model)
    mid = Net(f"{name}_MID")
    power_net(mid)
    # Q_A: source = input (A), drain = mid (C / VS)
    qa["S"] += v_in
    qa["D"] += mid
    qa["G"] += u["DGATE"]
    # Q_B: drain = mid, source = output
    qb["D"] += mid
    qb["S"] += v_out
    qb["G"] += u["HGATE"]
    u["A"] += v_in
    u["C"] += mid
    u["VS"] += mid
    u["OUT"] += v_out
    u["GND"] += GND
    u["RTN"] += NC                       # exposed pad: leave floating (datasheet)
    u["VSNS"] += mid
    c_vs = C("100n", "0603", note="100 V")
    c_vs[1, 2] += mid, GND
    c_cap = C("100n", "0603", note="25 V")
    c_cap[1, 2] += u["CAP"], mid
    # OV ladder from SW (internally switched to VSNS when enabled)
    r_ovt, r_ovb = R(ov_top), R(ov_bot)
    u["SW"] & r_ovt & u["OV"] & r_ovb & GND
    u["EN/UVLO"] += en
    return mid


@subcircuit
def usb_pd_input():
    # ---------------- connector
    j = Part("Connector", "USB_C_Receptacle_USB2.0_16P", ref="J1",
             footprint="Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal")
    _fields(j, "C3020560", "GCT USB4105-GF-A, 48 V / 5 A rated")
    j["VBUS"] += VBUS_RAW
    j["GND"] += GND
    j["SHIELD"] += GND
    j["D+"] += NC
    j["D-"] += NC
    j["SBU1"] += NC
    j["SBU2"] += NC
    c_cc1_conn, c_cc2_conn = Net("PD_C_CC1"), Net("PD_C_CC2")
    j["CC1"] += c_cc1_conn
    j["CC2"] += c_cc2_conn

    # VBUS before the sink switch: <= 10 uF total (TPS26750 / USB PD)
    c1 = C("4.7u", "1210", lcsc="C913445", note="100 V X7S")
    c1[1, 2] += VBUS_RAW, GND
    d1 = tvs("SMCJ54A", lcsc="C438116")
    d1["A"] += GND
    d1["K"] += VBUS_RAW

    # ---------------- TPD4S480 EPR front end
    tpd = TPD4S480()
    tpd["VBUS"] += VBUS_RAW
    tpd["VBUS_LV"] += VBUS_LV
    tpd["VPWR"] += PD_LDO3V3
    tpd["C_CC1"] += c_cc1_conn
    tpd["C_CC2"] += c_cc2_conn
    tpd["RPD_G1"] += c_cc1_conn          # dead-battery Rd needed (sink must be seen when unpowered)
    tpd["RPD_G2"] += c_cc2_conn
    tpd["C_SBU1", "C_SBU2", "SBU1", "SBU2"] += NC, NC, NC, NC
    tpd["EPR_BLK_G"] += NC               # sink-only: no VBUS blocking FET
    tpd["GND"] += GND
    tpd["EP"] += GND
    cb = C("100n", "0805", note="100 V")
    cb[1, 2] += tpd["VBIAS"], GND
    cvp = C("100n")
    cvp[1, 2] += PD_LDO3V3, GND
    r_flt = R("100k")
    r_flt[1, 2] += PD_LDO3V3, tpd["FLT"]
    testpoint("PD_FLT")[1] += tpd["FLT"]

    # ---------------- TPS26750
    pd = TPS26750()
    pd["VBUS"] += VBUS_LV
    c_vbus = C("4.7u", "1206", note="50 V; TPS26750 C_VBUS 1-10 uF")
    c_vbus[1, 2] += VBUS_LV, GND
    cc1_sys, cc2_sys = Net("PD_CC1"), Net("PD_CC2")
    pd["CC1"] += cc1_sys
    pd["CC2"] += cc2_sys
    tpd["CC1"] += cc1_sys
    tpd["CC2"] += cc2_sys
    for n in (cc1_sys, cc2_sys):
        cc = C("330p", note="C_CCy 200-480 pF")
        cc[1, 2] += n, GND

    pd["VIN_3V3"] += P3V3
    c_vin = C("10u", "0805")
    c_vin[1, 2] += P3V3, GND
    pd["LDO_3V3"] += PD_LDO3V3
    c_ldo3 = C("10u", "0805")
    c_ldo3[1, 2] += PD_LDO3V3, GND
    c_ldo15 = C("10u", "0805", note="4.5-12 uF")
    c_ldo15[1, 2] += pd["LDO_1V5"], GND
    pd["GND"] += GND
    pd["EP"] += GND
    pd["VSYS"] += GND
    pd["NC"] += NC
    # PP5V: sink-only design. Tied to GND through a 0R so it can be re-routed (open question, TODO.md).
    r_pp5 = R("0R", note="PP5V: sink-only -> GND (verify with TI E2E)")
    pp5 = Net("PD_PP5V")
    power_net(pp5)
    pd["PP5V"] += pp5
    r_pp5[1, 2] += pp5, GND

    # boot strap: SafeMode, I2C address index #2 (0x21): ADCIN1 = ADCIN2 = 0 (tie to GND)
    for pin in ("ADCIN1", "ADCIN2"):
        rdn = R("0R", note="SafeMode strap (Table 7-6: ADCIN1=0, ADCIN2=0)")
        rdn[1, 2] += pd[pin], GND
        rup = R("DNP")
        rup.fields["DNP"] = "yes"
        rup[1, 2] += PD_LDO3V3, pd[pin]

    # host I2C (target) to MCU I2C1; interrupt to MCU
    pd["I2Ct_SCL"] += I2C1_SCL
    pd["I2Ct_SDA"] += I2C1_SDA
    pd["I2Ct_IRQ"] += PD_IRQ
    r_irq = R("10k")
    r_irq[1, 2] += P3V3, PD_IRQ

    # controller I2C -> config EEPROM (pull-ups to LDO_3V3 per datasheet)
    ee = Part("Memory_EEPROM", "24LC512", footprint="Package_SO:SOIC-8_3.9x4.9mm_P1.27mm", value="AT24C512C")
    _fields(ee, "C12371", "config bundle >= 36 KB, address 0x50")
    ee["A0", "A1", "A2", "WP", "GND"] += GND, GND, GND, GND, GND
    ee["VCC"] += PD_LDO3V3
    ce = C("100n")
    ce[1, 2] += PD_LDO3V3, GND
    ee["SDA"] += pd["I2Cc_SDA"]
    ee["SCL"] += pd["I2Cc_SCL"]
    for sig in ("I2Cc_SDA", "I2Cc_SCL", "I2Cc_IRQ"):
        rp = R("4.7k" if sig != "I2Cc_IRQ" else "10k")
        rp[1, 2] += PD_LDO3V3, pd[sig]

    # GPIOs: GPIO0 -> TPD4S480 EPR_EN (config must map "EPR enable" to GPIO0); others to test points
    pd["GPIO0"] += tpd["EPR_EN"]
    testpoint("PD_GPIO0_EPR_EN")[1] += pd["GPIO0"]
    for g in ("GPIO1", "GPIO2", "GPIO3", "GPIO6", "GPIO7", "GPIO4", "GPIO5"):
        rg = R("100k", note="unused GPIO pull-down (datasheet: tie unused to GND)")
        rg[1, 2] += pd[g], GND
        if g in ("GPIO1", "GPIO2", "GPIO3"):
            testpoint(f"PD_{g}")[1] += pd[g]
    testpoint("PD_GPIO11")[1] += pd["GPIO11"]

    # POWER_PATH_EN (not a logic-level output) -> 2-stage buffer (fig. 8-5) -> PD_SINK_EN
    ppe = pd["POWER_PATH_EN"]
    n1, sink_en = Net("PD_PPE_N"), Net("PD_SINK_EN")
    r_a, r_b, r_c = R("100k"), R("100k"), R("100k")
    r_a[1, 2] += PD_LDO3V3, ppe
    q1, q2 = NMOS_small(), NMOS_small()
    q1["G", "S", "D"] += ppe, GND, n1
    r_b[1, 2] += PD_LDO3V3, n1
    q2["G", "S", "D"] += n1, GND, sink_en
    r_c[1, 2] += PD_LDO3V3, sink_en
    testpoint("PD_SINK_EN")[1] += sink_en

    # ---------------- sink switch (5 A path)
    lm74800_path(VBUS_RAW, VIN_BUS, sink_en, "USBIN", "BSC040N10NS5", tag="usbin_path")


@subcircuit
def dc_input():
    j = Part("Connector_Generic", "Conn_01x02", ref="J2", value="XT60PW-M DC IN",
             footprint="Connector_AMASS:AMASS_XT60PW-M_1x02_P7.20mm_Horizontal")
    _fields(j, "C98732", "12-55 V, 20 A. Pin 1 = +, pin 2 = GND (check XT60 polarity marking at layout)")
    j[1] += DCIN_RAW
    j[2] += GND
    c = C("1u", "1206", note="100 V")
    c[1, 2] += DCIN_RAW, GND
    d = tvs("SMCJ54A", lcsc="C438116")
    d["A"] += GND
    d["K"] += DCIN_RAW
    # UVLO: EN/UVLO ladder from the mid node -> on above ~9 V (1.2 V * 115/15)
    en = Net("DCIN_EN")
    mid = lm74800_path(DCIN_RAW, VIN_BUS, en, "DCIN", "IPT015N10N5", tag="dcin_path")
    r1, r2 = R("100k"), R("15k")
    mid & r1 & en & r2 & GND


@subcircuit
def input_sense():
    """VIN_BUS -> 1 mOhm shunt -> VIN_PWR, INA228 @0x40, VIN divider for the MCU."""
    rs = R("1m", "2512", lcsc="C2903470", note="3 W, Kelvin-route sense traces")
    rs[1, 2] += VIN_BUS, VIN_PWR
    ina = Part("Sensor_Energy", "INA228", footprint="Package_SO:TSSOP-10_3x3mm_P0.5mm")
    _fields(ina, "C2887910", "input power meter, I2C 0x40")
    ina["Vin+"] += VIN_BUS
    ina["Vin-"] += VIN_PWR
    ina["Vbus"] += VIN_PWR
    ina["VS"] += P3V3
    ina["GND"] += GND
    ina["A0", "A1"] += GND, GND
    ina["SDA"] += I2C1_SDA
    ina["SCL"] += I2C1_SCL
    ina["~{Alert}"] += INA_ALERT
    cf = C("100n")
    cf[1, 2] += P3V3, GND
    # input sense filter (INA228 datasheet: 10 Ohm + 100 nF differential optional)
    # VIN divider to MCU: 191k / 10k -> 56 V = 2.79 V
    rt, rb, cv = R("191k"), R("10k"), C("100n")
    VIN_PWR & rt & VIN_SNS & rb & GND
    cv[1, 2] += VIN_SNS, GND
