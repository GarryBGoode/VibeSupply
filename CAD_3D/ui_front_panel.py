"""
UI front panel: the plate with the screen, the three buttons, the scroll wheels and the LEDs behind it, the on-off
button in it, and the screws for the UI board.

Frame: see UIPanelData (panel frame: origin at the panel centre on its front face, Z out towards the user).

    python CAD_3D/ui_front_panel.py          # build, print a summary, show in ocp_vscode
"""

from dataclasses import dataclass

import build123d as bd

from board_screw import BoardScrew, create_board_screw
from button_assembly import ButtonAssembly, create_button_assembly
from geom_defs import PanelPlacement, UIPanelData
from led import create_led, create_led_cutter
from mech_design import ui_panel
from powerbutton import create_powerbutton, create_powerbutton_cutter
from screen import create_screen, create_screen_cutter
from scrollwheel_assembly import ScrollWheelAssembly, create_scrollwheel_assembly

PANEL_COLOR = "#717171"


@dataclass
class UIPanel:
    """Everything in the panel frame.
    panel is the printed part: the plate with the button sleeves, the wheel supports and the screw bosses joined and
    the openings cut.
    """

    data: UIPanelData
    panel: bd.Part
    screen: bd.Compound
    buttons: bd.Compound  # the three button caps + switches
    scrollwheels: tuple[bd.Compound, ...]  # encoder + wheel + switch, one per wheel
    screws: bd.Compound  # UI board screws + heat-set inserts
    leds: bd.Compound
    onoff_button: bd.Compound  # output on-off toggle

    @property
    def shape(self) -> bd.Compound:
        return bd.Compound(
            label="ui_panel",
            children=[
                self.panel,
                self.screen,
                self.buttons,
                *self.scrollwheels,
                self.screws,
                self.leds,
                self.onoff_button,
            ],
        )


def _location(placement: PanelPlacement, z: float) -> bd.Location:
    return bd.Pos(placement.x, placement.y, z) * bd.Rot(0, 0, placement.rotation)


def _placed(shape: bd.Shape, location: bd.Location) -> bd.Shape:
    """Move a part, or the parts of an assembly themselves, so each child is in the panel frame whatever reads it."""
    if shape.children:
        return bd.Compound(
            label=shape.label,
            children=[_placed(child, location) for child in shape.children],
        )
    placed = location * shape
    placed.label, placed.color = shape.label, shape.color
    return placed


def create_panel(
    data: UIPanelData,
    buttons: ButtonAssembly,
    scrollwheel: ScrollWheelAssembly,
    screw: BoardScrew,
) -> bd.Part:
    """The printed panel. `buttons`, `scrollwheel` and `screw` are the components in their own frames, as generated
    from data.buttons, data.scrollwheel and data.screw; what they add to and cut from the plate is placed here.
    """
    button_loc = _location(data.button_placement, data.board_z)
    screen_loc = _location(data.screen_placement, data.screen_z)
    wheel_locs = [_location(p, data.board_z) for p in data.scrollwheel_placements]
    screw_locs = [_location(p, data.board_z) for p in data.screw_placements]
    led_locs = [_location(p, data.board_z) for p in data.led_placements]
    # the on-off button frame is on the panel front face
    onoff_loc = _location(data.onoff_button_placement, 0)

    panel = bd.Box(
        data.width,
        data.height,
        data.thickness,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MAX),
    ).translate((0, data.offset_y, 0))

    # merge: button sleeves, wheel supports and screw bosses
    for sleeve in buttons.sleeves:
        panel += button_loc * sleeve
    for wheel_loc in wheel_locs:
        for support in scrollwheel.supports:
            panel += wheel_loc * support
    for screw_loc in screw_locs:
        panel += screw_loc * screw.boss
    # the supports are generated up to the top of the wheel: trim to the front face
    panel -= bd.Box(
        2 * data.width,
        2 * data.height,
        data.wheel_protrusion + 1,
        align=(bd.Align.CENTER, bd.Align.CENTER, bd.Align.MIN),
    )

    # cut: button, wheel, screen, LED and on-off button openings, insert holes for the screws
    for cutter in buttons.cutters:
        panel -= button_loc * cutter
    for wheel_loc in wheel_locs:
        panel -= wheel_loc * scrollwheel.cover_cutter
    panel -= screen_loc * create_screen_cutter(data.screen)
    for screw_loc in screw_locs:
        panel -= screw_loc * screw.cutter
    led_cutter = create_led_cutter(data.led)
    for led_loc in led_locs:
        panel -= led_loc * led_cutter
    panel -= onoff_loc * create_powerbutton_cutter(data.onoff_button)

    panel.label, panel.color = "panel", bd.Color(PANEL_COLOR)
    return panel


