"""
Global nets shared between the schematic modules.

Naming: power rails are P<volt>..., signals are UPPER_SNAKE. Nets that cross to the MCU carry the
STM32 pin in the comment (pin map: design/mcu.py).
"""

from skidl import Net

# ---------------------------------------------------------------- grounds / rails
GND = Net("GND")
GND_ISO = Net("GND_ISO")          # PC side of the USB isolator (not connected to GND!)

VBUS_RAW = Net("VBUS_RAW")        # USB-C PD connector VBUS (5-28 V)
VBUS_S = Net("VBUS_S")            # after the AP33772S 5 mOhm current-sense resistor
DCIN_RAW = Net("DCIN_RAW")        # DC input wires (9-30 V, survives a 48 V battery)
VIN_BUS = Net("VIN_BUS")          # common bus after both ideal diodes
VIN_PWR = Net("VIN_PWR")          # after the input shunt = buck input
LOGIC_IN = Net("LOGIC_IN")        # diode-OR of VBUS_RAW / DCIN_RAW / P5V_ISO -> 3.3 V buck
P3V3 = Net("+3V3")
P3V3A = Net("+3V3A")              # MCU VDDA (ferrite-filtered)
P12V = Net("+12V_AUX")            # LM5164 aux rail: LTC7803 EXTVCC (must be >= 7 V), clamp gate driver, 5 V analog LDO, fan (DNP)
P5VA = Net("+5VA")                # analog 5 V: op-amps, INA240, comparators, AP33772S V5V (via diode)
VBUS_PC = Net("VBUS_PC")          # isolated side: PC USB VBUS
P5V_ISO = Net("+5V_ISO")          # B0505S output (our side)

# ---------------------------------------------------------------- power stage
ITH = Net("ITH")                  # LTC7803 ITH: pulled down by CV amp, CC amp, current clamp
RUN = Net("RUN")                  # LTC7803 RUN
VOUT_INT = Net("VOUT_INT")        # after post filter (CV sense point)
VOUT_SH = Net("VOUT_SH")          # after 1 mOhm output shunt (clamp attaches here)
VTERM = Net("VTERM")              # after output switch, before fuse
OUT_P = Net("OUT+")               # output terminal (after fuse)
IL_AMP = Net("IL_AMP")            # INA240A3 output, 0.2 V/A (inductor current) -> CC amp

# ---------------------------------------------------------------- MCU interface (pin in comment)
DAC_V = Net("DAC_V")              # PA4 DAC1_OUT1: Vout/10.19
DAC_I = Net("DAC_I")              # PA5 DAC1_OUT2: IL * 0.2 V/A
DAC_ICL = Net("DAC_ICL")          # PA6 DAC2_OUT1: ITH clamp PNP base
DACV_F = Net("DACV_F")            # filtered DAC_V (CV amp +, regen clamp reference)
VOUT_SNS = Net("VOUT_SNS")        # PA1 ADC1_IN2 / COMP1_INP: VOUT_INT / 12
OVP_FLT = Net("OVP_FLT")          # PA0 COMP1_OUT
VTERM_SNS = Net("VTERM_SNS")      # PA2 ADC1_IN3: terminal voltage / 12 (clamped)
VIN_SNS = Net("VIN_SNS")          # PA3 ADC1_IN4: VIN_PWR / 13
IL_SNS = Net("IL_SNS")            # PB0 ADC1_IN15 / COMP4_INP: IL_AMP * 0.68
OCP_FLT = Net("OCP_FLT")          # PB1 COMP4_OUT
ITH_MON = Net("ITH_MON")          # PC2 ADC1_IN8
NTC_FET = Net("NTC_FET")          # PC3 ADC1_IN9
NTC_IND = Net("NTC_IND")          # PC4 ADC2_IN5
NTC_CLAMP = Net("NTC_CLAMP")      # PC5 ADC2_IN11
NTC_OUTSW = Net("NTC_OUTSW")      # PB2 ADC2_IN12
BUCK_RUN = Net("BUCK_RUN")        # PB12 (high = run)
BUCK_PSKIP = Net("BUCK_PSKIP")    # PB14 (high/default = pulse-skip, low = forced continuous)
OUT_EN = Net("OUT_EN")            # PB5 (high = output switch on)
CLAMP_DIS = Net("CLAMP_DIS")      # PB6 (high = regen clamp disabled; default enabled)
FAULT = Net("FAULT")              # PC15 readback: OR of OVP_FLT, OCP_FLT, HW_OVP
I2C1_SCL = Net("I2C1_SCL")        # PA15 (power bus: AP33772S 0x52, INA228 0x40/0x41, opt. DAC80502)
I2C1_SDA = Net("I2C1_SDA")        # PB7
PD_IRQ = Net("PD_IRQ")            # PB9 (AP33772S INT, active high)
PD_SINK_EN = Net("PD_SINK_EN")    # PB3 (high = USB-C sink path on; was SWO)
INA_ALERT = Net("INA_ALERT")      # PC14
USB_DP = Net("USB_DP")            # PA12 (to ADuM3160 DD+)
USB_DM = Net("USB_DM")            # PA11 (to ADuM3160 DD-)

# UI board (ribbon)
I2C2_SCL = Net("I2C2_SCL")        # PA9
I2C2_SDA = Net("I2C2_SDA")        # PA8
UI_INT = Net("UI_INT")            # PA10
LCD_SCK = Net("LCD_SCK")          # PB13 SPI2_SCK
LCD_MOSI = Net("LCD_MOSI")        # PB15 SPI2_MOSI
LCD_CS = Net("LCD_CS")            # PC8
LCD_DC = Net("LCD_DC")            # PC9
LCD_RST = Net("LCD_RST")          # PC12
ENC1_A = Net("ENC1_A")            # PC6 TIM3_CH1
ENC1_B = Net("ENC1_B")            # PC7 TIM3_CH2
ENC1_SW = Net("ENC1_SW")          # UI board only: TCA9535 P05
ENC2_A = Net("ENC2_A")            # PC0 TIM1_CH1
ENC2_B = Net("ENC2_B")            # PC1 TIM1_CH2
ENC2_SW = Net("ENC2_SW")          # UI board only: TCA9535 P06
OE_BTN = Net("OE_BTN")            # PD2
PWR_BTN = Net("PWR_BTN")          # PC13 WKUP2
BUZZER = Net("BUZZER")            # PA7 TIM17_CH1
UART_TX = Net("UART_TX")          # PC10 USART3_TX
UART_RX = Net("UART_RX")          # PC11 USART3_RX

from skidl.pin import pin_drives as _drv


def power_net(*nets):
    """Mark nets that are driven by regulators/connectors through passives, so ERC knows they are powered."""
    for n in nets:
        n.drive = _drv.POWER


power_net(GND, GND_ISO, VBUS_RAW, VBUS_S, DCIN_RAW, VIN_BUS, VIN_PWR, LOGIC_IN, P3V3, P3V3A,
          P12V, P5VA, VBUS_PC, P5V_ISO)
