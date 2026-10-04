"""
Scroll wheel + EC10E encoder + B3F switch + case supports - the wheel turns the encoder, pressing it clicks the switch.

Frame: see ScrollWheelAssemblyData (encoder frame: pin B on the board top surface, wheel axis along Y, Z up).

    python CAD_3D/scrollwheel_assembly.py          # build, print a summary, show in ocp_vscode
"""

from dataclasses import dataclass

import build123d as bd

from encoder import create_encoder_ec10e
from geom_defs import ScrollWheelAssemblyData
from scrollwheel import (
    generate_scrollwheel,
    generate_scrollwheel_cutter,
    generate_scrollwheel_supports,
)
from tactile_switch import create_tactile_switch_b3f

WHEEL_COLOR = "#e08020"
SUPPORT_COLOR = "#6080a0"
CUTTER_COLOR = bd.Color(0.9, 0.2, 0.2, 0.25)

SCROLLWHEEL_ASSEMBLY = ScrollWheelAssemblyData()


@dataclass
class ScrollWheelAssembly:
    """Everything in the assembly (= encoder) frame.
    encoder and switch go on the board, wheel is a part of its own. The supports are untrimmed (they reach up to the
    top of the wheel) and are to be trimmed and joined to the cover plate; cover_cutter is to be subtracted from it.
    """

    data: ScrollWheelAssemblyData
    encoder: bd.Compound
    switch: bd.Compound
    wheel: bd.Part
    support_front: bd.Part  # race + end stop for the round shaft, behind the switch
    support_rear: bd.Part  # flat stop for the hex shaft tip, behind the encoder
    cover_cutter: bd.Part  # wheel drum grown by data.cover_gap

    @property
    def supports(self) -> tuple[bd.Part, bd.Part]:
        return (self.support_front, self.support_rear)

    @property
    def shape(self) -> bd.Compound:
        """The physical parts, for display and interference checks (no cutter)."""
        return bd.Compound(
            label="scrollwheel",
            children=[self.encoder, self.wheel, self.switch, *self.supports],
        )


def _moved(assembly: bd.Compound, location: bd.Location) -> bd.Compound:
    """Move the parts of an assembly themselves, so each child is in the parent frame whatever reads it."""
    children = []
    for child in assembly.children:
        part = location * child
        part.label, part.color = child.label, child.color
        children.append(part)
    return bd.Compound(label=assembly.label, children=children)


def create_scrollwheel_assembly(
    data: ScrollWheelAssemblyData = SCROLLWHEEL_ASSEMBLY, simple: bool = True
) -> ScrollWheelAssembly:
    """simple=False generates the helical pattern on the wheel, which takes a while."""
    encoder = create_encoder_ec10e(data.encoder)
    encoder.label = "encoder"

    switch = _moved(create_tactile_switch_b3f(data.switch), bd.Pos(*data.switch_origin))
    switch.label = "switch"

    # wheel, supports and cutter are generated in the wheel frame
    wheel_location = bd.Pos(*data.wheel_center) * bd.Rot(*data.wheel_rotation)
    wheel = wheel_location * generate_scrollwheel(data.wheel, simple=simple)
    wheel.label, wheel.color = "wheel", bd.Color(WHEEL_COLOR)

    supports = []
    for support, name in zip(
        generate_scrollwheel_supports(data.wheel), ("support_front", "support_rear")
    ):
        support = wheel_location * support
        support.label, support.color = name, bd.Color(SUPPORT_COLOR)
        supports.append(support)

    cutter = wheel_location * generate_scrollwheel_cutter(data.wheel, data.cover_gap)
    cutter.label, cutter.color = "cover_cutter", CUTTER_COLOR

    support_front, support_rear = supports
    return ScrollWheelAssembly(
        data, encoder, switch, wheel, support_front, support_rear, cutter
    )


def print_summary(data: ScrollWheelAssemblyData = SCROLLWHEEL_ASSEMBLY) -> None:
    d = data
    print(
        f"wheel drum     Y {d.wheel_front_y:.2f} .. {d.wheel_rear_y:.2f}, Z {d.wheel_bottom_z:.2f} .. {d.wheel_top_z:.2f}"
    )
    print(
        f"hex shaft      length {d.hex_shaft_length:.2f}, tip Y {d.rear_support_y:.2f} "
        f"(rotor Y {d.encoder.face_f_y:.2f} .. {d.encoder.boss_rear_y:.2f})"
    )
    print(
        f"round shaft    dia {d.shaft_diameter:.2f}, length {d.shaft_length:.2f}, tip Y {d.front_support_y:.2f}, "
        f"plunger axis Y {d.switch_center_xy[1]:.2f}, gap {d.plunger_gap:.2f}"
    )
    print(f"switch pin 1   at {d.switch_origin}")
    print(
        f"with supports  Y {d.y_min:.2f} .. {d.y_max:.2f}, supports down to Z {d.support_bottom_z:.2f}"
    )
    print(f"cover opening  {d.cover_gap:.2f} gap around the drum")
    if d.wheel_bottom_z < 0:
        print(
            f"wheel reaches {-d.wheel_bottom_z:.2f} mm below the board top surface -> board cutout needed"
        )


if __name__ == "__main__":
    from ocp_vscode import show

    print_summary()
    asm = create_scrollwheel_assembly(simple=False)
    show(asm.shape, asm.cover_cutter)
