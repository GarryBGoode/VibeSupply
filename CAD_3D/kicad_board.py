"""
KiCad board -> build123d: the board slab (Edge.Cuts outline, drilled holes) plus a simplified body per footprint
(electronic_components.py), placed in the enclosure.

The board data comes from out/mech_<board>.json; it is re-exported with KiCad's Python (tools/export_mech.py)
whenever it is older than the .kicad_pcb or the exporter. Only the SAVED board is seen.
"""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import build123d as bd

from electronic_components import LEAD_MAX_DRILL, ComponentInfo, create_component
from geom_defs import EnclosureData, PCBPlacement, PCBSizeData

ROOT = Path(__file__).resolve().parents[1]
KICAD_BIN = Path("C:/Program Files/KiCad/10.0/bin")
EXPORTER = ROOT / "tools/export_mech.py"
BOARD_COLOR = "#1f6b35"


@dataclass
class BoardModel:
    name: str
    shape: bd.Compound  # slab + components, enclosure frame
    slab: bd.Part
    components: list[ComponentInfo]
    origin: tuple[float, float, float]  # board frame origin (centre, bottom face) in the enclosure frame


def load_board_data(name: str) -> dict:
    pcb = ROOT / f"kicad/supply_{name}/supply_{name}.kicad_pcb"
    out = ROOT / f"out/mech_{name}.json"
    if not out.exists() or out.stat().st_mtime < max(pcb.stat().st_mtime, EXPORTER.stat().st_mtime):
        # pcbnew needs KiCad's bin dir on PATH and no venv Python settings
        env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
        env["PATH"] = f"{KICAD_BIN}{os.pathsep}{env.get('PATH', '')}"
        r = subprocess.run([str(KICAD_BIN / "python.exe"), str(EXPORTER), name], cwd=ROOT, env=env,
                           capture_output=True, text=True)
        if r.returncode:
            raise RuntimeError(f"{EXPORTER.name} {name} failed:\n{r.stdout}\n{r.stderr}")
    return json.loads(out.read_text())


def create_board_slab(data: dict, thickness: float) -> bd.Part:
    """Board slab in the board frame: Edge.Cuts outline (KiCad Y flipped), extruded from Z=0 to Z=thickness, with the
    drilled holes that are not component leads (mounting holes, NPTH)."""
    face = None
    for outline in data["outlines"]:
        f = bd.Polygon(*[(x, -y) for x, y in outline["outer"]], align=None)
        for hole in outline["holes"]:
            f -= bd.Polygon(*[(x, -y) for x, y in hole], align=None)
        face = f if face is None else face + f
    for fp in data["footprints"]:
        for pad in fp["pads"]:
            d = min(pad["drill"])
            if not pad["plated"] or d >= LEAD_MAX_DRILL or fp["mount"] != "tht":
                face -= bd.Pos(pad["xy"][0], -pad["xy"][1]) * bd.Circle(d / 2)
    # explicit direction: the Y flip reverses the outline winding, so the face normal may point down
    slab = bd.extrude(face, thickness, dir=(0, 0, 1))
    slab.color = bd.Color(BOARD_COLOR)
    return slab


def create_board(name: str, pcb: PCBSizeData, placement: PCBPlacement, enclosure: EnclosureData) -> BoardModel:
    data = load_board_data(name)
    if abs(data["thickness"] - pcb.thickness) > 1e-3:
        print(f"WARNING {name}: KiCad stackup thickness {data['thickness']} != mech_design {pcb.thickness}")
    xs = [x for o in data["outlines"] for x, _ in o["outer"]]
    ys = [y for o in data["outlines"] for _, y in o["outer"]]
    if abs(max(xs) - min(xs) - pcb.length) > 0.01 or abs(max(ys) - min(ys) - pcb.width) > 0.01:
        print(f"WARNING {name}: KiCad outline {max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} != mech_design "
              f"{pcb.length} x {pcb.width} (run tools/run_board_setup.ps1)")

    origin = placement.origin(enclosure, pcb)
    loc = bd.Pos(*origin)
    slab = loc * create_board_slab(data, pcb.thickness)
    slab.label = "pcb"
    slab.color = bd.Color(BOARD_COLOR)
    components, children = [], [slab]
    for fp in data["footprints"]:
        info = create_component(fp, pcb.thickness)
        placed = []
        for s in info.shapes:
            moved = loc * s
            moved.label, moved.color = s.label, s.color
            placed.append(moved)
        info.shapes = placed
        components.append(info)
        if len(placed) == 1:
            children.append(placed[0])
        elif placed:
            children.append(bd.Compound(label=info.ref, children=placed))
    shape = bd.Compound(label=f"supply_{name}", children=children)
    return BoardModel(name, shape, slab, components, origin)


if __name__ == "__main__":
    from ocp_vscode import show

    from mech_design import enclosure_aluminum, pcb_placement_power, pcb_size_power

    board = create_board("power", pcb_size_power, pcb_placement_power, enclosure_aluminum)
    show(board.shape)
