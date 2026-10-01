# USB-C PD Bench Supply — Design Plan

Hobby bench supply, loosely inspired by the DP100, powered from a USB PD 3.1 EPR charger (up to 28 V / 5 A = 140 W).
Schematic is written in skidl (`power_design.py`, `control_design.py`, `ui_design.py` + per-block modules), layout in KiCad.

Status: **pivot to 140 W / 10 A done (2026-09-27): requirements, IC re-shop, calculations, LTspice and the skidl schematic are updated.**
Board split into supply_power + supply_control done in skidl (2026-10-01, §4). Next: netlist/BOM review, remaining LCSC picks, KiCad layout. The pre-pivot 240 W / 20 A design is in git (`d8d0a65`).
Numbers in `calc/results.md`, `sim/results.md`; work items in `TODO.md`.

---

## 1. Requirements

| Item | Decision |
|---|---|
| Input | USB-C PD 3.1 sink, 5–28 V, **up to 140 W** (28 V / 5 A EPR fixed PDO; EPR AVS used if the charger offers it). Graceful with SPR (≤ 20 V, ≤ 100 W) chargers |
| Aux input | Extra DC input (panel connector on the end cap, wired to the board), **≤ 30 V, rated 10 A** (24 V bricks, up to 7S Li-ion), OR-ed with the USB-C input through ideal diodes. **Over-voltage lockout at ~31–32 V and no damage up to ≥ 60 V** (a 48 V battery on the DC input is a likely mistake). Kept as a development fallback when the PD side misbehaves |
| Topology | Synchronous buck only |
| Output | **0 … ≈ 26.5 V, 0 … 10 A**. 10 A up to ≈ Vin − 3.5 V (26.5 V from a 30 V DC source); from 28 V USB-C ≈ 26.5 V max at ≈ 4.3 A — the LTC7803's slope compensation limits current near dropout (LTspice). USB-C: ≈ 130 W out; DC: 10 A × Vout and a user-set input power limit |
| Modes | CV / CC (hardware loops), power limit (firmware, via CC setpoint), input-current limit |
| Reverse energy | Must survive BLDC regen / backfeed: no energy back into the charger, active clamp on the output (clamp unchanged: 2 Ω, 50 W for ~10 s, ~10 W average) |
| Output switching | Back-to-back N-FETs on **+** only. Ground is never switched |
| Noise | Reasonably low ripple (target ≤ 20 mVpp at full load); stable with PWM / pulsed loads |
| Cooling | **Fanless**: buck FETs, inductor and clamp resistor are thermally tied to the aluminium extrusion (the enclosure is the heatsink). Fan header removed 2026-09-28 (board space) |
| Voltage class | Everything downstream of the inputs sees ≤ ~32 V, plus regen margin → **60 V FETs**, ≥ 50 V MLCCs. Input-side protection parts must survive ≥ 60 V |
| PC link | USB-C data port, **galvanically isolated**; USB CDC (SCPI-like) + firmware update over USB DFU, no programmer needed |
| UI | Separate UI board over ribbon cable: TFT, 2× EC11 encoders w/ push, 5-way nav, dedicated lit Output-Enable button, power button |
| Output terminals | 4 mm binding posts on the front cap, wired to the board (output XT60 dropped 2026-09-28) |
| Remote sense | No |
| Assembly | Fab + assembly house (JLCPCB/PCBWay). 0402 / QFN where it matters (analog, power ICs); 0805/0603 + SOIC/TSSOP where tinkering is likely (LEDs, MCU periphery, UI board) |

