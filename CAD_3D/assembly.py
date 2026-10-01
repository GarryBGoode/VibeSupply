"""
Enclosure + supply_power + supply_control, everything in the enclosure frame (see mech_design.py).

    python CAD_3D/assembly.py          # build, print a summary, show in ocp_vscode
"""

from dataclasses import dataclass

import build123d as bd

from enclosure import create_enclosure
from kicad_board import BoardModel, create_board
from mech_design import (
    enclosure_aluminum,
    pcb_placement_control,
    pcb_placement_power,
    pcb_size_control,
    pcb_size_power,
)

ENCLOSURE_COLOR = bd.Color(0.75, 0.77, 0.80, 0.35)


@dataclass
class Assembly:
    shape: bd.Compound
    enclosure: bd.Part
    power: BoardModel
    control: BoardModel


def create_assembly() -> Assembly:
    enclosure = create_enclosure(enclosure_aluminum)
    enclosure.label = "enclosure"
    enclosure.color = ENCLOSURE_COLOR
    power = create_board("power", pcb_size_power, pcb_placement_power, enclosure_aluminum)
    control = create_board("control", pcb_size_control, pcb_placement_control, enclosure_aluminum)
    shape = bd.Compound(label="supply1", children=[enclosure, power.shape, control.shape])
    return Assembly(shape, enclosure, power, control)


def print_summary(asm: Assembly, tallest: int = 6) -> None:
    floor = -enclosure_aluminum.inside_height / 2
    for board in (asm.power, asm.control):
        comps = board.components
        by_source = {s: sum(c.source == s for c in comps) for s in ("model", "fpid", "ref", "fallback", "none")}
        print(f"\nsupply_{board.name}: {len(comps)} footprints, heights from {by_source}, "
              f"bottom face {board.origin[2] - floor:.2f} mm above the floor")
        for c in comps:
            if c.source == "fallback" and c.shapes:
                print(f"  FALLBACK {c.ref:6} {c.fpid}: {c.height} mm assumed -> add an override")
            if c.estimate:
                print(f"  ESTIMATE {c.ref:6} {c.height} mm ({c.note})")
        for side in ("top", "bottom"):
            parts = [c for c in comps if c.side == side and c.shapes]
            parts.sort(key=lambda c: -c.height)
            listing = ", ".join(f"{c.ref} {c.height:.1f}" for c in parts[:tallest])
            if parts:
                print(f"  tallest {side:6}: {listing}")


if __name__ == "__main__":
    asm = create_assembly()
    print_summary(asm)
    from ocp_vscode import show

    show(asm.shape)
