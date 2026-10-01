"""
USB-C PD bench supply — supply_control board (skidl): ~21 mm above supply_power, 110 x 74.5 mm (2026-09-30).

Run:     .venv/Scripts/python control_design.py
Output:  out/supply_control.net (KiCad netlist -> import into kicad/supply_control), out/supply_control_bom.csv

Contents: STM32G474 (SWD, UART, reset/boot, UI ribbon), isolated USB (ADuM3160 + B0505S), LMR38010 3.3 V buck with
the isolated-USB leg of the LOGIC_IN diode-OR, and the 2x20 B2B socket (bottom side, mirrored; design/interconnect.py).
The UI board (ui_design.py) connects to the ribbon header J703 on this board.
"""

from design import board, housekeeping, interconnect, mcu, usb_iso


def build():
    housekeeping.logic_supply(tag="logic_supply")
    usb_iso.usb_isolated(tag="usb_isolated")
    mcu.mcu(tag="mcu")
    interconnect.b2b("control", tag="b2b_control")


if __name__ == "__main__":
    build()
    board.finish("supply_control")
