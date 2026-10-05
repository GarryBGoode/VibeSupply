"""
UI board setup from the front panel design: board outline with its cutouts (wheel drums, on-off button), keep-outs
(screw bosses on the top side, screw heads on the bottom side), and the placement of every footprint that has to line
up with the panel (scroll wheel encoders + push switches, nav buttons, screw holes, panel LEDs).

All of it comes from CAD_3D/geom_defs.py (UIPanelData.board_*, instance mech_design.ui_panel), read through the
project venv (KiCad's Python has no numpy). MECH below only says which reference plays which role.

Run with KiCad's Python, with the board CLOSED in KiCad (KiCad would overwrite the result when it saves):
    .\\tools\\run_ui_board_setup.ps1             # after every change of the panel design
    .\\tools\\run_ui_board_setup.ps1 -Sync       # after every change of ui_design.py: first bring the board in line
                                                # with out/supply_ui.net (what "Update PCB from netlist" does in KiCad)

Re-runnable: it replaces only what it created itself (the "board_setup" group: outline, cutouts, keep-outs) and moves
only the footprints listed in MECH, which it locks and collects in the group "ui_mech". Other footprints, tracks and
zones stay; tools/place.py (.\\tools\\run_place.ps1 ui) arranges the footprints that are not locked.

-Sync: footprints that are not in the netlist are removed; a footprint whose library footprint changed is replaced in
place (position, rotation, side and lock are kept); new footprints appear next to the board; values, fields and pad
nets are updated. Tracks are not touched.

Coordinates: the panel frame origin (panel centre) sits at board_setup.ORIGIN_MM on the sheet, with the grid and
drill/place origins there. The board top side faces the panel: KiCad x = panel x, KiCad y = -panel y, rotations
counter-clockwise in both.
"""

import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import board_setup as BS  # noqa: E402

ROOT = BS.ROOT
PCB = ROOT / "kicad/supply_ui/supply_ui/supply_ui.kicad_pcb"
NETLIST = ROOT / "out/supply_ui.net"
PROJECT_LIBS = {"supply1": ROOT / "footprints/supply1.pretty"}  # as in the project's fp-lib-table
KICAD_LIBS = Path(os.environ.get("KICAD10_FOOTPRINT_DIR", "C:/Program Files/KiCad/10.0/share/kicad/footprints"))
MECH_TAG = "ui_mech"
TITLE = "USB-C PD bench supply - UI board"
PARK_GAP = 10.0  # -Sync: new footprints appear this far from the board edge

mm, tomm = pcbnew.FromMM, pcbnew.ToMM

# reference (ui_design.py) -> role (UIPanelData.board_footprints)
MECH = {
    "SW1": "wheel_1.encoder",  # voltage wheel, left
    "SW3": "wheel_1.switch",
    "SW2": "wheel_2.encoder",  # current wheel, right
    "SW4": "wheel_2.switch",
    "SW5": "button.left",
    "SW7": "button.center",  # ENTER
    "SW6": "button.right",
    "H1": "screw_1",
    "H2": "screw_2",
    "H3": "screw_3",
    "D4": "led_1",  # CV, under the voltage wheel
    "D3": "led_2",  # CC, under the current wheel
}

MECH_SNIPPET = r"""
import dataclasses, json, sys
sys.path.insert(0, "CAD_3D")
import mech_design as m
p = m.ui_panel
d = dataclasses.asdict
print("MECH_JSON " + json.dumps(dict(
    thickness=p.board_thickness,
    hole_diameter=p.screw.board_hole_diameter,
    outline=d(p.board_outline),
    cutouts={k: d(v) for k, v in p.board_cutouts.items()},
    keepouts_top={k: d(v) for k, v in p.board_keepouts.items()},
    keepouts_bottom={k: d(v) for k, v in p.board_keepouts_bottom.items()},
    footprints={k: d(v) for k, v in p.board_footprints.items()},
    pads=p.board_pads,
)))
"""


def read_mech():
    r = subprocess.run([str(BS.VENV_PY), "-c", MECH_SNIPPET], cwd=ROOT, capture_output=True, text=True)
    line = next((l for l in r.stdout.splitlines() if l.startswith("MECH_JSON ")), None)
    if r.returncode or not line:
        sys.exit(f"reading CAD_3D/mech_design.py through {BS.VENV_PY} failed:\n{r.stdout}\n{r.stderr}")
    return json.loads(line.removeprefix("MECH_JSON "))


# --- geometry ---------------------------------------------------------------------------------------------------------

def pt(x, y):
    """Panel frame mm -> internal units (Y flipped)."""
    return BS.pt(x, -y)


