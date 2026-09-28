"""
Housekeeping supplies and fan.

- LOGIC_IN: diode-OR of raw VBUS, raw DC input and the isolated USB 5 V -> the MCU boots from any source,
  before the PD sink path is enabled (the MCU enables it after the AP33772S reports a contract).
- +3V3: LMR38010 (4.2-80 V), 400 kHz, 22 uH.
- +12V_AUX: LM5164 (6-100 V) from VIN_PWR, 300 kHz COT with type-3 ripple injection, 68 uH. LTC7803 EXTVCC
  (needs >= 7 V: at a 9 V input the rail sags to ~8.5 V, still fine), clamp gate driver, +5VA LDO, fan (DNP).
  Enabled above ~8.3 V. Below ~9 V input the output stays off (firmware, VIN_SNS).
- +5VA: LP2985-5.0 from +12V_AUX (op-amps, INA240, comparators, AP33772S V5V backup).
- +3V3A: ferrite-filtered +3V3 for the MCU VDDA and NTC pull-ups.
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import C, FB, L, LED, LMR38010, NMOS_small, R, _fields, schottky_1a, testpoint


@subcircuit
def logic_supply():
    for src, val in ((VBUS_RAW, "SS110"), (DCIN_RAW, "SS110"), (P5V_ISO, "SS14")):
        d = schottky_1a(val)
        d["A"] += src
        d["K"] += LOGIC_IN
    for v, size in (("2.2u", "1206"), ("2.2u", "1206"), ("100n", "0603")):
        c = C(v, size, note="100 V")
        c[1, 2] += LOGIC_IN, GND

    u = LMR38010()
    sw, bst, fb = Net("LOG_SW"), Net("LOG_BOOT"), Net("LOG_FB")
    u["VIN"] += LOGIC_IN
    u["EN"] += LOGIC_IN
    u["GND"] += GND
    u["EP"] += GND
    u["SW"] += sw
    u["BOOT"] += bst
    u["FB"] += fb
    u["PG"] += NC
    r_rt = R("66.5k", note="400 kHz: RT = 30970 * f^-1.027")
    r_rt[1, 2] += u["RT"], GND
    c_b = C("100n")
    c_b[1, 2] += bst, sw
    l1 = L("22uH", "Inductor_SMD:L_Bourns_SRN6045TA", note="22 uH >= 1 A shielded (e.g. SRN6045TA-220M)")
    l1[1, 2] += sw, P3V3
    r_ft, r_fb = R("23.2k"), R("10k")
    P3V3 & r_ft & fb & r_fb & GND          # 1.0 V * (1 + 23.2/10) = 3.32 V
    for _ in range(2):
        co = C("22u", "0805", note="10 V")
        co[1, 2] += P3V3, GND
    testpoint("+3V3")[1] += P3V3

    # +3V3A for VDDA / NTCs
    fbd = FB()
    fbd[1, 2] += P3V3, P3V3A
    for v in ("1u", "100n"):
        c = C(v)
        c[1, 2] += P3V3A, GND

    # power LED
    led, rl = LED("green"), R("1k")
    P3V3 & rl & led["A"]
    led["K"] += GND


@subcircuit
def aux_supply():
    u = Part("Regulator_Switching", "LM5164DDA")
    _fields(u, "C477928")
    sw, bst, fb, en, ra = Net("AUX_SW"), Net("AUX_BST"), Net("AUX_FB"), Net("AUX_EN"), Net("AUX_RA")
    u["VIN"] += VIN_PWR
    u["GND"] += GND
    u["EP"] += GND
    u["SW"] += sw
    u["BST"] += bst
    u["FB"] += fb
    u["EN/UVLO"] += en
    u["PGOOD"] += NC
    for v, size in (("2.2u", "1206"), ("100n", "0603")):
        c = C(v, size, note="100 V")
        c[1, 2] += VIN_PWR, GND
    r_e1, r_e2 = R("100k"), R("22k")
    VIN_PWR & r_e1 & en & r_e2 & GND        # 1.5 V * 122/22 = 8.3 V
    r_on = R("100k", note="FSW(kHz) = VOUT * 2500 / RON(k) = 300 kHz")
    r_on[1, 2] += u["RON"], GND
    c_b = C("2.2n", note="50 V X7R (datasheet)")
    c_b[1, 2] += bst, sw
    l1 = L("68uH", "Inductor_SMD:L_Bourns-SRN8040_8x8.15mm", note="68 uH >= 1.2 A (e.g. SRN8040-680M)")
    l1[1, 2] += sw, P12V
    r_ft, r_fb = R("90.9k"), R("10k")
    P12V & r_ft & fb & r_fb & GND           # 1.2 V * (1 + 90.9/10) = 12.1 V
    # type-3 ripple injection (datasheet table 6-1): RA*CA >= tON*(VIN-VOUT)/20 mV
    r_a, c_a, c_bb = R("470k"), C("3.3n", note="50 V"), C("1n")
    sw & r_a & ra
    c_a[1, 2] += ra, P12V
    c_bb[1, 2] += ra, fb
    for _ in range(2):
        co = C("10u", "1206", note="25 V")
        co[1, 2] += P12V, GND
    testpoint("+12V_AUX")[1] += P12V

    # +5VA
    ldo = _fields(Part("Regulator_Linear", "LP2985-5.0"), "C74511")
    ldo["VIN"] += P12V
    ldo["ON/~{OFF}"] += P12V
    ldo["GND"] += GND
    ldo["VOUT"] += P5VA
    c_bp = C("10n")
    c_bp[1, 2] += ldo["BP"], GND
    c_i = C("1u", "0805", note="25 V")
    c_i[1, 2] += P12V, GND
    c_o = C("2.2u", "0805")
    c_o[1, 2] += P5VA, GND
    testpoint("+5VA")[1] += P5VA


@subcircuit
def fan():
    """Fallback only: the design is fanless (extrusion as heatsink). Header + driver fitted as DNP."""
    j = Part("Connector_Generic", "Conn_01x04", value="FAN 4-pin",
             footprint="Connector:FanPinHeader_1x04_P2.54mm_Vertical")
    j.fields["DNP"] = "yes"
    j[1] += GND
    j[2] += P12V
    tach, pwm = Net("FAN_TACH_PIN"), Net("FAN_PWM_PIN")
    j[3] += tach
    j[4] += pwm
    r_t, r_tp = R("1k"), R("10k")
    tach & r_t & FAN_TACH
    r_tp[1, 2] += P3V3, FAN_TACH
    q = NMOS_small()
    q["D", "S", "G"] += pwm, GND, FAN_PWM      # open-drain PWM (fan has its own pull-up); inverted in firmware
    r_g = R("100k")
    r_g[1, 2] += FAN_PWM, GND
