import math
from dataclasses import dataclass, field, replace
from typing import Literal

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
    # gap all round the drum in the board cutout (see board_cutout)
    board_gap: float = 0.5

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

    @property
    def board_cutout(self) -> tuple[float, float, float, float] | None:
        """Board cutout for the drum, (x0, y0, x1, y1) in the assembly frame: the drum's section at the board top
        surface (where it is widest) grown by `board_gap`. None if the drum stays above the board.
        """
        radius = self.wheel_diameter / 2 + self.board_gap
        if radius <= self.encoder.mount_height:
            return None
        half = math.sqrt(radius**2 - self.encoder.mount_height**2)
        return (
            -half,
            self.wheel_front_y - self.board_gap,
            half,
            self.wheel_rear_y + self.board_gap,
        )


@dataclass(frozen=True)
class ScreenData:
    """1.9" IPS display module. Frame: origin at the centre of the module pcb on its top surface, Z up (towards the
    viewer); the panel sits on the pcb top surface.

    The pcb and screen X/Y sizes are known; values marked (est) are eyeballed from pictures, to be measured on the
    real module.

    The module is wired: a short ribbon is soldered into its header holes (`pin_positions`) and plugs onto a
    right-angle pin header on the UI board, so the header position does not have to match anything on the board.
    """

    width: float = 62
    height: float = 29
    pcb_thickness: float = 1.6  # (est)
    screen_width: float = 43.72
    screen_height: float = 23.7
    screen_thickness: float = 2.3  # (est) above the pcb top surface
    hole_diameter: float = 3.0  # (est)
    hole_offset: float = 0.5  # (est) hole edge to pcb edge
    # pin header: a row along Y near the +X edge of the pcb, centred on Y
    pin_count: int = 8
    pin_pitch: float = 2.54
    pin_edge_offset: float = 2.0  # (est) row centre line to the pcb edge
    # panel opening: gap all round the screen, and a lead-in chamfer on the pcb side of the opening
    opening_clearance: float = 0.3
    opening_chamfer: float = 1.0

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

    @property
    def pin_positions(self) -> tuple[tuple[float, float], ...]:
        """Pins 1..pin_count; pin 1 (GND) at the +Y end (est: to be checked on the real module)."""
        x = self.width / 2 - self.pin_edge_offset
        y1 = (self.pin_count - 1) * self.pin_pitch / 2
        return tuple((x, y1 - i * self.pin_pitch) for i in range(self.pin_count))


@dataclass(frozen=True)
class ButtonData:
    diameter: float = 10
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


@dataclass(frozen=True)
class ButtonAssemblyData:
    """Three buttons in a row, each resting on the plunger of a B3F switch, guided by sleeves coming down from the
    panel.

    Frame: origin on the board top surface under the centre button axis, X along the row, Z up. The switches are
    not rotated (leads spread along X), their plunger axes are on the button pressure points
    (ButtonData.switch_positions).

    The button length is derived here from the panel height, see `buttons`; `depth` of button_style is ignored.
    """

    button_style: ButtonData = field(default_factory=ButtonData)
    switch: TactileSwitchB3FData = field(default_factory=TactileSwitchB3FData)
    # panel front face above the board top surface
    panel_height: float = 15.0
    # button foot above the plunger top; 0 = resting on it
    plunger_gap: float = 0.0

    @property
    def button_z(self) -> float:
        """Buttons origin = bottom of the button feet and sleeves, above the board."""
        return self.switch.height + self.plunger_gap

    @property
    def buttons(self) -> ButtonData:
        return replace(self.button_style, depth=self.panel_height - self.button_z)

    @property
    def switch_origins(self) -> tuple[tuple[float, float, float], ...]:
        """Switch frame origins (pin 1) of the left, centre and right switch."""
        cx, cy = self.switch.center_xy
        return tuple((x - cx, -cy, 0.0) for x in self.buttons.switch_positions)