### Reality checks (140 W / 10 A)
- 140 W in → **≈ 130 W out** after ~7–9 W of losses + housekeeping. Full 10 A from USB-C only up to **≈ 13 V**; ≈ 5.4 A at 24 V.
- Max output from the 28 V PDO ≈ 26.5 V at ≈ 4.3 A (LTspice: the LTC7803's slope compensation limits the current near dropout).
- 28 V is an EPR voltage: it needs an **EPR (50 V / 5 A, "240 W") e-marked cable**. With a plain 100 W 5 A cable the charger stays at 20 V / 5 A = 100 W.
- Don't rely on AVS: many 140 W chargers only offer the fixed 28 V EPR PDO. SPR fixed PDOs (and PPS, if the PD chip handles it) cover part load.
- Losses at 10 A: **≈ 7–8 W** including 2 W housekeeping (CSD18531Q5A ×2, 300 kHz; calc §2), top FET ≤ 3 W (vs 17–20 W at 20 A).
  → fanless looks feasible if the FETs, inductor and clamp resistor dump heat into the aluminium extrusion.
- The clamp's ~10 W average rating is now about the same as the buck's worst-case loss, so sustained regen dominates the fanless thermal budget. Firmware must enforce it from the NTC.

### 1a. Pivot 2026-09-26: impact on the existing design
Why: 48 V / 5 A EPR chargers are rare and expensive; dozens of single-port 140 W (28 V) chargers exist.

| Block | Old (240 W / 20 A) | New (proposed) | Status |
|---|---|---|---|
| PD controller + front end | TPS26750 + TPD4S480, EPR 48 V | **Diodes AP33772S** (PD3.1 certified, EPR/AVS ≤ 28 V, PPS, full I2C host control, CC short protection to 34 V, $2.24). Drops the TPD4S480, EEPROM and GUI config. See `calc/ic_reshop.md` | **chosen** |
| USB sink path | LM74800 + 2× CSD19532Q5B, 5 A | Unchanged | keep |
| DC input path | LM74800 + 2× IPT015N10N5 (TOLL), 20 A | 10 A: LM74800 + 2× CSD18540Q5B (60 V, 2.2 mΩ), OV lockout ~31 V | proposed |
| Buck controller | LTC7801 (150 V, sim-verified scheme) | **ADI LTC7803** (40 V, same ITH / FB-at-0.7 V scheme as the LTC7801, 100 % duty, 40 ns min on, SENSE works down to 0 V, LTspice model, $9.75). 5 V gate drive → logic-level 60 V FETs. 40 V abs max → bus hard-limited to ~31 V + VIN-pin RC/TVS, see `calc/ic_reshop.md` | **chosen** |
| Buck FETs / fsw | 2× ISC030N10NM6, 300 kHz | **2× TI CSD18531Q5A** (60 V logic-level, 5.8 mΩ @4.5 V, low Qoss/Qrr), **300 kHz**. 200 kHz saves 0.8 W but gives sub-harmonic oscillation above ~80 % duty (LTspice) | **decided** (calc §1) |
| Inductor | SER2918H-682 (Isat 46 A) | **Coilcraft SER2918H-103KL** (10 µH, 2.86 mΩ, Isat 32 A, same footprint, LCSC C3911665): 0.4 W copper at 10 A | **decided** |
| Controller sense shunt | 2.5 mΩ (peak limit 26–34 A) | **2.0 mΩ** (2× 4 mΩ 2512): low-duty limit 22.5–27.5 A; slope compensation shrinks it at high duty → 10 A available up to ≈ Vin − 3.5 V (LTspice) | **decided** |
| CC loop / DAC scaling | INA240A2, 20 A = 2.5 V | **INA240A3** (gain 100) → 0.2 V/A, 14.5 A full scale; CV divider 91.9 k / 10 k (29.6 V full scale). ITH clamp must be **duty-aware** (offset ~0.45 V up to D 0.75, ~1.0 V near D 0.9) | **decided** |
| Output filter | 0.47 µH / 30 A + 6+6× 4.7 µF 100 V | Same 0.47 µH FXL1040 + damper + polymer; 4+4× 4.7 µF 100 V; ≈ 3 mV pp ripple (calc) | **decided** |
| Output switch | 2× IPT015N10N5 (TOLL) | 2× CSD18540Q5B (SON 5×6, 60 V), VOM1271 driver | proposed |
| Regen clamp | 2 Ω LTO100 (TO-247), burst-only | **Unchanged** (agreed) | keep |
| Fuse / reverse diode | 30 A blade | ≈ 15 A blade | resize |
| Aux 12 V, fan | LM5164 → EXTVCC + 40 mm fan | **Keep the 12 V aux rail** (LM5164) → LTC7803 EXTVCC; 5 V analog rail from it. EXTVCC from 5 V left INTVCC in dropout and the controller stalled after idle (LTspice). Fan header unpopulated. **External boost diode** INTVCC → BOOST needed | **decided** |
| MCU, isolated USB, UI board | — | Unchanged | keep |

---

## 2. Architecture

```
 USB-C PWR ── 5 mΩ ── AP33772S (PD sink: EPR 28 V / AVS / PPS)          USB-C DATA (to PC)
     │   (VCC, ISENP)      │ I2C (host), INT                                  │
     ▼                     ▼                                             ADuM3160 + isolated 5 V DC/DC
 LM74800 ideal diode + sink switch (OV lockout ~31 V, EN from MCU) ─┐         │ USB FS
                                                                    ├─► VIN_BUS (≤ ~31 V) ─► STM32G474
 DC IN wires (9–30 V, 10 A) ─ LM74800 (OV lockout ~31 V, 100 V FETs)┘      │         (supervisor, 3 DACs, COMPs, UI, USB)
                                                                           ▼                   │ DAC: Vset, Iset, ITH clamp
                                                   LTC7803 sync buck, 300 kHz ◄── external CV / CC error amps (ADA4522)
                                                   2× CSD18531Q5A, 10 µH, 2 mΩ               ▲            ▲
                                                             │                               │            │
                                                   LC post-filter ──► output shunt (INA240A3 on the inductor shunt for
                                                             │         the loop, INA228 for metering)
                                                   regen clamp (2 Ω; Vout > Vset + margin, or bus > ~33 V)
                                                             │
                                                   back-to-back 100 V N-FET switch (VOM1271) ──► 15 A fuse ──► 4 mm posts (wired)
                                                                                                  └─ reverse-polarity diode
```

### Control concept
- **Buck controller runs current-mode; the regulation loops are external precision op-amps**, set by the STM32's 12-bit DACs:
  - CV amp: compares divided Vout (÷10.19) to `DAC_V` (0 V capable).
  - CC amp: compares the **inductor current** (INA240A3 across the 2.0 mΩ sense shunt, 0.2 V/A) to `DAC_I`.
    Sensing after the post filter was unstable near a short (calc §9); the 1 mΩ output shunt is for metering and a slow firmware trim.
  - Both steer the LTC7803's ITH node through a diode-OR (lowest demand wins). The LTC7803's own error amp is parked by holding
    VFB at ~0.7 V (above the 0.56 V foldback threshold, below the 0.88 V FB-OVP).
    **Anti-windup:** each amp's compensation network returns to ITH, not to its own output (LTspice-verified).
  - **Fast current clamp:** PNP from ITH to GND, base from a 3rd DAC channel → caps the cycle-by-cycle peak current at Iset + ~3 A.
    **The ITH ↔ current map depends on duty** (≈ 25 A/V + 0.45 V up to D 0.75, ≈ 15 A/V + 0.8 V near D 0.9): firmware computes the
    clamp from Vset/Vin and calibrates it at run time (ITH_MON + IL_SNS).
- **Output envelope:** 10 A up to ≈ Vin − 3.5 V; near dropout the LTC7803's slope compensation limits the current
  (28 V USB-C → ≈ 26.5 V at ≈ 4.3 A). Firmware limits Iset accordingly and keeps the output off below ~8–9 V input.
- **Power limit** in firmware (≥ 1 kHz): `I_lim = min(I_set, P_max / V_out, source-contract limit, duty limit)`.
- **Input current limit**: input shunt → INA228; firmware lowers `DAC_I` if input current approaches the PD contract.
- **Regen / backfeed**: buck runs in pulse-skip (no reverse inductor current) whenever there's a risk of backfeed.
  Firmware may switch to forced-continuous for low noise at light load when the output isn't being pushed.
- **Input voltage selection**: firmware reads the source PDOs from the AP33772S and requests the lowest voltage (fixed, PPS or
  EPR AVS) that gives enough headroom above Vout for the requested power.
- **Hardware trips independent of firmware**: STM32 COMP+DAC on Vout (OVP) and inductor current (OCP), plus an LMV331 absolute
  OVP at ~32 V → latch that stops the buck (RUN) and opens the output switch.
- **Thermal**: fanless; FETs and the clamp resistor are tied to the aluminium extrusion. Firmware throttles on the NTCs
  (full power is occasional use: ≈ 6.5 W continuous budget for a ≤ 55 °C case, worst-case load reaches it after ~20 min) and derates the clamp's average from the enclosure temperature.

---

## 3. Part selection

Numbers: `calc/results.md`, `sim/results.md`; IC comparison: `calc/ic_reshop.md`; stock: `calc/stock_check_5.txt`.

### 3.1 Input
| Function | Part | Why |
|---|---|---|
| PD sink | **Diodes AP33772S** (W-QFN4040-24, FA02 firmware, LCSC C50341643) | USB-IF certified PD3.1; EPR 28 V + AVS, PPS ≤ 21 V; full I2C host control (SRCPDO read, PD_REQMSG); CC short protection to 34 V; no EEPROM/GUI config. 5 mΩ VBUS sense for its OCP/current readback. V5V backed from +5VA via a diode so it can't clamp I2C1 when no USB-C is plugged in. Low LCSC stock: buy early |
| USB sink path | **LM74800** + 2× **CSD18540Q5B** (60 V, 2.2 mΩ) | Ideal diode (no backfeed into the charger) + switch; OV lockout ~31 V (243 k / 10 k); EN = MCU `PD_SINK_EN` after the AP33772S reports a contract. The AP33772S's own NMOS driver is unused |
| DC input path | **LM74800** + 2× **ISC030N10NM6** (100 V) | 9–30 V, 10 A; OV lockout ~31 V; must survive a 48 V battery (SMCJ54A TVS, 100 V FETs); UVLO ~9 V |
| Input TVS | SMBJ30A on VBUS, SMCJ54A on the DC input, SMBJ33A on the bus | VBUS: above 28 V + 5 %, below the AP33772S's 34 V; bus: soft protection for the LTC7803 |
| Input shunt + meter | 1 mΩ 2512 + **INA228** (0x40) | Input power limit per source |

### 3.2 Power stage
| Function | Part | Why |
|---|---|---|
| Buck controller | **ADI LTC7803** (MSOP-16-EP, LCSC C1016554) | Same ITH / FB-parked scheme as the LTC7801; SENSE works down to 0 V; 100 % duty; 40 ns min on; pulse-skip; LTspice model. 40 V abs max → bus hard-limited to ~31 V, VIN pin 10 Ω + 1 µF + 36 V zener. **EXTVCC from the 12 V aux** (5 V stalls it). **External boost diode** CMDSH-4E. 300 kHz (RFREQ 124 k). Low LCSC stock: buy early |
| FETs | 2× **TI CSD18531Q5A** (60 V logic-level, 5.8 mΩ @4.5 V) | Lowest loss: the bottom FET's low Qoss/Qrr is paid in the top FET (calc §1) |
| Inductor | **Coilcraft SER2918H-103KL** (10 µH, 2.86 mΩ, Isat 32 A, LCSC C3911665) | Same footprint as before; 0.4 W copper at 10 A |
| Sense | 2× 4 mΩ 2512 (**2.0 mΩ**) | Low-duty limit 22.5–27.5 A (< Isat); enough current at high duty (LTspice t5) |
| Input caps | 6× 4.7 µF 100 V X7S 1210 + 100 µF 100 V electrolytic | ~5 A RMS worst case |
| Output filter | C1: 4× 4.7 µF + damper (100 µF polymer + 0.1 Ω) → 0.47 µH FXL1040 → C2: 4× 4.7 µF + 100 µF 24 mΩ polymer | ≈ 3–6 mV pp ripple |
| CC-loop amp | **INA240A3** (gain 100) → 0.2 V/A, 14.5 A = 2.9 V | |
| CV/CC error amps | **ADA4522-2** on +5VA | CV: Rz 47.5 k / Cf 1.3 nF / Cp 68 pF; CC: Rz 2.4 k / Cf 27 nF / Cp 1.3 nF |

### 3.3 Output stage
| Function | Part | Why |
|---|---|---|
| Output switch | 2× **BSC040N10NS5** (100 V) back-to-back + **VOM1271** | The terminals face the outside world (external batteries, the 54 V TVS) |
| Regen clamp | 2 Ω **Vishay LTO100** (TO-247, on the power board's bottom side, tab on the extrusion floor via gap pad, M3 into H906), BSC040N10NS5, UCC27511; two LMV331 triggers (Vout > Vset + ~0.5–1 V; VIN_PWR > ~33 V) | Burst 50 W / ~10 s, average derated from the enclosure NTC |
| Fuse | 15 A MINI blade (32 V) + Keystone 3568 holder | LCSC part to pick |
| Protection | MBRB40100CT reverse crowbar, SMCJ54A | Reversed battery → fuse opens |
| Terminals | 4 mm binding posts (wired) | Output XT60 dropped 2026-09-28 |

### 3.4 Control, housekeeping, UI
| Function | Part | Why |
|---|---|---|
| MCU | **STM32G474RET6** (LQFP-64) on supply_control | 3 DACs (Vset, Iset, ITH clamp), VREFBUF 2.9 V, comparators, ADCs, timers, USB FS + DFU. The analog loop stays on supply_power; only setpoints and measurements cross the B2B header, over ~20 mm (split 2026-09-30) |
| USB isolation | **ADuM3160** + B0505S | PC ground loop broken; PC powers the logic for flashing |
| Logic rail | **LMR38010** → 3.3 V from a diode-OR of raw VBUS, DC input and the isolated USB 5 V | Boots from any source |
| Aux 12 V | **LM5164** from VIN_PWR (on above ~8.3 V) | LTC7803 EXTVCC (≥ 7 V needed), clamp driver, +5VA (LP2985-5.0) |
| Temp sensing | NTCs: buck FETs, inductor, output switch, clamp resistor, USB-C connector (AP33772S OTP) | Throttling + clamp budget |
| Display / UI board | 2.42" SSD1309 128×64 SPI OLED module, TCA9535 (also the encoder pushes), 2× EC11, 2×10 1.27 mm ribbon (3.3 V digital only) | Changed 2026-09-28 (OLED on top of the front add-on). Firmware: dim after idle + pixel shift against burn-in |

---

## 4. Board partitioning
- **Two stacked boards (split done in skidl 2026-10-01)**, linked by a 2×20 2.54 mm B2B header (`design/interconnect.py`):
  - **supply_power** (`power_design.py`, 4-layer, 2 oz outer if possible; lowest slot, ≈ 170 × 74.5 mm): USB-C PWR, DC-in wire
    pads, PD sink, input paths + shunt, buck, filters, analog control (CV/CC amps, ITH clamp, DAC filters, HW OVP, fault logic),
    output stage + regen clamp, +12V_AUX / +5VA, the LOGIC_IN diodes (VBUS, DC in) and a local +3V3A. Buck FETs, clamp FET and
    clamp resistor sit where the board meets the extrusion (via arrays under the FETs + gap pad). The **LTO100 is back on the
    board** (TO-247 tab-down footprint, R419), meant for the bottom side with its insulated tab on a gap pad on the floor and an
    M3 screw from outside (H906). Bottom-side stack: TO-247 ≈ 5 mm + pad in the 7.06–7.46 mm floor gap.
  - **supply_control** (`control_design.py`, slot 6 = second from the top, 110 × 74.5 mm, 10 mm free at one end): STM32G474,
    SWD/UART/reset/boot, UI ribbon header (J703), isolated USB, LMR38010 3.3 V buck with the isolated-USB leg of LOGIC_IN, +3V3A for
    VDDA. The analog inputs from the power board get 100 Ω + 1 nF at the MCU pins.
  - **Across the header**: 24 signals (3 DACs, 9 analog sense lines, I2C1, PD/INA interrupts, enables, fault lines), LOGIC_IN up,
    +3V3 down, 13 GND. No power-stage current or return current crosses, so the ground offset between the boards stays at the
    logic-current level (the setpoints and the loop are referenced on the power board). The control socket is on its board's
    bottom side, mirrored: pin 2k−1 ↔ 2k (see `interconnect.py`); `tools/b2b_check.py` verifies both netlists.
  - Why this cut (2026-09-30): the single board needed ≈ 5,500 mm² of courtyard on ≈ 11,300 mm² of usable top side (~49 %, with
    a 10 A stage, precision analog, an isolation gap and a 64-pin MCU); the power board now has ≈ 4,400 mm² (~39 %) and no
    isolation gap / MCU fan-out. Moving the input stage up too was rejected: 10 A and its return current would cross the boards
    (a few mV of load-dependent ground offset → tens of mV of CV error through the ÷10.19 divider).
- **Enclosure size (2026-09-28):** extrusion 120 mm long, 78 mm wide outside, 75 mm across the slot bottoms, 70 mm between
  the slot ribs, 40 mm inside height, 1.5 mm walls; slots 2 mm high on a 3.5 mm pitch, the lowest slot 7.06 mm above the floor.
  Plus a ~50 mm 3D-printed front add-on (PETG/ASA) with the display on top and the controls/posts on its front face (to be
  designed in 3D; may grow). Rear end cap: USB-C PWR, isolated USB-C, DC-in panel connector.
  → Board ≈ 74.5 mm wide (0.25 mm clearance in the slots); keep a ~3.5 mm band along both long edges free of
  parts on both sides (slot + rib). Board in the lowest slot → ~5.5 mm aluminium spacer + gap pad under the power stage.
  Power stage in the aluminium part (bottom side = heat path, no parts there); MCU, control, housekeeping and the UI ribbon in
  the add-on part (both sides usable). Thermal budget for a ≤ 55 °C case ≈ 6.5 W continuous (calc/results.md §3).
- **Board stack (`CAD_3D/mech_design.py`):** the **power board** in the lowest slot (≈ 170 mm, reaches into the add-on) and the
  **control board** in slot 6, the last-but-one (`control_pcb_slot_index = -2`, 110 mm; slot 7 would add 3.5 mm but sits close to
  the ceiling bosses). Along the length (decided 2026-10-01): both boards have their rear edge at the rear end cap, the front end
  is free; in KiCad the rear is on the left (−X), and the board centre is the grid / drill origin (`tools/board_setup.py`).
- **Slot geometry (checked 2026-09-30 against the Hammond 1455K1201 drawing):** the 8 slots are **not centred**. The profile
  view, measured to scale, gives 7.04 mm from the floor to the lowest slot vs 6.40 mm from the top slot to the ceiling; the
  7.06 mm dimension is also from the inner floor. So the pattern is shifted ≈ 0.31 mm up (`slot_offset = 0.31`). Apart from
  this the profile is mirror-symmetric, so the extrusion **can be assembled upside down** and the floor gap then becomes 6.44 mm.
  Mark "up" on the real part before drilling (the drilled holes fix the orientation). Heights from the inner floor (board
  resting on the slot bottom; the 1.6 mm board has 0.4 mm play in the 2 mm slot):
  | | Height from the inner floor |
  |---|---|
  | Power board (slot 0) | bottom face 7.06–7.46, top face 8.66–9.06 |
  | Control board (slot 6, chosen) | bottom face 28.06–28.46, top face 29.66–30.06 |
  | Between the boards (slot 6) | **19.0–19.8 mm** clear. The SER2918H (17.78 mm max) leaves only **1.2–2.0 mm**: no control-board bottom-side parts above it, and check the other tall parts (bulk caps, fuse holder) |
  | Above the control board (slot 6) | ≈ 9.9–10.3 mm to the ceiling, ≈ 5.8 mm under the corner screw bosses |
  | (slot 7 for comparison) | bottom face 31.56–31.96; 22.5–22.9 mm between the boards, 6.44–6.84 mm to the ceiling, ≈ 2.3 mm under the bosses |
  | Below the power board | the spacer + gap-pad stack must fill 7.06–7.46 mm plus extrusion tolerance and orientation (up to −0.62 mm) |

  Design so these tolerances don't matter: the gap pad's compression range absorbs the stack error. The link between the boards
  (decided 2026-09-30): **2×20 2.54 mm female headers on both boards + long male-male pins** (19.8 mm stack with the parts at hand);
  the pins don't have to be fully seated, which takes up the slot play, and the two boards plug together outside the enclosure
  and slide in as one unit.
- **3D workflow (build123d, `CAD_3D/`):** `geom_defs.py` holds the parameter dataclasses, one module per part holds its
  `create_*()` function (`enclosure.py`, ...), `mech_design.py` is the single source of the mechanical reference values, and
  `check_fit.py` will build the assembly and report clearances. The PLAN numbers above are copies; `mech_design.py` wins.
  KiCad → 3D (2026-10-01): `tools/export_mech.py` → `out/mech_<board>.json` → `kicad_board.py` + `electronic_components.py`
  (F.Fab box × height from the KiCad model or an override) → `assembly.py`. Frames documented in `mech_design.py`.
  Next: clearance report and a height-zone DXF for a KiCad User layer in `check_fit.py`. For the UI, 3D leads: front-panel positions in `mech_design.py` drive the printed add-on
  and the UI board footprint placement.
- **Enclosure (decided 2026-09-28):** slotted extrusion, the board slides into the side slots (no screw bosses). The case is
  bonded to GND = output negative through H905. H905 sits in the power stage next to the half bridge: one countersunk M3 from
  outside clamps floor → aluminium spacer block + gap pad → board, and also holds down the inductor / bulk caps. Only the bare
  GND ring around H905 touches metal; the FET tabs (SW, VIN_PWR) sit on the insulating gap pad. The LTO100 clamp resistor
  needs a second drilled hole (H906). Measure the slot-to-floor gap before finalizing the layout.
  **H905 / H906 are threaded (2026-10-01):** Würth WA-SMSI 9774030360R (steel, tin-plated, M3 through-thread, 3 mm tall,
  Ø6 mm, reflow-soldered on the top side; KiCad `Mounting_Wuerth` footprint; alt. PEM SMTSO-M3-3ET or its Sinhoo clones). The
  screw comes up from the floor, so no nut has to be reached under the control board. Both rings are GND.
- **UI board** (2-layer): display, 2× EC11, 5-way nav, lit Output-Enable button, power button, I/O expander, buzzer. Only 3.3 V
  digital on the ribbon (SPI to the display ≤ ~20 MHz, alternate signal/ground wires).

## 5. Firmware scope (later)
Setpoint DACs, duty-aware ITH clamp, power-limit loop, PD policy (AP33772S: read PDOs, request fixed/PPS/AVS, EPR entry),
sink-path enable, input-voltage check (output off below ~8–9 V), metering, protection latch handling, thermal throttling and clamp
budget, UI, menu, USB CDC SCPI, jump-to-DFU command.

## 6. Open items / risks
1. LTC7803 at 40 V abs max: depends on the ~31 V OV lockouts; measure switch-node ringing on the first board.
2. Sense-signal ripple is small (~5 mV vs LTC's 10–20 mV): careful Kelvin layout + SENSE RC filter.
3. VOM1271 turn-off time with the BSC040N10NS5 pair (Si8751 not stocked).
4. AP33772S with its NMOS driver unused, and with V5V fed while VCC is absent — check on the bench / with Diodes.
5. LCSC picks for the small parts still without numbers (TODO.md).

## 7. Next steps
1. ~~Pivot: requirements, IC re-shop, calculations, LTspice~~ (done 2026-09-27).
2. ~~skidl schematic update~~ — split 2026-10-01: `power_design.py` (supply_power, 251 parts) + `control_design.py`
   (supply_control, 75 parts) + `ui_design.py` (UI, 69 parts), ERC clean, B2B check 40/40. See `design/README.md`.
3. Review the netlists/BOMs; close the remaining part picks in `TODO.md`; buy the AP33772S and LTC7803 early.
4. Layout in KiCad (4-layer supply_power, supply_control, 2-layer UI board) around the chosen extrusion; board split done in skidl 2026-10-01 (§4).
5. Firmware and staged bring-up from a current-limited bench supply on the DC input.

## References
- AP33772S datasheet (DS46176): https://www.diodes.com/datasheet/download/AP33772S.pdf (local: datasheets/ap33772s.pdf)
- LTC7803 datasheet: https://www.analog.com/en/products/ltc7803.html (local: datasheets/ltc7803.pdf)
- CSD18531Q5A / CSD18540Q5B: https://www.ti.com/lit/ds/symlink/csd18531q5a.pdf, https://www.ti.com/lit/ds/symlink/csd18540q5b.pdf
- LM74800-Q1: https://www.ti.com/product/LM74800-Q1
- LM5148 (runner-up buck controller): https://www.ti.com/lit/ds/symlink/lm5148.pdf
- Pre-pivot parts (git d8d0a65): TPS26750 (SLVSH67, TRM SLVUCR7), TPD4S480, LTC7801
