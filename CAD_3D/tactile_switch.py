"""
Omron B3F 6 x 6 mm THT tactile switch - simplified body for placement and interference checks.

Frame: see TactileSwitchB3FData (pin 1 on the board top surface, footprint axes, Z up, plunger axis at the body centre).
"""

import build123d as bd
from geom_defs import TactileSwitchB3FData

BODY_COLOR = "#202020"
METAL_COLOR = "#c0c0c0"
PLUNGER_COLOR = "#d040a0"  # B3F-1020 plunger is pink

B3F_1020 = TactileSwitchB3FData()  # 5.0 mm, 0.98 N


def _y_extrude(face: bd.Sketch, y0: float, y1: float) -> bd.Part:
    """Extrude an XZ-plane sketch (local x = X, local y = Z) between Y = y0 and Y = y1."""
    return bd.Pos(0, max(y0, y1), 0) * bd.extrude(bd.Plane.XZ * face, amount=abs(y1 - y0))


def _box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> bd.Part:
    return bd.Pos(x0, y0, z0) * bd.Box(x1 - x0, y1 - y0, z1 - z0, align=bd.Align.MIN)


def create_tactile_switch_b3f(data: TactileSwitchB3FData = B3F_1020) -> bd.Compound:
    """Switch as an assembly of labelled parts (housing, cover, plunger, 4 leads) in the switch frame."""
    d = data
    cx, cy = d.center_xy
    half = d.body_size / 2
    cover_z = d.body_height - d.cover_thickness

    housing = _box(cx - half, cx + half, cy - half, cy + half, 0, cover_z)
    housing.label, housing.color = "housing", bd.Color(BODY_COLOR)

    cover = _box(cx - half, cx + half, cy - half, cy + half, cover_z, d.body_height)
    s = d.stake_pitch / 2
    for sx in (-1, 1):
        for sy in (-1, 1):
            cover += bd.Pos(cx + sx * s, cy + sy * s, d.body_height) * bd.Cylinder(
                d.stake_dia / 2, d.stake_height, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
            )
    cover.label, cover.color = "cover", bd.Color(METAL_COLOR)

    plunger = bd.Pos(cx, cy, d.body_height) * bd.Cylinder(
        d.plunger_dia / 2, d.height - d.body_height, align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
    )
    plunger.label, plunger.color = "plunger", bd.Color(PLUNGER_COLOR)

    # --- leads: centre line in XZ for the +X side, relative to the body centre, mirrored for -X ---
    t, w = d.lead_section
    knee_x = d.lead_knee_span / 2 - t / 2
    tip_x = d.pin_pitch_x / 2
    path = [
        (half - 0.4, d.lead_exit_height),  # anchored inside the housing
        (half + 0.3, d.lead_exit_height),
        (knee_x, d.lead_knee_z),
        (tip_x, d.lead_jog_z),
        (tip_x, -d.lead_length),
    ]
    leads = []
    for x, y in d.pin_xy:
        sx = 1 if x > cx else -1
        line = bd.Polyline(*[(cx + sx * px, pz) for px, pz in path])
        leads.append(_y_extrude(bd.trace(line, line_width=t), y - w / 2, y + w / 2))
    for part, name in zip(leads, ("pin_1a", "pin_1b", "pin_2a", "pin_2b")):
        part.label, part.color = name, bd.Color(METAL_COLOR)

    return bd.Compound(label="B3F", children=[housing, cover, plunger, *leads])


def create_tactile_switch_b3f_keepout(data: TactileSwitchB3FData = B3F_1020) -> bd.Part:
    """Boundary box of the switch incl. leads, for quick interference checks."""
    (x0, y0, z0), (x1, y1, z1) = data.bbox_min, data.bbox_max
    return _box(x0, x1, y0, y1, z0, z1)


if __name__ == "__main__":
    from ocp_vscode import show

    sw = create_tactile_switch_b3f()
    bb = sw.bounding_box()
    print(f"bbox min {bb.min}  max {bb.max}")
    print(f"dataclass bbox {B3F_1020.bbox_min} .. {B3F_1020.bbox_max}")
    show(sw)
