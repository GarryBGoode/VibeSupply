# USB-C PD Bench Supply — Design Plan

Hobby bench supply, loosely inspired by the DP100, powered from a USB PD 3.1 EPR charger (up to 48 V / 5 A = 240 W).
Schematic is written in skidl (`supply_design.py` + per-block modules), layout in KiCad.

Status: **schematic (skidl) done, ready for review/layout** — netlists in `out/`, structure in `design/README.md`; numbers in `calc/results.md`, `sim/results.md`; work items in `TODO.md`.

---

## 1. Requirements (agreed)

| Item | Decision |
|---|---|
| Input | USB-C PD 3.1 EPR sink, 5–48 V, up to 240 W. Graceful with 140 W (28 V) and SPR (≤20 V) chargers |
| Aux input | Extra DC input (XT60), 12–55 V, **rated 20 A**, OR-ed with the USB-C input through ideal diodes |
| Topology | Synchronous buck only |
| Output | 0 … 50 V (≈ Vin − 2 V), 0 … 20 A. USB-C: limited by the PD contract (≤ ~225 W out). DC input: limited by 20 A × Vout (≈ 920 W at 46 V from 48 V) and a user-set input power limit |
| Modes | CV / CC (hardware loops), power limit (firmware, via CC setpoint), input-current limit |
| Reverse energy | Must survive BLDC regen / backfeed: no energy back into the charger, active clamp on the output |
| Output switching | Back-to-back N-FETs on **+** only. Ground is never switched |
| Noise | Reasonably low ripple (target ≤ 20 mVpp at full load); stable with PWM / pulsed loads |
| Cooling | Room for a small PWM fan (40 mm), temperature controlled |
| PC link | USB-C data port, **galvanically isolated**; USB CDC (SCPI-like) + firmware update over USB DFU, no programmer needed |
| UI | Separate UI board over ribbon cable: TFT, 2× EC11 encoders w/ push, 5-way nav, dedicated lit Output-Enable button, power button |
| Output terminals | 4 mm binding posts **and** XT60, in parallel |
| Remote sense | No |
| Assembly | Fab + assembly house (JLCPCB/PCBWay). 0402 / QFN where it matters (analog, power ICs); 0805/0603 + SOIC/TSSOP where tinkering is likely (LEDs, MCU periphery, UI board) |

### Reality checks (already discussed)
- 10 A @ 24 V needs ~255 W input → not possible; expect **~9.4 A @ 24 V** from a 240 W source.
- Max output ≈ 45–46 V from 48 V input (duty-cycle limit + drops).
- 240 W needs a 48 V-capable EPR charger **and** a 240 W (50 V / 5 A) e-marked cable.
- On USB-C, 20 A is available below ~11 V; above that the power limit governs.
- On a strong DC source the limit is current, not power: losses are ~17–20 W at 20 A at any Vout, so the thermal design is the same as the 240 W worst case (12 V / 20 A).

---

## 2. Architecture

```
 USB-C PWR ──TPD4S480──TPS26750 (PD policy, EPR/AVS)            USB-C DATA (to PC)
     │   (CC/VBUS protect,     │ I2C (host)                          │
     │    VBUS divider)        │                                  ADuM3160 + isolated 5V DC/DC
     ▼                         ▼                                      │ USB FS
 LM74800 ideal-diode + sink switch ─┐                                 ▼
                                    ├─► VIN_BUS (≤ 55 V) ──► STM32G474 (supervisor, DACs, COMPs, UI, USB)
 XT60 DC IN ── LM74800 (20 A) ───────┘        │                   │ DAC: Vset, Iset   ▲ ADC/INA228
                                             ▼                   ▼                   │
                                   LTC7801 sync buck  ◄── external CV / CC error amps (op-amps)
                                   100 V FETs, L, shunt              ▲           ▲
                                             │                       │           │
                                   LC post-filter ──► output shunt (INA240 for loop, INA228 for metering)
                                             │
                                   regen clamp / down-programmer (FET + power resistor)
                                             │
                                   back-to-back N-FET switch (isolated FET driver) ──► fuse ──► 4 mm posts + XT60
                                                                                          └─ reverse-polarity diode
```

