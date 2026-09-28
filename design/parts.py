"""
Part library + helpers for the USB-C PD bench supply.

- Generic passives (R, C, CP, L, ...) with default footprints and an optional LCSC number.
- Custom symbols for parts that are not in the KiCad 10 libraries. Pinouts are copied from the
  datasheets (see comments); each one lists the source it was checked against.
- KiCad library parts are used directly where they exist.

Footprint size policy (see PLAN.md): 0603 by default (assembly-friendly and still hand-solderable),
bigger where power/voltage needs it. No 0402 anywhere.
"""

import os

from skidl import KICAD10, Net, Part, footprint_search_paths, lib_search_paths, set_default_tool
from skidl.pin import pin_types as T

set_default_tool(KICAD10)
footprint_search_paths[KICAD10] = [os.path.expandvars(r"%APPDATA%\kicad\10.0")]
lib_search_paths[KICAD10].append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "symbols"))

PROJ_FP = "supply1"          # project footprint library: footprints/supply1.pretty
SYM_LIB = "supply1"          # project symbol library: symbols/supply1.kicad_sym (generated)
PROJ_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------

_R_FP = {"0603": "Resistor_SMD:R_0603_1608Metric", "0805": "Resistor_SMD:R_0805_2012Metric",
         "1206": "Resistor_SMD:R_1206_3216Metric", "2512": "Resistor_SMD:R_2512_6332Metric"}
_C_FP = {"0603": "Capacitor_SMD:C_0603_1608Metric", "0805": "Capacitor_SMD:C_0805_2012Metric",
         "1206": "Capacitor_SMD:C_1206_3216Metric", "1210": "Capacitor_SMD:C_1210_3225Metric"}


def _fields(p, lcsc=None, note=None):
    if lcsc:
        p.fields["LCSC"] = lcsc
    if note:
        p.fields["Note"] = note
    return p


def R(value, size="0603", lcsc=None, note=None):
    return _fields(Part("Device", "R", value=value, footprint=_R_FP[size]), lcsc, note)


def C(value, size="0603", lcsc=None, note=None):
    return _fields(Part("Device", "C", value=value, footprint=_C_FP[size]), lcsc, note)


def CP(value, footprint, lcsc=None, note=None):
    return _fields(Part("Device", "C_Polarized", value=value, footprint=footprint), lcsc, note)


def L(value, footprint, lcsc=None, note=None):
    return _fields(Part("Device", "L", value=value, footprint=footprint), lcsc, note)


def FB(value="600R@100MHz", size="0603"):
    return Part("Device", "FerriteBead_Small", value=value,
                footprint=f"Inductor_SMD:L_{size}_1608Metric" if size == "0603" else f"Inductor_SMD:L_{size}_2012Metric")


def LED(color="green", size="0805"):
    return Part("Device", "LED", value=color, footprint=f"LED_SMD:LED_{size}_2012Metric")


def NMOS_small():
    """2N7002 in SOT-23 (logic switching)."""
    return Part("Transistor_FET", "2N7002", footprint="Package_TO_SOT_SMD:SOT-23")


def PNP_small():
    return Part("Transistor_BJT", "BC857", footprint="Package_TO_SOT_SMD:SOT-23", lcsc="C556165") \
        if False else _fields(Part("Transistor_BJT", "BC857", footprint="Package_TO_SOT_SMD:SOT-23"), "C556165")


def schottky_small():
    """BAT54W (SOT-323) small-signal Schottky: diode-OR into ITH, clamps."""
    return Part("Diode", "BAT54W", footprint="Package_TO_SOT_SMD:SOT-323_SC-70")


def schottky_1a(value="SS110"):
    """1 A / 100 V Schottky (SMA)."""
    return Part("Device", "D_Schottky", value=value, footprint="Diode_SMD:D_SMA")


def tvs(value, footprint="Diode_SMD:D_SMC", lcsc=None):
    """Unidirectional TVS (KiCad's D_TVS is the bidirectional symbol, so D_Zener is used: pins K, A)."""
    return _fields(Part("Device", "D_Zener", value=value, footprint=footprint), lcsc)


def comparator():
    """LMV331 single comparator, open-drain output, SOT-23-5 (pins 1 +, 2 V-, 3 -, 4 OUT, 5 V+)."""
    return Part("Comparator", "LMV331", footprint="Package_TO_SOT_SMD:SOT-23-5")


