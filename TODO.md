# Work items

Running list for the USB-C PD bench supply. Plan: [PLAN.md](PLAN.md). Numbers: [calc/results.md](calc/results.md)
(regenerate with `.venv/Scripts/python calc/buck_calc.py`).

Legend: **[you]** needs your decision or a download · **[me]** I'll do it · ☐ open · ☑ done

## Decisions needed (pivot 2026-09-26: 140 W USB / 10 A — see PLAN §1a)
- ☑ Q1 DC input: **≤ 30 V**, 10 A, OV lockout ~31–32 V, survives ≥ 60 V → output 0–27 V, 60 V class parts (2026-09-26)
- ☑ Q2 Cooling: **fanless**, aluminium extrusion as the heatsink, unpopulated fan header as a fallback (2026-09-26)
- ☑ Q3 **Re-shop both** the PD sink chip and the buck controller (2026-09-26)

## Board size / enclosure (2026-09-28)
- ☑ Enclosure: extrusion 120 × 70 × 40 mm inside + ~50 mm 3D-printed front add-on → ~170 × 70 × 40. Power stage stays in the
  aluminium part (heat path), logic moves into the add-on. The 210 × 125 outline was only the placement-script placeholder.
- ☑ Cuts: DC-input XT60 → wire pads (panel connector on the end cap), output XT60 removed, fan header removed, LTO100 clamp resistor
  → wired to the wall. Kept: second DC input, isolated USB, SWD + UART + RESET/BOOT.
- ☑ Extrusion profile (2026-09-28): 78 outside / 75 slot bottoms / 70 between ribs, 1.5 mm walls, 2 mm slots on 3.5 mm pitch,
  lowest slot 7.06 mm above the floor → board ≈ 74.5 mm wide, ~3 mm edge keep-out both sides, ~5.5 mm spacer + gap pad (PLAN §4)
- ☐ **[you]** Add-on in 3D: display on top, controls/posts on the front face (may make the add-on longer)

## Mechanics / 3D (build123d, `CAD_3D/`, 2026-09-30) — see PLAN §4
- ☑ Structure: `geom_defs.py` (dataclasses), `enclosure.py` (`create_enclosure`), `mech_design.py` (reference values),
  `check_fit.py` (empty, later)
- ☑ Slot offset checked against the Hammond drawing (profile view measured to scale): floor→lowest slot 7.04, top slot→ceiling
  6.40 → the pattern really is ≈ 0.31 mm off-centre; `slot_offset = 0.31` is right. The extrusion is otherwise symmetric, so it can
  go in upside down (floor gap 6.44)
- ☐ **[you]** Measure the real extrusion (floor→lowest slot bottom from both sides) and mark "up" before drilling H905 / LTO100
- ☑ `mech_design.py` board width is 74.5 now (was 75 = zero clearance in the slot bottoms)
- ☑ Board split (2026-10-01): supply_power (slot 0, ~170 mm) + supply_control (slot 6 = `control_pcb_slot_index = -2`, 110 × 74.5 mm).
  Link: 2×20 2.54 mm female headers + long male-male pins (19.8 mm stack at hand; slot 6 gives **19.0–19.8 mm** between the board
  surfaces, pins not fully seated take up the play). skidl done: `power_design.py` / `control_design.py`, PLAN §4
- ☐ **[you]** Slot 6: only **1.2–2.0 mm** between the SER2918H top (17.78 mm max) and the control board → no bottom-side parts on
  the control board above the inductor; check the other tall power-board parts (100 µF radial D10, fuse holder + fuse) against it
- ☐ **[me]** LCSC picks: Würth 9774030360R WA-SMSI M3 × 3 mm insert (H905, H906; alt. PEM SMTSO-M3-3ET / Sinhoo clone), 2×20 2.54 mm
  female header (J951, J971; match the height of the pins you have), long male-male pins