def create_ui_panel(data: UIPanelData = ui_panel, simple: bool = False) -> UIPanel:
    """simple=False generates the helical pattern on the wheels and the thread on the on-off button, which takes a
    while."""
    buttons = create_button_assembly(data.buttons)
    scrollwheel = create_scrollwheel_assembly(data.scrollwheel, simple=simple)
    screw = create_board_screw(data.screw)

    panel = create_panel(data, buttons, scrollwheel, screw)

    screen = _placed(
        create_screen(data.screen), _location(data.screen_placement, data.screen_z)
    )
    screen.label = "screen"

    button_loc = _location(data.button_placement, data.board_z)
    button_parts = [
        _placed(part, button_loc) for part in (*buttons.caps, *buttons.switches)
    ]

    scrollwheels = []
    for i, placement in enumerate(data.scrollwheel_placements, start=1):
        wheel_loc = _location(placement, data.board_z)
        parts = (scrollwheel.encoder, scrollwheel.wheel, scrollwheel.switch)
        scrollwheels.append(
            bd.Compound(
                label=f"scrollwheel_{i}",
                children=[_placed(part, wheel_loc) for part in parts],
            )
        )

    screws = []
    for placement in data.screw_placements:
        screw_loc = _location(placement, data.board_z)
        screws += [_placed(part, screw_loc) for part in (screw.screw, screw.insert)]

    led = create_led(data.led)
    leds = [_placed(led, _location(p, data.board_z)) for p in data.led_placements]

    onoff_button = _placed(
        create_powerbutton(data.onoff_button, simple=simple),
        _location(data.onoff_button_placement, 0),
    )
    onoff_button.label = "onoff_button"

    return UIPanel(
        data=data,
        panel=panel,
        screen=screen,
        buttons=bd.Compound(label="buttons", children=button_parts),
        scrollwheels=tuple(scrollwheels),
        screws=bd.Compound(label="screws", children=screws),
        leds=bd.Compound(label="leds", children=leds),
        onoff_button=onoff_button,
    )


def print_summary(data: UIPanelData = ui_panel) -> None:
    d = data
    b = d.buttons

    def positions(placements: tuple[PanelPlacement, ...]) -> str:
        return ", ".join(f"({p.x:.1f}, {p.y:.1f})" for p in placements)

    print(f"panel          {d.width:.1f} x {d.height:.1f} x {d.thickness:.1f}")
    print(
        f"UI board       top surface {d.board_depth:.2f} below the panel front face "
        f"(wheels {d.wheel_protrusion:.2f} above it)"
    )
    print(
        f"buttons        length {b.buttons.depth + b.buttons.button_height:.2f}, "
        f"foot {b.button_z:.2f} above the board, {b.buttons.button_height:.2f} above the panel"
    )
    print(
        f"screen opening {d.screen.opening_clearance:.2f} gap around the screen, "
        f"{d.screen.opening_chamfer:.2f} lead-in chamfer"
    )
    for i, p in enumerate(d.scrollwheel_placements, start=1):
        print(f"scroll wheel {i} at ({p.x:.1f}, {p.y:.1f}), rotation {p.rotation:.0f}")
    print(
        f"board screws   {d.screw.size} x {d.screw.length:.0f} into {d.screw.insert_size} inserts "
        f"at {positions(d.screw_placements)}; bosses {d.screw.boss_height:.2f} long"
    )
    print(
        f"LEDs           at {positions(d.led_placements)}, {d.led_protrusion:.2f} above the panel, "
        f"body {d.led.standoff:.2f} above the board, {d.led.lead_length_used:.2f} of "
        f"{d.led.lead_length:.2f} lead used"
    )
    o, op = d.onoff_button, d.onoff_button_placement
    print(
        f"on-off button  at ({op.x:.1f}, {op.y:.1f}), hole {o.hole_diameter:.2f} dia, "
        f"{o.depth_behind_panel:.2f} behind the panel front face "
        f"({o.depth_behind_panel - d.board_depth - d.board_thickness:.2f} beyond the back of the UI board)"
    )


if __name__ == "__main__":
    from ocp_vscode import show

    print_summary()
    ui = create_ui_panel()
    show(ui.shape)
