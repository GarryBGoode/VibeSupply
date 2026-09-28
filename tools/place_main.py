"""
Initial placement for the main board: groups the parts by function and packs them around their IC.

Run with KiCad's Python (KiCad must NOT have the board open, or it will overwrite the result):
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/place_main.py

What it does
- Draws a placeholder 210 x 125 mm Edge.Cuts outline (only if the board has none yet).
- Places the power path explicitly (connectors on the rear/front edges, half bridge, inductor, filter chain).
- Packs every functional cluster (IC + its passives) into a compact box inside its block region.
- Wraps each cluster in a KiCad group named "place:<block>/<cluster>" with a label on User.Comments,
  and draws the block regions on User.Comments.
Re-running removes its own groups/labels first and moves every footprint again, so it will undo manual placement.

Floor plan (x right, y down; rear panel = left edge, front panel = right edge):
    +-----------+----+--------------------------------+------------+
    | USB-C PD  | IN | buck: caps | FETs | L | filter  |  output    |
    |-----------|SNS |          controller / INA240     |  stage     |
    | DC in     |    |                                  |            |
    +------+----+----+-----------+----------+-----------+  (fuse,    |
    |USB   | housekeeping        |   MCU    | control   |   switch,  |
    |iso   | (3V3, 12V, 5VA, fan)| + ribbon | (CV/CC)   |   terminals)|
    +------+---------------------+----------+-----------+------------+
"""

import math
import re
import sys
from pathlib import Path

import pcbnew

PCB = Path(__file__).resolve().parents[1] / "kicad/supply_main/supply_main/supply_main.kicad_pcb"

X0, Y0 = 50.0, 40.0           # board origin on the sheet (mm)
BW, BH = 210.0, 125.0         # placeholder board size
GAP_IN = 0.8                  # courtyard gap inside a cluster
GAP_OUT = 2.0                 # gap between clusters
LABEL_H = 1.4                 # room for the cluster label above each cluster
TAG = "place:"

# ---------------------------------------------------------------- floor plan (board-relative mm)
REGIONS = {
    "usb_pd_input": (0, 0, 48, 45),
    "dc_input": (0, 45, 48, 30),
    "input_sense": (48, 0, 11, 75),
    "buck": (59, 0, 96, 75),
    "output_stage": (155, 0, 55, 125),
    "usb_isolated": (0, 75, 36, 50),
    "housekeeping": (36, 75, 44, 50),
    "mcu": (80, 75, 45, 50),
    "control": (125, 75, 30, 50),
}

# ---------------------------------------------------------------- clusters: (name, [refs]); first ref = anchor
R = lambda a, b, p="C": [f"{p}{i}" for i in range(a, b + 1)]

