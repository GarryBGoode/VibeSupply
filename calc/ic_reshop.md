# IC re-shop after the pivot (140 W / 10 A, ≤ 32 V bus) — 2026-09-26

Stock and prices: `stock_check_5.txt` (jlcsearch mirror, qty 1, USD). Datasheets in `datasheets/`.

## PD sink controller

Must have: 28 V EPR fixed PDO, I2C host control (read the source's PDOs, request fixed / PPS / AVS), public register map,
CC pins that survive a short to VBUS at 28 V, LCSC stock.

| Part | EPR 28 V | Host control over I2C | CC short-to-VBUS | Extras | LCSC | $ | Verdict |
|---|---|---|---|---|---|---|---|
| **Diodes AP33772S** (QFN-24 4×4) — **chosen 2026-09-26** | yes, + EPR AVS ≤ 28 V, SPR PPS ≤ 21 V | full: SRCPDO (0x20) reads all 13 PDOs, PD_REQMSG (0x31) requests PDO/APDO + current, PDCONFIG (0x05) enables EPR; status, INT pin, VOUT V/I readback | **34 V** (VCC 3–31 V op., 34 V abs max) | USB-IF certified (PD3.1, TID 10062); charge-pump NMOS gate driver (PWR_EN); OVP/UVP/OCP/OTP, NTC input; no EEPROM, no config GUI | C50341643 (FA02, standard FW) / C24374260 (FA01) | 2.24 | **recommended**. Low LCSC stock (80 + 59): buy early; also at Mouser/Digi-Key |
| TI TPS26750 + TPD4S480 + EEPROM (current design) | yes (and 48 V) | full (4CC commands) | 63 V via TPD4S480 | certified; needs a GUI-generated config and a 64 KB EEPROM | C42166327 + C43131250 + C12371 | 5.55 | fallback; already in the schematic |
| WCH CH224A (ESSOP-10) | yes (fixed 28 V only) | **fixed PDOs only**: PPS, AVS and reading the source caps are **CH224Q-only** | not specified | datasheet has no electrical-characteristics table | C42459160 | 0.46 | rejected: no source-cap readout, thin datasheet |
| WCH CH224Q (DFN-10 2×2) | yes | full register set incl. SRCCAP, PPS, AVS | not specified | — | not stocked | — | rejected: not at LCSC, thin datasheet |
| Hynetek HUSB238A | yes | yes, but the full datasheet with the register map isn't public (only a 1-page brief) | 33 V class | — | C24833806 | 0.48 | rejected (as before) |
| STM32 UCPD + TCPP01-M12 | — | own firmware stack | TCPP01 only protects to 22 V | — | — | — | rejected: no 28 V-rated protection part, big firmware job |
| TPS25730, CYPD3177, STUSB4500, IP2721, CH224K | SPR only (≤ 20 V) | | | | | | rejected |

Consequences of choosing the AP33772S:
- TPD4S480, the config EEPROM and the TPS26750 GUI config go away. The PD policy (which PDO to request) lives in the STM32 firmware.
- The USB path still needs reverse-current blocking (a 30 V DC input OR-ed with a 20 V USB contract would otherwise backfeed the charger),
  so the **LM74800 stays on the USB path**. Its EN comes from the MCU after the AP33772S reports a valid contract (INT + status).
  The AP33772S's own PWR_EN NMOS driver can drive a series FET as a second, firmware-independent protection layer (OVP/UVP/OCP). Decide at schematic time.

## Buck controller

Must have: ≤ 32 V operating with ≥ ~60 V abs max, peak current mode, a COMP/ITH node that the external CV/CC op-amps can pull down,
no FB-based foldback (or one that can be defeated), ≥ ~97 % duty (27 V out from 28 V), a no-reverse-current light-load mode (regen),
output range up to ≥ 27 V, LCSC stock.

| Part | Vin (abs max) | Vout range | Gate drive | COMP drive | Duty / min on | Light-load modes | Sim model | LCSC | $ | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| TI LM5148 (VQFN-24 3.5×5.5) | 3.5–80 V (85 V) | 0.8–55 V; VOUT/ISNS+ pins 60 V abs max | 5 V (VCC LDO, or VCCX from an external 5 V) → logic-level FETs | EXTCOMP = gm amp output (1200 µS, ~180 µA source — datasheet table text is garbled, confirm): external diode-OR pull-down works like on the LTC7801 | ~99 % (dropout mode skips off-times), 50 ns min on, 90 ns min off | PFM = diode emulation (no reverse current) or FPWM, selected by a pin | TI PSpice (encrypted), **no LTspice** | C7470701, **26.7k** | **1.02** | **recommended**, see risks below |
| ADI LTC7801 (current design) | 4–140 V (150 V) | 0.8–60 V | 5–10 V programmable | ITH, sim-verified | 100 %, 80 ns | pulse-skip / Burst / FCM | LTspice, verified | C690198, 21 pcs | 20.34 | fallback: verified but 20× the price, low stock |
| TI LM25148 | 3.5–42 V | 0.8–36 V | 5 V | same as LM5148 | same | same | PSpice | C3188828, 2k | 2.26 | rejected: same die family, lower voltage, pricier than the LM5148 |
| ADI LTC3891 / LTC7800 | 4–60 V | **0.8–24 V** | 5 V | ITH | 99 % | yes | LTspice | C107921, 401 | 12.86 | rejected: output limited to 24 V |
| **ADI LTC7803** (MSOP-16-EP / QFN-16 3×3) — **chosen 2026-09-26** | 4.5–40 V, **40 V abs max** (VIN, SW, SENSE±) | 0.8–40 V; SENSE± common mode **0–40 V** (works in a short) | 5.15 V INTVCC; EXTVCC 4.7–30 V → logic-level FETs | ITH, same scheme as the LTC7801: FB held at 0.70 V (foldback below 0.56 V, FB-OVP at 0.88 V); VSENSE(MAX) 45/50/55 mV is even specified at VFB = 0.7 V | **100 %** (boost charge pump), **40 ns** min on | Burst / **pulse-skip** (no reverse current) / FCM via MODE | **LTspice** | C1016554 (EMSE), 38 pcs; QFN C1016564, 14 pcs | 9.75 | **chosen**: LTC7801 architecture, LTspice work carries over; no hiccup, no REGSD. Needs the ≤ 32 V bus to be enforced (see below) |
| ADI LTC7802 | 4.5–40 V | | | ITH | 100 % | | LTspice | | 9.20 | rejected: dual controller, not needed |
| TI LM5141 / LM25141 | 3.8–65 V / 42 V | **1.5–15 V** | 5 V | COMP | | | PSpice | | 2.43 / 1.11 | rejected: output ≤ 15 V; 440 kHz / 2.2 MHz only |
| TI LM5145 / LM5146, SCT82A30 | 75 / 100 V | | | | | | | | 2.0–2.5 | rejected: voltage-mode control |
| TI LM61495 (integrated 10 A) | 3–36 V | | | | | | | | 2.63 | rejected: 36 V abs max |
| MPS MP9928 / MP2908A | 4–60 V | | | | | | | | 2.3–2.7 | not evaluated: MPS pages don't load from here |

### LM5148 (runner-up): risks that ruled it out
1. **No LTspice model.** TI only ships encrypted PSpice models. Plan: build a behavioural LM5148 in LTspice from the datasheet
   (peak current mode, CS gain 10, 60 mV limit, gm EA 1200 µS / 180 µA, internal slope compensation, 50 ns / 90 ns) and re-run the existing
   test benches. The external CV/CC loops dominate the dynamics, so a behavioural modulator is good enough to verify them.
   Optional cross-check: TI's model in the free PSpice for TI.
2. **Current sensing near 0 V out.** VOUT is specified from 0.8 V up; the CS amplifier's behaviour with the output shorted (VOUT ≈ 0) isn't spelled out.
   Hiccup protection implies it works in a short, but CC regulation into a dead short needs confirming (PSpice model, TI E2E, or bench test on the first board).
3. **FB fixed-output detection.** FB tied to VDDA directly or through 24.9 k / 49.9 k selects fixed 3.3 / 5 / 12 V, latched at power-up.
   The "FB held at 0.7 V" trick must use a divider that can't be mistaken for those (e.g. from a separate reference, or high-value resistors).
   The EA then sources its full current into EXTCOMP, and the external amps pull it down, as with the LTC7801.
4. **Hiccup** only counts cycles at the 60 mV cycle-by-cycle limit (512 cycles). The ITH/COMP clamp keeps the peak below that, so no hiccup in normal CC.
   The 3 ms internal soft start is harmless: SS below 0.7 V just keeps COMP low for the first ~2.6 ms.
5. **VOUT → VIN internal ESD diode**: conducts if VIN drops > 2 V below VOUT (the top-FET body diode does the same anyway). Add a small series R in the VIN pin filter.

If it were chosen:
- **5 V gate drive** → logic-level 60 V FETs (plenty exist; to pick in the FET round).
- The **aux rail becomes 5 V** (LM5164 at 5 V → VCCX + op-amps) instead of 12 V EXTVCC. With no fan, nothing needs 12 V any more.
- Saves ~$19 per board and the LTC7801 stock risk.

### LTC7803: why 40 V is acceptable, and the protection it needs
The 40 V abs max equals the operating maximum, so the datasheet gives no headroom above 40 V. Our bus is hard-limited to ~31–32 V,
which leaves ~8 V (25 %) for everything that can push a pin higher. What hits which pin:

| Pin(s) | Threat | Measure |
|---|---|---|
| VIN | bus transients, hot-plug ringing | RC filter at the pin (≈ 10 Ω + 1 µF) + small TVS/zener to GND (~33–36 V) at the pin. The R limits the current, so a small part clamps hard |
| SW, BOOST | switch-node ringing on every edge (≈ 3–10 V over the bus) | cannot be TVS-clamped → tight hot loop (input MLCCs right at the FETs), 5 V gate drive (moderate edges), gate-resistor footprints, RC snubber footprint across the bottom FET; **measure the ringing on the first board** |
| VIN_BUS (all of the above) | source surge faster than the LM74800 OV cut-off; regen through the top-FET body diode | LM74800 OV lockout on **both** inputs at ≈ 31 V (it also refuses to switch on an over-voltage source at plug-in); bulk + MLCCs absorb µs events; SMBJ33A-class TVS on the bus for small, slow excess (breakdown 36.7 V min — soft protection only); regen clamp comparator also watches VIN_BUS (> ~33 V → clamp on) |
| SENSE± (output node) | regen / external source pushing the output | regen clamp (2 Ω) switches in at Vset + margin and at an absolute ~33 V; output switch opens on a firmware fault |
| EXTVCC | — | fed from the **12 V** aux rail (abs max 30 V). Not 5 V: INTVCC then sits in LDO dropout (~4.9 V), the boost supply sags and in LTspice the LTC7803 stalled after an idle period |
| BOOST | — | **external low-leakage boost diode** INTVCC → BOOST (the LTC7803 has none inside; ADI uses a CMDSH-4E) |

The 60 V FETs stay: the FETs see the same spike, and 60 V parts cost nothing extra.
