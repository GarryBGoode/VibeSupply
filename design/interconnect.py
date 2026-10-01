"""
Board-to-board header between supply_power (lowest slot) and supply_control (~21 mm above it).

Mechanics: a 2x20 2.54 mm female header on each board (power: top side, control: bottom side), long male-male pins
in between (19.8 mm with the parts at hand; pulled out a little they bridge 21 mm). The two boards plug together
outside the enclosure and slide in as one unit.

Pin numbers in B2B_PINOUT are the POWER board's. The control board's socket sits on its bottom side, i.e. it is
mirrored: with KiCad's default left/right flip, a straight pin that lands on power pin 2k-1 lands on control pin 2k
(and vice versa). `b2b("control")` applies that swap, so place the control socket with its pin 1 directly above the
power socket's pin 2 (same row, same X), and its pin 2 above the power socket's pin 1.

Only signals and logic power cross; no power-stage current and no power-stage return current. Ground pins are spread
so every analog signal has a GND neighbour; LOGIC_IN (up to ~60 V with a 48 V battery on the DC input) has only GND
around it.
"""

from skidl import Part, subcircuit

from .nets import *
from .parts import C

B2B_FP = "Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical"

B2B_PINOUT = {
    # logic power: LOGIC_IN up (-> LMR38010 on the control board), +3V3 down (INA228s, VOM1271 LED, pull-ups, +3V3A)
    1: LOGIC_IN, 2: GND, 3: GND, 4: GND, 5: P3V3, 6: P3V3, 7: GND, 8: GND,
    # digital
    9: I2C1_SCL, 10: I2C1_SDA, 11: PD_IRQ, 12: INA_ALERT, 13: PD_SINK_EN, 14: OUT_EN, 15: BUCK_RUN, 16: BUCK_PSKIP,
    17: CLAMP_DIS, 18: FAULT, 19: OVP_FLT, 20: OCP_FLT, 21: GND, 22: GND,
    # analog: DAC setpoints (filtered on the power board), then the sense signals (RC-filtered on both ends)
    23: DAC_V, 24: GND, 25: DAC_I, 26: GND, 27: DAC_ICL, 28: GND,
    29: VOUT_SNS, 30: IL_SNS, 31: VTERM_SNS, 32: VIN_SNS, 33: ITH_MON, 34: GND,
    35: NTC_FET, 36: NTC_IND, 37: NTC_CLAMP, 38: NTC_OUTSW, 39: GND, 40: GND,
}
assert sorted(B2B_PINOUT) == list(range(1, 41))


def mirrored(pin):
    """Power-board pin -> control-board pin on the same straight pin (odd/even swap within a row)."""
    return pin + 1 if pin % 2 else pin - 1


@subcircuit
def b2b(side):
    """side = "power" (socket on the top side) or "control" (socket on the bottom side, mirrored)."""
    assert side in ("power", "control")
    j = Part("Connector_Generic", "Conn_02x20_Odd_Even", value=f"B2B to supply_{'control' if side == 'power' else 'power'}", footprint=B2B_FP)
    for pin, net in B2B_PINOUT.items():
        j[pin if side == "power" else mirrored(pin)] += net
    # local decoupling where +3V3 enters / leaves
    for v, size in (("4.7u", "0805"), ("100n", "0603")):
        c = C(v, size)
        c[1, 2] += P3V3, GND
