"""
Placement snapshot: draws a board's footprints (courtyards, pads, references), the floor-plan frames and the rule areas
into a PNG, coloured by placement cluster (group). For reviewing placement without opening KiCad.

    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/snapshot.py [power] [control] [ui]   -> out/placement_<board>.png
"""

import colorsys
import sys
import zlib
from pathlib import Path

import pcbnew
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
S = 9.0      # px per mm
M = 40       # margin px
tomm = pcbnew.ToMM
FONT = "C:/Windows/Fonts/arial.ttf"


def font(px):
    try:
        return ImageFont.truetype(FONT, max(7, int(px)))
    except OSError:
        return ImageFont.load_default()


def colour(name, light=0.82):
    h = (zlib.crc32(name.encode()) % 360) / 360
    r, g, b = colorsys.hls_to_rgb(h, light, 0.55)
    return int(r * 255), int(g * 255), int(b * 255)


def board_path(name):
    d = ROOT / f"kicad/supply_{name}"
    path = d / f"supply_{name}.kicad_pcb"
    return path if path.exists() else d / f"supply_{name}" / path.name  # supply_ui has its project one level down


def snapshot(name):
    b = pcbnew.LoadBoard(str(board_path(name)))
    xs, ys = [], []
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            for p in (d.GetStart(), d.GetEnd()):
                xs.append(tomm(p.x))
                ys.append(tomm(p.y))
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    W, H = int((x1 - x0) * S) + 2 * M, int((y1 - y0) * S) + 2 * M + 30
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img, "RGBA")

    def P(x, y):  # sheet mm -> px
        return M + (x - x0) * S, M + (y - y0) * S

    def poly_pts(shape_poly):
        pts = []
        for i in range(shape_poly.OutlineCount()):
            o = shape_poly.Outline(i)
            pts.append([P(tomm(o.CPoint(j).x), tomm(o.CPoint(j).y)) for j in range(o.PointCount())])
        return pts

    # board (with its cutouts) + rule areas
    ps = pcbnew.SHAPE_POLY_SET()
    if b.GetBoardPolygonOutlines(ps, False) and ps.OutlineCount():
        for i in range(ps.OutlineCount()):
            chain = lambda c: [P(tomm(c.CPoint(j).x), tomm(c.CPoint(j).y)) for j in range(c.PointCount())]  # noqa: E731
            dr.polygon(chain(ps.Outline(i)), fill=(246, 246, 240), outline="black", width=2)
            for h in range(ps.HoleCount(i)):
                dr.polygon(chain(ps.Hole(i, h)), fill="white", outline="black", width=2)
    else:
        dr.rectangle([P(x0, y0), P(x1, y1)], fill=(246, 246, 240), outline="black", width=2)
    for z in b.Zones():
        if z.GetIsRuleArea():
            for pts in poly_pts(z.Outline()):
                fill = (255, 80, 80, 45) if "tall" in z.GetZoneName() else (150, 150, 150, 70)
                dr.polygon(pts, fill=fill, outline=(150, 60, 60) if "tall" in z.GetZoneName() else None)
    # frames / notes on User.Comments
    for d in b.GetDrawings():
        if d.GetLayer() == pcbnew.Cmts_User:
            if d.GetClass() == "PCB_SHAPE":
                dr.line([P(tomm(d.GetStart().x), tomm(d.GetStart().y)), P(tomm(d.GetEnd().x), tomm(d.GetEnd().y))],
                        fill=(90, 90, 160), width=1 if tomm(d.GetWidth()) < 0.2 else 3)
            elif d.GetClass() == "PCB_TEXT":
                p = d.GetPosition()
                dr.text(P(tomm(p.x), tomm(p.y)), d.GetText(), fill=(60, 60, 150), font=font(1.0 * S))
    # footprints: bottom side first (outlined), then top
    fps = sorted(b.GetFootprints(), key=lambda f: not f.IsFlipped())
    for f in fps:
        f.BuildCourtyardCaches()
        bottom = f.IsFlipped()
        cy = f.GetCourtyard(pcbnew.B_CrtYd if bottom else pcbnew.F_CrtYd)
        g = f.GetParentGroup()
        gname = g.GetName() if g else ""
        fill = colour(gname) if gname.startswith("place:") else (225, 225, 225)
        if bottom:
            for pts in poly_pts(cy):
                dr.polygon(pts, fill=(255, 170, 60, 60), outline=(220, 110, 0))
        else:
            for pts in poly_pts(cy):
                dr.polygon(pts, fill=fill + (230,), outline=(70, 70, 70))
        for p in f.Pads():
            bb = p.GetBoundingBox()
            c = (190, 140, 40) if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else (180, 60, 60)
            if bottom and p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                continue
            dr.rectangle([P(tomm(bb.GetLeft()), tomm(bb.GetTop())), P(tomm(bb.GetRight()), tomm(bb.GetBottom()))],
                         fill=c + (150,))
    for f in fps:
        cy = f.GetCourtyard(pcbnew.B_CrtYd if f.IsFlipped() else pcbnew.F_CrtYd)
        bb = cy.BBox() if cy.OutlineCount() else f.GetBoundingBox(False)
        w, h = tomm(bb.GetWidth()), tomm(bb.GetHeight())
        ref = f.GetReference()
        size = max(7, min(1.4 * S, 0.9 * min(w, h) * S, 1.6 * w * S / max(len(ref), 1)))
        c = P(tomm(bb.GetCenter().x), tomm(bb.GetCenter().y))
        dr.text(c, ref, fill=(150, 70, 0) if f.IsFlipped() else (0, 0, 0), font=font(size), anchor="mm")
    dr.text((M, H - 28), f"supply_{name}: grey = top courtyards (coloured by cluster group), orange = bottom side, "
            f"red hatch = tall power-board parts below; 1 mm = {S:.0f} px", fill="black", font=font(14))
    out = ROOT / f"out/placement_{name}.png"
    img.save(out)
    print(out)


if __name__ == "__main__":
    for n in sys.argv[1:] or ["power", "control"]:
        snapshot(n)
