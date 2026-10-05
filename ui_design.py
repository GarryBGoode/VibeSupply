"""
USB-C PD bench supply — UI board (skidl). Connects to supply_control (J703) via the 2x10 2.54 mm ribbon (design/mcu.py UI_PINOUT).

Run:     .venv/Scripts/python ui_design.py
Output:  out/supply_ui.net, out/supply_ui_bom.csv

Contents: 1.9" ST7789 170x320 IPS SPI module header (8-pin GND/VCC/SCL/SDA/RES/DC/CS/BLK, wired to the module, backlight
PWM from the MCU),
2x Alps EC10E mouse-style scroll wheels (left = voltage, right = current; A/B RC-debounced, direct to MCU timers) with a
B3F-1020 tact switch under the free axle end as the wheel push (on the expander), 3 navigation buttons + CC / CV panel LEDs
(3 mm THT, legs long enough to reach the panel) + FAULT LED on a TCA9535 (I2C 0x20), connector for the panel-mount latching OUTPUT button (E-Switch PV4, red ring LED driven by the expander),
magnetic buzzer. Everything 0603/0805/THT: easy to rework. The POWER rocker is wired to supply_control (LMR38010 EN).
"""

import builtins
import csv
from collections import defaultdict
from pathlib import Path

from skidl import ERC, KICAD10, Net, Part, generate_netlist

from design import reflock
from design.mcu import UI_CONN_FP, UI_PINOUT
from design.nets import *
from design.parts import PROJ_FP, C, LED, NMOS_small, R, _fields, schottky_1a, testpoint

OUT = Path(__file__).with_name("out")

# Omron B3F-1020: 6x6 THT, 5.0 mm, 100 gf, 1M operations. Wheel pushes and nav buttons (printed caps) use the same part;
# B3F-1022 (150 gf, 300k operations) fits the same footprint if 100 gf turns out too light.
# The height belongs to the front panel design: CAD_3D/geom_defs.py TactileSwitchB3FData.
TACT_MPN = "B3F-1020"
TACT_FP = "Button_Switch_THT:SW_TH_Tactile_Omron_B3F-102x"


def tact(name):
    sw = Part("Switch", "SW_Push", value=name, footprint=TACT_FP)
    sw.fields["MPN"] = TACT_MPN
    return sw


def debounced_input(src_pin_net, out_net, pull_to=None):
    """10k pull-up (or pull-down) + 1k/10nF RC towards the ribbon."""
    rp, rs, c = R("10k"), R("1k"), C("10n")
    rp[1, 2] += (pull_to or P3V3), src_pin_net
    src_pin_net & rs & out_net
    c[1, 2] += out_net, GND


