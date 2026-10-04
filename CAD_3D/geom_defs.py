from dataclasses import dataclass, field
import numpy as np


@dataclass(frozen=True)
class EnclosureEndcapScrewPattern:
    width: float = 70
    height: float = 35
    screw_dia: float = 3


@dataclass(frozen=True)
class EnclosureSlotData:
    slot_count: int = 8
    slot_cut_height: float = 2
    slot_pitch: float = 3.5
    # Distance from side of the enclosure to slot cut depth
    # Negative value creates ribs, but slot cut height and placement remains the same
    slot_cut_depth: float = -2.5
    # vertical deviation of pattern from its default centered position
    slot_offset: float = 0.31

    @property
    def slot_height_total(self) -> float:
        # Total height occupied by all slots including the gaps between them
        # There must be gap (uncut extrusion) on both ends
        return (self.slot_count + 1) * self.slot_pitch - self.slot_cut_height

    @property
    def slot_positions_mid(self) -> np.ndarray:

        positions = np.arange(0, self.slot_count) * self.slot_pitch
        # pattern goes: cut - extr - cut extr ... extr
        # shift down half cut to center on cuts
        positions = positions - self.slot_cut_height / 2
        # shift down to center
        positions = positions - self.slot_height_total / 2 + self.slot_pitch
        return positions + self.slot_offset

    @property
    def slot_positions_top(self) -> np.ndarray:
        return self.slot_positions_mid + self.slot_cut_height / 2

    @property
    def slot_positions_bottom(self) -> np.ndarray:
        return self.slot_positions_mid - self.slot_cut_height / 2


@dataclass(frozen=True)
class EnclosureData:
    length: float = 120
    width: float = 78
    height: float = 43
    wall_thickness: float = 1.5
    corner_radius: float = 4
    slots: EnclosureSlotData = field(default_factory=EnclosureSlotData)
    screws: EnclosureEndcapScrewPattern = field(
        default_factory=EnclosureEndcapScrewPattern
    )

    @property
    def inside_width(self) -> float:
        return self.width - 2 * self.wall_thickness

    @property
    def inside_height(self) -> float:
        return self.height - 2 * self.wall_thickness

    @property
    def slot_position_from_case_bottom(self) -> np.ndarray:
        # Z coordinates of slot placement surfaces measured from the inner bottom surface of enclosure
        return +self.inside_height / 2 + self.slots.slot_positions_bottom


@dataclass(frozen=True)
class ScrollWheelData:
    """Data for a scroll wheel component.
    Normally centered on origin, axis along Z, top shaft round, bottom shaft hexagonal.
    """

    diameter: float = 20.0
    width: float = 15.0
    shaft_diameter_top: float = 4.0
    shaft_hex_diameter_bottom: float = 1.73
    shaft_length_top: float = 13.0
    shaft_length_bottom: float = 13.0
    support_width: float = 3.0
    support_clearance: float = 0.2
    chamfer: float = 1.0  # drum edges


@dataclass(frozen=True)
class PCBSizeData:
    length: float = 170
    width: float = 75
    thickness: float = 1.6
    edge_keepout: float = 3.5


@dataclass(frozen=True)
class PCBPlacement:
    """Where a board sits in the enclosure: resting on the bottom of slot `slot_index`, centred across the width,
    with its rear edge `rear_gap` in front of the rear end of the extrusion (enclosure -X end).
    """

    slot_index: int
    rear_gap: float = 0

    def origin(
        self, enclosure: "EnclosureData", pcb: PCBSizeData
    ) -> tuple[float, float, float]:
        """Board frame origin (board centre, bottom face) in the enclosure frame."""
        x = -enclosure.length / 2 + self.rear_gap + pcb.length / 2
        z = (
            -enclosure.inside_height / 2
            + enclosure.slot_position_from_case_bottom[self.slot_index]
        )
        return (x, 0.0, float(z))


@dataclass(frozen=True)
class H905_placement:
    """Placement of H905 nut on the PCB."""

    x: float = -25
    y: float = 0


