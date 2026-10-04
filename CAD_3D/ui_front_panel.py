from screen import *
from scrollwheel_assembly import *
from geom_defs import *
import build123d as bd
from buttons import *

if __name__ == "__main__":
    from ocp_vscode import show

    scroll_depth = 3
    panel_thickness = 2

    screen_data = ScreenData()
    screen = create_screen(screen_data)

    screen_pos = bd.Pos(0, 25, -panel_thickness)
    screen = screen_pos * screen

    scrollwheel_data = ScrollWheelAssemblyData()
    scrollwheel = create_scrollwheel_assembly(scrollwheel_data, simple=True)
    scrollwheel_1 = scrollwheel.shape

    pcb_depth = scrollwheel_data.wheel_top_z - scroll_depth
    button_depth = pcb_depth - 5

    buttons_data = ButtonData(
        spacing=5,
        depth=button_depth,
        foot_add_height=1,
        foot_add_width=1,
        sleeve_width=1,
    )

    buttons = create_buttons(buttons_data)
    buttonshape = buttons.shape
    button_pos = bd.Pos(0, 0, -buttons_data.depth)
    buttonshape = button_pos * buttonshape

    scroll_pos = (
        bd.Pos(-25, -20, 0) * bd.Rotation(0, 0, 90) * bd.Pos(0, 0, -(pcb_depth))
    )

    scrollwheel_1 = scroll_pos * scrollwheel_1

    scrollwheel_2 = bd.mirror(scrollwheel_1, about=bd.Plane.YZ)

    panel = bd.Box(
        75, 90, panel_thickness, align=[bd.Align.CENTER, bd.Align.CENTER, bd.Align.MAX]
    )
    panel.color = "#717171"
    panel = (
        panel
        - button_pos * buttons.cutter_center
        - button_pos * buttons.cutter_left
        - button_pos * buttons.cutter_right
    )
    panel = (
        panel
        - scroll_pos * scrollwheel.cover_cutter
        - bd.mirror(scroll_pos * scrollwheel.cover_cutter, about=bd.Plane.YZ)
    )
    panel = panel - screen_pos * create_screen_cutter(screen_data)

    show(scrollwheel_1, scrollwheel_2, screen, buttonshape, panel)
