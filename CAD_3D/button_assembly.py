"""
Three buttons + B3F switches + sleeves - pressing a button clicks the switch under it.

Frame: see ButtonAssemblyData (origin on the board top surface under the centre button, X along the row, Z up).

    python CAD_3D/button_assembly.py          # build, print a summary, show in ocp_vscode
"""

from dataclasses import dataclass

import build123d as bd

from buttons import create_buttons
from geom_defs import ButtonAssemblyData
from scrollwheel_assembly import _moved
from tactile_switch import create_tactile_switch_b3f

BUTTON_COLOR = "#d0d0d0"
SLEEVE_COLOR = "#6080a0"
CUTTER_COLOR = bd.Color(0.9, 0.2, 0.2, 0.25)

BUTTON_ASSEMBLY = ButtonAssemblyData()


@dataclass
class ButtonAssembly:
    """Everything in the assembly frame.
    The switches go on the board, the caps are parts of their own. The sleeves reach up to the panel front face and
    are to be joined to the panel; the cutters (the button openings through the sleeves) are to be subtracted from it.
    """

    data: ButtonAssemblyData
    switches: tuple[bd.Compound, ...]  # left, center, right
    caps: tuple[bd.Part, ...]  # left, right, center
    sleeves: tuple[bd.Part, ...]
    cutters: tuple[bd.Part, ...]

    @property
    def shape(self) -> bd.Compound:
        """The physical parts, for display and interference checks (no cutters)."""
        return bd.Compound(
            label="buttons", children=[*self.switches, *self.caps, *self.sleeves]
        )


def create_button_assembly(data: ButtonAssemblyData = BUTTON_ASSEMBLY) -> ButtonAssembly:
    switches = []
    for origin, name in zip(data.switch_origins, ("left", "center", "right")):
        switch = _moved(create_tactile_switch_b3f(data.switch), bd.Pos(*origin))
        switch.label = f"switch_{name}"
        switches.append(switch)

    # buttons, sleeves and cutters are generated in the button frame
    buttons = create_buttons(data.buttons)
    button_location = bd.Pos(0, 0, data.button_z)

    def moved(parts, color) -> tuple[bd.Part, ...]:
        result = []
        for part in parts:
            label = part.label
            part = button_location * part
            part.label, part.color = label, color
            result.append(part)
        return tuple(result)

    return ButtonAssembly(
        data=data,
        switches=tuple(switches),
        caps=moved(buttons.caps, bd.Color(BUTTON_COLOR)),
        sleeves=moved(buttons.sleeves, bd.Color(SLEEVE_COLOR)),
        cutters=moved(buttons.cutters, CUTTER_COLOR),
    )


def print_summary(data: ButtonAssemblyData = BUTTON_ASSEMBLY) -> None:
    d = data
    b = d.buttons
    print(
        f"buttons        foot Z {d.button_z:.2f}, panel face Z {d.panel_height:.2f}, "
        f"top Z {d.panel_height + b.button_height:.2f} (length {b.depth + b.button_height:.2f})"
    )
    print(
        f"switches       plunger top Z {d.switch.height:.2f}, gap {d.plunger_gap:.2f}, "
        f"body top Z {d.switch.body_height:.2f}"
    )
    for origin, name in zip(d.switch_origins, ("left", "center", "right")):
        print(f"switch {name:6}  pin 1 at {origin}")


if __name__ == "__main__":
    from ocp_vscode import show

    print_summary()
    asm = create_button_assembly()
    show(asm.shape)
