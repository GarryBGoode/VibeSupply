"""
Board setup for the KiCad boards (layout step 1): outline, slot keep-outs, 4-layer stackup, design rules, net classes
and custom DRC rules for supply_power and supply_control.

Run with KiCad's Python, with the board CLOSED in KiCad (KiCad would overwrite the result when it saves):
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/board_setup.py            # both boards
    "C:/Program Files/KiCad/10.0/bin/python.exe" tools/board_setup.py power      # one board

Re-runnable at any time (e.g. after a mech_design.py change): it replaces only what it created itself (the
"board_setup" group: outline + slot keep-outs), and overwrites the stackup, design rules, net classes and the
.kicad_dru file. Footprints, tracks and your own zones/graphics stay. Rules you add in Board Setup by hand get
overwritten -> add them here instead.

Mechanical values (board size, edge keep-out) come from CAD_3D/mech_design.py, read through the project venv
(KiCad's Python has no build123d).

Coordinates: the board centre sits at ORIGIN_MM on the sheet and both the grid origin and the drill/place origin are
set there. With the grid origin selected as the coordinate origin in KiCad, the coordinates read like
mech_design.py's board frame (0,0 = board centre), but with Y pointing down.
Axis convention (2026-10-01): KiCad left (-X) = rear end cap; both boards have their rear edge at the rear end cap,
the right (front) end is free.
"""

import json
import re
import subprocess
import sys
from pathlib import Path

import pcbnew

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / ".venv/Scripts/python.exe"
ORIGIN_MM = (150.0, 100.0)  # board centre on the sheet
TAG = "board_setup"

mm = pcbnew.FromMM

# --- per-board configuration ------------------------------------------------------------------------------------------
# Net classes: name -> (track, clearance, via_dia, via_drill, colour, [net patterns]). Default is the class "Default".
# Patterns are KiCad wildcards on the net names from out/supply_<board>.net.

POWER_CLASSES = {
    "Default": (0.2, 0.2, 0.6, 0.3, None, []),
    # 10 A paths (mostly pours; the track width is only the router's starting value). The regen clamp path is 15 A burst.
    "Power": (1.0, 0.25, 0.8, 0.4, (220, 60, 60), [
        "VBUS_RAW", "VBUS_S", "USBIN_MID", "DCIN_RAW", "DCIN_MID", "VIN_BUS", "VIN_PWR", "SW", "IL_SENSE+", "VC1",
        "VOUT_INT", "VOUT_SH", "OUTSW_MID", "VTERM", "OUT+", "CLAMP_R"]),
    # gate drive / bootstrap: short and wide
    "Gate": (0.4, 0.2, 0.6, 0.3, (230, 140, 30), [
        "BUCK_TG", "BUCK_BG", "BUCK_BOOST", "CLAMP_G", "OUTSW_G", "OE_G"]),
    # low-current supply rails
    "Supply": (0.4, 0.2, 0.6, 0.3, (60, 140, 220), [
        "+12V_AUX", "+5VA", "+3V3", "+3V3A", "LOGIC_IN", "AUX_SW", "BUCK_INTVCC", "BUCK_VINC", "PD_V5V"]),
    # Kelvin sense pair of the buck shunt: route as a pair from the shunt pads, away from SW
    "Kelvin": (0.2, 0.2, 0.6, 0.3, (170, 80, 200), ["BUCK_SENSE_P", "BUCK_SENSE_N"]),
}

CONTROL_CLASSES = {
    "Default": (0.2, 0.15, 0.6, 0.3, None, []),
    "Supply": (0.4, 0.2, 0.6, 0.3, (60, 140, 220), [
        "+3V3", "+3V3A", "LOGIC_IN", "LOG_SW", "+5V_ISO", "VREF+"]),
    # PC side of the isolation barrier (GND_ISO is the PC's ground)
    "ISO": (0.3, 0.2, 0.6, 0.3, (40, 170, 90), ["GND_ISO", "VBUS_PC", "ISO_*"]),
}