def ntc(value="10k B3950"):
    return Part("Device", "Thermistor_NTC", value=value, footprint="Resistor_SMD:R_0603_1608Metric")


def testpoint(name):
    tp = Part("Connector", "TestPoint", footprint="TestPoint:TestPoint_Pad_D1.0mm")
    tp.fields["Label"] = name
    return tp


def power_fet(model="CSD18531Q5A"):
    """Power MOSFETs, all SON 5x6 with pins 1-3 S, 4 G, 5-8 + tab D.
    CSD18531Q5A (60 V logic-level, buck), CSD18540Q5B (60 V, USB sink path; KiCad has no symbol of its own, the
    CSD18532Q5B one has the same package/pinout), BSC040N10NS5 / ISC030N10NM6 (100 V: DC input, output switch, clamp)."""
    if model == "CSD18531Q5A":
        return _fields(Part("Transistor_FET", "CSD18531Q5A", footprint="Package_TO_SOT_SMD:TDSON-8-1"), "C2876524")
    if model == "CSD18540Q5B":
        return _fields(Part("Transistor_FET", "CSD18532Q5B", value="CSD18540Q5B",
                            footprint="Package_TO_SOT_SMD:TDSON-8-1"), "C86513")
    if model in ("ISC030N10NM6", "BSC040N10NS5"):
        p = Part("Transistor_FET", "BSC040N10NS5", value=model,
                 footprint="Package_SON:Infineon_PG-TDSON-8_6.15x5.15mm")
        return _fields(p, {"ISC030N10NM6": "C3278643", "BSC040N10NS5": "C534334"}[model])
    raise ValueError(model)


# ------------------------------------------------------------------------------------------------
# custom symbols
# ------------------------------------------------------------------------------------------------

CUSTOM_DEFS = {}


def _custom(name, ref_prefix, footprint, pins, lcsc=None, desc=""):
    """Register a custom part (pins: list of (num, name, type)). The KiCad symbol is generated from this
    table into symbols/supply1.kicad_sym (design/symgen.py), and the part is loaded from that library."""
    CUSTOM_DEFS[name] = dict(ref_prefix=ref_prefix, footprint=footprint, pins=pins, lcsc=lcsc, desc=desc)

    def make(**kw):
        prt = Part(SYM_LIB, name, **kw)
        if lcsc:
            prt.fields["LCSC"] = lcsc
        return prt
    return make


# Diodes AP33772S (DS46176 Rev. 10, table 1), W-QFN4040-24 (Type A1): EP 2.7 x 2.7 mm, 0.5 mm pitch
AP33772S = _custom("AP33772S", "U", "Package_DFN_QFN:QFN-24-1EP_4x4mm_P0.5mm_EP2.7x2.7mm_ThermalVias", [
    (1, "ISENP", T.INPUT), (2, "NC", T.NOCONNECT), (3, "GND", T.PWRIN), (4, "SDA", T.BIDIR),
    (5, "SCL", T.INPUT), (6, "FLIP", T.OUTPUT), (7, "GPIO", T.BIDIR), (8, "LED", T.OUTPUT),
    (9, "INT", T.OUTPUT), (10, "NC", T.NOCONNECT), (11, "VSEL", T.PASSIVE), (12, "V18", T.PWROUT),
    (13, "OTP", T.PASSIVE), (14, "NC", T.NOCONNECT), (15, "IFB", T.PASSIVE), (16, "CC2", T.BIDIR),
    (17, "CC1", T.BIDIR), (18, "DN", T.BIDIR), (19, "DP", T.BIDIR), (20, "V5V", T.PWROUT),
    (21, "NC", T.NOCONNECT), (22, "VOUT", T.INPUT), (23, "PWR_EN", T.OUTPUT), (24, "VCC", T.PWRIN),
    (25, "EP", T.PWRIN)], lcsc="C50341643", desc="USB PD 3.1 EPR (28 V) sink controller, I2C host control")

