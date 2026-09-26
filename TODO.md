# Work items

Running list for the USB-C PD bench supply. Plan: [PLAN.md](PLAN.md). Numbers: [calc/results.md](calc/results.md)
(regenerate with `.venv/Scripts/python calc/buck_calc.py`).

Legend: **[you]** needs your decision or a download · **[me]** I'll do it · ☐ open · ☑ done

## Decisions needed
- (none open)

## Datasheets / parts to confirm
Shortlist with LCSC numbers: [calc/parts_shortlist.md](calc/parts_shortlist.md)
- ☑ LCSC/JLC stock check (2026-09-26): everything found or substituted (Coilcraft inductor, VOM1271 driver, IPT015N10N5 switch FETs, 2 Ω clamp resistor, 58 V fuse)
- ☐ **[me]** VOM1271: Isc 15 µA @10 mA / ~30 µA @20 mA → ~14 ms turn-on at 20 mA LED drive (datasheet). Turn-off is only specified at 200 pF → verify on the bench / in the schematic stage.
- ☑ TPS26750 strap: SafeMode, ADCIN1 = ADCIN2 = GND → I2C 0x21 (Table 7-6)
- ☐ **[me]** Rds(on)-vs-temperature curve for ISC030N10NM6 (×1.45 at 100 °C assumed); K_QRR = 0.5 (dead-time effect) to confirm with Infineon's SPICE model if obtainable.
- ☐ **[me]** Inductor core loss at 300 kHz (Coilcraft calculator); 1 W assumed.
- ☐ **[me]** 100 V 1210 MLCC DC-bias derating (4.7 µF X7S: ~40 % left at 46–48 V assumed); ripple current per cap.
- ☐ **[me]** Pick: PCB blade-fuse holder, 4 mm binding posts, fan + header, heatsink (depends on enclosure extrusion).
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
- Full 240 W from USB-C needs the 48 V PDO (5 A PD limit), so AVS only helps efficiency at part load.
- Top FET runs ~7.5–8 W at 20 A / high duty → the heatsink + fan are mandatory, not optional.

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