DRU_HEADER = "(version 1)\n\n# Written by tools/board_setup.py; edit the script, not this file (re-running overwrites it).\n"

# Footprint-internal geometry: fine-pitch IC / connector pins (USB-C, QFN, TSSOP, MSOP: 0.2 mm gaps) sit closer than the
# Power / Gate class clearances, and connectors / threaded inserts have pads right at their own holes. Later rules win,
# so the board-specific rules below (isolation barrier) still apply on top of these.
COMMON_DRU = """
(rule "fine-pitch IC / connector pins"
  (condition "A.Type == 'Pad' && B.Type == 'Pad' && (A.memberOfFootprint('U*') || A.memberOfFootprint('J*')) && (B.memberOfFootprint('U*') || B.memberOfFootprint('J*'))")
  (constraint clearance (min 0.15mm)))

(rule "own holes of connectors and inserts"
  (condition "A.Type == 'Pad' && B.Type == 'Pad' && ((A.memberOfFootprint('J*') && B.memberOfFootprint('J*')) || (A.memberOfFootprint('H*') && B.memberOfFootprint('H*')))")
  (constraint hole_clearance (min 0mm)))
"""

POWER_DRU = DRU_HEADER + COMMON_DRU + """
# High-current pads connect to pours without thermal spokes (spokes would choke 10 A; reflow at the assembly house).
(rule "power pads solid"
  (condition "A.Type == 'Pad' && A.hasNetclass('Power')")
  (constraint zone_connection solid))

# Large GND pads (1206 and up: power MLCCs, bulk caps, FET sources, TVS, inserts) solid too; small passives keep
# their spokes (tombstoning).
(rule "large GND pads solid"
  (condition "A.Type == 'Pad' && A.NetName == 'GND' && (A.Size_X >= 1.6mm || A.Size_Y >= 1.6mm)")
  (constraint zone_connection solid))
"""

CONTROL_DRU = DRU_HEADER + COMMON_DRU + """
# Isolation barrier: PC-side copper (net class ISO) keeps 1.5 mm from everything else on every layer, which also
# forces the plane split under U602 (ADuM3160). PS601 (B0505S, SIP-4 on 2.54 mm) has both sides on adjacent pins,
# so its own pads are exempt; so are unconnected pads (USB-C SBU).
(rule "isolation barrier"
  (condition "A.hasNetclass('ISO') && !B.hasNetclass('ISO') && B.NetName != '' && !A.memberOfFootprint('PS601')")
  (constraint clearance (min 1.5mm)))
"""

BOARDS = {
    "power": dict(
        title="USB-C PD bench supply - power board",
        classes=POWER_CLASSES, dru=POWER_DRU,
        # JLC 4-layer, 2 oz outer: min track / space 0.15 mm. Inner 1 oz (GND plane carries the 10 A return).
        cu_outer=0.070, cu_inner=0.035, min_track=0.15, min_clear=0.15,
        layer_types={pcbnew.In1_Cu: pcbnew.LT_POWER, pcbnew.In2_Cu: pcbnew.LT_MIXED},
    ),
    "control": dict(
        title="USB-C PD bench supply - control board",
        classes=CONTROL_CLASSES, dru=CONTROL_DRU,
        # JLC 4-layer standard (JLC04161H-7628): 1 oz outer, 0.5 oz inner; min 0.09 mm, we stay at 0.127
        cu_outer=0.035, cu_inner=0.0152, min_track=0.127, min_clear=0.127,
        layer_types={pcbnew.In1_Cu: pcbnew.LT_POWER, pcbnew.In2_Cu: pcbnew.LT_MIXED},
    ),
}

