"""
Input power: USB-C PD sink (AP33772S + 5 mOhm VBUS sense + LM74800 ideal diode / sink switch),
XT60 DC input (LM74800), input shunt + INA228, VIN sense divider.

References: AP33772S datasheet DS46176 Rev. 10 (fig. 1 typical application, table 4 VSEL, I2C address 0x52),
LM7480-Q1 datasheet SNOSD95C. Design notes: calc/ic_reshop.md.

USB path: VBUS -> 5 mOhm (AP33772S current sense, ISENP) -> VBUS_S -> LM74800 (ideal diode + switch, OV lockout
~31 V) -> VIN_BUS. The AP33772S's own NMOS driver (PWR_EN) is not used: the LM74800 blocks backfeed (a 30 V DC
input OR-ed with a 20 V contract would otherwise push current into the charger) and gives a fast hardware OV cut-off.
The MCU enables the path (PD_SINK_EN) once the AP33772S reports a valid contract, and drops it on an AP33772S
interrupt (OVP/UVP/OCP/OTP). EPR 28 V needs an EPR (240 W e-marked) cable.
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import AP33772S, C, LM74800, R, _fields, ntc, power_fet, schottky_small, testpoint, tvs, LED


@subcircuit
def lm74800_path(v_in, v_out, en, name, fet_model, ov_top="243k", ov_bot="10k"):
    """Back-to-back common-drain N-FETs: Q_A = ideal diode (DGATE), Q_B = on/off + OV cut-off (HGATE).
    OV cut-off ≈ 1.23 V * (1 + top/bot) = 31.1 V with 243k/10k: the LTC7803 (40 V abs max) depends on it."""
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
    r_ovt, r_ovb = R(ov_top, note="1 %"), R(ov_bot, note="1 %")
    u["SW"] & r_ovt & u["OV"] & r_ovb & GND
    u["EN/UVLO"] += en
    return mid


@subcircuit
def usb_pd_input():
    # ---------------- connector
    j = Part("Connector", "USB_C_Receptacle_USB2.0_16P", ref="J1",
             footprint="Connector_USB:USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal")
    _fields(j, "C3020560", "GCT USB4105-GF-A, 48 V / 5 A rated")
    cc1, cc2, dp, dn = Net("PD_CC1"), Net("PD_CC2"), Net("PD_DP"), Net("PD_DN")
    j["VBUS"] += VBUS_RAW
    j["GND"] += GND
    j["SHIELD"] += GND
    j["D+"] += dp                        # AP33772S moisture detection / legacy detection
    j["D-"] += dn
    j["SBU1"] += NC
    j["SBU2"] += NC
    j["CC1"] += cc1
    j["CC2"] += cc2

    # VBUS before the sink switch: <= 10 uF total (USB PD)
    c1 = C("4.7u", "1210", lcsc="C913445", note="100 V X7S")
    c1[1, 2] += VBUS_RAW, GND
    d1 = tvs("SMBJ30A", footprint="Diode_SMD:D_SMB", lcsc="C113998")
    d1["A"] += GND                       # 30 V standoff: above a 28 V EPR contract (+5 %), below the AP33772S 34 V abs max
    d1["K"] += VBUS_RAW

    # ---------------- AP33772S (fig. 1)
    pd = AP33772S()
    vbus_s = VBUS_S
    rs = R("5m", "2512", lcsc="C2903482", note="AP33772S current sense (OCP / current readback), Kelvin to VCC/ISENP")
    rs[1, 2] += VBUS_RAW, vbus_s
    pd["VCC"] += VBUS_RAW
    pd["ISENP"] += vbus_s
    r_vo = R("200")
    r_vo[1, 2] += vbus_s, pd["VOUT"]     # VOUT monitor on the switch input (its own NMOS switch is not used)
    pd["PWR_EN"] += NC                    # charge-pump gate drive, unused
    testpoint("PD_PWR_EN")[1] += pd["PWR_EN"]
    pd["CC1"] += cc1
    pd["CC2"] += cc2
    for n in (cc1, cc2):                  # the AP33772S needs external Rd (fig. 1)
        rd = R("5.1k", note="Rd, 1 %")
        rd[1, 2] += n, GND
    pd["DP"] += dp
    pd["DN"] += dn
    pd["GND"] += GND
    pd["EP"] += GND
    pd["NC"] += NC
    c_vcc = C("1u", "1206", note="50 V")
    c_vcc[1, 2] += VBUS_RAW, GND
    c_vs = C("4.7u", "1210", lcsc="C913445", note="100 V X7S")
    c_vs[1, 2] += vbus_s, GND
    v5v = Net("PD_V5V")
    power_net(v5v)
    pd["V5V"] += v5v
    c_v5 = C("1u")
    c_v5[1, 2] += v5v, GND
    # Alternative supply (datasheet: V5V may be fed with 5 V when VCC is off): keeps the AP33772S powered from the
    # DC input so its unpowered I2C pins can't clamp the shared I2C1 bus (INA228s).
    d_v5 = schottky_small()
    d_v5["A"] += P5VA
    d_v5["K"] += v5v
    for pin in ("V18", "IFB"):
        cx = C("100n")
        cx[1, 2] += pd[pin], GND
    # OTP: 10k NTC near the connector (100 uA source)
    t = ntc()
    t[1, 2] += pd["OTP"], GND
    # VSEL: 100k = 5 V default request until the MCU takes over (table 4)
    r_vsel = R("100k", note="1 %: VSEL = 5 V default")
    r_vsel[1, 2] += pd["VSEL"], GND
    # LED: contract indicator (table 15)
    led, r_led = LED("green"), R("1k")
    pd["LED"] & r_led & led["A"]
    led["K"] += GND
    pd["FLIP"] += NC
    pd["GPIO"] += NC
    testpoint("PD_FLIP")[1] += pd["FLIP"]

    # host I2C (I2C1, 3.3 V pull-ups in mcu.py; VIH = 1.4 V) and interrupt (push-pull 4.85 V, active high)
    pd["SCL"] += I2C1_SCL
    pd["SDA"] += I2C1_SDA
    r_int, r_ipd = R("1k", note="series: 4.85 V push-pull into a 5 V tolerant MCU pin"), R("100k")
    pd["INT"] & r_int & PD_IRQ
    r_ipd[1, 2] += PD_IRQ, GND

    # ---------------- sink switch (5 A path), enabled by the MCU (default off while in reset)
    r_en = R("100k", note="sink path off while the MCU is in reset")
    r_en[1, 2] += PD_SINK_EN, GND
    testpoint("PD_SINK_EN")[1] += PD_SINK_EN
    lm74800_path(vbus_s, VIN_BUS, PD_SINK_EN, "USBIN", "CSD18540Q5B", tag="usbin_path")


@subcircuit
def dc_input():
    j = Part("Connector_Generic", "Conn_01x02", ref="J2", value="XT60PW-M DC IN",
             footprint="Connector_AMASS:AMASS_XT60PW-M_1x02_P7.20mm_Horizontal")
    _fields(j, "C98732", "9-30 V, 10 A; survives a 48 V battery (OV lockout). Pin 1 = +, pin 2 = GND (check at layout)")
    j[1] += DCIN_RAW
    j[2] += GND
    c = C("1u", "1206", note="100 V")
    c[1, 2] += DCIN_RAW, GND
    d = tvs("SMCJ54A", lcsc="C438116")   # 54 V standoff: must not conduct on a mistakenly connected 48 V battery
    d["A"] += GND
    d["K"] += DCIN_RAW
    # UVLO: EN/UVLO ladder from the mid node -> on above ~9 V (1.2 V * 115/15)
    en = Net("DCIN_EN")
    # 100 V FETs here: the DC input must survive a 48 V battery plus surges clamped by the 54 V TVS
    mid = lm74800_path(DCIN_RAW, VIN_BUS, en, "DCIN", "ISC030N10NM6", tag="dcin_path")
    r1, r2 = R("100k"), R("15k")
    mid & r1 & en & r2 & GND


@subcircuit
def input_sense():
    """VIN_BUS -> 1 mOhm shunt -> VIN_PWR, INA228 @0x40, VIN divider for the MCU, bus TVS."""
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
    # bus TVS (soft protection for the LTC7803's 40 V pins; the LM74800 OV lockouts do the real work)
    d = tvs("SMBJ33A", footprint="Diode_SMD:D_SMB", lcsc="C173526")
    d["A"] += GND
    d["K"] += VIN_PWR
    # VIN divider to MCU: 120k / 10k -> 37.7 V = 2.9 V (firmware keeps the output off below ~8 V in)
    rt, rb, cv = R("120k", note="1 %"), R("10k", note="1 %"), C("100n")
    VIN_PWR & rt & VIN_SNS & rb & GND
    cv[1, 2] += VIN_SNS, GND
