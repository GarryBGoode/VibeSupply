"""
UI board screw + heat-set insert + boss - the screw goes in from behind the board, into the insert in the boss.

Frame: see BoardScrewData (origin on the board top surface on the screw axis, Z up towards the panel).

    python CAD_3D/board_screw.py          # build, print a summary, show in ocp_vscode
"""

from dataclasses import dataclass

import build123d as bd
from bd_warehouse.fastener import HeatSetNut, PanHeadScrew

from geom_defs import BoardScrewData

BOSS_COLOR = "#6080a0"
CUTTER_COLOR = bd.Color(0.9, 0.2, 0.2, 0.25)

BOARD_SCREW = BoardScrewData()

_Z_MIN = (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)


@dataclass
class BoardScrew:
    """Everything in the screw frame.
    The boss is to be joined to the panel, the cutter (the hole for the insert and the screw tip) is to be
    subtracted from it.
    """

    data: BoardScrewData
    screw: bd.Part
    insert: bd.Part
    boss: bd.Part
    cutter: bd.Part
    hole_depth: float  # of the cutter, from the end of the boss

    @property
    def shape(self) -> bd.Compound:
        """The physical parts, for display and interference checks (no cutter)."""
        return bd.Compound(
            label="board_screw", children=[self.screw, self.insert, self.boss]
        )


def create_board_screw(data: BoardScrewData = BOARD_SCREW) -> BoardScrew:
    # bd_warehouse: screw origin under the head, thread towards -Z -> head under the board, thread towards +Z
    screw = PanHeadScrew(
        size=data.size,
        length=data.length,
        fastener_type=data.fastener_type,
        simple=True,
    )
    color = screw.color
    screw = bd.Pos(0, 0, -data.board_thickness) * bd.Rot(180, 0, 0) * screw
    screw.label, screw.color = "screw", color

    # bd_warehouse: insert from Z = 0 up -> flush with the end of the boss
    insert = HeatSetNut(
        size=data.insert_size, fastener_type=data.insert_type, simple=True
    )
    insert_length = insert.nut_thickness
    insert.label = "insert"

    screw_depth = data.length - data.board_thickness
    hole_depth = max(insert_length, screw_depth) + data.hole_margin
    cutter = bd.Cylinder(data.insert_hole_diameter / 2, hole_depth, align=_Z_MIN)
    cutter.label, cutter.color = "cutter", CUTTER_COLOR

    boss = bd.Cylinder(data.boss_diameter / 2, data.boss_height, align=_Z_MIN) - cutter
    boss.label, boss.color = "boss", bd.Color(BOSS_COLOR)

    return BoardScrew(data, screw, insert, boss, cutter, hole_depth)


def print_summary(asm: BoardScrew) -> None:
    d = asm.data
    print(
        f"screw          {d.size} x {d.length:.0f}, {d.length - d.board_thickness:.2f} into the boss"
    )
    print(
        f"insert         {d.insert_size} ({d.insert_type}), {asm.insert.nut_diameter:.2f} dia x "
        f"{asm.insert.nut_thickness:.2f} long"
    )
    print(
        f"boss           {d.boss_diameter:.2f} dia x {d.boss_height:.2f}, "
        f"hole {d.insert_hole_diameter:.2f} dia x {asm.hole_depth:.2f} deep"
    )


if __name__ == "__main__":
    from ocp_vscode import show

    asm = create_board_screw()
    print_summary(asm)
    show(asm.shape)
