import build123d as bd
from geom_defs import *
import numpy as np


def generate_scrollwheel(input: ScrollWheelData, simple=True) -> bd.Part:
    """Generate a 3D model of a scroll wheel based on the input data.
    If simple=False, generates detailed helical cuts on the scroll wheel surface.
    The scroll wheel is centered on the origin (wheel drum center), with axis on Z."""
    bump_count = 24
    base_cylinder = bd.Cylinder(
        radius=input.diameter / 2,
        height=input.width,
        align=[bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER],
    )
    notch_depth = 0.5
    axis = bd.Line((0, 0, 0), (0, 0, input.width / 2))
    helix_guide = bd.Helix(
        pitch=input.width * 6,
        height=input.width / 2,
        center=(0, 0, 0),
        radius=input.diameter / 2,
    )

    base_cylinder = base_cylinder.chamfer(
        input.chamfer, input.chamfer, base_cylinder.edges()
    )

    scrollwheel = base_cylinder
    if not simple:
        with bd.BuildPart() as cuts:
            with bd.BuildSketch() as wheel_sketch:
                with bd.Locations((input.diameter / 2, 0, 0)):
                    pitch_len = input.diameter * np.pi / bump_count
                    bd.Trapezoid(
                        width=pitch_len * 0.6,
                        height=notch_depth,
                        left_side_angle=90 - 15.0,
                        right_side_angle=90 - 15.0,
                        rotation=90,
                        align=[bd.Align.CENTER, bd.Align.MIN],
                    )
            # bd.extrude(amount=input.width, mode=bd.Mode.SUBTRACT)
            bd.sweep(path=axis, binormal=helix_guide, mode=bd.Mode.ADD)
            bd.mirror(about=bd.Plane.XY)

        scrollwheel = (
            base_cylinder - bd.PolarLocations(radius=0, count=bump_count) * cuts.part
        )

    top_shaft = bd.Cylinder(
        radius=input.shaft_diameter_top / 2,
        height=input.shaft_length_top,
        align=[bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN],
    )
    top_shaft = top_shaft.chamfer(
        length=input.shaft_diameter_top / 4,
        length2=None,
        edge_list=[(top_shaft.edges() < bd.Axis.Z)[0]],
    )
    hex_profile = bd.RegularPolygon(
        radius=input.shaft_hex_diameter_bottom / 2, side_count=6, major_radius=False
    )

    bot_shaft = bd.extrude(hex_profile, amount=-input.shaft_length_bottom)
    bot_shaft = bot_shaft.chamfer(
        length=input.shaft_hex_diameter_bottom / 6,
        length2=None,
        edge_list=(bot_shaft.edges() > bd.Axis.Z)[:6],
    )

    scrollwheel = (
        scrollwheel
        + bd.Pos(0, 0, input.width / 2) * top_shaft
        + bd.Pos(0, 0, -input.width / 2) * bot_shaft
    )
    return scrollwheel


def generate_scrollwheel_supports(input: ScrollWheelData) -> bd.Part:
    """
    Generates supports for the scrollwheel. Returns a tuple of 2 supports for the 2 ends.
    Supports shall attach to the housing and should later be trimmed.
    Supports reach up to the edge of the wheel in Y direction.
    """
    r = input.shaft_diameter_top / 2 + input.support_clearance
    w = input.support_width
    overhang = 1
    with bd.BuildPart(
        bd.Plane.XY.offset(
            input.width / 2 + input.shaft_length_top + input.support_clearance / 2
        )
    ) as support_top:
        with bd.BuildSketch() as support_sketch:
            with bd.BuildLine() as sketchline:
                bd.RadiusArc(
                    start_point=(-r, 0),
                    end_point=(r, 0),
                    radius=r,
                )

                bd.Polyline(
                    [
                        (r, 0),
                        (r, -w * overhang),
                        (r + w, -w * overhang),
                        (r + w, 0),
                        (r + w, input.diameter / 2),
                        (-r - w, input.diameter / 2),
                        (-r - w, 0),
                        (-r - w, -w * overhang),
                        (-r, -w * overhang),
                        (-r, 0),
                    ]
                )
                vertices = sketchline.line.vertices().sort_by(bd.Axis.Y)[:4]
                bd.chamfer(vertices, length=w / 4)
            bd.make_face()
        bd.extrude(amount=-w)
        with bd.BuildSketch() as support_sketch2:
            with bd.BuildLine() as sketchline2:
                bd.Polyline(
                    [
                        (r + w, -w * overhang),
                        (r + w, input.diameter / 2),
                        (-r - w, input.diameter / 2),
                        (-r - w, -w * overhang),
                        (r + w, -w * overhang),
                    ]
                )
                vertices = sketchline2.line.vertices().sort_by(bd.Axis.Y)[:2]
                bd.chamfer(vertices, length=w / 4)
            bd.make_face()
        bd.extrude(amount=w)

    support_bot = bd.Box(
        w * 2,
        input.diameter / 2 + w,
        w * 2,
        align=[bd.Align.CENTER, bd.Align.MIN, bd.Align.MAX],
    )
    support_bot = support_bot.translate(
        (
            0,
            -w,
            -input.width / 2 - input.shaft_length_bottom - input.support_clearance / 2,
        )
    )
    support_bot = support_bot.chamfer(
        length=w / 4,
        length2=None,
        edge_list=(support_bot.faces() > bd.Axis.Y)[0].edges(),
    )
    return support_top.part, support_bot


def generate_scrollwheel_cutter(input: ScrollWheelData, gap: float = 0.5) -> bd.Part:
    """
    Generates a cutting template for the opening around the wheel: the wheel drum (without shafts and pattern)
    offset outwards by `gap` on every face, chamfers included. Same frame as the scroll wheel.
    """
    cutter = bd.Cylinder(
        radius=input.diameter / 2 + gap,
        height=input.width + 2 * gap,
        align=[bd.Align.CENTER, bd.Align.CENTER, bd.Align.CENTER],
    )
    # chamfer length that keeps the chamfer faces `gap` away as well
    chamfer = input.chamfer + gap * (2 - np.sqrt(2))
    return cutter.chamfer(chamfer, chamfer, cutter.edges())


if __name__ == "__main__":
    from geom_defs import ScrollWheelData
    from ocp_vscode import show

    input_data = ScrollWheelData(diameter=20)
    support1, support2 = generate_scrollwheel_supports(input_data)
    wheel = generate_scrollwheel(input_data, simple=True)
    cutter = generate_scrollwheel_cutter(input_data)
    show(wheel, support1, support2, cutter, alphas=[1, 1, 1, 0.3])
