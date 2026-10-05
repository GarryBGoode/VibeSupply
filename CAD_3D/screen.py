import build123d as bd
from geom_defs import ScreenData

# cutter reach above the pcb top surface, more than any panel thickness
CUTTER_HEIGHT = 30


def create_screen(input: ScreenData):
    """Screen module in the screen frame (see ScreenData): pcb top surface on the XY plane."""
    pcb_align = (bd.Align.CENTER, bd.Align.CENTER, bd.Align.MAX)
    pcb = bd.Box(input.width, input.height, input.pcb_thickness, align=pcb_align)
    hole_locs = bd.Locations(*input.hole_pattern)
    pinhole = bd.Cylinder(1.5 / 2, input.pcb_thickness, align=pcb_align)
    pin_locs = bd.Locations(*input.pin_positions)

    pcb = pcb - hole_locs * bd.Cylinder(
        input.hole_diameter / 2, input.pcb_thickness, align=pcb_align
    )
    pcb = pcb - pin_locs * pinhole
    pcb.label, pcb.color = "pcb", bd.Color("#2500cc")

    screen = bd.Box(
        input.screen_width,
        input.screen_height,
        input.screen_thickness,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    screen.label, screen.color = "screen", bd.Color("#000000")
    return bd.Compound(children=[pcb, screen])


def create_screen_cutter(input: ScreenData) -> bd.Part:
    """To be subtracted from the panel, which sits on the pcb top surface: the opening for the screen with
    opening_clearance all round, widened by opening_chamfer on the pcb side as a lead-in, and the mounting holes.
    """
    width = input.screen_width + 2 * input.opening_clearance
    height = input.screen_height + 2 * input.opening_clearance
    chamfer = input.opening_chamfer

    opening = bd.Box(
        width,
        height,
        CUTTER_HEIGHT,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    if chamfer > 0:
        opening += bd.loft(
            [
                bd.Rectangle(width + 2 * chamfer, height + 2 * chamfer),
                bd.Pos(0, 0, chamfer) * bd.Rectangle(width, height),
            ]
        )

    hole = bd.Cylinder(
        input.hole_diameter / 2,
        CUTTER_HEIGHT,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )
    for x, y in input.hole_pattern:
        opening += bd.Pos(x, y, 0) * hole
    return opening


if __name__ == "__main__":
    from ocp_vscode import show

    screen_data = ScreenData()
    screen = create_screen(screen_data)
    show(screen, create_screen_cutter(screen_data), alphas=[1, 0.3])
