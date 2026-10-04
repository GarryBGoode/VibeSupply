import build123d as bd
from geom_defs import ScreenData


def create_screen(input: ScreenData):

    pcb = bd.Box(input.width, input.height, 1.6)
    pcb.color = "#2500cc"
    hole_locs = bd.Locations(*input.hole_pattern)
    pinhole = bd.Cylinder(1.5 / 2, 1.6)
    pin_locs = bd.GridLocations(x_spacing=1, y_spacing=2.54, x_count=1, y_count=8)

    pcb = pcb - hole_locs * bd.Cylinder(input.hole_diameter / 2, 1.6)
    pcb = pcb - bd.Pos(input.width / 2 - 2, 0, 0) * pin_locs * pinhole
    screen = bd.Box(input.screen_width, input.screen_height, 3).translate((0, 0, 1.6))
    screen.color = "#000000"
    module = bd.Compound(children=[pcb, screen])

    # align pcb top with xy plane
    return bd.Pos(0, 0, -1.6 / 2) * module


def create_screen_cutter(input: ScreenData):
    screen = bd.Box(input.screen_width, input.screen_height, 30)
    hole_locs = bd.Locations(*input.hole_pattern)
    holes = hole_locs * bd.Cylinder(input.hole_diameter / 2, 30)
    return bd.Compound(children=[screen, *holes])


if __name__ == "__main__":
    from ocp_vscode import show

    screen_data = ScreenData()
    screen = create_screen(screen_data)
    show(screen)
