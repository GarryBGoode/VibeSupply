"""
USB-C PD bench supply — UI board (skidl). Connects to supply_control (J703) via the 2x10 1.27 mm ribbon (design/mcu.py UI_PINOUT).

Run:     .venv/Scripts/python ui_design.py
Output:  out/supply_ui.net, out/supply_ui_bom.csv

Contents: 2.42" SSD1309 128x64 SPI OLED module header (7-pin, common GND/VCC/SCL/SDA/RES/DC/CS pinout),
2x EC11E encoders (A/B RC-debounced, direct to MCU timers; pushes on the expander), 5 navigation buttons + 3 status LEDs +
bi-colour output-enable LED on a TCA9535 (I2C 0x20), output-enable and power buttons (on-board tactile +
connector for panel-mount lit buttons), magnetic buzzer. Everything 0603/0805/THT: easy to rework.
"""

import builtins
import csv
from collections import defaultdict
from pathlib import Path

from skidl import ERC, KICAD10, Net, Part, generate_netlist

from design import reflock
from design.mcu import UI_CONN_FP, UI_PINOUT
from design.nets import *
from design.parts import C, LED, NMOS_small, R, _fields, schottky_1a, testpoint

OUT = Path(__file__).with_name("out")


def debounced_input(src_pin_net, out_net, pull_to=None):
    """10k pull-up (or pull-down) + 1k/10nF RC towards the ribbon."""
    rp, rs, c = R("10k"), R("1k"), C("10n")
    rp[1, 2] += (pull_to or P3V3), src_pin_net
    src_pin_net & rs & out_net
    c[1, 2] += out_net, GND


def build():
    # ---- ribbon
    j = Part("Connector_Generic", "Conn_02x10_Odd_Even", ref="J1", value="to supply_control", footprint=UI_CONN_FP)
    for pin, net in UI_PINOUT.items():
        j[pin] += net
    for v in ("10u", "100n"):
        c = C(v, "0805")
        c[1, 2] += P3V3, GND

    # ---- display module (7-pin header, pinout of the common 2.42" SSD1309 SPI modules - check yours;
    # SCL = D0 = SCK, SDA = D1 = MOSI; the module's own boost makes the panel voltage from 3.3 V)
    d = Part("Connector_Generic", "Conn_01x07", value="OLED 2.42in SSD1309 SPI",
             footprint="Connector_PinSocket_2.54mm:PinSocket_1x07_P2.54mm_Vertical")
    for pin, net in zip(range(1, 8), (GND, P3V3, LCD_SCK, LCD_MOSI, LCD_RST, LCD_DC, LCD_CS)):
        d[pin] += net

    # ---- encoders (A/B/push, common to GND)
    for a, b, s in ((ENC1_A, ENC1_B, ENC1_SW), (ENC2_A, ENC2_B, ENC2_SW)):
        enc = Part("Device", "RotaryEncoder_Switch", value="EC11E15244G1",
                   footprint="Rotary_Encoder:RotaryEncoder_Alps_EC11E-Switch_Vertical_H20mm_MountingHoles")
        _fields(enc, "C370970")
        enc["C"] += GND
        enc["S2"] += GND
        for pin, net in (("A", a), ("B", b), ("S1", s)):
            raw = Net(f"{net.name}_RAW")
            enc[pin] += raw
            debounced_input(raw, net)

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
    for i, name in enumerate(("UP", "DOWN", "LEFT", "RIGHT", "ENTER")):
        sw = Part("Switch", "SW_Push", value=name, footprint="Button_Switch_THT:SW_PUSH_6mm")
        n = Net(f"BTN_{name}")
        sw[1, 2] += n, GND
        rp = R("10k")
        rp[1, 2] += P3V3, n
        ex[port0[f"P0{i}"]] += n
    ex[port0["P05"]] += ENC1_SW                    # encoder pushes (RC-debounced above, active low)
    ex[port0["P06"]] += ENC2_SW
    testpoint("EXP_P07")[1] += ex[port0["P07"]]
    # LEDs (expander sinks, active low): P10 OE red, P11 OE green, P12 CC, P13 CV, P14 FAULT
    led_nets = {}
    for pin, color, label in (("P10", "red", "OE_R"), ("P11", "green", "OE_G"), ("P12", "red", "CC"),
                              ("P13", "green", "CV"), ("P14", "yellow", "FAULT")):
        led, rl = LED(color), R("330")
        k = Net(f"LED_{label}_K")
        P3V3 & rl & led["A"]
        led["K"] += k
        ex[port1[pin]] += k
        led_nets[label] = k
    for p in ("P15", "P16", "P17"):
        testpoint(f"EXP_{p}")[1] += ex[port1[p]]

    # ---- output-enable and power buttons: on-board tactile + connector for a panel-mount lit button
    oe_raw, pwr_raw = Net("OE_BTN_RAW"), Net("PWR_BTN_RAW")
    for raw, name in ((oe_raw, "OUTPUT"), (pwr_raw, "POWER")):
        sw = Part("Switch", "SW_Push", value=name, footprint="Button_Switch_THT:SW_PUSH_6mm")
        sw[1, 2] += raw, (GND if name == "OUTPUT" else P3V3)
    debounced_input(oe_raw, OE_BTN)                        # active low
    debounced_input(pwr_raw, PWR_BTN, pull_to=GND)         # active high (WKUP pin), 10k pull-down
    # panel button: 1 switch, 2 switch return, 3 LED red K, 4 LED green K, 5 LED common anode (+3V3 via R)
    jp = Part("Connector_Generic", "Conn_01x05", value="OE panel button",
              footprint="Connector_JST:JST_XH_B5B-XH-A_1x05_P2.50mm_Vertical")
    jp[1, 2] += oe_raw, GND
    jp[3, 4] += led_nets["OE_R"], led_nets["OE_G"]
    ra = R("330")
    ra[1, 2] += P3V3, jp[5]
    jpw = Part("Connector_Generic", "Conn_01x02", value="POWER panel button",
               footprint="Connector_JST:JST_XH_B2B-XH-A_1x02_P2.50mm_Vertical")
    jpw[1, 2] += pwr_raw, P3V3

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

    for _ in range(4):
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
