# Schematic (skidl) — how it's organised

Two boards, two netlists:

| Board | Script | Output |
|---|---|---|
| Main (power + MCU) | `supply_design.py` | `out/supply_main.net`, `out/supply_main_bom.csv` |
| UI (display, knobs, buttons) | `ui_design.py` | `out/supply_ui.net`, `out/supply_ui_bom.csv` |

Run from the project root with `.venv/Scripts/python supply_design.py` (and `ui_design.py`).
ERC runs every time; the last check was main board 0 errors / 3 benign open-drain warnings, UI board clean.

## Modules (main board)

| File | Block | Ref numbers |
|---|---|---|
| `design/power_in.py` | USB-C PD sink (TPD4S480 + TPS26750 + EEPROM + LM74800), XT60 DC input (LM74800), input shunt + INA228 | 1xx |
| `design/buck.py` | LTC7801, ISC030N10NM6 ×2, SER2918H, 2.5 mΩ sense, C1 + damper, 0.47 µH post filter, C2, INA240A2, NTCs | 2xx |
| `design/control.py` | CV/CC amps (ADA4522-2) → ITH diode-OR, PNP current clamp, DAC filters, sense dividers, HW OVP, FAULT → RUN | 3xx |
| `design/output.py` | output shunt + INA228, regen clamp (LMV331 → UCC27511 → FET → 2 Ω LTO100), VOM1271 output switch, fuse, reverse diode, XT60 + binding-post lugs | 4xx |
| `design/housekeeping.py` | LOGIC_IN diode-OR, LMR38010 3.3 V, LM5164 12 V aux, LP2985 5 V analog, fan | 5xx |
| `design/usb_iso.py` | isolated USB-C device port: USBLC6, ADuM3160, B0505S | 6xx |
| `design/mcu.py` | STM32G474RET6, SWD/UART headers, reset/boot, I2C pull-ups, UI ribbon; **pin map in the docstring** | 7xx |
| `design/nets.py` | all shared net names (MCU pin in the comment) | |
| `design/parts.py` | passive helpers (0603 default), custom part pin tables | |
| `design/symgen.py` | writes `symbols/supply1.kicad_sym` from the custom pin tables (runs automatically) | |

References are assigned per block (`supply_design.py: assign_refs`), and tags equal refs. So adding a part to one block
doesn't renumber the others, and KiCad can keep matching footprints when you re-import the netlist.

## Custom library bits

- `symbols/supply1.kicad_sym`: TPS26750, TPD4S480, LTC7801 (TSSOP-24 FE), LM74800, LMR38010, VOM1271, B0505S-1WR3. It's generated from the pin tables, so don't edit it by hand.
- `footprints/supply1.pretty/L_Coilcraft_SER2918H.kicad_mod`: the main inductor. Pad 3 (mounting) is approximate.
- `kicad/supply_main/supply_main/` and `kicad/supply_ui/supply_ui/`: `fp-lib-table` and `sym-lib-table` pointing at the two
  libraries above. KiCad only reads the tables that sit next to the `.kicad_pro`, so the project files must live in those folders
  (that's what KiCad's New Project dialog creates when "Create a new folder" is ticked).

## Getting to a PCB

1. In KiCad: New Project → `kicad/supply_main/` → name `supply_main` with "Create a new folder" ticked (same for `supply_ui`).
2. Open the PCB editor → File → Import → Netlist → `out/supply_main.net` → Update PCB.
3. After schematic changes: re-run the script and re-import. Keep "match footprints by reference" ticked; the refs are stable.

## Watch-outs found while writing it

- skidl reads a pin name like `"P12"` as pin *number* 12 as well. On the TCA9535 that is GND! The UI board addresses expander pins by number for this reason.
- LM74800 exposed pad (RTN) must be left floating (connected to `NC` here) — do not tie it to the GND pour.
- SER2918H pad 3 is mechanical only: keep it off the SW copper.