def area_path(a):
    """BoardArea -> closed path in the panel frame: list of ("line", p0, p1) / ("arc", start, mid, end)."""
    w, h, r = a["width"] / 2, a["height"] / 2, a["corner_radius"]
    rot = math.radians(a["rotation"])
    c, s = math.cos(rot), math.sin(rot)

    def world(x, y):
        return (a["x"] + c * x - s * y, a["y"] + s * x + c * y)

    if r <= 0:
        corners = [world(sx * w, sy * h) for sx, sy in ((1, -1), (1, 1), (-1, 1), (-1, -1))]
        return [("line", corners[i], corners[(i + 1) % 4]) for i in range(4)]
    path, arcs = [], []
    for (sx, sy), a0 in zip(((1, -1), (1, 1), (-1, 1), (-1, -1)), (-90, 0, 90, 180)):
        cx, cy = sx * (w - r), sy * (h - r)
        arcs.append([world(cx + r * math.cos(math.radians(a0 + da)), cy + r * math.sin(math.radians(a0 + da)))
                     for da in (0, 45, 90)])
    for i, arc in enumerate(arcs):
        path.append(("arc", *arc))
        nxt = arcs[(i + 1) % 4][0]
        if math.dist(arc[2], nxt) > 1e-6:
            path.append(("line", arc[2], nxt))
    return path


def is_circle(a):
    return a["width"] == a["height"] == 2 * a["corner_radius"]


def add_edge(board, group, a):
    """Closed Edge.Cuts contour of a BoardArea."""
    def shape(kind):
        s = pcbnew.PCB_SHAPE(board)
        s.SetShape(kind)
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(mm(0.1))
        return s

    items = []
    if is_circle(a):
        s = shape(pcbnew.SHAPE_T_CIRCLE)
        s.SetCenter(pt(a["x"], a["y"]))
        s.SetEnd(pt(a["x"] + a["corner_radius"], a["y"]))
        items.append(s)
    else:
        for kind, *pts in area_path(a):
            if kind == "line":
                s = shape(pcbnew.SHAPE_T_SEGMENT)
                s.SetStart(pt(*pts[0]))
                s.SetEnd(pt(*pts[1]))
            else:
                s = shape(pcbnew.SHAPE_T_ARC)
                s.SetArcGeometry(pt(*pts[0]), pt(*pts[1]), pt(*pts[2]))
            items.append(s)
    for s in items:
        s.SetLocked(True)
        board.Add(s)
        group.AddItem(s)


def add_keepout(board, group, name, a, layer, inner_radius=0.0, steps=48):
    """Round rule area on one side: no footprints (screw boss / screw head). Copper is fine under it.
    inner_radius > 0 makes it a ring: the mounting hole's own courtyard stays outside, or DRC would flag the hole."""
    assert is_circle(a), "only round keep-outs so far"
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetZoneName(f"{BS.TAG}:{name}")
    ls = pcbnew.LSET()
    ls.AddLayer(layer)
    z.SetLayerSet(ls)
    z.SetDoNotAllowFootprints(True)
    for setter in (z.SetDoNotAllowTracks, z.SetDoNotAllowVias, z.SetDoNotAllowPads, z.SetDoNotAllowZoneFills):
        setter(False)
    o = z.Outline()
    o.NewOutline()
    radii = [(-1, a["corner_radius"])]
    if inner_radius > 0:
        o.NewHole()
        radii.append((0, inner_radius))
    for hole, r in radii:
        for i in range(steps):
            t = 2 * math.pi * i / steps
            o.Append(pt(a["x"] + r * math.cos(t), a["y"] + r * math.sin(t)), -1, hole)
    z.SetLocked(True)
    board.Add(z)
    group.AddItem(z)


# --- netlist ----------------------------------------------------------------------------------------------------------

def sexpr(text):
    """Minimal s-expression reader: nested lists of strings."""
    tokens = re.findall(r'\(|\)|"(?:[^"\\]|\\.)*"|[^\s()]+', text)
    stack = [[]]
    for t in tokens:
        if t == "(":
            stack.append([])
        elif t == ")":
            done = stack.pop()
            stack[-1].append(done)
        else:
            stack[-1].append(t[1:-1].replace('\\"', '"').replace("\\\\", "\\") if t.startswith('"') else t)
    return stack[0][0]


def read_netlist():
    """-> ({ref: dict(value, footprint, fields, path)}, {(ref, pin): net name})"""
    def child(node, key):
        return next((c for c in node if isinstance(c, list) and c and c[0] == key), None)

    def text(node, key):
        c = child(node, key)
        return c[1] if c and len(c) > 1 else ""

    tree = sexpr(NETLIST.read_text(encoding="utf-8"))
    comps, nets = {}, {}
    for comp in child(tree, "components")[1:]:
        fields = {}
        for f in (child(comp, "fields") or [])[1:]:
            fields[text(f, "name")] = f[2] if len(f) > 2 else ""
        fields.pop("Footprint", None)
        comps[text(comp, "ref")] = dict(value=text(comp, "value"), footprint=text(comp, "footprint"), fields=fields,
                                        path="/" + text(comp, "tstamps"))
    for net in child(tree, "nets")[1:]:
        for node in net[1:]:
            if isinstance(node, list) and node[0] == "node":
                nets[(text(node, "ref"), text(node, "pin"))] = text(net, "name")
    return comps, nets