COMMON_RULES = dict(
    via_min_dia=0.5, via_min_drill=0.2,  # 0.2: thermal vias of the _ThermalVias IC footprints; our own vias stay 0.3
                                         # (JLC: 0.15 mm minimum; check the price of < 0.3 mm holes when ordering)
    via_min_annular=0.1, hole_clearance=0.25, hole_to_hole=0.25,
    copper_edge=0.4,  # JLC >= 0.2 + routing tolerance; the long edges have the 3 mm slot keep-out anyway
    silk_min_height=0.8, silk_min_thickness=0.15,  # JLC: 1.0 mm text recommended, 0.15 mm line minimum
    track_widths=[0.2, 0.3, 0.4, 0.6, 1.0, 1.5, 2.0, 3.0],
    vias=[(0.6, 0.3), (0.8, 0.4), (1.0, 0.5)],
)


# --- mechanics --------------------------------------------------------------------------------------------------------

MECH_SNIPPET = r"""
import json, sys
sys.path.insert(0, "CAD_3D")
import mech_design as m
out = {}
for b in ("power", "control"):
    s = getattr(m, f"pcb_size_{b}")
    out[b] = dict(length=s.length, width=s.width, thickness=s.thickness, edge_keepout=s.edge_keepout)
print("MECH_JSON " + json.dumps(out))
"""


def read_mech():
    r = subprocess.run([str(VENV_PY), "-c", MECH_SNIPPET], cwd=ROOT, capture_output=True, text=True)
    line = next((l for l in r.stdout.splitlines() if l.startswith("MECH_JSON ")), None)
    if r.returncode or not line:
        sys.exit(f"reading CAD_3D/mech_design.py through {VENV_PY} failed:\n{r.stdout}\n{r.stderr}")
    return json.loads(line.removeprefix("MECH_JSON "))


# --- board items ------------------------------------------------------------------------------------------------------

def pt(x, y):
    """Board-centre-relative mm (KiCad orientation, Y down) -> internal units."""
    return pcbnew.VECTOR2I(mm(ORIGIN_MM[0] + x), mm(ORIGIN_MM[1] + y))


def detach(board, item):
    """board.Remove() hands the C++ object to Python; when the proxy is then garbage-collected, SWIG fails to destroy
    it and corrupts its type table (later ZONE.Outline() returns a bare SwigPyObject). Take ownership away again ->
    the object just leaks, which is fine for a short-lived script."""
    board.Remove(item)
    item.thisown = False


def remove_own_items(board):
    for g in list(board.Groups()):
        if g.GetName() == TAG:
            items = [i.Cast() for i in g.GetItems()]
            g.RemoveAll()
            for item in items:
                detach(board, item)
            detach(board, g)
    # rule areas created by an earlier run that lost their group (e.g. ungrouped by hand)
    for z in list(board.Zones()):
        if z.GetIsRuleArea() and z.GetZoneName().startswith(TAG + ":"):
            detach(board, z)


def add_outline(board, group, L, W):
    r = pcbnew.PCB_SHAPE(board)
    r.SetShape(pcbnew.SHAPE_T_RECT)
    r.SetStart(pt(-L / 2, -W / 2))
    r.SetEnd(pt(L / 2, W / 2))
    r.SetLayer(pcbnew.Edge_Cuts)
    r.SetWidth(mm(0.1))
    r.SetLocked(True)
    board.Add(r)
    group.AddItem(r)


def add_slot_keepout(board, group, name, L, y0, y1):
    """Rule area over a long-edge band: no parts, pads, tracks, vias or pours on the outer layers (the aluminium slot
    and rib touch the board there). Inner layers stay usable for planes."""
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetZoneName(f"{TAG}:{name}")
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.B_Cu)
    z.SetLayerSet(ls)
    for setter in (z.SetDoNotAllowTracks, z.SetDoNotAllowVias, z.SetDoNotAllowPads, z.SetDoNotAllowZoneFills,
                   z.SetDoNotAllowFootprints):
        setter(True)
    o = z.Outline()
    o.NewOutline()
    for x, y in ((-L / 2, y0), (L / 2, y0), (L / 2, y1), (-L / 2, y1)):
        o.Append(pt(x, y))
    z.SetLocked(True)
    board.Add(z)
    group.AddItem(z)


# --- settings ---------------------------------------------------------------------------------------------------------

