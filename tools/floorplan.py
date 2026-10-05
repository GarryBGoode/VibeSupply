"""
Floor plan + placement recipe for the supply boards (layout steps 2 and 3). Pure data; tools/place.py executes it.

Coordinates: mm, board frame = board centre (the grid/drill origin set by tools/board_setup.py), KiCad orientation:
x to the right = towards the front, y DOWN. Left (-x) = rear end cap; both boards have their rear edge there.
Power board: x -85..+85; control board: x -55..+55 (control x = power x + 30). Usable y: +-34.25 (slot keep-outs).
The aluminium extrusion ends at power x = +35; beyond that is the printed add-on. The control board covers power x <= +25.

Entries
- AREAS: name -> list of (x0, y0, x1, y1) rectangles, drawn on User.Comments; clusters are packed inside their area.
- FIXED: (ref, x, y, orient, side). (x, y) = courtyard-bbox centre. x may be "W" / "E" = flush with that board edge.
  orient = (padA, padB, dir) or a list of those: the vector padA -> padB points to dir (N/S/E/W); padA None = the
  courtyard centre. None = 0 deg. side "top" (default) / "bottom".
  y may be "N" / "S" likewise. ("E", 6.5) = the courtyard goes 6.5 mm past that edge (right-angle header).
- CLUSTERS: (name, area, anchor, [members], target[, side]). The anchor is an IC (or a FIXED part); members are placed
  next to the anchor pin they connect to (decoupling caps spread over the supply pins), then the whole cluster is moved
  as close to target (x, y) as its area allows. target None = the anchor is FIXED and stays. side "top" (default) /
  "bottom" = where the members go (and the anchor, unless it is FIXED).
  Parts in neither list get attached automatically to the cluster they share a net with (reported).

UI board: same conventions, but its frame is the front panel's (CAD_3D/geom_defs.py UIPanelData) with y negated:
x = panel x, y = -panel y, origin = panel centre. Board x -35..+35, y -38.5 (far edge, behind the display) ..+33.5.
Everything that lines up with the panel is placed and locked by tools/ui_board_setup.py and is not listed here.
"""

# ======================================================================================================== power board