@dataclass(frozen=True)
class BoardScrewData:
    """Screw that holds the UI board against a boss on the back of the panel. It goes in from behind the board, into
    a heat-set insert in the end of the printed boss.

    Frame: origin on the board top surface (= end of the boss) on the screw axis, Z up towards the panel.
    """

    size: str = "M3-0.5"
    length: float = 8.0
    # bd_warehouse PanHeadScrew; iso14583 = pan head, torx
    fastener_type: Literal["iso1580", "iso14583", "asme_b_18.6.3"] = "iso14583"
    # bd_warehouse HeatSetNut; McMaster-Carr M3 Standard = 4.7 dia x 5.7 long
    insert_size: str = "M3-0.5-Standard"
    insert_type: Literal["McMaster-Carr", "Hilitchi"] = "McMaster-Carr"
    # hole the insert is melted into; also clears the screw tip behind the insert
    insert_hole_diameter: float = 4.0
    # hole deeper than the insert and the screw tip
    hole_margin: float = 1.0
    boss_diameter: float = 8.0
    # clearance hole in the board
    board_hole_diameter: float = 3.2
    # no components on the board bottom side: screw head (5.6) + room for the driver
    head_keepout_diameter: float = 7.0
    board_thickness: float = 1.6
    # boss length: board top surface up to the back of the panel plate
    boss_height: float = 12.0


