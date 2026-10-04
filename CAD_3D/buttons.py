import build123d as bd
from geom_defs import *


@dataclass
class Buttons:
    left: bd.Part
    right: bd.Part
    center: bd.Part
    left_sleeve: bd.Part
    right_sleeve: bd.Part
    center_sleeve: bd.Part
    merge_sleeve: bool
    cutter_left: bd.Part
    cutter_right: bd.Part
    cutter_center: bd.Part

    @property
    def caps(self) -> tuple[bd.Part, ...]:
        """The moving parts."""
        return (self.left, self.right, self.center)

    @property
    def sleeves(self) -> tuple[bd.Part, ...]:
        """To be joined to the panel; with merge_sleeve the center sleeve is the single merged one."""
        if self.merge_sleeve:
            return (self.center_sleeve,)
        return (self.left_sleeve, self.right_sleeve, self.center_sleeve)

    @property
    def cutters(self) -> tuple[bd.Part, ...]:
        """To be subtracted from the panel: the button openings through the sleeves."""
        return (self.cutter_left, self.cutter_right, self.cutter_center)

    @property
    def shape(self) -> bd.Compound:
        return bd.Compound(children=[*self.caps, *self.sleeves])


def create_buttons(input: ButtonData):

    center_sketch = bd.RegularPolygon(
        radius=input.diameter / 2, side_count=8, rotation=360 / 8 / 2
    )

    center_button = bd.extrude(
        center_sketch,
        amount=input.depth + input.button_height,
    )

    center_sketch_buff = bd.offset(
        center_sketch, amount=input.foot_add_width, kind=bd.Kind.INTERSECTION
    )
    center_sketch_raise = bd.Pos(0, 0, input.foot_add_height) * center_sketch
    foot_center = bd.loft([center_sketch_buff, center_sketch_raise])

    center_button = center_button + foot_center

    sleeve_sketch_center_1 = bd.offset(
        center_sketch,
        amount=input.foot_add_width + input.clearance,
        kind=bd.Kind.INTERSECTION,
    )
    sleeve_sketch_center_2 = bd.offset(
        center_sketch,
        amount=input.foot_add_width + input.clearance + input.sleeve_width,
        kind=bd.Kind.INTERSECTION,
    )
    sleeve_sketch_center_3 = bd.offset(
        center_sketch_raise,
        amount=input.clearance,
        kind=bd.Kind.INTERSECTION,
    )

    sleeve_outer = bd.extrude(sleeve_sketch_center_2, amount=input.depth)
    center_cutter = bd.loft(
        [sleeve_sketch_center_1, sleeve_sketch_center_3]
    ) + bd.extrude(sleeve_sketch_center_3, amount=input.depth - input.foot_add_height)

    sleeve_center = sleeve_outer - center_cutter
    # just an arrow shape that I like
    arrow_sketch = bd.Face(
        bd.Polyline(
            (0, 10, 0),
            (5, 10, 0),
            (16, 3, 0),
            (16, -3, 0),
            (5, -10, 0),
            (0, -10, 0),
            (2, 0, 0),
            (0, 10, 0),
        )
    ).translate(
        (-6.5, 0, 0)
    )  # guessing a good center (pressure) point

    # adjust for nominal scale
    arrow_sketch = arrow_sketch.scale(input.diameter / 2 / 10, about=bd.Vector(0, 0, 0))
    arrow_sketch_buff = bd.offset(
        arrow_sketch, amount=input.foot_add_width, kind=bd.Kind.INTERSECTION
    )
    arrow_sketch_raise = bd.Pos(0, 0, input.foot_add_height) * arrow_sketch
    foot_arrow = bd.loft([arrow_sketch_buff, arrow_sketch_raise])

    sleeve_sketch_arrow_1 = bd.offset(
        arrow_sketch,
        amount=input.foot_add_width + input.clearance,
        kind=bd.Kind.INTERSECTION,
    )
    sleeve_sketch_arrow_2 = bd.offset(
        arrow_sketch,
        amount=input.foot_add_width + input.clearance + input.sleeve_width,
        kind=bd.Kind.INTERSECTION,
    )
    sleeve_sketch_arrow_3 = bd.offset(
        arrow_sketch_raise,
        amount=input.clearance,
        kind=bd.Kind.INTERSECTION,
    )

    sleeve_outer_arrow = bd.extrude(
        sleeve_sketch_arrow_2, amount=input.depth, dir=bd.Vector(0, 0, 1)
    )
    sleeve_arrow_cutter = bd.loft(
        [sleeve_sketch_arrow_1, sleeve_sketch_arrow_3]
    ) + bd.extrude(
        sleeve_sketch_arrow_3,
        amount=input.depth - input.foot_add_height,
        dir=bd.Vector(0, 0, 1),
    )
    sleeve_arrow = sleeve_outer_arrow - sleeve_arrow_cutter

    right_pos = bd.Pos(input.spacing + input.diameter, 0, 0)

    button_right = right_pos * (
        bd.extrude(
            arrow_sketch,
            amount=input.depth + input.button_height,
            dir=bd.Vector(0, 0, 1),
        )
        + foot_arrow
    )

    sleeve_right = right_pos * sleeve_arrow
    cutter_right = right_pos * sleeve_arrow_cutter

    button_left = bd.mirror(button_right, about=bd.Plane.YZ)
    sleeve_left = bd.mirror(sleeve_right, about=bd.Plane.YZ)
    cutter_left = bd.mirror(cutter_right, about=bd.Plane.YZ)

    if input.merge_sleeve:
        to_extrude = sleeve_right.faces().sort_by(bd.Axis.X)[:2]
        to_extrude_2 = sleeve_left.faces().sort_by(bd.Axis.X)[-2:]

        # extrude_until doesn't seem to work here
        # filler = bd.extrude(
        #     to_extrude, dir=bd.Vector(-1, 0, 0), until=bd.Until.NEXT, target=sleeve_left
        # )

        filler = bd.extrude(
            to_extrude,
            dir=bd.Vector(-1, 0, 0),
            amount=input.spacing + input.diameter,
        )
        filler = filler + bd.extrude(
            to_extrude_2,
            dir=bd.Vector(1, 0, 0),
            amount=input.spacing + input.diameter,
        )
        sleeve_center = sleeve_left + sleeve_right + filler - center_cutter

    center_button = bd.chamfer(
        center_button.faces().sort_by(bd.Axis.Z)[-1].edges(), length=0.5
    )
    button_left = bd.chamfer(
        button_left.faces().sort_by(bd.Axis.Z)[-1].edges(), length=0.5
    )
    button_right = bd.chamfer(
        button_right.faces().sort_by(bd.Axis.Z)[-1].edges(), length=0.5
    )
    center_button.label = "center"
    button_left.label = "left"
    button_right.label = "right"
    sleeve_center.label = "center_sleeve"
    sleeve_left.label = "left_sleeve"
    sleeve_right.label = "right_sleeve"

    return Buttons(
        center=center_button,
        left=button_left,
        right=button_right,
        center_sleeve=sleeve_center,
        left_sleeve=sleeve_left,
        right_sleeve=sleeve_right,
        merge_sleeve=input.merge_sleeve,
        cutter_center=center_cutter,
        cutter_left=cutter_left,
        cutter_right=cutter_right,
    )


if __name__ == "__main__":
    from ocp_vscode import show

    input_data = ButtonData()
    buttons = create_buttons(input_data)
    show(buttons.shape)