### Control concept
- **Buck controller runs current-mode; the regulation loops are external precision op-amps**, set by the STM32's 12-bit DACs:
  - CV amp: compares divided Vout to `DAC_V` (0 V capable).
  - CC amp: compares the **inductor current** (INA240A2 across the controller's 2.5 mΩ sense shunt) to `DAC_I`.
    Sensing after the post filter was unstable near a short (calc §9); the 1 mΩ output shunt is used for metering and a slow firmware trim.
  - Both steer the controller's ITH node through a diode-OR (lowest demand wins) — the classic lab-supply structure.
    **Anti-windup:** each amp's compensation network returns to ITH, not to its own output (LTspice-verified, sim/results.md).
  - **Fast current clamp:** PNP from ITH to GND, base from a 3rd DAC channel → caps the cycle-by-cycle peak current at Iset + ~3 A.
    It acts instantly on shorts and load steps; the CC amp then settles the average. Firmware calibrates the ITH↔current mapping at run time.
    Verified in LTspice: the LTC7801's ITH pull-up is only ~100 µA, so the op-amps override it easily. REGSD is defeated with 330 k from INTVCC to SS.
- **Power limit** in firmware (≥1 kHz): `I_lim = min(I_set, P_max / V_out, source-contract limit)`.
- **Input current limit**: input shunt → INA228 + fast comparator; firmware lowers `DAC_I` if input current approaches the PD contract.
- **Regen / backfeed**: buck runs in pulse-skip (no reverse inductor current) whenever there's a risk of backfeed.
  Firmware may switch to forced-continuous for low noise at light load when the output isn't being pushed.
- **Input voltage selection**: firmware requests the lowest PD voltage (fixed PDO or EPR AVS 15–48 V) that gives enough headroom above Vout for the requested power. This improves efficiency, ripple and minimum-on-time margin at low outputs.
- **Hardware trips independent of firmware**: STM32 COMP+DAC on Vout (OVP) and Iout (OCP) → latch that disables the buck and opens the output switch.

---

## 3. Part selection

Verification column: **DS** = checked against datasheet in this session, **known** = standard part, not yet re-checked, **TODO** = must read datasheet before schematic.

### 3.1 USB PD input
| Function | Part | Why | Ver. |
|---|---|---|---|
| PD controller | **TI TPS26750** (VQFN-32 4×4) | USB-IF certified PD3.1, EPR 28/36/48 V **and AVS** sink. Public host interface (TRM SLVUCR7): host can write sink caps (0x33), enable EPR AVS and set voltage/current (Autonegotiate Sink 0x37), read source caps (0x30), active contract (0x34/0x35), load the config bundle over I2C (PBMs/PBMc/PBMe) or program its EEPROM (FLwd) | DS |
| EPR front end | **TI TPD4S480** (WQFN-20 3×3) | TPS26750 pins are only 28 V rated; TPD4S480 gives 63 V short-to-VBUS protection for CC1/CC2 and the divided `VBUS_LV` sense — TI's reference EPR pairing | DS (product page) |
| Config EEPROM | AT24C512C (64 KB, addr 0x50, SOIC-8) on TPS26750 I2Cc | TPS26750 requires ≥36 KB; lets the PD side boot and negotiate even with blank/broken STM32 firmware. ADCIN strap = **SafeMode** (sink path stays off until the EEPROM config is loaded; TI's recommendation with EEPROM) | DS |
| Sink switch + anti-backfeed | **TI LM74800-Q1** (WSON-12 3×3; 3–65 V, 70 V abs max, −65 V reverse) ideal-diode (DGATE) + load-switch/OV cut-off (HGATE), back-to-back N-FETs | Blocks any reverse current into the charger; enabled from TPS26750 `POWER_PATH_EN` (via buffer per DS fig. 8-5) AND MCU. USB path sized for 5 A | TODO |
| DC-input path | Second LM74800-Q1 + 2× IPT015N10N5 (TOLL, 1.5 mΩ), copper/shunt sized for **20 A continuous**, reverse-polarity protected | Full-power operation from a 48 V brick or battery | LCSC data |
| Input caps | 10× 4.7 µF 100 V X7S/X7R 1210 at the half-bridge + ≥100 µF 100 V electrolytic (ESR 0.1–0.3 Ω, damping); ≤10 µF on raw VBUS before the sink switch | ~10 A RMS worst case, ≈0.8 V pp ripple (calc §5) | calc |
| Input TVS | SMBJ/SMCJ ~54 V standoff | Surge only; cannot clamp below the 65 V of the ideal-diode controller at high current, so also rely on the controlled PD slew | TODO |
| **Rejected** | HUSB238A | VBUS/GATE abs-max 33 V; 48 V needs an external pre-regulator; I2C register map not public | DS |
| **Rejected** | AP33772S, CH224A/Q, AP43771H | EPR limited to 28 V (140 W) | DS / web |
| **Rejected** | STM32 UCPD | No 48 V front end / mature EPR stack | web |

The TPS26750 is a TI part but needs **no TI MCU and no TI firmware development**: it's configured once with TI's web GUI, then controlled from the STM32 over I2C with documented 4-character commands.

### 3.2 Power stage
| Function | Part | Why | Ver. |
|---|---|---|---|
| Buck controller | **ADI LTC7801** (TSSOP-24 w/ pad, or QFN-24) | 4–140 V (150 V abs max) — big margin for regen/transients; **gate drive programmable 5–10 V** so standard 100 V FETs work; current mode; 0.8–60 V out; 100 % duty; burst/pulse-skip/forced-CCM; EXTVCC input; **LTspice model** for loop verification | DS (see notes below) |
| Alternative | TI LM5148 | 80 V, current mode, PFM/FPWM, hiccup OCP, 50 ns min on-time — but **5 V gate drive only** (needs logic-level 80–100 V FETs) | DS |
| Power FETs | **Infineon ISC030N10NM6** ×2 (top + bottom; OptiMOS 6, 100 V, 3.0 mΩ max, Qg 55 nC, Qrr 266 nC @1000 A/µs, SuperSO8 5×6) at **300 kHz** | Lowest loss among the fully-specified candidates (calc §1): top FET ~7.5 W worst case vs ~11 W for TI CSD19532Q5B. Needs via array + bottom heatsink + fan. Alternative: ISC040N10NM7 (Qrr only given at 100 A/µs) | DS |
| Inductor | **Coilcraft SER2918H-682KL** (6.8 µH ±10 %, Isat 45.9 A, DCR ≤ 2.86 mΩ, Irms 25 A, LCSC C3911802) | ΔI ≤ 5.9 A pp, peak 22.9 A at 20 A; ~1 W more copper loss than the Würth 7443640680B, which LCSC doesn't stock | DS (distributor data) |
| Current sense (controller) | **2.5 mΩ** (2× 5 mΩ 2512 3 W), Kelvin | Peak limit 26.4 / 30 / 33.6 A (min/typ/max), well below the inductor Isat. 1 W at 20 A | calc + sim |
| Output filter | C1: 6× 4.7 µF 100 V X7S 1210 + damper (100 µF 63 V polymer + 0.1 Ω) → **0.47 µH** FXL1040-R47 (1.7 mΩ, 30 A) → C2: 6× 4.7 µF 100 V 1210 + 100 µF 63 V polymer (24 mΩ) | ≈6 mV pp ripple (calc); CV loop fc ≈ 8–10 kHz, PM ≥ 74°, GM ≥ 9 dB; 9 A step → 0.63 V dip in LTspice | calc + sim |
| Current amp (CC loop) | **TI INA240A2** (gain 50, −4…80 V CM, PWM rejection) across the 2.8 mΩ inductor shunt → 0.14 V/A, 20 A = 2.8 V (DAC on VREFBUF 2.9 V) | CC loop fc ≈ 10 kHz, load-independent (calc §9, sim t3) | known |
| Metering | **TI INA228** ×2 (85 V, 20-bit, I2C) — output shunt + input shunt (common VIN_BUS shunt, range 0–20 A) | Accurate V/I/P/energy for display & logging; input power limit per source | known |
| CV/CC error amps | **ADI ADA4522-2** (zero-drift, 55 V, RRO, SOIC-8) on a 5 V rail | The part used in the LTspice runs; input CM to V+ − 1.5 V covers the 2.9 V DAC range | sim |

**LTC7801 datasheet notes (datasheets/ltc7801.pdf, Rev. B)**
- **Current foldback**: when VFB < 70 % of nominal (≈ 0.56 V) the peak limit is lowered progressively to 40 %. This would break "CC into a short".
  → **Chosen control scheme: hold VFB at a fixed ~0.70 V** (divider from a reference; above the foldback threshold, below the 0.88 V FB-OVP threshold).
  The internal error amp then saturates high, and the **external CV and CC amps pull ITH down through a diode-OR**. So foldback and FB-OVP never trigger, and all regulation is done by the external loops.
  Output OVP is provided by the STM32 comparators and the clamp instead.
- MODE: pulse-skip (1.4 V … INTVCC−1.3 V) and Burst **block reverse inductor current**; forced-continuous (MODE = INTVCC) allows it. MODE is switched by the MCU through a small transistor/divider; the default (MCU in reset) is pulse-skip.
- SENSE± common mode 0–65 V abs max → the internal output node must stay below ~60 V, including during clamp events. Max Vout setpoint 50 V.
- VSENSE(MAX) 66/75/84 mV (min/typ/max); tON(min) 80 ns; fsw 50–900 kHz; DRVSET = INTVCC → 10 V gate drive; EXTVCC switchover 4.7 V (DRVUV low) / 7.7 V; EXTVCC abs max 14 V → feed from the 12 V aux rail.
- Hiccup/REGSD only relates to EXTVCC / SS behaviour; no FB-based hiccup found.

### 3.3 Output stage
| Function | Part | Why | Ver. |
|---|---|---|---|
| Output switch | 2× **Infineon IPT015N10N5** (TOLL, 100 V, 1.5 mΩ) back-to-back | Blocks both directions when off; ~1.4 W at 20 A | LCSC data |
| Switch driver | **Vishay VOM1271** photovoltaic MOSFET driver with built-in fast turn-off (8.4 V Voc, 15 µA) | Isolated, so it works at any output voltage down to 0 V. ~30 ms turn-on → firmware closes the switch with the buck at 0 V and ramps afterwards. (Si8751 isn't stocked at LCSC) | web DS summary |
| Regen clamp / down-programmer | Comparator (Vout > Vset + margin) → IPT015N10N5 + **2 Ω** Vishay LTO100 (TO-247, 100 W) bolted to the main heatsink, NTC + firmware energy budget | **Burst-only rating (agreed):** 50 W for ~10 s (≈500 J), ~10 W average, output off + warning beyond that. Absorbs 50 W down to ~10 V out. Verified in LTspice (t4) | calc + sim |
| Fuse | **Littelfuse 0997030.WXN** (30 A blade, 58 V DC, 1.85 mΩ) + PCB holder | Reverse-battery and last-resort protection | LCSC data |
| Reverse-polarity diode | Heavy Schottky / TVS across terminals, behind the fuse | Reversed battery → diode conducts → fuse opens | TODO |
| Terminals | 4 mm binding posts (panel, wired) + PCB XT60 | Agreed | — |

### 3.4 Control, housekeeping, UI
| Function | Part | Why | Ver. |
|---|---|---|---|
| MCU | **STM32G474RET6** (LQFP-64, 0.5 mm) | 12-bit DACs (**3 external channels needed: Vset, Iset, ITH clamp** — G474 has exactly 3: DAC1 CH1/CH2, DAC2 CH1), VREFBUF 2.9 V, 7 comparators, op-amps, fast ADCs, HW quadrature timers, USB FS + ROM DFU bootloader | known |
| USB isolation | **ADuM3160** (full-speed) + 1 W isolated 5 V module (B0505S class) | Breaks ground loop PC ↔ output; the isolated module also powers the logic from the PC, so it can be flashed with no charger connected | known |
| Logic rail | **TI LMR38010** (4.2–80 V, 1 A) → 3.3 V, fed from diode-OR of *raw* VBUS, DC input and the isolated USB 5 V | The MCU boots from any source, before the PD sink path is enabled (TPS26750 SafeMode) | known |
| Aux 12 V rail | **TI LM5164** (6–100 V, 1 A) | EXTVCC for LTC7801, fan, clamp driver; enabled once VIN_BUS ≥ ~15 V | known |
| Fan | 40 mm 12 V 4-pin PWM header + tach | Agreed | — |
| Temp sensing | NTCs: buck FETs, inductor, output switch, clamp resistor | Fan curve + derating | — |
| Display | 2.0" 320×240 IPS, ST7789, SPI — e.g. HS20HS072RX bare panel (LCSC C5329582) + FPC connector on the UI board | Common, cheap, swappable | — |
| UI board I/O | TCA9535 (I2C expander) for nav buttons / LEDs; encoders + OE button wired direct | Keeps the ribbon small and the encoders on hardware timers | — |
| Ribbon | 2×10 2.54 mm IDC | Hand-friendly, easy to re-cable once the enclosure is decided | — |

---

## 4. Board partitioning
- **Main board** (4-layer, 2 oz outer if possible): USB-C PWR, XT60 DC in, PD front end, input path, buck, filters, shunts, clamp, output switch, output connectors, MCU, isolated USB, housekeeping, fan header, heatsink area.
- **UI board** (2-layer): display, 2× EC11, 5-way nav, lit Output-Enable button, power button, I/O expander, buzzer (optional). Only 3.3 V logic on the ribbon.

## 5. Firmware scope (later)
Setpoint DACs, power-limit loop, PD policy (voltage selection, AVS), metering, protection latch handling, UI (V/I on knobs, push = digit select), menu (OVP/OCP/OPP, presets, slew, battery-charge mode, PD info, calibration, logging), USB CDC SCPI, jump-to-DFU command.

## 6. Open items / risks
1. ~~LTC7801 datasheet~~ — resolved: FB held at 0.7 V and ITH driven externally (see 3.2); verified in LTspice (sim/results.md).
2. ~~Ideal-diode choice~~ — LM74800-Q1 on both inputs (65 V operating / 70 V abs max). TVS: standoff ≥ 54 V, so it cannot fully protect the 70 V rating under a high-energy surge; accepted (PD voltage changes are slew-controlled, DC input is a bench source).
3. Si8751: check turn-off time with the chosen FET pair's Qg (46 µs figure is for the datasheet load) and LCSC stock.
4. ~~Clamp sizing~~ — burst-only: 50 W for ~10 s, ~10 W average (decided 2026-09-25).
7. ~~DC-input power rating~~ — decided 2026-09-25: DC input rated **20 A**; power stage 20 A × Vout; firmware input-power limit per source (PD contract / user setting).
5. ~~LCSC/JLC stock check~~ — done 2026-09-26, see `calc/parts_shortlist.md`. LTC7801 is ~$20 with low stock: buy early.
6. TPS26750 boot-config (ADCIN strap) selection and GUI-generated config for "sink only, EPR, AVS, host controlled".

## 7. Next steps
1. ~~Datasheet open items~~, ~~calculations~~, ~~LTspice~~ (done).
2. ~~skidl schematic~~ — `supply_design.py` (main, 321 parts) + `ui_design.py` (UI, 71 parts), ERC clean. See `design/README.md`.
3. Review the netlists/BOMs; close the remaining part picks in `TODO.md`.
4. Layout in KiCad (4-layer main board, 2-layer UI board): heatsink + fan position from the chosen extrusion.
5. Firmware (STM32G474: DAC/COMP setup, PD policy over I2C, UI, USB CDC/SCPI, DFU) and staged bring-up from a current-limited bench supply on the DC input.

## References
- TPS26750 datasheet (SLVSH67): https://www.ti.com/lit/ds/symlink/tps26750.pdf
- TPS26750 TRM (SLVUCR7): https://www.ti.com/lit/pdf/slvucr7
- TPS26750 EEPROM update over I2C (SLVAFL1): https://www.ti.com/lit/an/slvafl1/slvafl1.pdf
- TPD4S480: https://www.ti.com/product/TPD4S480
- HUSB238A datasheet: https://datasheet.lcsc.com/datasheet/pdf/4ea6514a52a5c41dd654270022eda65d.pdf?productCode=C24833806
- LTC7801: https://www.analog.com/en/products/ltc7801.html
- LM5148: https://www.ti.com/lit/ds/symlink/lm5148.pdf
- TPS4811-Q1 (rejected for output switch): https://www.ti.com/product/TPS4811-Q1