CLUSTERS = {
    "usb_pd_input": [
        ("USB-C PWR in", ["C101", "C102", "D101"]),
        ("AP33772S PD sink", ["U101", "C103", "C104", "D102", "C105", "C106", "TH101", "R102", "R103", "R104",
                              "R105", "R106", "D103", "R107", "R108", "TP101", "TP102"]),
        ("USB sink switch LM74800", ["U102", "C107", "C108", "R109", "R110", "R111", "TP103"]),
    ],
    "dc_input": [
        ("LM74800 DC", ["U161", "C162", "C163", "R161", "R162", "R163", "R164"]),
    ],
    "input_sense": [
        ("INA228 VIN", ["U181", "C181", "R182", "R183", "C182"]),
    ],
    "buck": [
        ("Gate R / boost / snubber", ["R208", "R209", "R210", "C208", "TP202", "C207", "D202"]),
        ("LTC7803 controller", ["U201", "C201", "R201", "D201", "C202", "C203", "R202", "R203", "C204", "C205",
                                "C206", "R204", "R213", "R214", "C218", "TP201"]),
        ("MODE pulse-skip/FCM", ["Q201", "R205", "R206", "R207"]),
        ("INA240 IL", ["U202", "C229", "R216", "R217", "C230"]),
        ("NTC buck FETs", ["TH201", "R218", "C231"]),
        ("NTC inductor", ["TH202", "R219", "C232"]),
    ],
    "output_stage": [
        ("Output switch drive VOM1271", ["U405", "R420", "Q404", "Q405", "R421", "R422", "TP402"]),
        ("Output INA228", ["U401", "C401"]),
        ("Clamp gate driver UCC27511", ["U404", "C406", "R414", "R415", "R416", "R417", "R418", "D401", "D402",
                                        "TP401"]),
        ("Clamp comparator Vout", ["U402", "C403", "R402", "R403", "C402", "R404", "R405", "R406", "R407"]),
        ("Clamp comparator bus", ["U403", "C405", "R408", "R409", "C404", "R410", "R411", "R412", "R413"]),
        ("NTC clamp resistor", ["TH401", "R423", "C408"]),
        ("NTC output switch", ["TH402", "R424", "C409"]),
    ],
    "usb_isolated": [
        ("USB ESD + CC", ["U601", "R601", "R602", "C601", "C606"]),
        ("ADuM side1", ["C602", "C604"]),
        ("ADuM side2", ["C603", "C605"]),
        ("B0505S out", ["C607", "R603"]),
    ],
    "housekeeping": [
        ("LOGIC_IN diode-OR", ["D501", "D502", "D503", "C501", "C502", "C503"]),
        ("LMR38010 3.3V", ["U501", "R501", "C504", "L501", "R502", "R503", "C505", "C506", "TP501"]),
        ("+3V3A filter", ["FB501", "C507", "C508"]),
        ("Power LED", ["D504", "R504"]),
        ("LM5164 12V aux", ["U541", "C541", "C542", "R541", "R542", "R543", "C543", "L541", "R544", "R545",
                            "R546", "C544", "C545", "C546", "C547", "TP541"]),
        ("LP2985 +5VA", ["U542", "C548", "C549", "C550", "TP542"]),
        ("Fan (DNP)", ["J581", "Q581", "R581", "R582", "R583"]),
    ],
    "mcu": [
        ("STM32G474 + decoupling", ["U701", "C701", "C702", "C703", "C704", "C705", "C706", "C707", "C708",
                                    "C709", "R701"]),
        ("I2C / IRQ pull-ups", R(702, 707, "R")),
        ("Debug: SWD, UART, RESET, BOOT", ["J701", "J702", "SW701", "SW702"]),
    ],
    "control": [
        ("CV/CC amps ADA4522-2", ["U301", "C304", "C305", "R304", "R305", "R306", "C306", "C307", "R307", "R308",
                                  "C308", "C309", "D301", "D302", "TP301", "TP302"]),
        ("DAC setpoint filters", ["R301", "C301", "R302", "C302", "R303", "C303"]),
        ("ITH PNP clamp + ITH_MON", ["Q301", "R309", "C310"]),
        ("Vout / Vterm sense", ["R310", "R311", "C311", "R312", "R313", "C312", "D303"]),
        ("HW OVP comparator", ["U302", "R314", "R315", "C313", "R316", "C314"]),
        ("FAULT -> RUN logic", ["D304", "D305", "D306", "R317", "TP303", "R318", "R319", "Q302", "TP304"]),
    ],
}

