"""
USB-C PD bench supply — supply_power board (skidl): lowest slot, bottom side = heat path to the extrusion floor.

Run:     .venv/Scripts/python power_design.py
Output:  out/supply_power.net (KiCad netlist -> import into kicad/supply_power), out/supply_power_bom.csv

Contents: USB-C PD input, DC input, input sense, buck + filters, analog control (CV/CC amps, ITH clamp, HW OVP), output
stage with the regen clamp (LTO100 on the board), +12V_AUX / +5VA, the LOGIC_IN feed and a local +3V3A.
The MCU, isolated USB and the 3.3 V buck are on supply_control (control_design.py), connected through the 2x20 B2B
header (design/interconnect.py). The UI board is ui_design.py.
Blocks live in design/*.py; the plan and all design numbers are in PLAN.md, calc/results.md, sim/results.md.
"""

from skidl import Part

from design import board, buck, control, housekeeping, interconnect, output, power_in
from design.nets import GND
from design.parts import _fields

INSERT_FP = "Mounting_Wuerth:Mounting_Wuerth_WA-SMSI-M3_H3mm_9774030360"


def mechanical():
    # No plain mounting holes: the board slides into the extrusion slots (H901-H904 removed 2026-10-01).
    # Case bond + power-stage clamp: countersunk M3 from outside through the floor, spacer block + gap pad, board,
    # into an SMT threaded insert (Wuerth WA-SMSI 9774030360R, M3 through-thread, 3 mm, reflow-soldered) on the top side.
    h = Part("Mechanical", "MountingHole_Pad", value="GND screw (M3 insert)", footprint=INSERT_FP)
    _fields(h, None, "Wuerth 9774030360R WA-SMSI M3 x 3 mm (alt. PEM SMTSO-M3-3ET); LCSC part to pick")
    h[1] += GND
    # LTO100 clamp resistor screw (through its insulated tab, bottom side): same insert, at the TO-247 tab hole
    h2 = Part("Mechanical", "MountingHole_Pad", value="LTO100 screw (M3 insert)", footprint=INSERT_FP)
    _fields(h2, None, "Wuerth 9774030360R WA-SMSI M3 x 3 mm (alt. PEM SMTSO-M3-3ET); LCSC part to pick")
    h2[1] += GND


def build():
    power_in.usb_pd_input(tag="usb_pd_input")
    power_in.dc_input(tag="dc_input")
    power_in.input_sense(tag="input_sense")
    buck.buck(tag="buck")
    control.control(tag="control")
    output.output_stage(tag="output_stage")
    housekeeping.logic_feed(tag="logic_feed")
    housekeeping.aux_supply(tag="aux_supply")
    interconnect.b2b("power", tag="b2b_power")
    mechanical()


if __name__ == "__main__":
    build()
    board.finish("supply_power")