def load_footprint(fpid):
    lib, name = fpid.split(":")
    fp = pcbnew.FootprintLoad(str(PROJECT_LIBS.get(lib, KICAD_LIBS / f"{lib}.pretty")), name)
    if fp is None:
        sys.exit(f"footprint {fpid} not found")
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def sync(board, outline, report):
    """Bring the footprints in line with the netlist (see the module docstring)."""
    comps, nets = read_netlist()
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    for ref in sorted(set(fps) - set(comps)):
        report.append(f"  - {ref} ({fps[ref].GetValue()}) is not in {NETLIST.name}: removed")
        BS.detach(board, fps.pop(ref))

    park_x = outline["x"] + outline["width"] / 2 + PARK_GAP
    park_y = outline["y"] + outline["height"] / 2
    net_items = {}
    for ref, comp in sorted(comps.items()):
        old = fps.get(ref)
        fp = old
        if old is None or old.GetFPIDAsString() != comp["footprint"]:
            fp = load_footprint(comp["footprint"])
            fp.SetReference(ref)
            board.Add(fp)
            if old is None:
                fp.SetPosition(pt(park_x, park_y))
                park_y -= tomm(fp.GetBoundingBox(False).GetHeight()) + 1.0
                report.append(f"  + {ref} ({comp['value']}) is new: next to the board")
            else:
                fp.SetPosition(old.GetPosition())
                if old.IsFlipped():
                    fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
                fp.SetOrientationDegrees(old.GetOrientationDegrees())
                fp.SetLocked(old.IsLocked())
                report.append(f"  ~ {ref}: {old.GetFPIDAsString()} -> {comp['footprint']}")
                BS.detach(board, old)
        if fp.GetValue() != comp["value"]:
            if fp is old:
                report.append(f"  ~ {ref}: value {old.GetValue()} -> {comp['value']}")
            fp.SetValue(comp["value"])
        for name, value in comp["fields"].items():
            if not fp.HasField(name) or fp.GetFieldText(name) != value:
                fp.SetField(name, value)
                fp.GetField(name).SetVisible(False)
        fp.SetPath(pcbnew.KIID_PATH(comp["path"]))
        for pad in fp.Pads():
            name = nets.get((ref, pad.GetNumber()), "")
            if pad.GetNetname() == name:
                continue
            if not name:
                pad.SetNetCode(0)
                continue
            net = net_items.get(name) or board.FindNet(name)
            if net is None:
                net = pcbnew.NETINFO_ITEM(board, name)
                board.Add(net)
            net_items[name] = net
            pad.SetNet(net)
            if fp is old:
                report.append(f"  ~ {ref} pad {pad.GetNumber()}: net -> {name}")


def netlist_differences(board):
    comps, _ = read_netlist()
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    out = [f"{r} is not in the netlist" for r in sorted(set(fps) - set(comps))]
    out += [f"{r} is not on the board" for r in sorted(set(comps) - set(fps))]
    out += [f"{r} has footprint {fps[r].GetFPIDAsString()}, the netlist says {c['footprint']}"
            for r, c in sorted(comps.items()) if r in fps and fps[r].GetFPIDAsString() != c["footprint"]]
    return out


# --- footprints -------------------------------------------------------------------------------------------------------

def panel_xy(v):
    """Internal units -> panel frame mm."""
    return (tomm(v.x) - BS.ORIGIN_MM[0], -(tomm(v.y) - BS.ORIGIN_MM[1]))


def place(fp, p):
    if fp.IsFlipped():
        fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    fp.SetOrientationDegrees(p["rotation"])
    fp.SetPosition(pt(p["x"], p["y"]))
    fp.SetLocked(True)


def check_pads(ref, fp, expected, tol=0.01):
    """Pads of the placed footprint against where the component model has them."""
    problems = []
    for number, want in expected.items():
        have = sorted(panel_xy(p.GetPosition()) for p in fp.Pads() if p.GetNumber() == number)
        want = sorted(tuple(xy) for xy in want)
        if len(have) != len(want) or any(math.dist(a, b) > tol for a, b in zip(have, want)):
            problems.append(f"  ! {ref} pad {number}: at {[tuple(round(v, 3) for v in xy) for xy in have]}, "
                            f"the model has it at {[tuple(round(v, 3) for v in xy) for xy in want]}")
    return problems


# --- main -------------------------------------------------------------------------------------------------------------

