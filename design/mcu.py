"""
STM32G474RET6 (LQFP-64) + debug/UART headers + UI ribbon connector (2x10, 2.54 mm). On supply_control since the
2026-09-30 board split; the power-stage signals arrive through the B2B header (design/interconnect.py). The analog
inputs from the power board get a 100 R + 1 nF filter at the MCU pin (header pickup, ADC sampling kick-back); they are
already filtered at the source, so the extra ~0.1 us doesn't matter, not even for the COMP1/COMP4 trips.

Pin map (alternate functions verified against the KiCad symbol's alternate list):

  PA0  OVP_FLT (COMP1_OUT)          PB0  IL_SNS (ADC1_IN15 / COMP4_INP)   PC0  ENC2_A (TIM1_CH1)
  PA1  VOUT_SNS (ADC1_IN2/COMP1_INP) PB1  OCP_FLT (COMP4_OUT)             PC1  ENC2_B (TIM1_CH2)
  PA2  VTERM_SNS (ADC1_IN3)         PB2  NTC_OUTSW (ADC2_IN12)            PC2  ITH_MON (ADC1_IN8)
  PA3  VIN_SNS (ADC1_IN4)           PB3  PD_SINK_EN                             PC3  NTC_FET (ADC1_IN9)
  PA4  DAC_V (DAC1_OUT1)            PB4  DCIN_ON                           PC4  NTC_IND (ADC2_IN5)
  PA5  DAC_I (DAC1_OUT2)            PB5  OUT_EN                           PC5  NTC_CLAMP (ADC2_IN11)
  PA6  DAC_ICL (DAC2_OUT1)          PB6  CLAMP_DIS                        PC6  ENC1_A (TIM3_CH1)
  PA7  BUZZER (TIM17_CH1)           PB7  I2C1_SDA                         PC7  ENC1_B (TIM3_CH2)
  PA8  I2C2_SDA                     PB8  BOOT0                            PC8  LCD_CS
  PA9  I2C2_SCL                     PB9  PD_IRQ                           PC9  LCD_DC
  PA10 UI_INT                       PB10 LCD_BL (TIM2_CH3)                PC10 UART_TX (USART3)
  PA11 USB_DM                       PB11 (free)                           PC11 UART_RX (USART3)
  PA12 USB_DP                       PB12 BUCK_RUN                         PC12 LCD_RST
  PA13 SWDIO                        PB13 LCD_SCK (SPI2_SCK)               PC13 (free)
  PA14 SWCLK                        PB14 BUCK_PSKIP                       PC14 INA_ALERT
  PA15 I2C1_SCL                     PB15 LCD_MOSI (SPI2_MOSI)             PC15 FAULT (readback)
  PD2  OE_BTN    PF0/PF1 (free)    PG10 NRST

Freed 2026-09-28: PB4 (backlight, OLED has none), PB10/PB11 (fan removed), PF0/PF1 (encoder pushes moved to the
UI board's TCA9535). PB4 reused 2026-10-01 for DCIN_ON (DC input path enable). 2026-10-01: IPS display instead of the
OLED -> backlight PWM LCD_BL on PB10 (TIM2_CH3, TIM2 otherwise unused), PC13 freed (backup-domain pin, weak drive).

USB uses the internal HSI48 + CRS (no crystal). VREF+ is driven by the internal VREFBUF (2.9 V).
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import C, R, _fields, testpoint

PIN_MAP = {
    "PA0": OVP_FLT, "PA1": VOUT_SNS, "PA2": VTERM_SNS, "PA3": VIN_SNS, "PA4": DAC_V, "PA5": DAC_I,
    "PA6": DAC_ICL, "PA7": BUZZER, "PA8": I2C2_SDA, "PA9": I2C2_SCL, "PA10": UI_INT, "PB10": LCD_BL, "PA11": USB_DM,
    "PA12": USB_DP, "PA15": I2C1_SCL,
    "PB0": IL_SNS, "PB3": PD_SINK_EN, "PB4": DCIN_ON, "PB1": OCP_FLT, "PB2": NTC_OUTSW, "PB5": OUT_EN, "PB6": CLAMP_DIS,
    "PB7": I2C1_SDA, "PB9": PD_IRQ, "PB12": BUCK_RUN, "PB13": LCD_SCK,
    "PB14": BUCK_PSKIP, "PB15": LCD_MOSI,
    "PC0": ENC2_A, "PC1": ENC2_B, "PC2": ITH_MON, "PC3": NTC_FET, "PC4": NTC_IND, "PC5": NTC_CLAMP,
    "PC6": ENC1_A, "PC7": ENC1_B, "PC8": LCD_CS, "PC9": LCD_DC, "PC10": UART_TX, "PC11": UART_RX,
    "PC12": LCD_RST, "PC14": INA_ALERT, "PC15": FAULT,
    "PD2": OE_BTN,
}

# UI ribbon: 2x10, 2.54 mm IDC (1.27 mm flat cable, pin n = wire n; was a 1.27 mm header until 2026-10-05). Same table
# is used by ui_design.py for the UI board side.
# 1.9" ST7789 IPS 170x320: SPI2 at 170 MHz / 8 = 21.25 MHz -> full 16-bit frame (870 kbit) in ~41 ms; the firmware redraws only
# changed regions. SCK between two GNDs. Pin 18 = backlight PWM (the module's BLK input).
# Encoder pushes go through the UI board's TCA9535; encoder A/B stay on MCU timers, OE button direct (PD2).
UI_PINOUT = {
    1: P3V3, 2: GND, 3: LCD_SCK, 4: GND, 5: LCD_MOSI, 6: LCD_CS, 7: LCD_DC, 8: LCD_RST, 9: GND, 10: I2C2_SCL,
    11: I2C2_SDA, 12: UI_INT, 13: ENC1_A, 14: ENC1_B, 15: ENC2_A, 16: ENC2_B, 17: OE_BTN, 18: LCD_BL,
    19: BUZZER, 20: P3V3,
}
# Right-angle on both boards (the same part): a straight 2.54 mm header is 8.5 mm tall before the plug goes on, the
# control board's top side has 9.9 mm. Lying down it is 5.1 mm; the body sits at the board edge with the pins past it,
# because the IDC socket (~6 mm thick around rows at 1.27 / 3.81 mm) reaches below the board surface.
UI_CONN_FP = "Connector_PinHeader_2.54mm:PinHeader_2x10_P2.54mm_Horizontal"

# analog inputs that come up the B2B header -> 100 R + 1 nF at the pin
PIN_FILTERED = {n.name for n in (VOUT_SNS, VTERM_SNS, VIN_SNS, IL_SNS, ITH_MON, NTC_FET, NTC_IND, NTC_CLAMP, NTC_OUTSW)}


@subcircuit
def mcu():
    u = Part("MCU_ST_STM32G4", "STM32G474RETx")
    _fields(u, "C521608")
    for name, net in PIN_MAP.items():
        if net.name in PIN_FILTERED:
            pin_net = Net(f"{net.name}_MCU")
            rf, cf = R("100"), C("1n")
            net & rf & pin_net
            cf[1, 2] += pin_net, GND
            u[name] += pin_net
        else:
            u[name] += net
    for name in ("PB11", "PC13", "PF0", "PF1"):      # free (see docstring)
        u[name] += NC

    # power
    u["VDD"] += P3V3
    u["VBAT"] += P3V3
    u["VSS"] += GND
    u["VSSA"] += GND
    u["VDDA"] += P3V3A
    for _ in range(4):
        c = C("100n")
        c[1, 2] += P3V3, GND
    c_bulk = C("4.7u", "0805")
    c_bulk[1, 2] += P3V3, GND
    c_a = C("100n")
    c_a[1, 2] += P3V3A, GND
    vref = Net("VREF+")
    u["VREF+"] += vref
    for v in ("1u", "100n"):
        c = C(v)
        c[1, 2] += vref, GND

    # reset / boot
    nrst, boot0 = Net("NRST"), Net("BOOT0")
    u["PG10"] += nrst
    u["PB8"] += boot0
    c_r = C("100n")
    c_r[1, 2] += nrst, GND
    r_b = R("10k")
    r_b[1, 2] += boot0, GND
    sw_r = Part("Switch", "SW_Push", value="RESET", footprint="Button_Switch_THT:SW_PUSH_6mm")
    sw_r[1, 2] += nrst, GND
    sw_b = Part("Switch", "SW_Push", value="BOOT", footprint="Button_Switch_THT:SW_PUSH_6mm")
    sw_b[1, 2] += boot0, P3V3

    # SWD (ARM 10-pin 1.27 mm)
    swd = Part("Connector_Generic", "Conn_02x05_Odd_Even", value="SWD",
               footprint="Connector_PinHeader_1.27mm:PinHeader_2x05_P1.27mm_Vertical")
    swd[1] += P3V3
    swd[2] += u["PA13"]
    swd[3, 5, 9] += GND, GND, GND
    swd[4] += u["PA14"]
    swd[6] += NC                        # SWO pin reused for PD_SINK_EN
    swd[7, 8] += NC, NC
    swd[10] += nrst

    # UART header (hand-solder friendly 2.54 mm)
    uart = Part("Connector_Generic", "Conn_01x04", value="UART",
                footprint="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical")
    uart[1, 2, 3, 4] += P3V3, UART_TX, UART_RX, GND

    # bus pull-ups
    for net, val in ((I2C1_SCL, "4.7k"), (I2C1_SDA, "4.7k"), (I2C2_SCL, "2.2k"), (I2C2_SDA, "2.2k"),
                     (UI_INT, "10k"), (INA_ALERT, "10k")):
        r = R(val)
        r[1, 2] += P3V3, net

    # UI ribbon
    j = Part("Connector_Generic", "Conn_02x10_Odd_Even", ref="J5", value="UI ribbon", footprint=UI_CONN_FP)
    for pin, net in UI_PINOUT.items():
        j[pin] += net
    return u