def set_design_rules(board, cfg, thickness):
    ds = board.GetDesignSettings()
    c = COMMON_RULES
    ds.SetBoardThickness(mm(thickness))
    ds.m_MinClearance = mm(cfg["min_clear"])
    ds.m_TrackMinWidth = mm(cfg["min_track"])
    ds.m_ViasMinSize = mm(c["via_min_dia"])
    ds.m_MinThroughDrill = mm(c["via_min_drill"])
    ds.m_ViasMinAnnularWidth = mm(c["via_min_annular"])
    ds.m_HoleClearance = mm(c["hole_clearance"])
    ds.m_HoleToHoleMin = mm(c["hole_to_hole"])
    ds.m_CopperEdgeClearance = mm(c["copper_edge"])
    ds.m_MinSilkTextHeight = mm(c["silk_min_height"])
    ds.m_MinSilkTextThickness = mm(c["silk_min_thickness"])
    # pre-defined sizes: entry 0 is KiCad's "use the net class value" placeholder
    ds.m_TrackWidthList.clear()
    for w in [0] + c["track_widths"]:
        ds.m_TrackWidthList.append(mm(w))
    ds.m_ViasDimensionsList.clear()
    for d, h in [(0, 0)] + c["vias"]:
        ds.m_ViasDimensionsList.append(pcbnew.VIA_DIMENSION(mm(d), mm(h)))
    ds.SetAuxOrigin(pt(0, 0))
    ds.SetGridOrigin(pt(0, 0))


def set_net_classes(board, classes):
    ns = board.GetDesignSettings().m_NetSettings
    ns.ClearNetclassPatternAssignments()
    ns.ClearNetclasses()
    for name, (track, clear, via_d, via_h, colour, patterns) in classes.items():
        nc = ns.GetDefaultNetclass() if name == "Default" else pcbnew.NETCLASS(name)
        nc.SetTrackWidth(mm(track))
        nc.SetClearance(mm(clear))
        nc.SetViaDiameter(mm(via_d))
        nc.SetViaDrill(mm(via_h))
        if colour:
            nc.SetPcbColor(pcbnew.COLOR4D(colour[0] / 255, colour[1] / 255, colour[2] / 255, 1.0))
        if name != "Default":
            ns.SetNetclass(name, nc)
        for p in patterns:
            ns.SetNetclassPatternAssignment(p, name)
    ns.ClearAllCaches()


def stackup_sexpr(cfg, thickness):
    """JLC-style 4-layer stackup (7628 prepregs); the core takes up the rest of the board thickness. Approximate:
    the fab's own stackup decides, this is for the 3D thickness and the record."""
    mask, prepreg = 0.01, 0.2104
    core = thickness - 2 * mask - 2 * cfg["cu_outer"] - 2 * cfg["cu_inner"] - 2 * prepreg
    t = "\t\t"

    def layer(name, typ, thick=None, extra=""):
        s = f'{t}\t(layer "{name}"\n{t}\t\t(type "{typ}")\n'
        if thick is not None:
            s += f"{t}\t\t(thickness {thick:.4f})\n"
        return s + extra + f"{t}\t)\n"

    def diel(n, typ, thick, material, er):
        extra = (f'{t}\t\t(color "FR4 natural")\n{t}\t\t(material "{material}")\n'
                 f"{t}\t\t(epsilon_r {er})\n{t}\t\t(loss_tangent 0.02)\n")
        return layer(f"dielectric {n}", typ, thick, extra)

    return (f"{t}(stackup\n"
            + layer("F.SilkS", "Top Silk Screen") + layer("F.Paste", "Top Solder Paste")
            + layer("F.Mask", "Top Solder Mask", mask) + layer("F.Cu", "copper", cfg["cu_outer"])
            + diel(1, "prepreg", prepreg, "7628", 4.4) + layer("In1.Cu", "copper", cfg["cu_inner"])
            + diel(2, "core", core, "FR4", 4.6) + layer("In2.Cu", "copper", cfg["cu_inner"])
            + diel(3, "prepreg", prepreg, "7628", 4.4) + layer("B.Cu", "copper", cfg["cu_outer"])
            + layer("B.Mask", "Bottom Solder Mask", mask) + layer("B.Paste", "Bottom Solder Paste")
            + layer("B.SilkS", "Bottom Silk Screen")
            + f'{t}\t(copper_finish "HAL lead-free")\n{t}\t(dielectric_constraints no)\n{t})\n')


