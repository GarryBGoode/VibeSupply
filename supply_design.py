"""
USB-C PD bench supply — main board (skidl).

Run:     .venv/Scripts/python supply_design.py
Output:  out/supply_main.net (KiCad netlist -> import into PCB), out/supply_main_bom.csv, out/supply_main_erc.log

Blocks live in design/*.py; the plan and all design numbers are in PLAN.md, calc/results.md, sim/results.md.
The UI board is a separate netlist: ui_design.py.
"""

import csv
from collections import defaultdict
from pathlib import Path

import builtins

from skidl import ERC, KICAD10, Part, generate_netlist

from design import buck, control, housekeeping, mcu, output, power_in, reflock, usb_iso
from design.nets import GND

OUT = Path(__file__).with_name("out")


def mechanical():
    for _ in range(4):
        Part("Mechanical", "MountingHole", value="M3", footprint="MountingHole:MountingHole_3.2mm_M3")
    # heatsink / enclosure ground screw
    h = Part("Mechanical", "MountingHole_Pad", value="GND screw", footprint="MountingHole:MountingHole_3.2mm_M3_Pad_Via")
    h[1] += GND


def build():
    power_in.usb_pd_input(tag="usb_pd_input")
    power_in.dc_input(tag="dc_input")
    power_in.input_sense(tag="input_sense")
    buck.buck(tag="buck")
    control.control(tag="control")
    output.output_stage(tag="output_stage")
    housekeeping.logic_supply(tag="logic_supply")
    housekeeping.aux_supply(tag="aux_supply")
    housekeeping.fan(tag="fan")
    usb_iso.usb_isolated(tag="usb_isolated")
    mcu.mcu(tag="mcu")
    mechanical()


# Reference numbering per block: parts get <prefix><base + n>, e.g. buck resistors R201, R202, ...
# Tags = refs, so KiCad can match footprints across netlist updates, and adding a part to one block
# does not renumber the others.
BLOCK_BASE = {
    "usb_pd_input": 100, "dc_input": 160, "input_sense": 180, "buck": 200, "control": 300,
    "output_stage": 400, "logic_supply": 500, "aux_supply": 540, "fan": 580, "usb_isolated": 600,
    "mcu": 700, "top": 900,
}
BLOCK_ORDER = list(BLOCK_BASE)


def block_of(p):
    names = [h.rstrip("0123456789") for h in p.hiertuple]
    return next((h for h in names if h in BLOCK_BASE), "top")


def num_range(block):
    nxt = BLOCK_ORDER.index(block) + 1
    return BLOCK_BASE[block] + 1, BLOCK_BASE[BLOCK_ORDER[nxt]] if nxt < len(BLOCK_ORDER) else 1000


def seed_refs(parts):
    """The original numbering (code order within each block). Only used when refs.lock.json doesn't exist yet."""
    counters, refs = defaultdict(int), {}
    for p in parts:
        block = block_of(p)
        counters[(block, p.ref_prefix)] += 1
        first, limit = num_range(block)
        num = first - 1 + counters[(block, p.ref_prefix)]
        assert num < limit, f"block {block}: too many {p.ref_prefix} parts for its number range"
        refs[id(p)] = f"{p.ref_prefix}{num}"
    return refs


def assign_refs():
    """Stable refs from refs_main.lock.json (design/reflock.py): existing parts keep their ref across edits,
    new parts get the next free number in their block. Tags = refs, so KiCad's netlist update keeps placement."""
    reflock.assign(list(builtins.default_circuit.parts), block_of, num_range,
                   Path(__file__).with_name("refs_main.lock.json"), seed_refs)


def write_bom(path):
    groups = defaultdict(list)
    for p in builtins.default_circuit.parts:
        key = (p.name, str(p.value), p.footprint, p.fields.get("LCSC", ""), p.fields.get("DNP", ""))
        groups[key].append(p.ref)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Qty", "Refs", "Part", "Value", "Footprint", "LCSC", "DNP"])
        for (name, value, fp, lcsc, dnp), refs in sorted(groups.items(), key=lambda kv: kv[1][0]):
            w.writerow([len(refs), " ".join(sorted(refs)), name, value, fp, lcsc, dnp])


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    build()
    assign_refs()
    ERC()
    generate_netlist(tool=KICAD10, file_=str(OUT / "supply_main.net"))
    write_bom(OUT / "supply_main_bom.csv")
    print(f"parts: {len(builtins.default_circuit.parts)}  nets: {len(builtins.default_circuit.get_nets())}")
