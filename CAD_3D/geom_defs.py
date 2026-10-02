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
class PCBSizeData:
    length: float = 170
    width: float = 75
    thickness: float = 1.6
    edge_keepout: float = 3.5


@dataclass(frozen=True)
class PCBPlacement:
    """Where a board sits in the enclosure: resting on the bottom of slot `slot_index`, centred across the width,
    with its rear edge `rear_gap` in front of the rear end of the extrusion (enclosure -X end)."""

    slot_index: int
    rear_gap: float = 0

    def origin(self, enclosure: "EnclosureData", pcb: PCBSizeData) -> tuple[float, float, float]:
        """Board frame origin (board centre, bottom face) in the enclosure frame."""
        x = -enclosure.length / 2 + self.rear_gap + pcb.length / 2
        z = -enclosure.inside_height / 2 + enclosure.slot_position_from_case_bottom[self.slot_index]
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
    The shaft axis runs along Y at Z = mount_height, X = 0. +Y is the shaft-insert face ("F" in the catalog), the side
    the bracket legs are on.

    Catalog dimensions are exact; values marked (est) are scaled from the drawing (which is drawn at H = 9 mm and
    reused for all heights) and only matter for looks / a little clearance.
    """

    # --- footprint (catalog "Mounting Hole Dimensions") ---
    pin_pitch: float = 2.5
    pin_hole_dia: float = 1.0
    bracket_pitch: float = 9.0  # 10.8 outer - 1.8 slot
    bracket_offset_y: float = 2.0  # bracket slot centres in front of (+Y) the pin row
    bracket_slot: tuple[float, float] = (1.8, 2.1)  # X, Y

    # --- shaft / rotor ---
    mount_height: float = 7.0  # H: shaft axis above the mounting surface
    hex_across_flats: float = 1.73  # +0.05/0
    rotor_dia: float = 2.98  # rotor ring seen in the front view
    rear_bore_dia: float = 2.2  # round bore at the rear (-Y) end of the rotor
    hex_end_depth: float = 1.7  # from face F: flared/hex part, then the round rear bore
    boss_dia: float = 3.6  # bearing boss on the rear face

    # --- body, front view (XZ) ---
    body_width: float = 9.8  # metal frame, X
    top_above_axis: float = 3.6  # arch top above the shaft axis
    terminal_block_below_axis: float = 5.0  # top of the terminal block below the axis
    arch_radius: float = 3.9  # (est) arch centred on the axis
    shoulder_above_axis: float = 1.2  # (est) flat frame shoulders either side of the arch
    clip_protrusion: float = 0.3  # (est) bracket clips at axis height stick out beyond the 9.8 frame, each side

    # --- body, side view (YZ), Y measured from the pin row ---
    face_f_y: float = 2.4  # ±0.3, face F (shaft entry) in front of the pin row
    body_thickness: float = 3.2  # plastic core behind face F
    front_plate: float = 0.6  # metal bracket plate in front of face F
    boss_length: float = 0.6  # boss behind the core -> 0.6 + 3.2 + 0.6 = (4.4) overall
    base_front_y: float = 3.7  # foot of the terminal block, front edge
    base_rear_y: float = -2.4  # 6.1 - 3.7
    base_width: float = 8.0  # (est) terminal block, X
    base_height: float = 1.2  # (est) full-depth foot height before it tapers into the core

    # --- leads below the board surface ---
    lead_length: float = 3.5  # pins and bracket legs below the mounting surface
    pin_section: tuple[float, float] = (0.7, 0.5)  # (est) X, Y
    leg_section: tuple[float, float] = (0.5, 1.6)  # (est) X, Y, sheet metal

    @property
    def pin_x(self) -> tuple[float, float, float]:
        """Pins A, B, C."""
        return (-self.pin_pitch, 0.0, self.pin_pitch)

    @property
    def bracket_xy(self) -> tuple[tuple[float, float], tuple[float, float]]:
        return ((-self.bracket_pitch / 2, self.bracket_offset_y), (self.bracket_pitch / 2, self.bracket_offset_y))

    @property
    def body_front_y(self) -> float:
        return self.face_f_y + self.front_plate

    @property
    def body_rear_y(self) -> float:
        return self.face_f_y - self.body_thickness

    @property
    def boss_rear_y(self) -> float:
        return self.body_rear_y - self.boss_length

    @property
    def terminal_block_top(self) -> float:
        return self.mount_height - self.terminal_block_below_axis

    @property
    def bbox_min(self) -> tuple[float, float, float]:
        """Boundary box of the whole part including leads (encoder frame)."""
        return (
            -self.body_width / 2 - self.clip_protrusion,
            min(self.base_rear_y, self.boss_rear_y),
            -self.lead_length,
        )

    @property
    def bbox_max(self) -> tuple[float, float, float]:
        return (
            self.body_width / 2 + self.clip_protrusion,
            max(self.base_front_y, self.body_front_y),
            self.mount_height + self.top_above_axis,
        )
