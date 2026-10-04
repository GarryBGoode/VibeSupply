"""
12 mm panel-mount illuminated push button (power button) - simplified body for placement and interference checks,
and the cutter for its panel hole.

Frame: see PowerButtonData (origin on the button axis on the panel front face, Z out towards the user).

    python CAD_3D/powerbutton.py          # build, print a summary, show in ocp_vscode
"""

import build123d as bd
from bd_warehouse.thread import IsoThread

from geom_defs import PowerButtonData

METAL_COLOR = "#c0c0c0"
BODY_COLOR = "#3080c0"
SEAL_COLOR = "#202020"
RING_COLOR = bd.Color(0.9, 0.1, 0.1, 0.8)

# cutter reach either side of the panel
CUTTER_MARGIN = 1

POWER_BUTTON = PowerButtonData()

_Z_MIN = (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN)
_Z_MAX = (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MAX)


def _ring(outer_diameter: float, inner_diameter: float, height: float) -> bd.Part:
    """From Z = 0 up."""
    return bd.Cylinder(outer_diameter / 2, height, align=_Z_MIN) - bd.Cylinder(
        inner_diameter / 2, height, align=_Z_MIN
    )


def _create_housing(d: PowerButtonData, simple: bool) -> bd.Part:
    """Metal housing: the head with the pocket for the button, and the threaded barrel."""
    chamfer_r, chamfer_z = d.head_chamfer
    radius = d.head_diameter / 2
    rim_height = d.head_height - chamfer_z

    head = bd.Cylinder(radius, rim_height, align=_Z_MIN)
    head += bd.Pos(0, 0, rim_height) * bd.Cone(
        radius, radius - chamfer_r, chamfer_z, align=_Z_MIN
    )
    head -= bd.Cylinder(d.button_diameter / 2, d.head_height, align=_Z_MIN)
    housing = bd.Pos(0, 0, d.head_bottom_z) * head

    if simple:
        barrel = bd.Cylinder(d.thread_diameter / 2, d.thread_length, align=_Z_MAX)
    else:
        # bd_warehouse: thread from Z = 0 up, to be fused with a core of its root radius
        thread = IsoThread(
            major_diameter=d.thread_diameter,
            pitch=d.thread_pitch,
            length=d.thread_length,
            external=True,
            end_finishes=("fade", "fade"),
        )
        barrel = bd.Cylinder(thread.min_radius, d.thread_length, align=_Z_MAX)
        barrel += bd.Pos(0, 0, -d.thread_length) * thread
    return housing + bd.Pos(0, 0, d.head_bottom_z) * barrel


def _create_nut(d: PowerButtonData) -> bd.Part:
    """Hexagon with two corners on X, the corners turned off to nut_across_corners."""
    hexagon = bd.RegularPolygon(d.nut_across_flats / 2, 6, major_radius=False)
    nut = bd.extrude(hexagon, amount=d.nut_thickness)
    nut &= bd.Cylinder(d.nut_across_corners / 2, d.nut_thickness, align=_Z_MIN)
    nut -= bd.Cylinder(d.thread_diameter / 2, d.nut_thickness, align=_Z_MIN)
    return bd.Pos(0, 0, d.nut_bottom_z) * nut


def _create_terminal(d: PowerButtonData) -> bd.Part:
    """Solder lug hanging down from the origin, flat faces towards Y."""
    hole_width, hole_length = d.terminal_hole
    profile = bd.Rectangle(
        d.terminal_width, d.terminal_length, align=(bd.Align.CENTER, bd.Align.MAX)
    )
    profile = bd.chamfer(
        profile.vertices().group_by(bd.Axis.Y)[0], d.terminal_tip_chamfer
    )
    profile -= bd.Pos(0, -d.terminal_hole_offset) * bd.SlotOverall(
        hole_length, hole_width, rotation=90
    )
    return bd.extrude(
        bd.Plane.XZ * profile, amount=d.terminal_thickness / 2, both=True
    )


