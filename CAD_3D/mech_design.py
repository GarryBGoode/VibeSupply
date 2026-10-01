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

# default 0,0 in center of board
nut_placement = H905_placement()

# Wall width of the endcap of the 3D print enclosure
endcap_wall_width = 1.5
