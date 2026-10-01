"""
Shared finishing steps for the power and control board scripts: per-block reference numbers (locked, see reflock.py),
ERC, netlist and BOM.
"""

import builtins
import csv
from collections import defaultdict
from pathlib import Path

from skidl import ERC, KICAD10, generate_netlist

from . import reflock

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"

# Reference numbering per block: parts get <prefix><base + n>, e.g. buck resistors R201, R202, ...
# One table for both boards, so a ref is unique across the whole supply (the blocks don't overlap between boards).
# Tags = refs, so KiCad can match footprints across netlist updates, and adding a part to one block
# does not renumber the others.
BLOCK_BASE = {
    "usb_pd_input": 100, "dc_input": 160, "input_sense": 180, "buck": 200, "control": 300,
    "output_stage": 400, "logic_supply": 500, "logic_feed": 530, "aux_supply": 540, "fan": 580,
    "usb_isolated": 600, "mcu": 700, "top": 900, "b2b_power": 950, "b2b_control": 970,
}
# "fan" (580) has no parts since 2026-09-28; the entry stays so the 5xx/6xx ranges don't move.
# Power board: usb_pd_input .. output_stage, logic_feed, aux_supply, top, b2b_power.
# Control board: logic_supply, usb_isolated, mcu, b2b_control.
BLOCK_ORDER = list(BLOCK_BASE)


def block_of(p):
    names = [h.rstrip("0123456789") for h in p.hiertuple]
    return next((h for h in names if h in BLOCK_BASE), "top")


def num_range(block):
    nxt = BLOCK_ORDER.index(block) + 1
    return BLOCK_BASE[block] + 1, BLOCK_BASE[BLOCK_ORDER[nxt]] if nxt < len(BLOCK_ORDER) else 1000


def seed_refs(parts):
    """The original numbering (code order within each block). Only used when the lock file doesn't exist yet."""
    counters, refs = defaultdict(int), {}
    for p in parts:
        block = block_of(p)
        counters[(block, p.ref_prefix)] += 1
        first, limit = num_range(block)
        num = first - 1 + counters[(block, p.ref_prefix)]
        assert num < limit, f"block {block}: too many {p.ref_prefix} parts for its number range"
        refs[id(p)] = f"{p.ref_prefix}{num}"
    return refs


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


def assign_refs(board):
    """Locked refs (refs_<power|control>.lock.json), then drop the shared nets from design/nets.py that have nothing
    attached on this board (e.g. the UI-only ENCx_SW)."""
    lock = ROOT / f"refs_{board.removeprefix('supply_')}.lock.json"
    reflock.assign(list(builtins.default_circuit.parts), block_of, num_range, lock, seed_refs)
    empty = [n for n in builtins.default_circuit.nets if not n.pins and n is not builtins.NC]
    builtins.default_circuit.rmv_nets(*empty)


def finish(board):
    """board = "supply_power" / "supply_control": refs, ERC, out/<board>.net and out/<board>_bom.csv."""
    OUT.mkdir(exist_ok=True)
    assign_refs(board)
    ERC()
    generate_netlist(tool=KICAD10, file_=str(OUT / f"{board}.net"))
    write_bom(OUT / f"{board}_bom.csv")
    print(f"{board}: parts: {len(builtins.default_circuit.parts)}  nets: {len(builtins.default_circuit.get_nets())}")
