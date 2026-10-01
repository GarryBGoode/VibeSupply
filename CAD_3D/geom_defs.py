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
class H905_placement:
    """Placement of H905 nut on the PCB."""

    x: float = -25
    y: float = 0