# ---------------------------------------------------------------- explicit placement (board-relative bbox centre)
# (ref, x, y, rot) — rot in degrees; bbox centre of the rotated courtyard lands on (x, y)
BX = REGIONS["buck"][0]
OX = REGIONS["output_stage"][0]
EXPLICIT = [
    # ---- buck hot loop: bulk + MLCC bank | half bridge | main inductor
    ("C217", BX + 7, 8, 0),
    *[(f"C{209 + i}", BX + 16 + 5 * (i % 2), 3.5 + 3.8 * (i // 2), 0) for i in range(6)],
    ("C215", BX + 16, 15.5, 0), ("C216", BX + 21, 15.5, 0),
    ("Q202", BX + 29.5, 7, 0), ("Q203", BX + 29.5, 15.5, 0),
    ("L201", BX + 51.5, 16, 0),
    # ---- sense resistors, C1 bank + damper, post filter, C2 bank + polymer
    ("R211", BX + 72, 4, 0), ("R212", BX + 72, 8.5, 0),
    ("C223", BX + 90, 7.5, 0), ("R215", BX + 81, 5, 90),
    *[(f"C{219 + i}", BX + 70.5 + 5 * (i % 2), 13.5 + 3.8 * (i // 2), 0) for i in range(4)],
    ("L202", BX + 76, 27, 0),
    *[(f"C{224 + i}", BX + 70.5 + 5 * (i % 2), 36 + 3.8 * (i // 2), 0) for i in range(4)],
    ("C228", BX + 89, 38, 0),
    ("H905", BX + 7, 24, 0),               # GND screw next to the half bridge / extrusion contact
    # ---- input sense shunt between the ORing paths and VIN_PWR
    ("R181", 53.5, 40, 90),
    ("D181", 53.5, 70, 90),               # bus TVS (SMBJ33A) on VIN_PWR
    # ---- USB-C: AP33772S sense resistor next to the connector, sink switch FETs
    ("R101", 17, 4, 0),
    ("Q101", 43.5, 29, 90), ("Q102", 43.5, 38.5, 90),
    # ---- DC input power path
    ("Q161", 28.5, 52.5, 0), ("Q162", 28.5, 64, 0),
    ("D161", 6, 70, 0), ("C161", 14, 70, 0),
    # ---- output stage power path
    ("R401", OX + 4, 48, 90),
    ("Q402", OX + 15.5, 41, 0), ("Q403", OX + 15.5, 53, 0),
    ("F401", OX + 29, 47, 90),
    ("D403", OX + 34, 30, 0), ("C407", OX + 34, 37.5, 0),
    ("D404", OX + 30, 69, 0),
    ("H401", OX + 48, 28, 0), ("H402", OX + 48, 70, 0),
    ("R419", OX + 17, 4, 0),               # 2R LTO100 along the top edge -> screwed to the extrusion
    ("Q401", OX + 17, 11, 0),
    # ---- isolated USB: barrier through U602 / PS601
    ("U602", 20, 84, 0), ("PS601", 20, 101, None),
    # ---- MCU
    ("J703", 102.5, BH - 6, 90),
    # ---- mounting holes in the corners
    ("H901", 4, 4, 0), ("H902", BW - 4, 4, 0), ("H903", 4, BH - 4, 0), ("H904", BW - 4, BH - 4, 0),
]

# edge connectors: (ref, edge, position along the edge)
EDGE = [("J101", "left", 14), ("J161", "left", 55), ("J601", "left", 83), ("J401", "right", 48)]

# cluster packing areas when a block needs more than its plain rectangle: block -> list of (x, y, w, h)
AREAS = {
    "buck": [(BX + 12, 21, 25, 13), (BX, 34, 67, 41), (BX + 82, 50, 14, 25), (BX + 84, 15, 12, 17)],
    "output_stage": [(OX, 16, 27, 22), (OX, 76, 55, 49), (OX + 27, 0, 20, 24), (OX, 54, 12, 20)],
    "usb_pd_input": [(11, 8, 37, 13), (11, 21, 20, 24), (28, 21, 12, 24), (1.5, 22, 10.5, 23)],
    "dc_input": [(36, 45, 12, 30)],
    "input_sense": [(48, 46, 11, 29), (48, 0, 11, 34)],
    "usb_isolated": [(1.5, 94, 11.5, 31), (27, 76, 9, 49)],
    "mcu": [(80, 75, 45, 37)],
}
CLUSTER_AREA = {                       # force a cluster into a specific area index of its block
    ("usb_pd_input", "USB-C PWR in"): 3,
    ("usb_pd_input", "AP33772S PD sink"): 0,
    ("usb_pd_input", "USB sink switch LM74800"): 2,
    ("buck", "Gate R / boost / snubber"): 0,
    ("buck", "NTC inductor"): 2,
    ("output_stage", "Clamp gate driver UCC27511"): 2,
    ("output_stage", "NTC output switch"): 0,
    ("buck", "INA240 IL"): 3,
    ("output_stage", "Output INA228"): 3,
    ("output_stage", "Output switch drive VOM1271"): 0,
    ("output_stage", "NTC clamp resistor"): 2,
    ("usb_isolated", "USB ESD + CC"): 0,
    ("usb_isolated", "ADuM side1"): 0,
    ("usb_isolated", "ADuM side2"): 1,
    ("usb_isolated", "B0505S out"): 1,
    ("input_sense", "INA228 VIN"): 0,
}


# ================================================================ helpers
def mm(v):
    return pcbnew.FromMM(v)


def vec(x, y):
    return pcbnew.VECTOR2I(mm(X0 + x), mm(Y0 + y))


def bbox(fp):
    """Courtyard bbox (mm, sheet coordinates) of the footprint as currently placed."""
    cy = fp.GetCourtyard(pcbnew.F_CrtYd)
    b = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
    return (pcbnew.ToMM(b.GetX()), pcbnew.ToMM(b.GetY()), pcbnew.ToMM(b.GetWidth()), pcbnew.ToMM(b.GetHeight()))


def set_rot(fp, rot):
    fp.SetOrientationDegrees(rot)
    fp.BuildCourtyardCaches() if hasattr(fp, "BuildCourtyardCaches") else None


def place_bbox_at(fp, x, y, rot=0):
    """Put the courtyard bbox centre at board-relative (x, y)."""
    set_rot(fp, rot)
    fp.SetPosition(vec(0, 0))
    bx, by, bw, bh = bbox(fp)
    px, py = pcbnew.ToMM(fp.GetPosition().x), pcbnew.ToMM(fp.GetPosition().y)
    dx, dy = px - (bx + bw / 2), py - (by + bh / 2)
    fp.SetPosition(vec(x + dx, y + dy))


def rect_of(fp):
    bx, by, bw, bh = bbox(fp)
    return (bx - X0, by - Y0, bw, bh)


def overlaps(a, b, gap):
    return not (a[0] + a[2] + gap <= b[0] or b[0] + b[2] + gap <= a[0] or
                a[1] + a[3] + gap <= b[1] or b[1] + b[3] + gap <= a[1])


def first_fit(w, h, area, obstacles, gap, step=0.5):
    ax, ay, aw, ah = area
    y = ay
    while y + h <= ay + ah + 1e-6:
        x = ax
        while x + w <= ax + aw + 1e-6:
            r = (x, y, w, h)
            hit = next((o for o in obstacles if overlaps(r, o, gap)), None)
            if hit is None:
                return x, y
            x = max(x + step, hit[0] + hit[2] + gap) if hit[1] <= y + h and hit[1] + hit[3] >= y else x + step
        y += step
    return None


LABEL_SIZE = 0.7
LABEL_CHAR_W = 0.9 * LABEL_SIZE        # stroke-font advance per character (approx.)


def pack_cluster(fps, label=""):
    """Arrange a cluster's footprints in a compact box; returns (w, h, [(fp, dx, dy)]) with bbox offsets."""
    sizes = []
    for fp in fps:
        set_rot(fp, 0)
        fp.SetPosition(vec(0, 0))
        sizes.append((fp, *bbox(fp)[2:]))
    area = sum(w * h for _, w, h in sizes)
    width = max(sizes[0][1], math.sqrt(area * 1.9), max(w for _, w, _ in sizes), len(label) * LABEL_CHAR_W)
    placed, out = [], []
    for fp, w, h in sizes:
        pos = first_fit(w, h, (0, 0, width, 1000), placed, GAP_IN, step=0.25)
        placed.append((pos[0], pos[1], w, h))
        out.append((fp, pos[0], pos[1]))
    W = max(max(p[0] + p[2] for p in placed), len(label) * LABEL_CHAR_W)
    H = max(p[1] + p[3] for p in placed)
    return W, H, out


# ================================================================ main
def main():
    board = pcbnew.LoadBoard(str(PCB))
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}

    # remove artefacts of a previous run
    for g in list(board.Groups()):
        if g.GetName().startswith(TAG):
            for item in list(g.GetItems()):
                if item.Type() != pcbnew.PCB_FOOTPRINT_T:
                    board.Remove(item)
            board.Remove(g)

    comments = board.GetLayerID("User.Comments") if board.GetLayerID("User.Comments") >= 0 else pcbnew.Cmts_User

    def text(s, x, y, size=1.0, group=None):
        t = pcbnew.PCB_TEXT(board)
        t.SetText(s)
        t.SetLayer(pcbnew.Cmts_User)
        t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
        t.SetTextThickness(mm(size * 0.15))
        t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
        t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_TOP)
        t.SetPosition(vec(x, y))
        board.Add(t)
        if group:
            group.AddItem(t)
        return t

    def rect(x, y, w, h, layer, width=0.1, group=None):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(pcbnew.SHAPE_T_RECT)
        s.SetStart(vec(x, y))
        s.SetEnd(vec(x + w, y + h))
        s.SetLayer(layer)
        s.SetWidth(mm(width))
        board.Add(s)
        if group:
            group.AddItem(s)
        return s

    def new_group(name):
        g = pcbnew.PCB_GROUP(board)
        g.SetName(TAG + name)
        board.Add(g)
        return g

    # board outline (placeholder) if none exists
    has_edge = any(d.GetLayer() == pcbnew.Edge_Cuts for d in board.GetDrawings())
    if not has_edge:
        rect(0, 0, BW, BH, pcbnew.Edge_Cuts, 0.1)

    # block frames + titles
    gf = new_group("frames")
    for name, (x, y, w, h) in REGIONS.items():
        rect(x + 0.3, y + 0.3, w - 0.6, h - 0.6, pcbnew.Cmts_User, 0.15, gf)
        text(name.upper(), x + 1, y + h - 2.2, 1.4, gf)
    bar_x = 20
    s = pcbnew.PCB_SHAPE(board)
    s.SetShape(pcbnew.SHAPE_T_SEGMENT)
    s.SetStart(vec(bar_x, 76))
    s.SetEnd(vec(bar_x, BH - 1))
    s.SetLayer(pcbnew.Cmts_User)
    s.SetWidth(mm(0.3))
    board.Add(s)
    gf.AddItem(s)
    text("ISOLATION BARRIER (GND_ISO | GND)", bar_x + 0.5, BH - 5, 1.0, gf)

    # everything to 0 deg first
    for fp in fps.values():
        fp.SetLayerAndFlip(pcbnew.F_Cu) if fp.IsFlipped() else None
        set_rot(fp, 0)

    obstacles = {k: [] for k in REGIONS}
    obstacles["_all"] = []
    done = set()

    def block_of(x, y):
        for k, (rx, ry, rw, rh) in REGIONS.items():
            if rx <= x < rx + rw and ry <= y < ry + rh:
                return k
        return "_all"

    def register(fp):
        r = rect_of(fp)
        obstacles[block_of(r[0] + r[2] / 2, r[1] + r[3] / 2)].append(r)
        # also register in neighbouring regions it overlaps
        for k, reg in REGIONS.items():
            if overlaps(r, reg, 0) and r not in obstacles[k]:
                obstacles[k].append(r)
        done.add(fp.GetReference())

    # ---- edge connectors: mouth faces out of the board
    for ref, edge, along in EDGE:
        fp = fps[ref]
        best = None
        for rot in (0, 90, 180, 270):
            set_rot(fp, rot)
            fp.SetPosition(vec(0, 0))
            bx, by, bw, bh = bbox(fp)
            pads = [p.GetPosition() for p in fp.Pads()]
            cx = sum(pcbnew.ToMM(p.x) for p in pads) / len(pads) - (bx + bw / 2)
            cy = sum(pcbnew.ToMM(p.y) for p in pads) / len(pads) - (by + bh / 2)
            # mouth = opposite of the pad centroid; want it pointing at the edge
            score = cx if edge == "left" else -cx if edge == "right" else 0
            if best is None or score > best[0]:
                best = (score, rot)
        rot = best[1]
        set_rot(fp, rot)
        fp.SetPosition(vec(0, 0))
        _, _, bw, bh = bbox(fp)
        # left edge: pads toward the board (right) -> mouth faces out
        x = bw / 2 if edge == "left" else BW - bw / 2
        place_bbox_at(fp, x, along, rot)
        register(fp)

    # ---- explicit parts
    for ref, x, y, rot in EXPLICIT:
        fp = fps[ref]
        if rot is None:                 # B0505S: input pins (1, 2) on the left, outputs on the right
            for r in (0, 90, 180, 270):
                set_rot(fp, r)
                p = {pd.GetNumber(): pcbnew.ToMM(pd.GetPosition().x) for pd in fp.Pads()}
                if p.get("1", 0) < p.get("4", 0) - 1:
                    rot = r
                    break
        place_bbox_at(fp, x, y, rot)
        register(fp)

    # ---- clusters
    groups_made = 0
    for block, clist in CLUSTERS.items():
        areas = AREAS.get(block, [REGIONS[block]])
        for cname, refs in clist:
            members = [fps[r] for r in refs if r in fps and r not in done]
            missing = [r for r in refs if r not in fps]
            if missing:
                print(f"WARN {cname}: missing {missing}")
            if not members:
                continue
            w, h, layout = pack_cluster(members, cname)
            h_tot = h + LABEL_H
            order = [CLUSTER_AREA[(block, cname)]] if (block, cname) in CLUSTER_AREA else range(len(areas))
            pos = None
            for ai in order:
                pos = first_fit(w, h_tot, areas[ai], obstacles[block], GAP_OUT)
                if pos:
                    break
            if pos is None:                                  # fall back to the whole block region
                pos = first_fit(w, h_tot, REGIONS[block], obstacles[block], GAP_OUT)
            if pos is None:
                print(f"WARN no room for {block}/{cname} ({w:.1f} x {h_tot:.1f} mm) -> parked below the board")
                pos = (0, BH + 5 + 20 * groups_made % 100)
            gx, gy = pos
            g = new_group(f"{block}/{cname}")
            text(cname, gx, gy, LABEL_SIZE, g)
            for fp, dx, dy in layout:
                bw, bh = bbox(fp)[2:]
                place_bbox_at(fp, gx + dx + bw / 2, gy + LABEL_H + dy + bh / 2, 0)
                g.AddItem(fp)
                done.add(fp.GetReference())
            obstacles[block].append((gx, gy, w, h_tot))
            groups_made += 1

    # ---- label explicit power-path parts with small notes
    notes = [
        (BX + 37, 1, "SW node"),
        (BX + 66, 0.2, "2.0 mOhm Kelvin"),
        (BX + 67, 22.2, "C1 + damper"),
        (BX + 67, 45.5, "C2 -> VOUT_INT"),
        (OX + 8, 59.5, "back-to-back switch"),
    ]
    gn = new_group("notes")
    for x, y, s in notes:
        text(s, x, y, 0.8, gn)

    left = sorted(set(fps) - done, key=lambda r: (re.sub(r"\d", "", r), int(re.sub(r"\D", "", r))))
    if left:
        print("WARN not placed:", " ".join(left))
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else PCB      # optional: write to another file for review
    board.Save(str(out))
    print(f"placed {len(done)} / {len(fps)} footprints, {groups_made} cluster groups -> {out.name}")


if __name__ == "__main__":
    main()