# ADI LTC7803 MSE (MSOP-16 with exposed pad), pin numbers from the datasheet pin configuration (MSE package)
LTC7803 = _custom("LTC7803", "U", "Package_SO:MSOP-16-1EP_3x4.039mm_P0.5mm_EP1.651x2.845mm_ThermalVias", [
    (1, "TRACK/SS", T.PASSIVE), (2, "SENSE+", T.INPUT), (3, "SENSE-", T.INPUT), (4, "VFB", T.INPUT),
    (5, "ITH", T.PASSIVE), (6, "RUN", T.INPUT), (7, "FREQ", T.PASSIVE), (8, "PLLIN/SPREAD", T.INPUT),
    (9, "MODE", T.INPUT), (10, "INTVCC", T.PWROUT), (11, "EXTVCC", T.PWRIN), (12, "VIN", T.PWRIN),
    (13, "BG", T.OUTPUT), (14, "BOOST", T.PASSIVE), (15, "TG", T.OUTPUT), (16, "SW", T.PASSIVE),
    (17, "GND", T.PWRIN)], lcsc="C1016554", desc="40 V synchronous buck controller, 100 % duty")

# TI LM74800-Q1 (SNOSD95C Table 6-1), WSON-12 DRR 3x3. Exposed pad = RTN: leave FLOATING (datasheet).
LM74800 = _custom("LM74800", "U", "Package_SON:WSON-12-1EP_3x3mm_P0.5mm_EP1.5x2.5mm", [
    (1, "DGATE", T.OUTPUT), (2, "A", T.INPUT), (3, "VSNS", T.INPUT), (4, "SW", T.PASSIVE),
    (5, "OV", T.INPUT), (6, "EN/UVLO", T.INPUT), (7, "GND", T.PWRIN), (8, "HGATE", T.OUTPUT),
    (9, "OUT", T.INPUT), (10, "VS", T.PWRIN), (11, "CAP", T.PASSIVE), (12, "C", T.INPUT),
    (13, "RTN", T.NOCONNECT)], lcsc="C3215600", desc="Ideal diode + load switch controller, 65 V")

# TI LMR38010 (SNVSC73B Table 6-1), SO-PowerPAD-8 (DDA)
LMR38010 = _custom("LMR38010", "U", "Package_SO:TI_SO-PowerPAD-8_ThermalVias", [
    (1, "GND", T.PWRIN), (2, "EN", T.INPUT), (3, "VIN", T.PWRIN), (4, "RT", T.PASSIVE),
    (5, "FB", T.INPUT), (6, "PG", T.OPENCOLL), (7, "BOOT", T.PASSIVE), (8, "SW", T.PWROUT),
    (9, "EP", T.PWRIN)], lcsc="C5219310", desc="4.2-80 V 1 A synchronous buck")

# Vishay VOM1271 (doc 83469), SOP-4 2.54 mm: 1 LED anode, 2 LED cathode, 3 Vout-, 4 Vout+
VOM1271 = _custom("VOM1271", "U", "Package_SO:SO-4_4.4x3.6mm_P2.54mm", [
    (1, "A", T.PASSIVE), (2, "K", T.PASSIVE), (3, "VO-", T.PASSIVE), (4, "VO+", T.PASSIVE)],
    lcsc="C146286", desc="Photovoltaic MOSFET driver with fast turn-off")

# Mornsun B0505S-1WR3, SIP-4 2.54 mm: 1 GND(in), 2 Vin, 3 0V(out), 4 +Vo
B0505S = _custom("B0505S-1WR3", "PS", "Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", [
    (1, "GND_IN", T.PWRIN), (2, "VIN", T.PWRIN), (3, "0V_OUT", T.PWROUT), (4, "VOUT", T.PWROUT)],
    lcsc="C7465178", desc="1 W isolated DC-DC 5 V -> 5 V")

# Main inductor: Coilcraft SER2918H-103KL (same body as the -682), pads 1/2 electrical, 3 mounting only (project footprint)
def main_inductor():
    p = Part("Device", "L", value="10uH SER2918H-103KL", footprint=f"{PROJ_FP}:L_Coilcraft_SER2918H")
    return _fields(p, "C3911665", "Isat 32.1 A, DCR 2.86 mOhm. Pad 3 (mounting) must connect to nothing / isolated copper")


# (re)generate symbols/supply1.kicad_sym from CUSTOM_DEFS so the library always matches the pin tables
from .symgen import write_symbol_lib  # noqa: E402

write_symbol_lib(CUSTOM_DEFS, os.path.join(PROJ_DIR, "symbols", "supply1.kicad_sym"))