- ☐ **[you/me]** Keep-outs from the stack (slot 6): control-board bottom side ≤ ~1.2 mm above the inductor; control-board top ≤ ~9.9 mm,
  ≤ ~5.8 mm within ~6 mm of the long edges (corner screw bosses; the model's bosses are simplified, so check again in `check_fit.py`)
- ☑ Board → 3D (2026-10-01): `tools/export_mech.py` (KiCad python, auto-run when stale) → `out/mech_<board>.json` →
  `CAD_3D/kicad_board.py` (slab + bodies) + `CAD_3D/electronic_components.py` (F.Fab box × height; heights from the KiCad
  STEP model bbox, overrides by ref/footprint) → `CAD_3D/assembly.py` (enclosure + both boards, summary, ocp_vscode).
  Rear end cap flush with the extrusion for now (`pcb_rear_gap = 0`); the power board sticks out at the front (add-on TBD).
- ☐ **[you]** Confirm the estimated heights: F401 fuse holder + inserted mini fuse (17.5 assumed), C223 (13.5 = L12 + 1.5),
  LTO100 body (5.0, no KiCad model), J601 HRO USB-C (3.3)
- ☐ **[me]** Size the spacer + gap-pad stack under the power stage for 7.06–7.46 mm (+ tolerance/orientation)
- ☐ **[me]** `check_fit.py` once the board split is laid out: boards in their slots + part boxes (or a KiCad STEP) → clearance
  report + height-zone DXF for KiCad
- ☐ **[you]** UI board + add-on in build123d (front-panel positions in `mech_design.py` drive both)

## UI rework: scroll wheels (2026-10-01) — see PLAN §3.4 / §4
- ☑ Concept: 2 scroll wheels with push on the add-on top next to the display (left = V, right = I; push = unlock, push again = lock),
  nav 5 → 3 buttons (Left / Right / Enter). Magnetic sensing (MT6701) rejected as scope creep; edge-drive jog encoders (EVQWK,
  SIQ-02FVS3) rejected (15 detents, need a vertical board)
- ☑ Parts: Alps **EC10E1220501** (24 det, shaft axis 9.0 mm, 1.73 mm hex bore with a 3° flare) + Omron **B3F-1060** (7.0 mm, 100 gf)
  under the free axle end; the same B3F-1060 for the 3 nav buttons
- ☑ skidl `ui_design.py`: EC10E ×2 (SW1 = V, SW2 = I), wheel pushes SW3/SW4 (ex-UP/DOWN refs), LEFT/RIGHT/ENTER on TCA9535
  P00–P02, P03/P04 spare → TP7/TP8, R13/R14 retired; still 69 parts, ERC clean. Ribbon pinout unchanged
- ☑ Footprint `footprints/supply1.pretty/RotaryEncoder_Alps_EC10E_Horizontal.kicad_mod` (from the catalog's mounting-hole drawing)
- ☐ **[you]** Buy samples (Farnell / DigiKey: EC10E1220501 ×3–4, B3F-1060 ×10; not found at LCSC → hand-solder, they're THT).
  With an ohmmeter, check which **end** pin is C (common): the footprint assumes A, B, C from left to right as seen from the top
  with the bracket slots towards −Y, but I can't tell from the catalog whether that view is mirrored
- ☐ **[you]** Wheel + axle + push in the add-on CAD: wheel Ø (12–14 mm → 1.6–1.8 mm per click), metal axle, collar on the B3F,
  switch 12–15 mm from the encoder hub (≥ 9 mm), top surface ≈ 2–3 mm below the wheel top. Then place SW1–SW4 to match
- ☐ **[me]** CAD heights for the UI board: EC10E body ≈ 12.6 mm (estimate; the Alps STEP is in the catalog zip if needed),
  B3F-1060 has a KiCad model

## Display: 1.9" IPS (2026-10-01) — see PLAN §3.4
- ☑ 2.42" OLED → **1.9" IPS 170×320 ST7789** (HESTORE IPS-1.9-ST7789-SPI-M). UI J3 → 8-pin socket (GND/VCC/SCL/SDA/RES/DC/CS/BLK,
  from the HESTORE drawing), BLK ← LCD_BL via R29 100 Ω, C12 10 µF local bulk; TP10 (UI_SPARE) retired. Ribbon pin 18
  UI_SPARE → LCD_BL, MCU PC13 → PB10 (TIM2_CH3), PC13 now free. UI 62 parts, control 80 parts, both ERC clean
- ☐ **[you]** Update PCB from netlist on supply_ui (J3 footprint 1×07 → 1×08, R29 / C12 new, TP10 gone) and supply_control
  (U701 pin 30 = PB10 LCD_BL, pin 2 = PC13 NC)
- ☐ **[you]** When the module arrives, check BLK with a meter: a pull-up to VCC (tens of kΩ) = transistor input, the PWM drives
  it as designed; ~0 Ω-ish diode path to the LEDs = direct anode → swap R29 for a high-side P-FET driver
- ☐ **[you]** Add-on CAD: the module screws to the printed top (4× M2 on 25.8 × 57.9 mm) behind a window over the 22.7 × 42.72
  active area; 5.1 mm total depth + header. Decide how J3 reaches it (socket stack vs short wires) — the UI board footprint
  for J3 is a vertical 1×08 socket for now
- ☐ **[me]** Firmware notes (later): ST7789 column offset 35, partial-buffer rendering, backlight dim after idle

## OUTPUT button + POWER rocker (2026-10-01) — see PLAN §4
- ☑ OUTPUT = latching lit push button (E-Switch PV4, 19 mm, on-on latching, gold, red ring LED): UI J6 (4-pin JST XH: switch,
  GND, LED anode via R27 100 Ω, LED cathode → TCA9535 P10). On-board OUTPUT tactile, on-board OE LEDs and the 5-pin J4 retired;
  P11 spare (TP)
- ☑ POWER = rocker → supply_control J501 → LMR38010 EN (R505 4.7k series, R506 47k pull-down, C509 10n, TP502). UI POWER tactile
  and J5 retired; ribbon pin 18 / PC13 renamed PWR_BTN → UI_SPARE. All three boards ERC clean, B2B 40/40
- ☐ **[you]** Update PCB from netlist on supply_ui (11 parts retired, J6 / TP9 / TP10 new) and supply_control (J501, R505, R506,
  C509, TP502 new)
- ☐ **[you]** Order: PV4 OUTPUT button (PV4F230SSG-311 = flat, solder, on-on, gold, red ring, bare LED; add -M01 for the power
  symbol; I built the code from the datasheet configurator, so confirm it exists and check the body depth behind the panel)
  + a rocker (RA1113112R or a gold-contact one) — together with the EC10E / B3F-1060 samples above
- ☑ DC input path is firmware-enabled (DCIN_ON, PB4, B2B pin 22 ex-GND): Q163/Q164 2N7002, D162 BZT52C12, R165 1M, R166 100k,
  TP161 on supply_power. Rocker off → DC path off too
- ☑ CC / CV LEDs → 3 mm THT (D3 red CC, D4 green CV), standing off the board up to the panel; FAULT stays 0805
- ☐ **[you]** Update PCB from netlist on supply_power too (6 new parts, J951 pin 22 now DCIN_ON), and on supply_ui (D3/D4 footprint
  change)
- ☐ **[you]** Rocker from a local shop; CC/CV LED positions in the add-on CAD (panel holes, standoff height)
- ☐ **[me]** Firmware notes: raise DCIN_ON at boot (hardware UVLO / OV still guard the DC path; VIN_SNS only reads after the path); OUTPUT is level-sensitive (pushed in at boot / after a trip → needs release + push), LED blinks
  when the output is not on although the button is in
- ☑ UI (2026-09-28): 2.42" SSD1309 SPI OLED (7-pin header) instead of the ST7789; ribbon 2×10 1.27 mm (`design/mcu.py` UI_PINOUT);
  encoder pushes moved to the TCA9535; MCU pins PB4, PB10, PB11, PF0, PF1 now free
- ☑ skidl (2026-09-28): cuts applied, main 297 parts / UI 69 parts, ERC clean. J161 = DC-in wire pads, J402 = LTO100 wire pads,
  J703 / UI J1 kept their refs (lock entry edited); retired J401, J581, Q581, R419, R581–R583, UI TP5/TP6
- ☑ skidl split (2026-10-01): supply_power 251 parts, supply_control 75 parts, UI 69 parts; all ERC clean, no single-pin nets,
  `tools/b2b_check.py` 40/40 pins and no refs shared between the boards. Both locks were seeded from the old `refs_main.lock.json`
  (refs kept; each board retires the other board's refs). R419 LTO100 back on the board (TO-247-2 tab-down), J402 retired;
  H905 + new H906 = WA-SMSI M3 inserts; LOGIC_IN diodes → D531/D532 (power), +3V3A filter on both boards; MCU-side
  100 Ω + 1 nF on the 9 analog inputs (R708–R716, C710–C718)
- ☑ Board setup (2026-10-01): `tools/board_setup.py` (KiCad's Python, boards closed; re-runnable, reads `mech_design.py` through the
  venv) → outline from `pcb_size_*`, slot keep-out rule areas (F.Cu/B.Cu, `edge_keepout` along both long edges; inner layers free),
  board centre = grid + drill/place origin at (150, 100), 4-layer stackup (power: 2 oz outer / 1 oz inner, min 0.15/0.15; control:
  1/0.5 oz, min 0.127), JLC-safe minimums (via ≥ 0.6/0.3, copper–edge 0.4, silk 1.0 × 0.15), net classes by net-name pattern
  (power: Power / Gate / Supply / Kelvin; control: Supply / ISO) and `.kicad_dru` rules (solid pour connection for Power-class
  pads and ≥ 1206 GND pads; control: 1.5 mm isolation barrier around the ISO class, PS601's own pins exempt). DRC clean, rules
  verified on a scratch board. Rules go into the script, not Board Setup (re-running overwrites them).
  Run it with `.\tools\run_board_setup.ps1`. Fixed 2026-10-01: re-runs crashed (`'SwigPyObject' object has no attribute
  'NewOutline'`) because `board.Remove()` hands the item to Python and the garbage-collected proxy corrupts SWIG's type table
  → `detach()` sets `thisown = False`
- ☑ H901–H904 removed from `power_design.py` (2026-10-01; numbers retired in the lock, 247 parts, ERC clean)
- ☑ Axis convention (2026-10-01): KiCad left (−X) = rear end cap; both boards have their rear edge at the rear end cap, the front
  (right) end is free. In power-board coordinates (centre = 0): rear edge −85, aluminium ends at ≈ +35 (120 mm), control board
  spans −85 … +25
- ◐ Axis convention moved into `CAD_3D/mech_design.py` (docstring + `PCBPlacement`, 2026-10-01); still TODO: let
  `tools/board_setup.py` read it from there
- ☑ PCB: netlists imported into `kicad/supply_power` / `kicad/supply_control` (you, 2026-10-01)
- ☑ Floor plan + first placement (layout steps 2 + 3, 2026-10-01): `tools/floorplan.py` (the data: areas, fixed power-path parts,
  clusters with targets — edit this), `tools/place.py` (engine), `tools/snapshot.py` (→ `out/placement_<board>.png`), run both with
  `.\tools\run_place.ps1 [power|control]`. Frames + notes on User.Comments (group `floorplan`), each cluster a group `place:<name>`.
  **Locked footprints / locked groups are never moved** (tested): move + lock what you want to keep, re-run, the rest follows.
  Power: input left (USB-C row, DC row, ideal diodes), VIN bulk + hot loop + U201 under the FET pair, L201 top, LC filter, output
  right; R419 on the bottom (body south, H906 near the bottom edge). Control: ISO column left, MCU centre, LMR38010 near LOGIC_IN,
  debug/UI at the front. J971 is derived from J951 (all 40 mirrored pins checked on every run); the control board gets rule areas
  (no bottom-side parts) over L201 / C217 / C223 / C228. Small refs (160 power, 59 control) hidden on silk, still on F.Fab.
  DRC: no courtyard overlaps; `board_setup.py` got rules for footprint-internal pad/hole clearances and min drill 0.2 mm (thermal vias)
- ☐ **[you]** Update the control PCB from the regenerated `out/supply_control.net` (Tools → Update PCB from Netlist, placement stays):
  the USB-C CC nets are now named ISO_CC1 / ISO_CC2 (`design/usb_iso.py`) → ISO class → clears the 24 isolation-rule DRC errors
- ☐ **[you]** Review the placement (KiCad + `out/placement_*.png`); move/lock what you want different, or tell me and I change
  `floorplan.py`
- ☐ **[me]** Layout step 4: power-stage review + copper (hot loop, SW node, gate drive, Kelvin pair from R211/R212 to U201 / U202,
  pours per layer, thermal vias, spacer-block area under the FETs on the bottom, H905 position against it)
- ☐ **[me/you]** H906 sits on R419's tab hole → DRC `holes_co_located` + `npth_inside_courtyard` (intended). Fix: TO-247 footprint
  without the tab hole in `footprints/supply1.pretty`, or a DRC exclusion
- ☐ **[me]** Silkscreen: place the remaining visible refs (62 silk overlaps on power, 9 on control)
- ☐ **[you]** Heights on the control board top (ceiling 9.9 mm): J703 ribbon header + plug, J702 UART header (+ plug only when the
  boards are out?), SW701/SW702. PS601 (B0505S, 10.2 mm) moved to the control board's bottom side
- ☐ **[me]** JLC: price of the 0.2 mm thermal-via holes in the `_ThermalVias` footprints (U101, U201, U541), else plain footprints + own vias
- ☑ `tools/place_main.py` deleted (2026-10-01; replaced by `tools/place.py`, old version in git)
- ☑ PCB → mech export: `tools/export_mech.py` → `out/mech_<board>.json` (all footprints, outline, drills; 2026-10-01)
- ☐ **[me]** Optional: posts H401/H402 (M4 lug pads) → solder-wire pads; SW701/SW702 → SMD tact switches
- ☑ Thermal model for the real extrusion (2026-09-28): 3.8 K/W, τ ≈ 12 min, budget 6.5 W for ≤ 55 °C; worst load throttles after
  ~21 min; clamp average ≈ 4.5 W with the buck idle → [calc/results.md](calc/results.md) §3

## Pivot rework
- ☑ IC re-shop → [calc/ic_reshop.md](calc/ic_reshop.md): **AP33772S** (PD sink) + **LTC7803** (buck controller) chosen 2026-09-26; LM5148 runner-up
- ☐ **[you]** Buy early: AP33772S (LCSC ~140 pcs) and LTC7803 (LCSC 38 pcs MSOP) — or Mouser/Digi-Key
- ☑ LTC7803 protection in the schematic: VIN-pin 10 Ω + 1 µF + 36 V zener, SMBJ33A bus TVS, SW snubber footprint, regen clamp also triggered by VIN_PWR > ~33 V
- ☑ USB path: LM74800 EN = MCU PB3 (PD_SINK_EN, default off) after the AP33772S reports a contract; AP33772S PWR_EN unused (test point)
- ☑ OV lockout ~31.1 V (243 k / 10 k) on **both** LM74800 inputs
- ☑ `calc/buck_calc.py` redone for 140 W / 10 A (2026-09-27): **CSD18531Q5A ×2, 300 kHz, SER2918H-103KL 10 µH, 2.0 mΩ sense, INA240A3**,
  4+4× 4.7 µF 100 V output MLCCs, fanless thermal model (worst ~8 W → extrusion ≈ 45 °C) → [calc/results.md](calc/results.md)
- ☑ LTspice port to the LTC7803 (t0–t8) → [sim/results.md](sim/results.md). Changes from it: 300 kHz (200 kHz → sub-harmonic), 2.0 mΩ,
  **EXTVCC from the 12 V aux rail** (5 V stalls the controller), external boost diode, duty-aware ITH clamp
- ☑ Output envelope accepted (2026-09-27): 10 A up to ≈ Vin − 3.5 V; from 28 V USB-C ≈ 26.5 V max at ≈ 4.3 A. Full power is occasional use; thermal throttling in firmware is fine
- ☑ LCSC picks: 4 mΩ 2512 (C2904236), CMDSH-4E (C5240486), SMBJ30A (C113998), SMBJ33A (C173526), BZT52C36 (C19077420), LP2985-50 (C74511)
- ☐ **[me]** Still without LCSC number: 15 A MINI blade fuse, and the older small parts (2N7002, BAT54W/S, SS110/SS14, LMV331, UCC27511, USBLC6, NTCs, LEDs, ferrite, inductors 22/68 µH, connectors, switches)
- ☐ **[me]** Check the STM32G4 DAC output load: DAC_ICL sees 100 Ω + 10 nF (DAC_V / DAC_I: 1 k + 100 nF); the buffered DAC is
  specified for ≤ 50 pF / ≥ 5 kΩ → maybe a larger series R or an internal OPAMP follower. (Predates the split; the header adds nothing relevant)
- ☐ **[me]** Firmware notes: duty-aware ITH clamp (map ~25 A/V + 0.45 V up to D 0.75, ~15 A/V + 0.8 V near D 0.9; calibrate at run time),
  Iset limited near dropout, S-curve end of the start-up ramp, clamp average derated from the enclosure NTC, all DAC setpoints ≤ 2.9 V
- ☐ **[me]** AP33772S PD policy (firmware): read SRCPDO, request the lowest PDO/AVS/PPS that covers Vset + headroom and the power need; EPR 28 V needs an EPR cable
- ☑ skidl modules updated (2026-09-27): main board 303 parts, ERC 0 errors / 2 benign warnings, 54 footprints resolve; UI board unchanged.
  PLAN §2–§7 rewritten for the new design
- ☐ **[you]** Review the netlists / BOMs (`out/`)
- ☐ **[me]** Refresh `calc/parts_shortlist.md` for the new parts (stock in `calc/stock_check_5.txt`)

## Datasheets / parts to confirm
Shortlist with LCSC numbers: [calc/parts_shortlist.md](calc/parts_shortlist.md)
- ☑ LCSC/JLC stock check (2026-09-26): everything found or substituted (Coilcraft inductor, VOM1271 driver, IPT015N10N5 switch FETs, 2 Ω clamp resistor, 58 V fuse)
- ☐ **[me]** VOM1271: Isc 15 µA @10 mA / ~30 µA @20 mA → ~14 ms turn-on at 20 mA LED drive (datasheet). Turn-off is only specified at 200 pF → verify on the bench / in the schematic stage.
- ☑ TPS26750 strap: SafeMode, ADCIN1 = ADCIN2 = GND → I2C 0x21 (Table 7-6)
- ☐ **[me]** CSD18531Q5A: Rds(on)-vs-temperature (×1.45 at 100 °C assumed), plateau voltage and K_QRR = 0.5 to confirm (TI PSpice model; the sim uses a VDMOS approximation).
- ☐ **[me]** SER2918H-103 core loss at 300 kHz / 2.6 A pp (Coilcraft calculator); 0.3 W assumed.
- ☐ **[me]** 100 V 1210 MLCC DC-bias derating (4.7 µF X7S: ~3 µF left at 27–30 V assumed); ripple current per cap.
- ☐ **[me]** Pick: PCB blade-fuse holder, 4 mm binding posts, gap pad + mounting to the extrusion (depends on the extrusion).
- ☐ **[me]** TPS26750 config for the web GUI (firmware-side, not needed for the PCB): settings list for "sink-only, EPR + AVS, host-controlled"

## Simulation (LTspice, LTC7801 model) — see sim/results.md
- ☑ CV loop: load steps, PWM loads (20 kHz / 2 kHz), margins → filter changed (0.47 µH post filter, 100 µF/0.1 Ω damper)
- ☑ CC loop from inductor-current sense; short entry/release; anti-windup via compensation returned to ITH
- ☑ FB held at 0.70 V: no foldback/OVP interaction; REGSD must be defeated (330 k INTVCC→SS)
- ☑ Regen injection with pulse-skip + clamp: no backfeed to the input
- ☑ Fast ITH clamp (PNP + 3rd DAC) added after the short-circuit test
- ☐ **[me]** Re-run once the real op-amp, INA240 and FET choices are made (Infineon SPICE model for Qrr/K_QRR if obtainable)
- ☐ **[me]** Output switch (VOM1271 + back-to-back FETs) turn-off during a fault; PD source voltage transitions under load
- ☑ Light-load bottom-FET glitch in t2: timestep artifact (disappears at 20 ns max step)

## Schematic (skidl) — see design/README.md
- ☑ Modules: `design/power_in.py`, `buck.py`, `control.py`, `output.py`, `housekeeping.py`, `usb_iso.py`, `mcu.py`, `interconnect.py`, `board.py`; top level `power_design.py` + `control_design.py` (was `supply_design.py`); UI board `ui_design.py`
- ☑ Custom symbols generated into `symbols/supply1.kicad_sym` from the pin tables in `design/parts.py`; custom footprint `footprints/supply1.pretty/L_Coilcraft_SER2918H`
- ☑ ERC: main board 0 errors (3 benign open-drain warnings), UI board clean. All 52 footprints resolve. No single-pin nets.
- ☑ Netlists: `out/supply_power.net`, `out/supply_control.net`, `out/supply_ui.net`, BOMs with LCSC numbers (the old `supply_main.*` outputs are deleted)
- ☐ **[you]** Review the netlists / BOMs
- ☐ **[me, optional]** Auto-generated KiCad schematic: skidl 2.3's placer crashes on both boards (`tools/gen_schematic.py`); retry after a skidl update or patch it — not needed for the PCB
- ☐ **[me]** Pick LCSC parts still without a number: LMR38010 22 µH inductor, LM5164 68 µH inductor, MBRB40100CT-class reverse diode, gate/logic 2N7002, BAT54W, SS110/SS14, passives (mostly JLC basic parts)
- ☐ **[me]** TPS26750 PP5V: currently 0 Ω to GND for sink-only — confirm (TI E2E / EVM schematic)
- ☐ **[me]** TPS26750 config (GUI): map "EPR enable" to GPIO0 (drives TPD4S480 EPR_EN); SafeMode strap, I2C 0x21
- ☐ **[me]** Mini 58 V fuse vs Keystone 3568 holder (58 V fuses have a rejection feature)
- ☐ **[me]** SER2918H footprint: pad 3 (mounting) position is approximate — check against the Coilcraft drawing before layout
- ☐ **[me]** VOM1271 output polarity (pin 4 = +) — double-check the datasheet drawing
- ☐ **[you]** Layout: KiCad projects live in `kicad/supply_power`, `kicad/supply_control` and `kicad/supply_ui/supply_ui` (fp/sym lib tables are next to the .kicad_pro), then PCB editor → File → Import → Netlist

## Known limitations (accepted, documented)
- Below ~1.15 V out from a 48 V input the controller pulse-skips (80 ns min on-time at 300 kHz): higher ripple, still regulates. From PD, the MCU can pick a lower input voltage when power allows.
- ~~Full 240 W from USB-C needs the 48 V PDO~~ → now: full 140 W needs the 28 V EPR PDO **and** an EPR (240 W e-marked) cable; AVS only helps efficiency at part load.
- ~~Top FET runs ~7.5–8 W at 20 A → fan mandatory~~ (pre-pivot; at 10 A the top FET is ~1.5–5 W, see PLAN §1).

## Done
- ☑ Enclosure: aluminium extrusion, probably 3D-printed front/back panels (2026-09-26)
- ☑ LTspice verification of loops, shorts, regen (sim/results.md)
- ☑ Requirements and architecture (PLAN.md)
- ☑ PD chip choice: TPS26750 + TPD4S480 (HUSB238A rejected)
- ☑ LTC7801 datasheet review → FB-held-at-0.7 V / external ITH control scheme
- ☑ Ideal-diode (LM74800-Q1) and output switch driver (Si8751) selection
- ☑ DC input rated 20 A
- ☑ Regen clamp: burst-only rating (50 W / ~10 s, ~10 W average), resistor on the main heatsink
- ☑ OptiMOS datasheets reviewed → ISC030N10NM6 for both buck FETs (Qrr compared at 1000 A/µs)
- ☑ Parts shortlist with LCSC numbers (calc/parts_shortlist.md)
- ☑ First-pass power-stage calculations (calc/results.md): 300 kHz, Würth 6.8 µH, 2.5 mΩ sense, filters, sensing, clamp, loop sanity check