def build():
    # ---- ribbon: the same right-angle header as on supply_control, it leaves the UI board sideways from its bottom side
    j = Part("Connector_Generic", "Conn_02x10_Odd_Even", ref="J1", value="to supply_control", footprint=UI_CONN_FP)
    for pin, net in UI_PINOUT.items():
        j[pin] += net
    for v in ("10u", "100n"):
        c = C(v, "0805")
        c[1, 2] += P3V3, GND

    # ---- display module: 1.9" IPS 170x320, ST7789 (HESTORE IPS-1.9-ST7789-SPI-M; 62 x 29 mm PCB, 4x d2.0 holes on
    # 25.8 x 57.9 mm, active area 22.7 x 42.72 mm). Header GND/VCC/SCL/SDA/RES/DC/CS/BLK, 2.54 mm; SCL = SCK, SDA = MOSI
    # (write-only SPI). VCC 3-5 V (on-module LDO); backlight 4 LEDs in parallel, ~80 mA at full brightness.
    # The module is screwed to the panel and WIRED: a short 8-way ribbon soldered into the module's header holes, with a
    # 1x08 2.54 mm socket housing on this right-angle pin header (there is no room for a board-to-board socket stack).
    d = Part("Connector_Generic", "Conn_01x08", value="IPS 1.9in ST7789 SPI (wired)",
             footprint="Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Horizontal")
    bl = Net("LCD_BLK")
    for pin, net in zip(range(1, 9), (GND, P3V3, LCD_SCK, LCD_MOSI, LCD_RST, LCD_DC, LCD_CS, bl)):
        d[pin] += net
    # BLK is normally a transistor input on these modules (floating = on) -> the MCU's PWM drives it directly. The 100R
    # keeps the GPIO safe (~3 mA) if a module turns out to have BLK straight on the LED anodes - check with a meter.
    rbl = R("100")
    rbl[1, 2] += LCD_BL, bl
    c = C("10u", "0805")                         # local bulk for the backlight's PWM current steps
    c[1, 2] += P3V3, GND

    # ---- scroll wheels: ENC1 = voltage (left), ENC2 = current (right). EC10E1220505: 24 detents / 12 PPR, shaft axis
    # 7.0 mm above the board; printed wheel on a hex axle through the hollow shaft. The axle's free end rests on a tact
    # switch (wheel push = unlock/lock), mouse style. Common C to GND.
    for a, b, s, name in ((ENC1_A, ENC1_B, ENC1_SW, "V"), (ENC2_A, ENC2_B, ENC2_SW, "I")):
        enc = Part("Device", "RotaryEncoder", value="EC10E1220505",
                   footprint=f"{PROJ_FP}:RotaryEncoder_Alps_EC10E_Horizontal")
        enc["C"] += GND
        push = tact(f"{name} WHEEL PUSH")
        for pins, net in ((enc["A"], a), (enc["B"], b), (push[1], s)):
            raw = Net(f"{net.name}_RAW")
            pins += raw
            debounced_input(raw, net)
        push[2] += GND

    # ---- I/O expander: nav buttons, LEDs
    ex = Part("Interface_Expansion", "TCA9535PWR")
    _fields(ex, "C130204", "I2C 0x20")
    ex["VCC"] += P3V3
    ex["GND"] += GND
    ex["A0", "A1", "A2"] += GND, GND, GND
    ex["SCL"] += I2C2_SCL
    ex["SDA"] += I2C2_SDA
    ex["~{INT}"] += UI_INT
    c = C("100n")
    c[1, 2] += P3V3, GND
    # NB: address expander pins by NUMBER. skidl also reads "P12" as "pin number 12" (= GND here).
    # TCA9535PWR: P00..P07 = pins 4..11, P10..P17 = pins 13..20
    port0 = {f"P0{i}": 4 + i for i in range(8)}
    port1 = {f"P1{i}": 13 + i for i in range(8)}
    # menu: the wheels scroll/adjust, Left/Right move the digit cursor and switch screens, Enter confirms
    for i, name in enumerate(("LEFT", "RIGHT", "ENTER")):
        sw = tact(name)
        n = Net(f"BTN_{name}")
        sw[1, 2] += n, GND
        rp = R("10k")
        rp[1, 2] += P3V3, n
        ex[port0[f"P0{i}"]] += n
    ex[port0["P05"]] += ENC1_SW                    # wheel pushes (RC-debounced above, active low)
    ex[port0["P06"]] += ENC2_SW
    for p in ("P03", "P04", "P07"):
        testpoint(f"EXP_{p}")[1] += ex[port0[p]]
    # LEDs (expander sinks, active low): P10 OUTPUT button ring LED (below), P12 CC, P13 CV, P14 FAULT.
    # CC / CV: 3 mm diffused THT, mounted standing off the board up to the panel (standard-efficiency red / green,
    # Vf ~2 V -> ~4 mA with 330R; change R for brightness). The footprint is only the two pads: the body is ~10 mm above
    # the board, so the courtyard doesn't claim board area. FAULT stays an on-board 0805 (debug).
    for pin, color, label in (("P12", "red", "CC"), ("P13", "green", "CV"), ("P14", "yellow", "FAULT")):
        if label in ("CC", "CV"):
            led = Part("Device", "LED", value=f"{color} 3mm diffused {label}", footprint=f"{PROJ_FP}:LED_D3.0mm_Standoff")
        else:
            led = LED(color)
        rl = R("330")
        k = Net(f"LED_{label}_K")
        P3V3 & rl & led["A"]
        led["K"] += k
        ex[port1[pin]] += k
    for p in ("P11", "P15", "P16", "P17"):
        testpoint(f"EXP_{p}")[1] += ex[port1[p]]

    # ---- OUTPUT: panel-mount latching push button, E-Switch PV4 (19 mm, SPDT on-on, gold contacts, red ring LED without
    # an internal resistor, 1.8 V @ 20 mA). The switch only reports its position (level, active low = pushed in); the
    # firmware owns the output state and the LED shows the REAL state (on / blinking = tripped or not armed). Pushed in at
    # power-up or after a trip -> stays off until the button is released and pushed again.
    # Connector: 1 switch NO, 2 switch COM (GND), 3 LED anode (+3V3 via 100R, ~13 mA), 4 LED cathode (expander P10)
    oe_raw, oe_led_a, oe_led_k = Net("OE_BTN_RAW"), Net("OE_LED_A"), Net("LED_OE_K")
    debounced_input(oe_raw, OE_BTN)
    jp = Part("Connector_Generic", "Conn_01x04", value="OUTPUT panel button",
              footprint="Connector_JST:JST_XH_B4B-XH-A_1x04_P2.50mm_Vertical")
    jp[1, 2, 3, 4] += oe_raw, GND, oe_led_a, oe_led_k
    ra = R("100")
    ra[1, 2] += P3V3, oe_led_a
    ex[port1["P10"]] += oe_led_k

    # ---- buzzer (magnetic, 3 V) with low-side NMOS + freewheel diode
    bz = Part("Device", "Buzzer", value="magnetic 3V", footprint="Buzzer_Beeper:Buzzer_12x9.5RM7.6")
    q = NMOS_small()
    bz_n = Net("BUZZER_K")
    bz[1, 2] += P3V3, bz_n
    q["D", "S", "G"] += bz_n, GND, BUZZER
    rg = R("100k")
    rg[1, 2] += BUZZER, GND
    df = schottky_1a("SS14")
    df["A"] += bz_n
    df["K"] += P3V3

    # one per board screw of the front panel (CAD_3D/geom_defs.py UIPanelData.screw_placements, placed by
    # tools/ui_board_setup.py)
    for _ in range(3):
        Part("Mechanical", "MountingHole", value="M3", footprint="MountingHole:MountingHole_3.2mm_M3")


def write_bom(path):
    groups = defaultdict(list)
    for p in builtins.default_circuit.parts:
        key = (p.name, str(p.value), p.footprint, p.fields.get("LCSC", ""))
        groups[key].append(p.ref)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Qty", "Refs", "Part", "Value", "Footprint", "LCSC"])
        for (name, value, fp, lcsc), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            w.writerow([len(refs), " ".join(sorted(refs)), name, value, fp, lcsc])


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    build()
    # stable refs across edits (design/reflock.py); the first run seeds the lock from skidl's automatic numbering
    reflock.assign(list(builtins.default_circuit.parts), lambda p: "ui", lambda b: (1, 1000),
                   Path(__file__).with_name("refs_ui.lock.json"), lambda parts: {id(p): p.ref for p in parts})
    # drop the power/control-board nets from design/nets.py that have nothing attached on this board
    empty = [n for n in builtins.default_circuit.nets if not n.pins and n is not builtins.NC]
    builtins.default_circuit.rmv_nets(*empty)
    ERC()
    generate_netlist(tool=KICAD10, file_=str(OUT / "supply_ui.net"))
    write_bom(OUT / "supply_ui_bom.csv")
    print(f"parts: {len(builtins.default_circuit.parts)}")
