import build123d as bd
from geom_defs import (
    EnclosureData,
    EnclosureSlotData,
    EnclosureEndcapScrewPattern,
)


def create_enclosure(
    enclosure_data: EnclosureData,
) -> bd.Part:
    """
    Create an enclosure part based on the provided enclosure data.
    Part will be centered on origin.
    """

    wall = enclosure_data.wall_thickness
    screw_hole = enclosure_data.screws.screw_dia
    fillet_radius = enclosure_data.corner_radius

    with bd.BuildPart() as enclosure_build:
        with bd.BuildSketch(bd.Plane.YZ) as base_sketch:
            bd.Rectangle(enclosure_data.width, enclosure_data.height)
            bd.fillet(base_sketch.sketch_local.vertices(), radius=fillet_radius)
            bd.offset(base_sketch.sketch_local, -wall, mode=bd.Mode.SUBTRACT)

        extrusion = bd.extrude(
            base_sketch.sketch, enclosure_data.length, dir=bd.Vector(1, 0, 0)
        )

    with bd.BuildPart() as screws_build:
        with (
            bd.BuildSketch(bd.Plane.YZ) as screw_sketch,
            bd.GridLocations(
                x_count=2,
                y_count=2,
                x_spacing=enclosure_data.screws.width,
                y_spacing=enclosure_data.screws.height,
            ) as grid,
        ):
            bd.Circle(enclosure_data.screws.screw_dia / 2 + wall, mode=bd.Mode.ADD)
            bd.Circle(enclosure_data.screws.screw_dia / 2, mode=bd.Mode.SUBTRACT)
        bd.extrude(screw_sketch.sketch, enclosure_data.length, dir=bd.Vector(1, 0, 0))
    enclosure = enclosure_build.part + screws_build.part

    with bd.BuildPart() as slot_build:
        # create slots on one side, mirror them next
        with bd.BuildSketch(bd.Plane.YZ) as slot_sketch:
            # side location
            with bd.Locations(
                (-enclosure_data.width / 2 + wall, enclosure_data.slots.slot_offset)
            ):
                # slot grid vertical
                with bd.GridLocations(
                    y_count=enclosure_data.slots.slot_count,
                    y_spacing=enclosure_data.slots.slot_pitch,
                    x_count=1,
                    x_spacing=0,
                ) as grid:
                    if enclosure_data.slots.slot_cut_depth < 0:
                        bd.Rectangle(
                            -enclosure_data.slots.slot_cut_depth,
                            enclosure_data.slots.slot_cut_height,
                            align=(bd.Align.MIN, bd.Align.CENTER),
                        )
                    else:
                        bd.Rectangle(
                            enclosure_data.slots.slot_cut_depth,
                            enclosure_data.slots.slot_cut_height,
                            align=(bd.Align.MAX, bd.Align.CENTER),
                        )
        if enclosure_data.slots.slot_cut_depth < 0:
            # cuts are negative relative to wall, more like extrusion
            # bring your own wall strategy... adding a wall
            with bd.Locations(
                (0, -enclosure_data.width / 2 + wall, enclosure_data.slots.slot_offset)
            ):
                bd.Box(
                    length=enclosure_data.length,
                    width=-enclosure_data.slots.slot_cut_depth,
                    height=enclosure_data.slots.slot_pitch
                    * (enclosure_data.slots.slot_count + 1)
                    - enclosure_data.slots.slot_cut_height,
                    align=(bd.Align.MIN, bd.Align.MIN, bd.Align.CENTER),
                )
            bd.extrude(
                slot_sketch.sketch,
                enclosure_data.length,
                dir=bd.Vector(1, 0, 0),
                mode=bd.Mode.SUBTRACT,
            )
        else:
            bd.extrude(
                slot_sketch.sketch,
                enclosure_data.length,
                dir=bd.Vector(1, 0, 0),
                mode=bd.Mode.ADD,
            )
        # mirror the slots to the other side
        bd.mirror(slot_build.part, about=bd.Plane.XZ)

    slots = slot_build.part
    if enclosure_data.slots.slot_cut_depth > 0:
        enclosure = enclosure - slots
    else:
        enclosure = enclosure + slots

    enclosure = enclosure.translate((-enclosure_data.length / 2, 0, 0))
    return enclosure


if __name__ == "__main__":
    from ocp_vscode import show

    slot_data = EnclosureSlotData(slot_cut_depth=-2)
    # screw_pattern = EnclosureEndcapScrewPattern()
    enclosure_data = EnclosureData(slots=slot_data)

    print(f"slot_positions mid: {enclosure_data.slots.slot_positions_mid}")
    print(f"slot_positions top: {enclosure_data.slots.slot_positions_top}")
    print(f"slot_positions bottom: {enclosure_data.slots.slot_positions_bottom}")
    print(f"offset from bottom: {enclosure_data.slot_position_from_case_bottom}")
    enclosure = create_enclosure(enclosure_data)
    show(enclosure)
