"""
Mechanical export of a KiCad board for the 3D side (CAD_3D/kicad_board.py): board outline, thickness and, per footprint,
reference, footprint id, value, side, position, rotation, F.Fab/B.Fab body outline, courtyard, 3D model entries and drilled
pads -> out/mech_<board>.json.

Normally run automatically by CAD_3D/kicad_board.py when the JSON is older than the .kicad_pcb. By hand:
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/export_mech.py [power] [control]

Read-only on the board file (KiCad may stay open; it exports what is saved).

The JSON is raw KiCad data, no interpretation: mm, relative to the drill/place origin (= board centre, set by
tools/board_setup.py), KiCad orientation (Y down, rotation in degrees counter-clockwise on screen). Outlines, arcs and
circles are flattened to point lists. The conversion to the CAD frame lives in CAD_3D/kicad_board.py.
"""

import json
import math
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
BOARDS = ("power", "control")
tomm = pcbnew.ToMM


def flatten_shape(shape, ox, oy):
    """PCB_SHAPE -> list of (x, y) mm relative to the origin, arcs/circles sampled."""
    rel = lambda v: (round(tomm(v.x) - ox, 4), round(tomm(v.y) - oy, 4))
    kind = shape.SHAPE_T_asString()
    if kind == "S_SEGMENT":
        return [rel(shape.GetStart()), rel(shape.GetEnd())]
    if kind in ("S_RECT", "S_RECTANGLE"):
        return [rel(p) for p in shape.GetRectCorners()]
    if kind == "S_POLYGON":
        poly = shape.GetPolyShape()
        return [rel(poly.Outline(0).CPoint(i)) for i in range(poly.Outline(0).PointCount())] if poly.OutlineCount() else []
    if kind == "S_BEZIER":
        return [rel(p) for p in (shape.GetStart(), shape.GetBezierC1(), shape.GetBezierC2(), shape.GetEnd())]
    if kind in ("S_CIRCLE", "S_ARC"):
        c = shape.GetCenter()
        cx, cy = tomm(c.x) - ox, tomm(c.y) - oy
        r = tomm(shape.GetRadius())
        if kind == "S_CIRCLE":
            a0, sweep = 0.0, 2 * math.pi
        else:
            s = shape.GetStart()
            a0 = math.atan2(tomm(s.y) - oy - cy, tomm(s.x) - ox - cx)
            sweep = math.radians(shape.GetArcAngle().AsDegrees())
        n = max(4, int(abs(sweep) / (math.pi / 8)) + 1)
        return [(round(cx + r * math.cos(a0 + sweep * i / n), 4), round(cy + r * math.sin(a0 + sweep * i / n), 4))
                for i in range(n + 1)]
    return []


def export(name):
    path = ROOT / f"kicad/supply_{name}/supply_{name}.kicad_pcb"
    b = pcbnew.LoadBoard(str(path))
    ds = b.GetDesignSettings()
    origin = ds.GetAuxOrigin()
    ox, oy = tomm(origin.x), tomm(origin.y)
    rel = lambda v: (round(tomm(v.x) - ox, 4), round(tomm(v.y) - oy, 4))

    outlines = []
    ps = pcbnew.SHAPE_POLY_SET()
    if b.GetBoardPolygonOutlines(ps, False):
        for i in range(ps.OutlineCount()):
            outer = ps.Outline(i)
            holes = [ps.Hole(i, h) for h in range(ps.HoleCount(i))]
            outlines.append(dict(outer=[rel(outer.CPoint(k)) for k in range(outer.PointCount())],
                                 holes=[[rel(h.CPoint(k)) for k in range(h.PointCount())] for h in holes]))

    fps = []
    for fp in b.Footprints():
        bottom = fp.IsFlipped()
        fab_layer = pcbnew.B_Fab if bottom else pcbnew.F_Fab
        fab = []
        for item in fp.GraphicalItems():
            if item.GetClass() == "PCB_SHAPE" and item.GetLayer() == fab_layer:
                fab.extend(flatten_shape(item, ox, oy))
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if bottom else pcbnew.F_CrtYd)
        courtyard = [rel(cy.Outline(0).CPoint(i)) for i in range(cy.Outline(0).PointCount())] if cy.OutlineCount() else []
        pads = []
        for p in fp.Pads():
            attr = p.GetAttribute()
            if attr in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                d = p.GetDrillSize()
                pads.append(dict(xy=rel(p.GetPosition()), drill=(round(tomm(d.x), 4), round(tomm(d.y), 4)),
                                 plated=attr == pcbnew.PAD_ATTRIB_PTH))
        attrs = fp.GetAttributes()
        fps.append(dict(
            ref=fp.GetReference(),
            fpid=fp.GetFPIDAsString(),
            value=fp.GetValue(),
            lcsc=next((f.GetText() for f in fp.GetFields() if f.GetName() == "LCSC"), ""),
            side="bottom" if bottom else "top",
            xy=rel(fp.GetPosition()),
            rot=round(fp.GetOrientationDegrees(), 4),
            mount="tht" if attrs & pcbnew.FP_THROUGH_HOLE else "smd" if attrs & pcbnew.FP_SMD else "other",
            fab=fab,
            courtyard=courtyard,
            models=[dict(file=m.m_Filename, show=m.m_Show,
                         offset=(m.m_Offset.x, m.m_Offset.y, m.m_Offset.z),
                         rotation=(m.m_Rotation.x, m.m_Rotation.y, m.m_Rotation.z),
                         scale=(m.m_Scale.x, m.m_Scale.y, m.m_Scale.z)) for m in fp.Models()],
            pads=pads,
        ))
    fps.sort(key=lambda f: f["ref"])

    data = dict(board=name, source=str(path.relative_to(ROOT)).replace("\\", "/"),
                thickness=round(tomm(ds.GetBoardThickness()), 4), outlines=outlines, footprints=fps)
    out = ROOT / f"out/mech_{name}.json"
    out.write_text(json.dumps(data, indent=1))
    print(f"{name}: {len(fps)} footprints -> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    for n in sys.argv[1:] or BOARDS:
        if n not in BOARDS:
            sys.exit(f"unknown board {n!r}, expected one of {BOARDS}")
        export(n)
