"""
Isolated USB device port: USB-C (UFP, 5.1k Rd) -> USBLC6 ESD -> ADuM3160 -> STM32 USB FS.
B0505S-1WR3 powers our logic from the PC (flash/configure without a charger), via LOGIC_IN.
GND_ISO is the PC's ground and must stay separate from GND (isolation gap in layout).
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import B0505S, C, R, _fields


@subcircuit
def usb_isolated():
    j = Part("Connector", "USB_C_Receptacle_USB2.0_16P", ref="J3",
             footprint="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12")
    _fields(j, "C2765186", "PC data port (isolated side)")
    ud_p, ud_m = Net("ISO_UD+"), Net("ISO_UD-")
    j["VBUS"] += VBUS_PC
    j["GND"] += GND_ISO
    j["SHIELD"] += GND_ISO
    j["D+"] += ud_p
    j["D-"] += ud_m
    j["SBU1", "SBU2"] += NC, NC
    for cc in ("CC1", "CC2"):
        rd = R("5.1k")
        n = Net(f"ISO_{cc}")  # named: the PCB puts every ISO_* net into the ISO net class (isolation rule)
        j[cc] += n
        rd[1, 2] += n, GND_ISO
    c_vb = C("4.7u", "0805", note="16 V")
    c_vb[1, 2] += VBUS_PC, GND_ISO

    esd = Part("Power_Protection", "USBLC6-2SC6", footprint="Package_TO_SOT_SMD:SOT-23-6")
    esd["I/O1"] += ud_p
    esd["I/O2"] += ud_m
    esd["VBUS"] += VBUS_PC
    esd["GND"] += GND_ISO

    iso = Part("Interface_USB", "ADUM3160")
    _fields(iso, "C284149")
    vdd1 = Net("ISO_VDD1")
    power_net(vdd1)
    iso["VBUS1"] += VBUS_PC
    iso["GND1"] += GND_ISO
    iso["VDD1"] += vdd1                       # internal 3.3 V LDO output on the PC side
    iso["PDEN"] += vdd1
    iso["SPU"] += vdd1                        # full speed
    iso["UD+"] += ud_p
    iso["UD-"] += ud_m
    iso["GND2"] += GND
    iso["DD+"] += USB_DP
    iso["DD-"] += USB_DM
    iso["PIN"] += P3V3                        # upstream pull-up always enabled
    iso["SPD"] += P3V3                        # full speed
    iso["VDD2"] += P3V3
    iso["VBUS2"] += P3V3                      # 3.3 V operation on side 2: VBUS2 = VDD2
    for v in ("1u", "100n"):
        c1 = C(v)
        c1[1, 2] += vdd1, GND_ISO
        c2 = C(v)
        c2[1, 2] += P3V3, GND

    dc = B0505S()
    dc["VIN"] += VBUS_PC
    dc["GND_IN"] += GND_ISO
    dc["VOUT"] += P5V_ISO
    dc["0V_OUT"] += GND
    ci, co = C("4.7u", "0805", note="16 V"), C("4.7u", "0805", note="16 V")
    ci[1, 2] += VBUS_PC, GND_ISO
    co[1, 2] += P5V_ISO, GND
    r_min = R("2.2k", note="minimum load keeps the unregulated B0505S output below ~6 V")
    r_min[1, 2] += P5V_ISO, GND