POWER = dict(
    areas={
        "INPUT (USB-C PD, DC in, ideal diodes)": [(-85, -34.25, -49, 34.25)],
        "VIN SENSE + 5VA": [(-49, -34.25, -18, -17)],
        "AUX 12V (LM5164)": [(-49, 6.5, -32.5, 27.5)],
        "BUCK CONTROLLER": [(-32.5, 6.5, -2, 27.5)],
        "ANALOG CONTROL (CV/CC, OVP, DACs)": [(-2, 6.5, 25, 27.5)],
        "SENSE + LC FILTER": [(12, -34.25, 35, 6.5)],
        "OUTPUT (shunt, switch, fuse, lugs)": [(35, -34.25, 85, 6.5)],
        "CLAMP + OUTPUT SWITCH DRIVE": [(25, 6.5, 85, 34.25)],
    },
    notes=[  # (x, y, text) on User.Comments
        (-48, -5.5, "VIN_PWR bulk + half bridge (hot loop)"),
        (-17, -33, "L201 (17.8 mm tall)"),
        (-40, 26.2, "B2B J951 (control board above)"),
        (18.5, 31.5, "R419 LTO100 on the BOTTOM, H906 = its screw"),
    ],
    lines=[  # ((x0, y0), (x1, y1), text)
        ((35, -37.25), (35, 37.25), "end of aluminium"),
        ((25, -37.25), (25, 37.25), "control board front edge"),
    ],
    fixed=[
        # ---- USB-C power input: connector -> AP33772S sense shunt -> back-to-back FETs (common drain) -> VIN_BUS
        ("J101", "W", -13, (None, "A4", "E"), "top"),
        ("R101", -71.9, -13, ("1", "2", "E"), "top"),
        ("Q101", -64.2, -13, (None, "5", "E"), "top"),
        ("Q102", -56.8, -13, (None, "5", "W"), "top"),
        # ---- DC input: wire pads (THT; DCIN_RAW pad 1 at the edge, leaves on an inner layer under the GND pad),
        #      strain-relief holes south -> back-to-back FETs -> VIN_BUS
        ("J161", "W", 15.1, [("1", "2", "E"), ("1", "", "S")], "top"),
        ("Q161", -64.6, 6, (None, "5", "E"), "top"),
        ("Q162", -56.6, 6, (None, "5", "W"), "top"),
        # ---- input shunt VIN_BUS -> VIN_PWR, bulk, bus TVS
        ("R181", -47, -4.5, ("1", "2", "S"), "top"),
        ("C217", -41, -14, ("1", "2", "S"), "top"),
        ("D181", -31, -12, ("1", "2", "S"), "top"),
        # ---- hot loop: input MLCCs (VIN_PWR north, GND south) | Q202 (VIN west, SW east) over Q203 (GND west, SW east)
        ("C214", -37.1, 0, ("1", "2", "S"), "top"),
        ("C213", -33.6, 0, ("1", "2", "S"), "top"),
        ("C212", -30.1, 0, ("1", "2", "S"), "top"),
        ("C211", -26.6, 0, ("1", "2", "S"), "top"),
        ("C210", -23.1, 0, ("1", "2", "S"), "top"),
        ("C209", -19.6, 0, ("1", "2", "S"), "top"),
        ("C216", -16.0, 0, ("1", "2", "S"), "top"),
        ("C215", -14.3, 0, ("1", "2", "S"), "top"),
        ("Q202", -9.4, -3.0, (None, "5", "W"), "top"),
        ("Q203", -9.4, 3.0, (None, "5", "E"), "top"),
        ("H905", -22, -11, None, "top"),
        # ---- main inductor, pads down: pad 1 (SW) right above the FET pair, pad 2 -> sense resistors
        ("L201", -3.1, -20.05, (None, "3", "N"), "top"),
        ("R211", 6.0, -3.9, ("1", "2", "E"), "top"),
        ("R212", 6.0, 0.3, ("1", "2", "E"), "top"),
        # ---- C1 damper, post filter, output bulk
        ("C223", 17, -12.5, ("1", "2", "S"), "top"),
        ("L202", 24, -1.5, ("1", "2", "E"), "top"),
        ("C228", 29.4, -13, ("1", "2", "E"), "top"),
        # ---- output: shunt -> back-to-back switch (common source) -> fuse -> OUT+ lugs
        ("R401", 38, -3, ("1", "2", "S"), "top"),
        ("Q402", 45.5, -3, (None, "5", "W"), "top"),
        ("Q403", 53.5, -3, (None, "5", "E"), "top"),
        ("F401", 67, -3, ("1", "2", "E"), "top"),
        ("H401", 79.5, -14, None, "top"),
        ("H402", 79.5, 9, None, "top"),
        ("D403", 68, -26, (None, "1", "W"), "top"),
        ("D404", 80, -28, ("1", "2", "S"), "top"),
        # ---- regen clamp: LTO100 under the board (body + tab on the floor, inside the aluminium), leads north to
        #      VOUT_SH / the clamp FET; H906 (its screw insert) ends up near the bottom edge
        ("R419", 26.25, 19.45, ("1", "", "S"), "bottom"),
        ("Q401", 40, 10, (None, "5", "W"), "top"),
        # ---- B2B header along the bottom edge, pin 1 (LOGIC_IN) at the rear end
        ("J951", -13.5, 31.0, ("1", "3", "E"), "top"),
    ],
    aligned=[("H906", "R419")],  # H906 insert concentric with R419's tab hole (NPTH)
    clusters=[
        # input
        ("USB-C PWR in", "INPUT (USB-C PD, DC in, ideal diodes)", "J101", ["C101", "C102", "D101"], None),
        ("AP33772S PD sink", "INPUT (USB-C PD, DC in, ideal diodes)", "U101",
         ["C103", "C104", "D102", "C105", "C106", "TH101", "R102", "R103", "R104", "R105", "R106", "D103", "R107",
          "R108", "TP101", "TP102"], (-70, -26)),
        ("LM74800 USB", "INPUT (USB-C PD, DC in, ideal diodes)", "U102",
         ["C107", "C108", "R109", "R110", "R111", "TP103"], (-61, -4.5)),
        ("DC in", "INPUT (USB-C PD, DC in, ideal diodes)", "J161", ["C161", "D161"], None),
        ("LM74800 DC", "INPUT (USB-C PD, DC in, ideal diodes)", "U161",
         ["C162", "C163", "R161", "R162", "R163", "R164"], (-62, 13)),
        ("LOGIC_IN feed", "INPUT (USB-C PD, DC in, ideal diodes)", "D531", ["D532", "C531"], (-62, 27)),
        # aux + VIN sense
        ("INA228 VIN", None, "R181", ["U181", "C181", "C182", "R182", "R183"], None),
        ("LM5164 12V aux", "AUX 12V (LM5164)", "U541",
         ["C541", "C542", "R541", "R542", "R543", "C543", "L541", "R544", "R545", "R546", "C544", "C545", "C546",
          "C547", "TP541"], (-40, 17)),
        ("LP2985 +5VA", "VIN SENSE + 5VA", "U542", ["C548", "C549", "C550", "TP542"], (-21, -22)),
        # buck controller
        ("LTC7803", "BUCK CONTROLLER", "U201",
         ["C201", "R201", "D201", "C202", "C203", "R202", "R203", "C204", "C205", "C206", "R204", "R213", "R214",
          "C218", "TP201", "D202", "C207", "R208", "R209", "Q301", "R309", "C310"], (-9, 15)),
        ("SW snubber", None, "Q203", ["R210", "C208", "TP202"], None),
        ("MODE pulse-skip", "BUCK CONTROLLER", "Q201", ["R205", "R206", "R207"], (-24, 12)),
        ("NTC buck FETs", None, "Q202", ["TH201", "R218", "C231"], None),
        ("+3V3A filter", "BUCK CONTROLLER", "FB531", ["C532", "C533"], (-29, 24)),
        # analog control
        ("INA240 IL", None, "R212", ["U202", "C229", "R216", "R217", "C230"], None),
        ("CV/CC amps", "ANALOG CONTROL (CV/CC, OVP, DACs)", "U301",
         ["C304", "C305", "R304", "R305", "R306", "C306", "C307", "R307", "R308", "C308", "C309", "D301", "D302",
          "TP301", "TP302"], (8, 15)),
        ("DAC filters", "ANALOG CONTROL (CV/CC, OVP, DACs)", "R301", ["C301", "R302", "C302", "R303", "C303"],
         (14, 24)),
        ("Vout/Vterm sense", "ANALOG CONTROL (CV/CC, OVP, DACs)", "R310",
         ["R311", "C311", "R312", "R313", "C312", "D303"], (21, 12)),
        ("HW OVP", "ANALOG CONTROL (CV/CC, OVP, DACs)", "U302", ["R314", "R315", "C313", "R316", "C314"], (19, 21)),
        ("FAULT -> RUN", "BUCK CONTROLLER", "Q302",
         ["D304", "D305", "D306", "R317", "R318", "R319", "TP303", "TP304"], (-18, 23)),
        ("B2B decoupling", "BUCK CONTROLLER", "J951", ["C951", "C952"], None),
        # sense + LC filter (anchored on the fixed L201/L202)
        ("NTC inductor", None, "L201", ["TH202", "R219", "C232"], None),
        ("C1 bank + damper R", "SENSE + LC FILTER", "L202", ["C219", "C220", "C221", "C222", "R215"], None),
        ("Vout bank", "SENSE + LC FILTER", "C228", ["C224", "C225", "C226", "C227"], None),
        # output
        ("INA228 VOUT", "OUTPUT (shunt, switch, fuse, lugs)", "U401", ["C401"], (43, -11)),
        ("NTC output switch", None, "Q403", ["TH402", "R424", "C409"], None),
        ("OUT+ HF cap", "OUTPUT (shunt, switch, fuse, lugs)", "D404", ["C407"], None),
        # clamp + output switch drive
        ("Output switch drive", "CLAMP + OUTPUT SWITCH DRIVE", "Q403",
         ["U405", "R420", "Q404", "Q405", "R421", "R422", "TP402"], None),
        ("Clamp gate driver", "CLAMP + OUTPUT SWITCH DRIVE", "U404",
         ["C406", "R414", "R415", "R416", "R417", "R418", "D401", "D402", "TP401"], (46, 18)),
        ("Clamp comparator Vout", "CLAMP + OUTPUT SWITCH DRIVE", "U402",
         ["C403", "R402", "R403", "C402", "R404", "R405", "R406", "R407"], (64, 13)),
        ("Clamp comparator bus", "CLAMP + OUTPUT SWITCH DRIVE", "U403",
         ["C405", "R408", "R409", "C404", "R410", "R411", "R412", "R413"], (66, 25)),
        ("NTC clamp resistor", None, "R419", ["TH401", "R423", "C408"], None),
    ],
)

