"""
STM32G474RET6 (LQFP-64) + debug/UART headers + UI ribbon connector.

Pin map (alternate functions verified against the KiCad symbol's alternate list):

  PA0  OVP_FLT (COMP1_OUT)          PB0  IL_SNS (ADC1_IN15 / COMP4_INP)   PC0  ENC2_A (TIM1_CH1)
  PA1  VOUT_SNS (ADC1_IN2/COMP1_INP) PB1  OCP_FLT (COMP4_OUT)             PC1  ENC2_B (TIM1_CH2)
  PA2  VTERM_SNS (ADC1_IN3)         PB2  NTC_OUTSW (ADC2_IN12)            PC2  ITH_MON (ADC1_IN8)
  PA3  VIN_SNS (ADC1_IN4)           PB3  PD_SINK_EN                             PC3  NTC_FET (ADC1_IN9)
  PA4  DAC_V (DAC1_OUT1)            PB4  LCD_BL (TIM16_CH1)               PC4  NTC_IND (ADC2_IN5)
  PA5  DAC_I (DAC1_OUT2)            PB5  OUT_EN                           PC5  NTC_CLAMP (ADC2_IN11)
  PA6  DAC_ICL (DAC2_OUT1)          PB6  CLAMP_DIS                        PC6  ENC1_A (TIM3_CH1)
  PA7  BUZZER (TIM17_CH1)           PB7  I2C1_SDA                         PC7  ENC1_B (TIM3_CH2)
  PA8  I2C2_SDA                     PB8  BOOT0                            PC8  LCD_CS
  PA9  I2C2_SCL                     PB9  PD_IRQ                           PC9  LCD_DC
  PA10 UI_INT                       PB10 FAN_PWM (TIM2_CH3)               PC10 UART_TX (USART3)
  PA11 USB_DM                       PB11 FAN_TACH (TIM2_CH4)              PC11 UART_RX (USART3)
  PA12 USB_DP                       PB12 BUCK_RUN                         PC12 LCD_RST
  PA13 SWDIO                        PB13 LCD_SCK (SPI2_SCK)               PC13 PWR_BTN (WKUP2)
  PA14 SWCLK                        PB14 BUCK_PSKIP                       PC14 INA_ALERT
  PA15 I2C1_SCL                     PB15 LCD_MOSI (SPI2_MOSI)             PC15 FAULT (readback)
  PD2  OE_BTN    PF0 ENC1_SW    PF1 ENC2_SW    PG10 NRST

USB uses the internal HSI48 + CRS (no crystal). VREF+ is driven by the internal VREFBUF (2.9 V).
"""

from skidl import Net, Part, subcircuit

from .nets import *
from .parts import C, R, _fields, testpoint

PIN_MAP = {
    "PA0": OVP_FLT, "PA1": VOUT_SNS, "PA2": VTERM_SNS, "PA3": VIN_SNS, "PA4": DAC_V, "PA5": DAC_I,
    "PA6": DAC_ICL, "PA7": BUZZER, "PA8": I2C2_SDA, "PA9": I2C2_SCL, "PA10": UI_INT, "PA11": USB_DM,
    "PA12": USB_DP, "PA15": I2C1_SCL,
    "PB0": IL_SNS, "PB3": PD_SINK_EN, "PB1": OCP_FLT, "PB2": NTC_OUTSW, "PB4": LCD_BL, "PB5": OUT_EN, "PB6": CLAMP_DIS,
    "PB7": I2C1_SDA, "PB9": PD_IRQ, "PB10": FAN_PWM, "PB11": FAN_TACH, "PB12": BUCK_RUN, "PB13": LCD_SCK,
    "PB14": BUCK_PSKIP, "PB15": LCD_MOSI,
    "PC0": ENC2_A, "PC1": ENC2_B, "PC2": ITH_MON, "PC3": NTC_FET, "PC4": NTC_IND, "PC5": NTC_CLAMP,
    "PC6": ENC1_A, "PC7": ENC1_B, "PC8": LCD_CS, "PC9": LCD_DC, "PC10": UART_TX, "PC11": UART_RX,
    "PC12": LCD_RST, "PC13": PWR_BTN, "PC14": INA_ALERT, "PC15": FAULT,
    "PD2": OE_BTN, "PF0": ENC1_SW, "PF1": ENC2_SW,
}

# UI ribbon (2x13 IDC). Same table is used by ui_design.py for the UI board side.
UI_PINOUT = {
    1: P3V3, 2: P3V3, 3: GND, 4: LCD_SCK, 5: GND, 6: LCD_MOSI, 7: LCD_CS, 8: LCD_DC, 9: LCD_RST, 10: LCD_BL,
    11: GND, 12: I2C2_SDA, 13: I2C2_SCL, 14: UI_INT, 15: ENC1_A, 16: ENC1_B, 17: ENC1_SW, 18: GND,
    19: ENC2_A, 20: ENC2_B, 21: ENC2_SW, 22: OE_BTN, 23: PWR_BTN, 24: BUZZER, 25: GND, 26: GND,
}


@subcircuit
def mcu():
    u = Part("MCU_ST_STM32G4", "STM32G474RETx")
    _fields(u, "C521608")
    for name, net in PIN_MAP.items():
        u[name] += net

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
    j = Part("Connector_Generic", "Conn_02x13_Odd_Even", ref="J5", value="UI ribbon",
             footprint="Connector_IDC:IDC-Header_2x13_P2.54mm_Vertical")
    for pin, net in UI_PINOUT.items():
        j[pin] += net
    return u