def setup(do_sync):
    mech = read_mech()
    if PCB.with_name(f"~{PCB.name}.lck").exists():
        sys.exit(f"{PCB.name} is open in KiCad (lock file present) - close it first")
    board = pcbnew.LoadBoard(str(PCB))
    report = []
    tb = board.GetTitleBlock()
    tb.SetTitle(TITLE)
    board.SetTitleBlock(tb)

    # footprints this script locked on an earlier run; those that no longer line up with the panel are released
    was_mech = set()
    for old in list(board.Groups()):
        if old.GetName() == MECH_TAG:
            was_mech |= {i.Cast().GetReference() for i in old.GetItems() if isinstance(i.Cast(), pcbnew.FOOTPRINT)}
            old.RemoveAll()
            BS.detach(board, old)

    if do_sync:
        sync(board, mech["outline"], report)
    else:
        report += [f"  ! {line} (-Sync fixes it)" for line in netlist_differences(board)]

    # outline, cutouts
    BS.remove_own_items(board)
    g = pcbnew.PCB_GROUP(board)
    g.SetName(BS.TAG)
    board.Add(g)
    add_edge(board, g, mech["outline"])
    for a in mech["cutouts"].values():
        add_edge(board, g, a)

    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(mech["thickness"]))
    ds.SetAuxOrigin(BS.pt(0, 0))
    ds.SetGridOrigin(BS.pt(0, 0))

    # footprints that line up with the panel
    gm = pcbnew.PCB_GROUP(board)
    gm.SetName(MECH_TAG)
    board.Add(gm)
    fps = {f.GetReference(): f for f in board.GetFootprints()}
    for ref in sorted(was_mech - set(MECH)):
        if ref in fps:
            fps[ref].SetLocked(False)
            report.append(f"  {ref} is no longer placed from the panel design: unlocked")
    placed = 0
    for ref, role in MECH.items():
        fp, p = fps.get(ref), mech["footprints"].get(role)
        if fp is None or p is None:
            report.append(f"  ! {ref} ({role}): " + ("not on the board" if fp is None else "no such role in the panel"))
            continue
        place(fp, p)
        gm.AddItem(fp)
        placed += 1
        report += check_pads(ref, fp, mech["pads"].get(role, {}))
        if role.startswith("screw"):
            drill = max(tomm(pad.GetDrillSize().x) for pad in fp.Pads())
            if abs(drill - mech["hole_diameter"]) > 0.01:
                report.append(f"  ! {ref}: hole {drill} mm, the panel design wants {mech['hole_diameter']} mm")
    gm.SetLocked(True)
    unmapped = sorted(set(mech["footprints"]) - set(MECH.values()))
    if unmapped:
        report.append(f"  ! roles without a footprint: {', '.join(unmapped)} (add them to MECH)")

    # keep-outs: bosses on top (boss_<n> belongs to screw_<n>, a ring around its courtyard), screw heads below
    role_fp = {role: fps[ref] for ref, role in MECH.items() if ref in fps}
    for name, a in mech["keepouts_top"].items():
        fp = role_fp.get(name.replace("boss", "screw"))
        inner = 0.0
        if fp:
            fp.BuildCourtyardCaches()
            box = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            inner = max(tomm(box.GetWidth()), tomm(box.GetHeight())) / 2 + 0.05
        if inner < a["corner_radius"]:  # else the hole's courtyard covers the boss already
            add_keepout(board, g, name, a, pcbnew.F_Cu, inner)
    for name, a in mech["keepouts_bottom"].items():
        add_keepout(board, g, name, a, pcbnew.B_Cu)
    g.SetLocked(True)

    assert pcbnew.SaveBoard(str(PCB), board), f"saving {PCB} failed"

    # what KiCad makes of the Edge.Cuts shapes
    board = pcbnew.LoadBoard(str(PCB))
    ps = pcbnew.SHAPE_POLY_SET()
    ok = board.GetBoardPolygonOutlines(ps, False)
    holes = ps.HoleCount(0) if ok and ps.OutlineCount() == 1 else -1
    if holes != len(mech["cutouts"]):
        report.append(f"  ! board outline: expected 1 contour with {len(mech['cutouts'])} cutouts, KiCad sees "
                      f"{ps.OutlineCount() if ok else 0} contour(s) with {holes} cutout(s)")

    o = mech["outline"]
    print(f"supply_ui: {o['width']} x {o['height']} mm, {len(mech['cutouts'])} cutouts, "
          f"{len(mech['keepouts_top'])} + {len(mech['keepouts_bottom'])} keep-outs (top + bottom), "
          f"{placed} footprints placed from the panel design and locked")
    for line in report:
        print(line)


if __name__ == "__main__":
    args = [a.lower().lstrip("-") for a in sys.argv[1:]]
    if set(args) - {"sync"}:
        sys.exit(f"usage: {Path(__file__).name} [sync]")
    setup("sync" in args)
