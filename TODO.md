# Work items

Running list for the USB-C PD bench supply. Plan: [PLAN.md](PLAN.md). Numbers: [calc/results.md](calc/results.md)
(regenerate with `.venv/Scripts/python calc/buck_calc.py`).

Legend: **[you]** needs your decision or a download · **[me]** I'll do it · ☐ open · ☑ done

## Decisions needed (pivot 2026-09-26: 140 W USB / 10 A — see PLAN §1a)
- ☑ Q1 DC input: **≤ 30 V**, 10 A, OV lockout ~31–32 V, survives ≥ 60 V → output 0–27 V, 60 V class parts (2026-09-26)
- ☑ Q2 Cooling: **fanless**, aluminium extrusion as the heatsink, unpopulated fan header as a fallback (2026-09-26)
- ☑ Q3 **Re-shop both** the PD sink chip and the buck controller (2026-09-26)

## Pivot rework
- ☑ IC re-shop → [calc/ic_reshop.md](calc/ic_reshop.md): **AP33772S** (PD sink) + **LTC7803** (buck controller) chosen 2026-09-26; LM5148 runner-up
- ☐ **[you]** Buy early: AP33772S (LCSC ~140 pcs) and LTC7803 (LCSC 38 pcs MSOP) — or Mouser/Digi-Key
- ☐ **[me]** LTC7803 protection: VIN-pin RC + TVS, bus TVS, SW snubber footprint, regen clamp also triggered by VIN_BUS > ~33 V
- ☐ **[me]** USB path: LM74800 EN from MCU after AP33772S reports a contract; decide whether AP33772S PWR_EN drives an extra series FET
- ☐ **[me]** OV lockout at ~31 V on **both** inputs (LM74800 OV pin) — the LTC7803 depends on it
- ☑ `calc/buck_calc.py` redone for 140 W / 10 A (2026-09-27): **CSD18531Q5A ×2, 300 kHz, SER2918H-103KL 10 µH, 2.0 mΩ sense, INA240A3**,
  4+4× 4.7 µF 100 V output MLCCs, fanless thermal model (worst ~8 W → extrusion ≈ 45 °C) → [calc/results.md](calc/results.md)
- ☑ LTspice port to the LTC7803 (t0–t8) → [sim/results.md](sim/results.md). Changes from it: 300 kHz (200 kHz → sub-harmonic), 2.0 mΩ,
  **EXTVCC from the 12 V aux rail** (5 V stalls the controller), external boost diode, duty-aware ITH clamp
- ☑ Output envelope accepted (2026-09-27): 10 A up to ≈ Vin − 3.5 V; from 28 V USB-C ≈ 26.5 V max at ≈ 4.3 A. Full power is occasional use; thermal throttling in firmware is fine
- ☐ **[me]** Pick LCSC parts: 4 mΩ 2512 sense resistors (2×), CMDSH-4E-class low-leakage boost Schottky, 15 A 58 V blade fuse + holder,
  5 V LDO for the analog rail (from 12 V), SMBJ33A bus TVS, ~36 V zener for the LTC7803 VIN pin
- ☐ **[me]** Firmware notes: duty-aware ITH clamp (map ~25 A/V + 0.45 V up to D 0.75, ~15 A/V + 0.8 V near D 0.9; calibrate at run time),
  Iset limited near dropout, S-curve end of the start-up ramp, clamp average derated from the enclosure NTC, all DAC setpoints ≤ 2.9 V
- ☐ **[me]** AP33772S PD policy (firmware): read SRCPDO, request the lowest PDO/AVS/PPS that covers Vset + headroom and the power need; EPR 28 V needs an EPR cable
- ☐ **[me]** Update the skidl modules, ERC, netlists/BOMs, `calc/parts_shortlist.md` (LCSC stock)
- ☐ **[me]** Update PLAN §2–§4 once the picks settle

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
- ☑ Modules: `design/power_in.py`, `buck.py`, `control.py`, `output.py`, `housekeeping.py`, `usb_iso.py`, `mcu.py`; top level `supply_design.py`; UI board `ui_design.py`
- ☑ Custom symbols generated into `symbols/supply1.kicad_sym` from the pin tables in `design/parts.py`; custom footprint `footprints/supply1.pretty/L_Coilcraft_SER2918H`
- ☑ ERC: main board 0 errors (3 benign open-drain warnings), UI board clean. All 52 footprints resolve. No single-pin nets.
- ☑ Netlists: `out/supply_main.net` (321 parts), `out/supply_ui.net` (71 parts), BOMs with LCSC numbers
- ☐ **[you]** Review the netlists / BOMs
- ☐ **[me, optional]** Auto-generated KiCad schematic: skidl 2.3's placer crashes on both boards (`tools/gen_schematic.py`); retry after a skidl update or patch it — not needed for the PCB
- ☐ **[me]** Pick LCSC parts still without a number: LMR38010 22 µH inductor, LM5164 68 µH inductor, MBRB40100CT-class reverse diode, gate/logic 2N7002, BAT54W, SS110/SS14, passives (mostly JLC basic parts)
- ☐ **[me]** TPS26750 PP5V: currently 0 Ω to GND for sink-only — confirm (TI E2E / EVM schematic)
- ☐ **[me]** TPS26750 config (GUI): map "EPR enable" to GPIO0 (drives TPD4S480 EPR_EN); SafeMode strap, I2C 0x21
- ☐ **[me]** Mini 58 V fuse vs Keystone 3568 holder (58 V fuses have a rejection feature)
- ☐ **[me]** SER2918H footprint: pad 3 (mounting) position is approximate — check against the Coilcraft drawing before layout
- ☐ **[me]** VOM1271 output polarity (pin 4 = +) — double-check the datasheet drawing
- ☐ **[you]** Display module: header assumes the common GND/VCC/SCL/SDA/RES/DC/CS/BLK pinout — check against the module you buy
- ☐ **[you]** Layout: KiCad projects live in `kicad/supply_main/supply_main` and `kicad/supply_ui/supply_ui` (fp/sym lib tables are next to the .kicad_pro), then PCB editor → File → Import → Netlist

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
