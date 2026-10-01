# Schematic (skidl) — how it's organised

Three boards, three netlists (the former main board was split on 2026-10-01, PLAN §4):

| Board | Script | Output | KiCad project |
|---|---|---|---|
| supply_power (lowest slot: input, buck, analog control, output, clamp, 12 V / 5 V aux) | `power_design.py` | `out/supply_power.net`, `out/supply_power_bom.csv` | `kicad/supply_power` |
| supply_control (slot 6: MCU, isolated USB, 3.3 V buck) | `control_design.py` | `out/supply_control.net`, `out/supply_control_bom.csv` | `kicad/supply_control` |
| UI (display, knobs, buttons) | `ui_design.py` | `out/supply_ui.net`, `out/supply_ui_bom.csv` | `kicad/supply_ui/supply_ui` |

Run from the project root with `.venv/Scripts/python power_design.py` (and `control_design.py`, `ui_design.py`), then
`.venv/Scripts/python tools/b2b_check.py`: it checks that the B2B header carries the same net on the same physical pin on
both boards and that no reference is used on both boards.
ERC runs every time; the last check (2026-10-01) was supply_power 251 parts, supply_control 75, UI 69, all clean.

## Modules

| File | Block | Ref numbers |
|---|---|---|
| `design/power_in.py` | USB-C PD sink (AP33772S + 5 mΩ sense + LM74800, EN from the MCU), DC input on wire pads (LM74800, 100 V FETs), OV lockouts ~31 V, input shunt + INA228, bus TVS | 1xx |
| `design/buck.py` | LTC7803 (300 kHz, EXTVCC 12 V, external boost diode, VIN zener), CSD18531Q5A ×2, SER2918H-103, 2.0 mΩ sense, C1 + damper, 0.47 µH post filter, C2, INA240A3, NTCs | 2xx |
| `design/control.py` | CV/CC amps (ADA4522-2) → ITH diode-OR, PNP current clamp, DAC filters, sense dividers, HW OVP, FAULT → RUN | 3xx |
| `design/output.py` | output shunt + INA228, regen clamp (2× LMV331: Vout > Vset + margin, bus > 33 V → UCC27511 → FET → 2 Ω LTO100), VOM1271 + 100 V output switch, 15 A fuse, reverse diode, binding-post lugs; LTO100 on wires (J402) | 4xx |
| `design/housekeeping.py` | control: `logic_supply` = isolated-USB leg of LOGIC_IN, LMR38010 3.3 V, +3V3A (50x). power: `logic_feed` = VBUS / DC-in legs of LOGIC_IN, local +3V3A (53x); `aux_supply` = LM5164 12 V aux (LTC7803 EXTVCC), LP2985 5 V analog (54x) | 5xx |
| `design/usb_iso.py` | control: isolated USB-C device port: USBLC6, ADuM3160, B0505S | 6xx |
| `design/mcu.py` | control: STM32G474RET6, SWD/UART headers, reset/boot, I2C pull-ups, UI ribbon (2×10 1.27 mm), 100 Ω + 1 nF on the analog inputs; **pin map in the docstring** | 7xx |
| `design/interconnect.py` | 2×20 2.54 mm B2B header, pinout table, mirroring of the control-side socket | J95x power, J97x control |
| `power_design.py` `mechanical()` | M3 holes, H905 (GND screw) and H906 (LTO100 screw) as Würth WA-SMSI M3 SMT inserts | 9xx |
| `design/board.py` | block → ref-number table (one for both boards, so refs are unique across the supply), ref lock, ERC, netlist, BOM | |
| `design/nets.py` | all shared net names (MCU pin in the comment) | |
| `design/parts.py` | passive helpers (0603 default), custom part pin tables | |
| `design/symgen.py` | writes `symbols/supply1.kicad_sym` from the custom pin tables (runs automatically) | |

References are assigned per block (100s = USB-C input, 200s = buck, …) and **locked**: `refs_power.lock.json`,
`refs_control.lock.json`, `refs_ui.lock.json` (logic in `design/reflock.py`). The power and control locks were both seeded from
the old main-board lock at the split, so every part kept its ref and each board lists the other board's refs as retired. Each part's identity (block, part, value, net on each pin) maps to the
ref it got first. On every run:
- unchanged parts keep their ref (identical parallel parts, e.g. an MLCC bank, are matched in code order);
- a part whose value, symbol or one connection changed keeps its ref and is listed as "changed";
- new parts get the next unused number in their block and are listed as "new";
- deleted parts are listed as "removed" and their number is never reused.

Tags equal refs (skidl derives the KiCad UUID from the tag), so both KiCad matching modes stay stable. Commit the lock
files together with the design. Delete a lock file only if you want a full renumber (and then re-place that board).

### Updating the PCB after a schematic change
1. Run the script and read the `refs (...)` summary it prints (changed / new / removed).
2. PCB editor → File → Import → Netlist → `out/supply_power.net` (or `supply_control.net`): **Link footprints using: Symbol reference**; tick
   **Replace footprints with those specified in netlist** if a package changed, **Delete footprints with no symbols** if
   parts were removed → Update PCB.
3. Existing footprints keep position, rotation and tracks. New parts land in a heap at the cursor: place them.
   Tracks of removed parts, or of pins that changed net, show up in DRC.

If a rewrite changes a part so much that it no longer matches (different symbol *and* different nets), it counts as
removed + new. That's the right answer for a genuinely different part; for a pure rename you can edit the lock entry.

## Custom library bits

- `symbols/supply1.kicad_sym`: AP33772S, LTC7803 (MSOP-16 MSE), LM74800, LMR38010, VOM1271, B0505S-1WR3. It's generated from the pin tables, so don't edit it by hand.
- `footprints/supply1.pretty/L_Coilcraft_SER2918H.kicad_mod`: the main inductor (SER2918H-103 uses the same body). Pad 3 (mounting) is approximate.
- `kicad/supply_power/`, `kicad/supply_control/` and `kicad/supply_ui/supply_ui/`: `fp-lib-table` and `sym-lib-table` pointing at
  the two libraries above. KiCad only reads the tables that sit next to the `.kicad_pro`, so the project files must live in those folders
  (that's what KiCad's New Project dialog creates when "Create a new folder" is ticked).

## Getting to a PCB

1. The KiCad projects exist (`kicad/supply_power`, `kicad/supply_control`, `kicad/supply_ui/supply_ui`).
2. Open the PCB editor → File → Import → Netlist → `out/supply_power.net` / `out/supply_control.net` → Update PCB.
   On the control board, put J971 on the **bottom** side (Flip, default left/right) with its pin 1 directly above J951's pin 2.
3. After schematic changes: re-run the script and re-import. Keep "match footprints by reference" ticked; the refs are stable.

## Watch-outs found while writing it

- skidl reads a pin name like `"P12"` as pin *number* 12 as well. On the TCA9535 that is GND! The UI board addresses expander pins by number for this reason.
- LM74800 exposed pad (RTN) must be left floating (connected to `NC` here) — do not tie it to the GND pour.
- SER2918H pad 3 is mechanical only: keep it off the SW copper.
- The CSD18540Q5B uses KiCad's CSD18532Q5B symbol (same package and pinout); the value field says CSD18540Q5B.
- STM32 PB3 (SWO) is used for PD_SINK_EN: SWD still works, SWO trace doesn't.