def create_powerbutton(
    data: PowerButtonData = POWER_BUTTON, simple: bool = True
) -> bd.Compound:
    """Button as an assembly of labelled parts (housing, seal, button, ring, nut, body, 4 terminals) in the button
    frame. simple=False generates the thread on the housing, which takes a while."""
    d = data

    housing = _create_housing(d, simple)
    housing.label, housing.color = "housing", bd.Color(METAL_COLOR)

    seal = _ring(d.seal_diameter, d.thread_diameter, d.seal_thickness)
    seal.label, seal.color = "seal", bd.Color(SEAL_COLOR)

    # button and ring fill the pocket in the head
    cap_diameter = d.button_diameter - 2 * d.ring_width
    cap_height = d.button_top_z - d.head_bottom_z
    button = bd.Pos(0, 0, d.head_bottom_z) * bd.Cylinder(
        cap_diameter / 2, cap_height, align=_Z_MIN
    )
    button.label, button.color = "button", bd.Color(METAL_COLOR)
    ring = bd.Pos(0, 0, d.head_bottom_z) * _ring(
        d.button_diameter, cap_diameter, cap_height
    )
    ring.label, ring.color = "ring", RING_COLOR

    nut = _create_nut(d)
    nut.label, nut.color = "nut", bd.Color(METAL_COLOR)

    body = bd.Cylinder(d.collar_diameter / 2, d.collar_height, align=_Z_MAX)
    body += bd.Cylinder(d.body_diameter / 2, d.body_length, align=_Z_MAX)
    body = bd.Pos(0, 0, d.thread_end_z) * body
    body.label, body.color = "body", bd.Color(BODY_COLOR)

    # the X pair faces the axis with its flat sides, like the Y pair
    terminal = _create_terminal(d)
    terminals = []
    names = ("terminal_x1", "terminal_x2", "terminal_y1", "terminal_y2")
    for (x, y), name in zip(d.terminal_xy, names):
        rotation = 90 if y == 0 else 0
        part = bd.Pos(x, y, d.body_bottom_z) * bd.Rot(0, 0, rotation) * terminal
        part.label, part.color = name, bd.Color(METAL_COLOR)
        terminals.append(part)

    return bd.Compound(
        label="power_button",
        children=[housing, seal, button, ring, nut, body, *terminals],
    )


def create_powerbutton_cutter(data: PowerButtonData = POWER_BUTTON) -> bd.Part:
    """To be subtracted from the panel: the borehole, through panel_thickness."""
    return bd.Pos(0, 0, CUTTER_MARGIN) * bd.Cylinder(
        data.hole_diameter / 2,
        data.panel_thickness + 2 * CUTTER_MARGIN,
        align=_Z_MAX,
    )


def print_summary(data: PowerButtonData = POWER_BUTTON) -> None:
    d = data
    print(
        f"power button   panel hole {d.hole_diameter:.2f} dia, head {d.head_diameter:.2f} dia, "
        f"{d.head_top_z:.2f} above the panel (seal {d.seal_thickness:.2f})"
    )
    print(
        f"behind panel   {d.depth_behind_panel:.2f} to the terminal tips: thread to {-d.thread_end_z:.2f}, "
        f"body {d.body_length:.2f}, terminals {d.terminal_length:.2f}"
    )
    print(
        f"nut            {d.nut_across_flats:.2f} across flats, {d.nut_across_corners:.2f} across corners, "
        f"Z {d.nut_bottom_z:.2f} .. {d.nut_top_z:.2f}"
    )
    print(
        f"panel          {d.panel_thickness:.2f} thick, up to {d.max_panel_thickness:.2f} fits the thread"
    )
    if d.panel_thickness > d.max_panel_thickness:
        print("power button thread is too short for this panel")


if __name__ == "__main__":
    from ocp_vscode import show

    print_summary()
    show(create_powerbutton(), create_powerbutton_cutter(), alphas=[1, 0.3])