@dataclass(frozen=True)
class EncoderEC10EData:
    """Alps EC10E hollow-shaft encoder, horizontal (catalog Update2510, drawing No.1 = EC10E1220505, H = 7 mm).

    Frame = footprint supply1:RotaryEncoder_Alps_EC10E_Horizontal in build123d axes: origin at pin B on the board top
    surface (mounting surface), X along the pin row (pin A at -X, as in the footprint), Y = KiCad -y, Z up.
    The shaft axis runs along Y at Z = mount_height, X = 0. The bracket legs are 2 mm behind (+Y) the pin row; the
    shaft enters from the front (-Y) through face F, which is on the pin side.

    Catalog side view, left = shaft entry: thin signal pins edge-on, 2 mm further back the 2 mm wide bracket legs (long
    centre line). The catalog dimensions the side view from the leg centre line: face F 2.4, foot front edge 3.7, foot 6.1.

    Catalog dimensions are exact; values marked (est) are scaled from the drawing (which is drawn at H = 9 mm and
    reused for all heights) and only matter for looks / a little clearance.
    """

    # general properties
    num_detents: int = 24

    # --- footprint (catalog "Mounting Hole Dimensions") ---
    pin_pitch: float = 2.5
    pin_hole_dia: float = 1.0
    bracket_pitch: float = 9.0  # 10.8 outer - 1.8 slot
    bracket_offset_y: float = 2.0  # bracket slot centres behind (+Y) the pin row
    bracket_slot: tuple[float, float] = (1.8, 2.1)  # X, Y

    # --- shaft / rotor ---
    mount_height: float = 7.0  # H: shaft axis above the mounting surface
    hex_across_flats: float = 1.73  # +0.05/0
    rotor_dia: float = 2.98  # rotor ring seen in the front view
    rear_bore_dia: float = 2.2  # round bore at the rear (+Y) end of the rotor
    hex_end_depth: float = 1.7  # from face F: flared/hex part, then the round rear bore
    boss_dia: float = 3.6  # bearing boss on the rear face

    # --- body, front view (XZ) ---
    body_width: float = 9.8  # metal frame, X
    top_above_axis: float = 3.6  # arch top above the shaft axis
    terminal_block_below_axis: float = 5.0  # top of the terminal block below the axis
    arch_radius: float = 3.9  # (est) arch centred on the axis
    shoulder_above_axis: float = (
        1.2  # (est) flat frame shoulders either side of the arch
    )
    clip_protrusion: float = (
        0.3  # (est) bracket clips at axis height stick out beyond the 9.8 frame, each side
    )

    # --- body, side view (YZ), distances from the bracket leg centre line, towards the front (-Y) ---
    face_f_from_leg: float = 2.4  # ±0.3, face F (shaft entry)
    base_front_from_leg: float = 3.7  # foot of the terminal block, front edge
    base_depth: float = 6.1  # foot, front to rear edge
    body_thickness: float = 3.2  # plastic core behind face F
    front_plate: float = 0.6  # metal bracket plate in front of face F
    boss_length: float = 0.6  # boss behind the core -> 0.6 + 3.2 + 0.6 = (4.4) overall
    base_width: float = 8.0  # (est) terminal block, X
    base_height: float = (
        1.2  # (est) full-depth foot height before it tapers into the core
    )

    # --- leads below the board surface ---
    lead_length: float = 3.5  # pins and bracket legs below the mounting surface
    pin_section: tuple[float, float] = (
        0.8,
        0.3,
    )  # (est) X, Y; flat, seen edge-on in the side view
    leg_section: tuple[float, float] = (
        0.5,
        2.0,
    )  # X (est, sheet metal, kinked in X), Y = 2 from the side view

    @property
    def pin_x(self) -> tuple[float, float, float]:
        """Pins A, B, C."""
        return (-self.pin_pitch, 0.0, self.pin_pitch)

    @property
    def bracket_xy(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return (
            (-self.bracket_pitch / 2, self.bracket_offset_y),
            (self.bracket_pitch / 2, self.bracket_offset_y),
        )

    @property
    def face_f_y(self) -> float:
        return self.bracket_offset_y - self.face_f_from_leg

    @property
    def body_front_y(self) -> float:
        return self.face_f_y - self.front_plate

    @property
    def body_rear_y(self) -> float:
        return self.face_f_y + self.body_thickness

    @property
    def boss_rear_y(self) -> float:
        return self.body_rear_y + self.boss_length

    @property
    def base_front_y(self) -> float:
        return self.bracket_offset_y - self.base_front_from_leg

    @property
    def base_rear_y(self) -> float:
        return self.base_front_y + self.base_depth

    @property
    def terminal_block_top(self) -> float:
        return self.mount_height - self.terminal_block_below_axis

    @property
    def bbox_min(self) -> tuple[float, float, float]:
        """Boundary box of the whole part including leads (encoder frame)."""
        return (
            -self.body_width / 2 - self.clip_protrusion,
            min(self.base_front_y, self.body_front_y),
            -self.lead_length,
        )

    @property
    def bbox_max(self) -> tuple[float, float, float]:
        return (
            self.body_width / 2 + self.clip_protrusion,
            max(self.base_rear_y, self.boss_rear_y),
            self.mount_height + self.top_above_axis,
        )


@dataclass(frozen=True)
class TactileSwitchB3FData:
    """Omron B3F 6 x 6 mm THT tactile switch, flat plunger, no ground terminal (datasheet p.4 "Standard, Flat Plunger
    Type"). Defaults = B3F-1020 (5.0 ±0.2 mm, 0.98 N); the same drawing covers B3F-1000 (4.3 mm) and B3F-102x/-1026.

    Frame = footprint Button_Switch_THT:SW_TH_Tactile_Omron_B3F-102x in build123d axes: origin at pin 1 (top-left pad in
    KiCad) on the board top surface (seating plane), X along the 6.5 mm pin pitch, Y = KiCad -y (pins 2 at Y = -4.5),
    Z up. The plunger axis is at the body centre (6.5 / 2, -4.5 / 2).
    Pins 1-1 and 2-2 (the pairs along X) are connected internally; the leads are kinked in X (7.7 over the knees,
    6.5 at the board) and seen edge-on in the YZ view.

    Catalog dimensions are exact; values marked (est) are scaled from the drawing and only matter for looks.
    """

    # --- footprint ---
    pin_pitch_x: float = 6.5
    pin_pitch_y: float = 4.5
    pin_hole_dia: float = 1.0

    # --- body ---
    body_size: float = 6.0  # square, ±0.2
    body_height: float = 3.4  # seating plane to the top of the metal cover
    cover_thickness: float = (
        0.3  # (est) metal cover plate on top of the plastic housing
    )
    stake_dia: float = 1.3  # (est) the four heat-staked bosses on the cover corners
    stake_pitch: float = 4.6  # (est)
    stake_height: float = 0.5  # (est) above the cover

    # --- plunger ---
    plunger_dia: float = 3.5
    height: float = 5.0  # plunger top above the seating plane, ±0.2 (B3F-1000: 4.3)

    # --- leads ---
    lead_length: float = 3.5  # below the seating plane
    lead_section: tuple[float, float] = (0.3, 0.7)  # X (sheet thickness), Y (width)
    lead_knee_span: float = 7.7  # ±0.5, outside of the leads at the knees
    lead_exit_height: float = 1.0  # (est) where the leads leave the housing sides
    lead_knee_z: float = -1.6  # (est) widest point below the seating plane
    lead_jog_z: float = -2.3  # (est) the jog back in to the 6.5 mm pitch ends here

    @property
    def center_xy(self) -> tuple[float, float]:
        return (self.pin_pitch_x / 2, -self.pin_pitch_y / 2)

    @property
    def pin_xy(self) -> tuple[tuple[float, float], ...]:
        """Pins 1, 1, 2, 2 (pad order of the footprint)."""
        px, py = self.pin_pitch_x, -self.pin_pitch_y
        return ((0.0, 0.0), (px, 0.0), (0.0, py), (px, py))

    @property
    def bbox_min(self) -> tuple[float, float, float]:
        """Boundary box of the whole part including leads (switch frame)."""
        cx, cy = self.center_xy
        half_x = max(self.body_size, self.lead_knee_span) / 2
        return (cx - half_x, cy - self.body_size / 2, -self.lead_length)

    @property
    def bbox_max(self) -> tuple[float, float, float]:
        cx, cy = self.center_xy
        half_x = max(self.body_size, self.lead_knee_span) / 2
        return (cx + half_x, cy + self.body_size / 2, self.height)


@dataclass(frozen=True)
class ScrollWheelAssemblyData:
    """Scroll wheel on an EC10E encoder, with a B3F switch under the round shaft (press = click) and two supports
    coming down from the case: a flat stop behind the encoder for the hex shaft tip, and a race for the round shaft
    tip behind the switch (open towards the board to allow the click, closed sideways and axially).

    Frame = encoder frame (see EncoderEC10EData): origin at encoder pin B on the board top surface, Z up. The wheel
    axis is the encoder shaft axis (along Y at Z = mount_height, X = 0): the wheel sits in front (-Y) of the encoder,
    its hex shaft pointing +Y through the rotor and its round shaft pointing -Y over the switch plunger.
    Along -Y: rear support | clearance | encoder | clearance | wheel drum | clearance | switch body | clearance |
    front support (race, then end stop).

    The wheel dimensions that have to fit the other parts (shaft lengths, shaft diameters) are derived here, see
    `wheel`; only the free ones are fields.
    """

    encoder: EncoderEC10EData = field(default_factory=EncoderEC10EData)
    switch: TactileSwitchB3FData = field(default_factory=TactileSwitchB3FData)
    wheel_diameter: float = 20.0
    wheel_width: float = 12.0
    support_width: float = 2
    # axial gap between neighbours: support <-> encoder <-> wheel drum <-> switch body <-> support
    clearance: float = (
        1.5  # round shaft underside above the plunger top; 0 = resting on it, negative = preloaded
    )
    plunger_gap: float = 0.25
    # gap all round the drum in the cover plate opening (see generate_scrollwheel_cutter)
    cover_gap: float = 0.5

    @property
    def shaft_diameter(self) -> float:
        """Round shaft, sized to sit `plunger_gap` above the plunger."""
        return 2 * (self.encoder.mount_height - self.switch.height - self.plunger_gap)

    @property
    def shaft_length(self) -> float:
        """Round shaft: over the switch, then into the race of the front support."""
        return 1 * self.clearance + self.switch.body_size

    @property
    def hex_shaft_length(self) -> float:
        """Hex shaft: through the encoder, tip on the rear support."""
        return self.rear_support_y - self.wheel_rear_y

    @property
    def wheel(self) -> ScrollWheelData:
        return ScrollWheelData(
            diameter=self.wheel_diameter,
            width=self.wheel_width,
            shaft_diameter_top=self.shaft_diameter,
            shaft_hex_diameter_bottom=self.encoder.hex_across_flats,
            shaft_length_top=self.shaft_length,
            shaft_length_bottom=self.hex_shaft_length,
            support_width=self.support_width,
        )

    @property
    def wheel_rotation(self) -> tuple[float, float, float]:
        """Wheel frame (axis on Z, hex shaft at -Z, supports towards +Y) -> assembly frame: wheel +Z onto -Y (hex
        shaft towards +Y), wheel +Y onto +Z (supports up to the case)."""
        return (90.0, 0.0, 0.0)

    @property
    def wheel_rear_y(self) -> float:
        """Drum face on the encoder side."""
        return self.encoder.bbox_min[1] - self.clearance

    @property
    def wheel_front_y(self) -> float:
        """Drum face on the switch side."""
        return self.wheel_rear_y - self.wheel_width

    @property
    def wheel_center(self) -> tuple[float, float, float]:
        return (
            0.0,
            self.wheel_rear_y - self.wheel_width / 2,
            self.encoder.mount_height,
        )

    @property
    def switch_center_xy(self) -> tuple[float, float]:
        """Plunger axis, under the wheel axis."""
        return (0.0, self.wheel_front_y - self.clearance - self.switch.body_size / 2)

    @property
    def switch_origin(self) -> tuple[float, float, float]:
        """Switch frame origin (pin 1); the switch is not rotated, its leads are spread along X."""
        cx, cy = self.switch.center_xy
        x, y = self.switch_center_xy
        return (x - cx, y - cy, 0.0)

    @property
    def rear_support_y(self) -> float:
        """Stop face of the rear support = hex shaft tip; the rotor spans encoder.face_f_y .. encoder.boss_rear_y."""
        return self.encoder.boss_rear_y + self.clearance

    @property
    def front_support_y(self) -> float:
        """Stop face of the front support = round shaft tip; the race covers the last `support_width` of the shaft."""
        return self.wheel_front_y - self.shaft_length

    @property
    def y_min(self) -> float:
        """Front end of the assembly including the supports."""
        return self.front_support_y - self.support_width

    @property
    def y_max(self) -> float:
        """Rear end of the assembly including the supports."""
        return self.rear_support_y + self.support_width

    @property
    def support_bottom_z(self) -> float:
        """Lowest point of the supports (as generated: `support_width` below the axis)."""
        return self.encoder.mount_height - self.support_width

    @property
    def wheel_bottom_z(self) -> float:
        """Lowest point of the drum; below 0 it needs a cutout in the board."""
        return self.encoder.mount_height - self.wheel_diameter / 2

    @property
    def wheel_top_z(self) -> float:
        return self.encoder.mount_height + self.wheel_diameter / 2


@dataclass(frozen=True)
class ScreenData:
    width: float = 62
    height: float = 29
    screen_width: float = 43.72
    screen_height: float = 23.7
    hole_diameter: float = 3.0
    hole_offset: float = 0.5

    @property
    def hole_pattern(self) -> list[tuple[float, float]]:
        """Returns the (x, y) positions of the mounting holes."""
        offset = self.hole_offset + self.hole_diameter / 2
        center_x = self.width / 2
        center_y = self.height / 2
        return [
            (offset - center_x, offset - center_y),
            (self.width - offset - center_x, offset - center_y),
            (self.width - offset - center_x, self.height - offset - center_y),
            (offset - center_x, self.height - offset - center_y),
        ]


@dataclass(frozen=True)
class ButtonData:
    diameter: float = 10.0
    spacing: float = 10.0
    depth: float = 10.0
    button_height: float = 1.5
    clearance: float = 0.25
    foot_add_width: float = 1.5
    foot_add_height: float = 1.5
    sleeve_width: float = 2.0
    merge_sleeve: bool = True

    @property
    def switch_positions(self) -> list[float]:
        """Returns the x positions of the switches (left, center, right)."""
        center = 0.0
        left = -self.spacing - self.diameter
        right = self.spacing + self.diameter
        return [left, center, right]