# ====================================================================================================== control board

# UI ribbon headers (J703 here, J1 on the UI board): PinHeader_2x10_P2.54mm_Horizontal. Its courtyard goes this far past
# the board edge: the plastic body ends at the edge, the 6 mm pins (+ 0.5 mm courtyard margin) and the plug are outside.
RIBBON_OVERHANG = 6.5

CONTROL = dict(
    areas={
        "ISO (PC side, GND_ISO)": [(-55, -34.25, -37.5, 34.25)],
        "LOGIC SUPPLY (LMR38010)": [(-34.5, 4, -6, 27.5)],
        "MCU": [(-34.5, -34.25, 35, 4), (-6, 4, 35, 27.5)],
        "FRONT: UI ribbon, SWD, UART, reset/boot": [(35, -28.25, 55, 21.5)],
    },
    notes=[
        (-37, 26, "PS601 B0505S on the BOTTOM (10.2 mm tall)"),
        (-6, 26.2, "B2B J971 on the BOTTOM"),
        (36, -33.5, "top side <= 5.8 mm within 6 mm of the long edges (screw bosses)"),
    ],
    lines=[
        ((-36, -37.25), (-36, 37.25), "isolation barrier (1.5 mm rule)"),
    ],
    fixed=[
        ("J601", "W", -20, (None, "A4", "E"), "top"),
        ("U602", -36, -18, ("1", "9", "E"), "top"),
        ("PS601", -36, 2, ("2", "3", "E"), "bottom"),
        # UI ribbon: right-angle header, pins towards the front (the add-on)
        ("J703", ("E", RIBBON_OVERHANG), -12, ("1", "2", "E"), "top"),
    ],
    aligned=[],
    b2b=("J971", "J951"),  # J971 (bottom) follows J951 on the power board, pins mirrored (design/interconnect.py)
    # power-board parts taller than ~12 mm: no bottom-side parts on the control board above them
    tall_below=["L201", "C217", "C223", "C228"],
    clusters=[
        ("USB-C iso in", "ISO (PC side, GND_ISO)", "J601", ["U601", "R601", "R602", "C601", "C606"], None),
        ("ADuM side 1 (PC)", "ISO (PC side, GND_ISO)", "U602", ["C602", "C604"], None),
        ("ADuM side 2 (MCU)", "MCU", "U602", ["C603", "C605"], None),
        ("B0505S out", "MCU", "PS601", ["C607", "R603"], None),
        ("LMR38010 3.3V", "LOGIC SUPPLY (LMR38010)", "U501",
         ["C501", "C502", "C503", "C504", "C505", "C506", "L501", "R501", "R502", "R503", "TP501", "D503", "D504",
          "R504"], (-20, 16)),
        ("+3V3A filter", "MCU", "FB501", ["C507", "C508"], (8, 8)),
        ("STM32G474", "MCU", "U701",
         ["C701", "C702", "C703", "C704", "C705", "C706", "C707", "C708", "C709", "R701",
          "R702", "R703", "R704", "R705", "R706", "R707",
          "R708", "R709", "R710", "R711", "R712", "R713", "R714", "R715", "R716",
          "C710", "C711", "C712", "C713", "C714", "C715", "C716", "C717", "C718"], (5, -12)),
        ("B2B decoupling", "MCU", "J971", ["C971", "C972"], None),
        ("Debug: SWD, UART, reset, boot", "FRONT: UI ribbon, SWD, UART, reset/boot", "J701",
         ["J702", "SW701", "SW702"], (44, 6)),
    ],
)