def write_stackup(pcb_path, cfg, thickness):
    """pcbnew's Python API has no stackup access -> put the (stackup ...) block into (setup ...) as text."""
    txt = pcb_path.read_text(encoding="utf-8")
    start = txt.find("(stackup")
    if start >= 0:  # drop the old block (balanced parentheses) and its line
        depth, i = 0, start
        while True:
            depth += {"(": 1, ")": -1}.get(txt[i], 0)
            i += 1
            if depth == 0:
                break
        line_start = txt.rfind("\n", 0, start) + 1
        txt = txt[:line_start] + txt[i:].lstrip(" \t").removeprefix("\n")
    m = re.search(r"\(setup[^\n]*\n", txt)
    assert m, "no (setup ...) section in the saved board"
    txt = txt[:m.end()] + stackup_sexpr(cfg, thickness) + txt[m.end():]
    pcb_path.write_text(txt, encoding="utf-8")


def set_text_defaults(pro_path):
    """Silk text defaults for new text (the API exposes only the first entry of the per-layer-class arrays)."""
    pro = json.loads(pro_path.read_text(encoding="utf-8"))
    d = pro["board"]["design_settings"]["defaults"]
    d.update(silk_text_size_h=1.0, silk_text_size_v=1.0, silk_text_thickness=0.15, silk_line_width=0.15,
             fab_text_size_h=0.8, fab_text_size_v=0.8, fab_text_thickness=0.12)
    pro_path.write_text(json.dumps(pro, indent=2) + "\n", encoding="utf-8")


# --- main -------------------------------------------------------------------------------------------------------------

def setup(name, mech):
    cfg, m = BOARDS[name], mech[name]
    d = ROOT / f"kicad/supply_{name}"
    pcb_path, pro_path = d / f"supply_{name}.kicad_pcb", d / f"supply_{name}.kicad_pro"
    if (d / f"~supply_{name}.kicad_pcb.lck").exists():
        sys.exit(f"{pcb_path.name} is open in KiCad (lock file present) - close it first")

    board = pcbnew.LoadBoard(str(pcb_path))
    board.SetCopperLayerCount(4)
    for layer, typ in cfg["layer_types"].items():
        board.SetLayerType(layer, typ)
    tb = board.GetTitleBlock()
    tb.SetTitle(cfg["title"])
    board.SetTitleBlock(tb)

    remove_own_items(board)
    g = pcbnew.PCB_GROUP(board)
    g.SetName(TAG)
    board.Add(g)
    L, W, k = m["length"], m["width"], m["edge_keepout"]
    add_outline(board, g, L, W)
    add_slot_keepout(board, g, "slot_keepout_top", L, -W / 2, -W / 2 + k)
    add_slot_keepout(board, g, "slot_keepout_bottom", L, W / 2 - k, W / 2)
    g.SetLocked(True)

    set_design_rules(board, cfg, m["thickness"])
    set_net_classes(board, cfg["classes"])
    board.SynchronizeNetsAndNetClasses(True)

    assert pcbnew.SaveBoard(str(pcb_path), board), f"saving {pcb_path} failed"
    write_stackup(pcb_path, cfg, m["thickness"])
    set_text_defaults(pro_path)
    (d / f"supply_{name}.kicad_dru").write_text(cfg["dru"], encoding="utf-8")
    print(f"supply_{name}: {L} x {W} mm, slot keep-out {k} mm, {len(board.GetFootprints())} footprints untouched")


if __name__ == "__main__":
    names = sys.argv[1:] or list(BOARDS)
    mech = read_mech()
    for n in names:
        setup(n, mech)
