"""
UI board, two ways:
- create_ui_board(): as the front panel defines it - outline, cutouts (wheel drums, on-off button), screw holes, no
  components. The KiCad board gets the same geometry from tools/ui_board_setup.py.
- create_kicad_ui_board(): the KiCad board (kicad/supply_ui, as SAVED): slab from Edge.Cuts plus a simplified body
  per footprint, like the power and control boards (kicad_board.py). The parts that line up with the panel (KiCad
  group "ui_mech") get no body: the panel assembly has the real models of those.

Frame: see UIPanelData (panel frame; the board top surface is at Z = board_z, facing the panel).

    python CAD_3D/ui_board.py          # build, print a summary, show the KiCad board in ocp_vscode
"""

import build123d as bd

from geom_defs import BoardArea, UIPanelData
from kicad_board import BoardModel, load_board_data, place_board
from mech_design import ui_panel

BOARD_COLOR = "#1f6b35"
# KiCad group of the footprints placed from the panel design (tools/ui_board_setup.py)
MECH_GROUP = "ui_mech"


def create_board_area(area: BoardArea) -> bd.Sketch:
    """The area as a face on the XY plane of the panel frame."""
    if area.is_circle:
        face = bd.Circle(area.width / 2)
    elif area.corner_radius > 0:
        face = bd.RectangleRounded(area.width, area.height, area.corner_radius)
    else:
        face = bd.Rectangle(area.width, area.height)
    return bd.Pos(area.x, area.y) * bd.Rot(0, 0, area.rotation) * face


def create_ui_board(data: UIPanelData = ui_panel) -> bd.Part:
    face = create_board_area(data.board_outline)
    for cutout in data.board_cutouts.values():
        face -= create_board_area(cutout)
    for p in data.screw_placements:
        face -= bd.Pos(p.x, p.y) * bd.Circle(data.screw.board_hole_diameter / 2)
    board = bd.Pos(0, 0, data.board_z) * bd.extrude(
        face, data.board_thickness, dir=(0, 0, -1)
    )
    board.label, board.color = "ui_board", bd.Color(BOARD_COLOR)
    return board


def check_kicad_board(data: UIPanelData, board: dict) -> list[str]:
    """What on the saved KiCad board differs from the panel design (empty = in line)."""
    problems = []
    if abs(board["thickness"] - data.board_thickness) > 1e-3:
        problems.append(
            f"thickness {board['thickness']} instead of {data.board_thickness}"
        )
    o = data.board_outline
    want = (o.x - o.width / 2, o.y - o.height / 2, o.x + o.width / 2, o.y + o.height / 2)
    xs = [x for c in board["outlines"] for x, _ in c["outer"]]
    ys = [-y for c in board["outlines"] for _, y in c["outer"]]
    have = (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0,) * 4
    if any(abs(a - b) > 0.01 for a, b in zip(have, want)):
        problems.append(
            "outline X/Y "
            + ", ".join(f"{v:.2f}" for v in have)
            + " instead of "
            + ", ".join(f"{v:.2f}" for v in want)
        )
    holes = sum(len(c["holes"]) for c in board["outlines"])
    if holes != len(data.board_cutouts):
        problems.append(f"{holes} cutouts instead of {len(data.board_cutouts)}")
    placed = [
        (fp["xy"][0], -fp["xy"][1], fp["rot"] % 360)
        for fp in board["footprints"]
        if fp.get("group") == MECH_GROUP
    ]
    for role, p in data.board_footprints.items():
        if not any(
            abs(x - p.x) < 0.01 and abs(y - p.y) < 0.01 and abs(r - p.rotation % 360) < 0.01
            for x, y, r in placed
        ):
            problems.append(f"no footprint at the place of {role}")
    return problems


def create_kicad_ui_board(data: UIPanelData = ui_panel) -> BoardModel:
    board = load_board_data("ui")
    for problem in check_kicad_board(data, board):
        print(
            f"WARNING ui: KiCad board differs from the panel design: {problem} (run tools/run_ui_board_setup.ps1)"
        )
    # KiCad's drill/place origin is the panel origin, the KiCad top side faces the panel
    origin = (0.0, 0.0, data.board_z - data.board_thickness)
    return place_board(
        "ui", board, data.board_thickness, origin, skip_groups=(MECH_GROUP,)
    )


def print_board_summary(board: BoardModel, tallest: int = 5) -> None:
    """Component heights of the KiCad board: what is in the way above and below it."""
    comps = board.components
    by_source = {
        s: sum(c.source == s for c in comps)
        for s in ("model", "fpid", "ref", "fallback", "none")
    }
    print(f"KiCad UI board {len(comps)} footprints with a body, heights from {by_source}")
    for c in comps:
        if c.source == "fallback" and c.shapes:
            print(f"  FALLBACK {c.ref:6} {c.fpid}: {c.height} mm assumed -> add an override")
    for side in ("top", "bottom"):
        parts = [c for c in comps if c.side == side and c.shapes]
        parts.sort(key=lambda c: -c.height)
        if parts:
            listing = ", ".join(f"{c.ref} {c.height:.1f}" for c in parts[:tallest])
            print(f"  tallest {side:6}: {listing}")


def print_summary(data: UIPanelData = ui_panel) -> None:
    d = data
    o = d.board_outline
    print(
        f"UI board       {o.width:.1f} x {o.height:.1f} x {d.board_thickness:.1f}, "
        f"X {o.x - o.width / 2:.1f} .. {o.x + o.width / 2:.1f}, Y {o.y - o.height / 2:.1f} .. {o.y + o.height / 2:.1f}"
    )
    for name, c in d.board_cutouts.items():
        size = (
            f"{c.width:.2f} dia" if c.is_circle else f"{c.width:.2f} x {c.height:.2f}"
        )
        print(
            f"cutout {name:13s} {size} at ({c.x:.2f}, {c.y:.2f}), rotation {c.rotation:.0f}"
        )
    print(
        f"screen gap     {d.screen_gap:.2f} between the board and the screen module pcb"
    )


if __name__ == "__main__":
    from ocp_vscode import show

    print_summary()
    board = create_kicad_ui_board()
    print_board_summary(board)
    show(board.shape)