# =========================================================================================================== UI board

# The top side faces the panel: wheels, switches, LEDs (all locked, from the panel design) and, in the 9.7 mm under the
# display module, the right-angle header for the display wires. Everything else goes on the bottom side, under the
# display: that half of the board has nothing coming through from the top.
_UI_LOGIC = "BOTTOM SIDE: connectors, expander, passives (under the display)"

UI = dict(
    default_side="bottom",
    areas={
        _UI_LOGIC: [(-34, -37.5, 34, -9.5)],
    },
    notes=[
        (-33, -8.5, "top side: display module 9.7 mm above the board (y < -10.5), button sleeves and wheel"),
        (-33, -7.0, "supports 5 mm above it elsewhere; bottom side: wheels reach 1.4 mm, the on-off button 10 mm below"),
    ],
    fixed=[
        # ribbon to supply_control: right-angle header on the bottom, at the far edge (towards the enclosure), plug
        # from outside the board
        ("J1", 0, ("N", RIBBON_OVERHANG), ("1", "2", "N"), "bottom"),
        # display wires: right-angle header on the top side under the module, plug from +x (the module's header holes
        # are along its +x edge)
        ("J3", 12.4, -19.5, [(None, "1", "W"), ("1", "8", "S")], "top"),
        # OUTPUT (on-off) button wires: next to its cutout, the plug comes from below like the button's terminals
        ("J6", -24, -13.5, ("1", "4", "E"), "bottom"),
        ("BZ1", -26.5, -26, None, "bottom"),
    ],
    clusters=[
        ("Ribbon decoupling", _UI_LOGIC, "J1", ["C1", "C2"], None, "bottom"),
        ("Display backlight + bulk", _UI_LOGIC, "J3", ["R29", "C12"], None, "bottom"),
        ("OUTPUT button", _UI_LOGIC, "J6", ["R23", "R24", "C10", "R27"], None, "bottom"),
        ("Buzzer driver", _UI_LOGIC, "BZ1", ["Q1", "D6", "R28"], None, "bottom"),
        ("TCA9535", _UI_LOGIC, "U1",
         ["C9", "R15", "R16", "R17", "R18", "R19", "R20", "D5", "TP3", "TP4"],
         (21, -22), "bottom"),
        # RC debounce: series R = anchor, pull-up + cap next to it; the wheel A/B ones near the ribbon header
        ("V wheel A", _UI_LOGIC, "R2", ["R1", "C3"], (-12, -26), "bottom"),
        ("V wheel B", _UI_LOGIC, "R4", ["R3", "C4"], (-12, -20), "bottom"),
        ("I wheel A", _UI_LOGIC, "R8", ["R7", "C6"], (-3, -26), "bottom"),
        ("I wheel B", _UI_LOGIC, "R10", ["R9", "C7"], (-3, -20), "bottom"),
        ("V wheel push", _UI_LOGIC, "R6", ["R5", "C5"], (14, -34), "bottom"),
        ("I wheel push", _UI_LOGIC, "R12", ["R11", "C8"], (22, -34), "bottom"),
    ],
)

BOARDS = {"power": POWER, "control": CONTROL, "ui": UI}

# Silkscreen: reference designators stay visible only where a human needs them; the rest stay on the Fab layer
# (assembly drawing). Hidden: courtyard < SILK_MIN_AREA mm^2 unless the prefix is listed or the value is an LED.
SILK_HIDE_SMALL = True
SILK_MIN_AREA = 12.0
SILK_KEEP_PREFIX = ("U", "J", "SW", "TP", "PS", "H", "F")