@dataclass(frozen=True)
class LedData:
    """3 mm round THT LED (T-1), standing off the board on its leads so that the dome reaches through the panel.

    Frame: origin on the board top surface midway between the two leads, leads along X, Z up.
    Footprint supply1:LED_D3.0mm_Standoff in this frame: pad 1 (cathode) at -X, pad 2 at +X, see `pad_xy`.
    Values marked (est) are typical T-1 dimensions, to be measured on the real part.
    """

    body_diameter: float = 3.0
    body_height: float = 5.3  # (est) bottom of the flange to the top of the dome
    flange_diameter: float = 3.8  # (est)
    flange_height: float = 1.0  # (est)
    pin_pitch: float = 2.54
    lead_section: float = 0.5  # (est) square
    # leads as supplied, from the body
    lead_length: float = 25.0
    # leads below the board top surface, after soldering and trimming
    lead_protrusion: float = 3.5
    # bottom of the body above the board top surface
    standoff: float = 5.0
    # radial gap around the body in the panel hole
    hole_clearance: float = 0.1

    @property
    def top_z(self) -> float:
        return self.standoff + self.body_height

    @property
    def lead_length_used(self) -> float:
        """Has to fit in lead_length."""
        return self.standoff + self.lead_protrusion

    @property
    def hole_diameter(self) -> float:
        return self.body_diameter + 2 * self.hole_clearance

    @property
    def pad_xy(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """Pads 1, 2; pad 1 is the footprint origin."""
        return ((-self.pin_pitch / 2, 0.0), (self.pin_pitch / 2, 0.0))


@dataclass(frozen=True)
class PowerButtonData:
    """12 mm panel-mount metal push button with an illuminated ring (datasheets/powerbutton/powerbutton_dims.webp).
    It goes in from the front of the panel and is clamped by the nut from behind.

    Frame: origin on the button axis on the panel front face (where the seal sits), Z out of the panel towards the
    user. X along the 5.5 mm terminal pair, Y along the 7.25 mm pair; the nut is drawn with two corners on X, as in
    the drawing.
    Along -Z: head | seal | panel | nut | rest of the thread | plastic body (collar, then switch block) | terminals.

    Dimensioned values are exact; values marked (est) are scaled from the drawing and only matter for looks / a
    little clearance. The drawing is not to scale along the axis (the thread is drawn about 3.4 mm short, as for a
    shorter variant), so the body length is derived from the dimensioned overall length, see `body_length`.
    The two side views draw both terminal pairs at the same spacing, but dimension them 5.5 and 7.25: to be
    measured on the real part, as is which pair is the switch and which the LED.
    """

    # --- panel ---
    hole_diameter: float = 12.0  # borehole, from the webshop
    panel_thickness: float = 2.0  # sets the nut position

    # --- head (bezel) ---
    head_diameter: float = 13.8
    head_height: float = 1.5  # (est)
    head_chamfer: tuple[float, float] = (1.2, 0.8)  # (est) radial, axial
    seal_diameter: float = 13.5  # (est) O-ring between the head and the panel
    seal_thickness: float = 1.0  # (est) as drawn, i.e. not compressed

    # --- button ---
    button_diameter: float = 9.0  # including the illuminated ring
    ring_width: float = 1.0  # (est)
    button_protrusion: float = 0.0  # (est) above the head; drawn flush

    # --- thread and nut ---
    thread_diameter: float = 12.0  # M12
    thread_pitch: float = 0.75  # (est) fine pitch; only used for the detailed model
    thread_length: float = 13.0  # from the underside of the head
    nut_across_flats: float = 13.9
    nut_across_corners: float = (
        15.7  # less than a sharp hexagon (16.05): the corners are turned off
    )
    nut_thickness: float = 2.0  # (est)

    # --- plastic body behind the thread ---
    overall_length: float = 27.6  # top of the head to the terminal tips
    collar_diameter: float = 10.8  # (est)
    collar_height: float = 3.4  # (est)
    body_diameter: float = 9.5  # (est) switch block, simplified to a cylinder

    # --- terminals (solder lugs) ---
    terminal_length: float = 4.0
    terminal_width: float = 2.0
    terminal_thickness: float = 0.5
    terminal_pitch_x: float = (
        5.5  # pair seen edge-on in the left side view; flat faces towards the axis
    )
    terminal_pitch_y: float = 7.25
    terminal_hole: tuple[float, float] = (0.7, 1.4)  # (est) slot width, length
    terminal_hole_offset: float = 2.5  # (est) slot centre below the body
    terminal_tip_chamfer: float = 0.4  # (est)

    @property
    def head_bottom_z(self) -> float:
        return self.seal_thickness

    @property
    def head_top_z(self) -> float:
        return self.seal_thickness + self.head_height

    @property
    def button_top_z(self) -> float:
        return self.head_top_z + self.button_protrusion

    @property
    def nut_top_z(self) -> float:
        """The nut sits against the back of the panel."""
        return -self.panel_thickness

    @property
    def nut_bottom_z(self) -> float:
        return self.nut_top_z - self.nut_thickness

    @property
    def thread_end_z(self) -> float:
        """End of the metal housing = top of the plastic body."""
        return self.head_bottom_z - self.thread_length

    @property
    def tip_z(self) -> float:
        """Terminal tips = rear end of the part."""
        return self.head_top_z - self.overall_length

    @property
    def body_bottom_z(self) -> float:
        return self.tip_z + self.terminal_length

    @property
    def body_length(self) -> float:
        """Plastic body, collar included: what is left of overall_length."""
        return self.thread_end_z - self.body_bottom_z

    @property
    def depth_behind_panel(self) -> float:
        """Space needed behind the panel front face, without the wires."""
        return -self.tip_z

    @property
    def max_panel_thickness(self) -> float:
        """With the nut fully on the thread."""
        return self.thread_length - self.seal_thickness - self.nut_thickness

    @property
    def terminal_xy(self) -> tuple[tuple[float, float], ...]:
        """X pair (-X, +X), then Y pair (-Y, +Y)."""
        x, y = self.terminal_pitch_x / 2, self.terminal_pitch_y / 2
        return ((-x, 0.0), (x, 0.0), (0.0, -y), (0.0, y))


@dataclass(frozen=True)
class PanelPlacement:
    """Where a UI element sits on the front panel: its origin in the panel frame (see UIPanelData) and its rotation
    about Z (degrees, counter-clockwise seen from the front)."""

    x: float = 0.0
    y: float = 0.0
    rotation: float = 0.0

    def locate(self, x: float, y: float, rotation: float = 0.0) -> "PanelPlacement":
        """A point (and orientation) given in the frame of the placed element -> panel frame."""
        a = math.radians(self.rotation)
        c, s = math.cos(a), math.sin(a)
        return PanelPlacement(
            self.x + c * x - s * y, self.y + s * x + c * y, self.rotation + rotation
        )


@dataclass(frozen=True)
class BoardArea:
    """Rounded rectangle on the UI board (outline, cutout or keep-out): `width` along its own X, `height` along its
    own Y, centred on (x, y) in the panel frame, rotated about Z like a PanelPlacement. A circle when
    width = height = 2 * corner_radius."""

    x: float
    y: float
    width: float
    height: float
    corner_radius: float = 0.0
    rotation: float = 0.0

    @classmethod
    def circle(cls, x: float, y: float, diameter: float) -> "BoardArea":
        return cls(x, y, diameter, diameter, diameter / 2)

    @property
    def is_circle(self) -> bool:
        return self.width == self.height == 2 * self.corner_radius


@dataclass(frozen=True)
class UIPanelData:
    """Front panel with the screen, the three buttons and the scroll wheels behind it.

    Panel frame: origin at the panel centre on its front (outer) face, X across the width, Y up, Z out of the panel
    towards the user. The plate is Z = -thickness .. 0, the UI board top surface is at Z = board_z.

    The depths that have to fit the other parts are derived here: the board depth from how far the wheels stick out
    of the panel, the button length from the board depth (see `buttons`); only the free ones are fields.

    The UI board is held against bosses on the back of the panel by screws from behind (see BoardScrewData).
    The LEDs stand on the board and reach through holes in the plate (see LedData).
    The on-off button is clamped in the plate and is wired, it does not sit on the board (see PowerButtonData).

    UI board: its top surface faces the panel, so seen from the front of the panel it reads like the KiCad top view
    (KiCad x = panel x, KiCad y = -panel y, rotations counter-clockwise in both). Its outline, cutouts, keep-outs and
    the footprints that have to line up with the panel are derived here (`board_*`); tools/ui_board_setup.py puts
    them on the KiCad board.
    """

    width: float = 75.0
    height: float = 80.0
    thickness: float = 2.0
    offset_y: float = +5.0

    # screen module: centre of the module pcb, pcb top surface against the back of the plate
    screen: ScreenData = field(default_factory=ScreenData)
    screen_placement: PanelPlacement = PanelPlacement(0, 25)

    # scroll wheels: encoder frame origin (pin B, on the wheel axis); rotated so the encoders are on the outside
    scrollwheel: ScrollWheelAssemblyData = field(
        default_factory=ScrollWheelAssemblyData
    )
    scrollwheel_placements: tuple[PanelPlacement, ...] = (
        PanelPlacement(-23.5, -19, 90),
        PanelPlacement(23.5, -19, -90),
    )
    # height that the wheel raises above the panel level
    wheel_protrusion: float = 3.7

    # buttons: centre of the centre button; `depth` of button_style is ignored, see `buttons`
    button_style: ButtonData = field(
        default_factory=lambda: ButtonData(
            spacing=5, foot_add_height=1, foot_add_width=1, sleeve_width=1
        )
    )
    button_switch: TactileSwitchB3FData = field(default_factory=TactileSwitchB3FData)
    button_placement: PanelPlacement = PanelPlacement(7, 1)

    # UI board screws: left and right of the buttons, and in the centre below the scroll wheels;
    # `board_thickness` and `boss_height` of screw_style are ignored, see `screw`
    board_thickness: float = 1.6
    screw_style: BoardScrewData = field(default_factory=BoardScrewData)
    screw_placements: tuple[PanelPlacement, ...] = (
        PanelPlacement(30, -7.5),
        PanelPlacement(0, -10),
        PanelPlacement(0, -30),
    )

    # LEDs: below the screen module, near the two sides; `standoff` of led_style is ignored, see `led`
    led_style: LedData = field(default_factory=LedData)
    led_placements: tuple[PanelPlacement, ...] = (
        PanelPlacement(-25, -27.0),
        PanelPlacement(25, -27.0),
    )
    # height that the LED dome raises above the panel level
    led_protrusion: float = 2.3

    # on-off button: toggles the output on and off (sold as a "power button", hence PowerButtonData; the actual
    # power switch is a separate part); button axis, mounted in the plate itself.
    # `panel_thickness` of onoff_button_data is ignored, see `onoff_button`
    onoff_button_placement: PanelPlacement = PanelPlacement(-25, 1)

    onoff_button_data: PowerButtonData = field(default_factory=PowerButtonData)

    # UI board outline: centred on X like the panel
    board_width: float = 70.0
    board_height: float = 72.0
    board_offset_y: float = 2.5
    board_corner_radius: float = 2.0
    # inside corners of the cutouts (milling)
    board_cutout_radius: float = 1.0
    # radial gap around the on-off button's thread (its widest part behind the nut) in its board cutout: the board
    # goes over the mounted button, the nut does not pass
    onoff_board_gap: float = 1.0

    @property
    def board_depth(self) -> float:
        """UI board top surface below the panel front face, set by the wheels."""
        return self.scrollwheel.wheel_top_z - self.wheel_protrusion

    @property
    def buttons(self) -> ButtonAssemblyData:
        return ButtonAssemblyData(
            button_style=self.button_style,
            switch=self.button_switch,
            panel_height=self.board_depth,
        )

    @property
    def screw(self) -> BoardScrewData:
        """Bosses from the back of the plate down to the board top surface."""
        return replace(
            self.screw_style,
            board_thickness=self.board_thickness,
            boss_height=self.board_depth - self.thickness,
        )

    @property
    def led(self) -> LedData:
        return replace(
            self.led_style,
            standoff=self.board_depth
            + self.led_protrusion
            - self.led_style.body_height,
        )

    @property
    def onoff_button(self) -> PowerButtonData:
        return replace(self.onoff_button_data, panel_thickness=self.thickness)

    @property
    def board_z(self) -> float:
        """Origin of everything that sits on the UI board (scroll wheels, buttons, screws, LEDs) = board top surface."""
        return -self.board_depth

    @property
    def screen_z(self) -> float:
        """Screen origin = top surface of the module pcb."""
        return -self.thickness

    @property
    def screen_gap(self) -> float:
        """UI board top surface to the underside of the screen module pcb: the room for its wires, and for what
        sits on the board under the screen."""
        return self.board_depth - self.thickness - self.screen.pcb_thickness

    # --- UI board ---

    @property
    def board_outline(self) -> BoardArea:
        return BoardArea(
            0.0,
            self.board_offset_y,
            self.board_width,
            self.board_height,
            self.board_corner_radius,
        )

    @property
    def board_cutouts(self) -> dict[str, BoardArea]:
        """Openings in the board: under the wheel drums, and around the on-off button."""
        out = {}
        cutout = self.scrollwheel.board_cutout
        if cutout:
            x0, y0, x1, y1 = cutout
            for i, p in enumerate(self.scrollwheel_placements, start=1):
                c = p.locate((x0 + x1) / 2, (y0 + y1) / 2)
                out[f"wheel_{i}"] = BoardArea(
                    c.x, c.y, x1 - x0, y1 - y0, self.board_cutout_radius, c.rotation
                )
        p = self.onoff_button_placement
        diameter = self.onoff_button.thread_diameter + 2 * self.onoff_board_gap
        out["onoff_button"] = BoardArea.circle(p.x, p.y, diameter)
        return out

    @property
    def board_keepouts(self) -> dict[str, BoardArea]:
        """No components on the board top side: where the screw bosses sit on the board."""
        return {
            f"boss_{i}": BoardArea.circle(p.x, p.y, self.screw.boss_diameter)
            for i, p in enumerate(self.screw_placements, start=1)
        }

    @property
    def board_keepouts_bottom(self) -> dict[str, BoardArea]:
        """No components on the board bottom side: the screw heads."""
        return {
            f"screw_head_{i}": BoardArea.circle(
                p.x, p.y, self.screw.head_keepout_diameter
            )
            for i, p in enumerate(self.screw_placements, start=1)
        }

    @property
    def board_footprints(self) -> dict[str, PanelPlacement]:
        """Footprint origins (and rotations) of the parts that have to line up with the panel. The footprint frames
        are those of the component dataclasses: encoder, tact switch, LED (pad 1); the screws are plain mounting
        holes."""
        out = {}
        for i, p in enumerate(self.scrollwheel_placements, start=1):
            out[f"wheel_{i}.encoder"] = p
            out[f"wheel_{i}.switch"] = p.locate(*self.scrollwheel.switch_origin[:2])
        names = ("left", "center", "right")
        for name, origin in zip(names, self.buttons.switch_origins):
            out[f"button.{name}"] = self.button_placement.locate(*origin[:2])
        for i, p in enumerate(self.screw_placements, start=1):
            out[f"screw_{i}"] = p
        for i, p in enumerate(self.led_placements, start=1):
            out[f"led_{i}"] = p.locate(*self.led.pad_xy[0])
        return out

    @property
    def board_pads(self) -> dict[str, dict[str, list[tuple[float, float]]]]:
        """Where the pads of the board_footprints have to end up (panel frame), by pad number: lets the KiCad side
        check that footprint and component model agree (pin order, mirroring, rotation).
        """

        def located(p: PanelPlacement, pads) -> dict[str, list[tuple[float, float]]]:
            out: dict[str, list[tuple[float, float]]] = {}
            for number, (x, y) in pads:
                q = p.locate(x, y)
                out.setdefault(number, []).append((q.x, q.y))
            return out

        def switch_pads(switch: TactileSwitchB3FData):
            return list(zip(("1", "1", "2", "2"), switch.pin_xy))

        out = {}
        encoder = self.scrollwheel.encoder
        encoder_pads = [(n, (x, 0.0)) for n, x in zip("ABC", encoder.pin_x)]
        encoder_pads += [("MP", xy) for xy in encoder.bracket_xy]
        for i, p in enumerate(self.scrollwheel_placements, start=1):
            out[f"wheel_{i}.encoder"] = located(p, encoder_pads)
            origin = p.locate(*self.scrollwheel.switch_origin[:2])
            out[f"wheel_{i}.switch"] = located(
                origin, switch_pads(self.scrollwheel.switch)
            )
        names = ("left", "center", "right")
        for name, origin in zip(names, self.buttons.switch_origins):
            q = self.button_placement.locate(*origin[:2])
            out[f"button.{name}"] = located(q, switch_pads(self.button_switch))
        for i, p in enumerate(self.led_placements, start=1):
            out[f"led_{i}"] = located(p, zip(("1", "2"), self.led.pad_xy))
        return out
