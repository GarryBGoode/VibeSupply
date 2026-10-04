"""
Alps EC10E hollow-shaft encoder (horizontal) - simplified body for placement and interference checks.

Frame: see EncoderEC10EData (pin B on the board top surface, footprint axes, Z up, shaft axis along Y at Z = H).
"""

import build123d as bd
from geom_defs import EncoderEC10EData

BODY_COLOR = "#303030"
METAL_COLOR = "#c0c0c0"
ROTOR_COLOR = "#f0f0f0"

EC10E1220505 = EncoderEC10EData()  # H = 7 mm


def _y_extrude(face: bd.Sketch, y0: float, y1: float) -> bd.Part:
    """Extrude an XZ-plane sketch (local x = X, local y = Z) between Y = y0 and Y = y1."""
    return bd.Pos(0, max(y0, y1), 0) * bd.extrude(bd.Plane.XZ * face, amount=abs(y1 - y0))


def _box(x0: float, x1: float, y0: float, y1: float, z0: float, z1: float) -> bd.Part:
    return bd.Pos(x0, y0, z0) * bd.Box(x1 - x0, y1 - y0, z1 - z0, align=bd.Align.MIN)


def create_encoder_ec10e(data: EncoderEC10EData = EC10E1220505) -> bd.Compound:
    """Encoder as an assembly of labelled parts (body, rotor, pins, legs) in the encoder frame."""
    d = data
    h = d.mount_height
    half_w = d.body_width / 2
    rotor_clearance = d.rotor_dia / 2 + 0.1

    # --- body: front-view profile through the core + front plate, foot tapering into it ---
    arch_z = h + d.top_above_axis - d.arch_radius
    profile = bd.Pos(0, (d.base_height + h + d.shoulder_above_axis) / 2) * bd.Rectangle(
        d.body_width, h + d.shoulder_above_axis - d.base_height
    )
    profile += bd.Pos(0, arch_z) * bd.Circle(d.arch_radius)
    profile -= bd.Pos(0, h) * bd.Circle(rotor_clearance)
    body = _y_extrude(profile, d.body_rear_y, d.body_front_y)

    foot = _box(-d.base_width / 2, d.base_width / 2, d.base_front_y, d.base_rear_y, 0, d.base_height)
    taper_top = d.terminal_block_top if d.terminal_block_top > d.base_height else d.base_height + 0.5
    taper = bd.loft(
        [
            bd.Plane.XY.offset(d.base_height)
            * bd.Pos(0, (d.base_rear_y + d.base_front_y) / 2)
            * bd.Rectangle(d.base_width, d.base_rear_y - d.base_front_y),
            bd.Plane.XY.offset(taper_top)
            * bd.Pos(0, (d.body_rear_y + d.body_front_y) / 2)
            * bd.Rectangle(d.base_width, d.body_rear_y - d.body_front_y),
        ]
    )
    body += foot + taper

    # bracket clips at axis height, protruding past the frame sides
    for sx in (-1, 1):
        x_in, x_out = sx * half_w, sx * (half_w + d.clip_protrusion)
        body += _box(min(x_in, x_out), max(x_in, x_out), d.body_front_y, d.face_f_y + 1.2, h - 0.6, h + 0.6)

    boss = bd.Circle(d.boss_dia / 2) - bd.Circle(rotor_clearance)
    body += _y_extrude(bd.Pos(0, h) * boss, d.boss_rear_y, d.body_rear_y)
    body.label, body.color = "body", bd.Color(BODY_COLOR)

    # --- rotor: hex bore from face F (-Y), round bore at the rear ---
    rotor = _y_extrude(bd.Pos(0, h) * bd.Circle(d.rotor_dia / 2), d.boss_rear_y, d.face_f_y)
    hex_bore = bd.Pos(0, h) * bd.RegularPolygon(d.hex_across_flats / 2, 6, major_radius=False)
    rotor -= _y_extrude(hex_bore, d.face_f_y - 1, d.boss_rear_y + 1)
    rear_bore = bd.Pos(0, h) * bd.Circle(d.rear_bore_dia / 2)
    rotor -= _y_extrude(rear_bore, d.face_f_y + d.hex_end_depth, d.boss_rear_y + 1)
    rotor.label, rotor.color = "rotor", bd.Color(ROTOR_COLOR)

    # --- leads ---
    px, py = d.pin_section
    pins = [
        _box(x - px / 2, x + px / 2, -py / 2, py / 2, -d.lead_length, d.base_height) for x in d.pin_x
    ]
    lx, ly = d.leg_section
    legs = [
        _box(x - lx / 2, x + lx / 2, y - ly / 2, y + ly / 2, -d.lead_length, taper_top)
        for x, y in d.bracket_xy
    ]
    for part, name in zip(pins + legs, ("pin_A", "pin_B", "pin_C", "leg_L", "leg_R")):
        part.label, part.color = name, bd.Color(METAL_COLOR)

    return bd.Compound(label="EC10E", children=[body, rotor, *pins, *legs])


def create_encoder_ec10e_keepout(data: EncoderEC10EData = EC10E1220505) -> bd.Part:
    """Boundary box of the encoder incl. leads, for quick interference checks."""
    (x0, y0, z0), (x1, y1, z1) = data.bbox_min, data.bbox_max
    return _box(x0, x1, y0, y1, z0, z1)


if __name__ == "__main__":
    from ocp_vscode import show

    enc = create_encoder_ec10e()
    bb = enc.bounding_box()
    print(f"bbox min {bb.min}  max {bb.max}")
    print(f"dataclass bbox {EncoderEC10EData().bbox_min} .. {EncoderEC10EData().bbox_max}")
    show(enc)
