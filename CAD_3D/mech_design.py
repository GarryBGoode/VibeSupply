"""
Single source of the mechanical reference values.

Axis convention (frames used across CAD_3D and tools/):
- Enclosure frame (build123d): origin at the centre of the extrusion, X along the length (-X = rear end cap,
  +X = front / 3D-printed add-on), Y across the width, Z up.
- Board frame (build123d): origin at the board centre on its bottom face, X/Y as the enclosure frame, Z up;
  top-side parts are above Z = thickness, bottom-side parts below Z = 0. PCBPlacement.origin() maps it into the
  enclosure frame.
- KiCad: origin at the board centre (drill/place + grid origin, tools/board_setup.py), KiCad left (-X) = rear end cap,
  Y points DOWN -> board frame = (x, -y). Rotations are counter-clockwise as seen from the top in both.
"""

from geom_defs import *

# the enclosure can be constructed by default data
enclosure_aluminum = EnclosureData()

# slot placement indices in the enclosure
# main power board on bottom, secondary control board on top (last but one)
power_pcb_slot_index = 0
control_pcb_slot_index = -2
# UI board(s) in special placement in addon

# PCB size data for the main power board
pcb_size_power = PCBSizeData(length=170, width=74.5, thickness=1.6, edge_keepout=3.0)
pcb_size_control = PCBSizeData(length=110, width=74.5, thickness=1.6, edge_keepout=3.0)

# Both boards have their rear edge at the rear end of the extrusion (rear end cap 3D printed, flush for now)
pcb_rear_gap = 0.0
pcb_placement_power = PCBPlacement(slot_index=power_pcb_slot_index, rear_gap=pcb_rear_gap)
pcb_placement_control = PCBPlacement(slot_index=control_pcb_slot_index, rear_gap=pcb_rear_gap)

# default 0,0 in center of board
nut_placement = H905_placement()

# Wall width of the endcap of the 3D print enclosure
endcap_wall_width = 1.5
