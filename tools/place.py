"""
Placement for the supply boards (layout steps 2 + 3): draws the floor plan from tools/floorplan.py on User.Comments and
places the footprints: FIXED parts at their coordinates, then every cluster (an IC + its passives, each passive next to
the pin it connects to) as close to its target as its area allows. Each cluster becomes a KiCad group
"place:<cluster>", so it can be dragged around by hand as one block.

Run with KiCad's Python, boards CLOSED in KiCad (power before control: J971 follows J951 on the power board):
    .\\tools\\run_place.ps1                 # both boards
    .\\tools\\run_place.ps1 control         # one board

Locked footprints (locked directly, or through a locked group) are never moved and act as obstacles: lock what you have
placed by hand, re-run, and the script arranges the rest around it. Everything else is moved on every run.
"""

import math
import sys
from collections import Counter
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import floorplan as FP  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TAG = "place:"
FRAME_TAG = "floorplan"
GAP_IN = 0.15      # courtyard gap inside a cluster
GAP_OUT = 0.8      # gap between a cluster's parts and anything outside the cluster (routing room)
COMPACT = 0.5      # member placement: weight of "close to the anchor" against "close to its pin"
GROUNDS = {"GND", "GND_ISO", ""}
DIRS = {"E": (1, 0), "W": (-1, 0), "N": (0, -1), "S": (0, 1)}
ROTS = (0, 90, 180, 270)

mm, tomm = pcbnew.FromMM, pcbnew.ToMM


def spiral(radius, step=0.25):
    pts = [(i * step, j * step) for i in range(-int(radius / step), int(radius / step) + 1)
           for j in range(-int(radius / step), int(radius / step) + 1)]
    pts = [p for p in pts if math.hypot(*p) <= radius]
    return sorted(pts, key=lambda p: (math.hypot(*p), p))


SPIRAL = spiral(12.0)
SPIRAL_FAR = spiral(30.0, 0.5)


def shift(r, dx, dy):
    return (r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy)


def overlap(a, b, gap):
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


def inside(r, box):
    return r[0] >= box[0] - 1e-6 and r[1] >= box[1] - 1e-6 and r[2] <= box[2] + 1e-6 and r[3] <= box[3] + 1e-6


def centre(r):
    return ((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)


def detach(board, item):
    """board.Remove() hands the object to Python; keep SWIG from destroying it (see board_setup.py)."""
    board.Remove(item)
    item.thisown = False


class Placer:
    def __init__(self, name):
        self.name = name
        self.cfg = FP.BOARDS[name]
        self.path = ROOT / f"kicad/supply_{name}/supply_{name}.kicad_pcb"
        if self.path.with_name(f"~{self.path.name}.lck").exists():
            sys.exit(f"{self.path.name} is open in KiCad (lock file present) - close it first")
        self.b = pcbnew.LoadBoard(str(self.path))
        self.x0s, self.y0s, self.L, self.W = outline(self.b)
        self.cx, self.cy = self.x0s + self.L / 2, self.y0s + self.W / 2
        self.fps = {f.GetReference(): f for f in self.b.GetFootprints()}
        self.obst = {"top": [], "bottom": []}  # (x0, y0, x1, y1, ref) in board coordinates
        self.pos = {}                           # ref -> (rot, bottom, px, py) footprint origin, board coordinates
        self.cache = {}
        self.report = []
        self.locked = locked_refs(self.b)
        for z in self.b.Zones():  # slot keep-outs block both sides
            if z.GetIsRuleArea() and z.GetZoneName().startswith("board_setup:"):
                r = self.to_board_rect(z.GetBoundingBox())
                self.obst["top"].append((*r, "slot"))
                self.obst["bottom"].append((*r, "slot"))
        for ref in self.locked:
            self.register_current(ref)

    # ------------------------------------------------------------------ coordinates / geometry
    def to_board_rect(self, box):
        return (tomm(box.GetLeft()) - self.cx, tomm(box.GetTop()) - self.cy,
                tomm(box.GetRight()) - self.cx, tomm(box.GetBottom()) - self.cy)

    def set_side(self, fp, bottom):
        if fp.IsFlipped() != bottom:
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)

    def geom(self, ref, rot, bottom):
        """Courtyard bbox and pads relative to the footprint origin, for a rotation and side."""
        key = (ref, rot, bottom)
        if key not in self.cache:
            assert ref not in self.locked
            fp = self.fps[ref]
            self.set_side(fp, bottom)
            fp.SetOrientationDegrees(rot)
            fp.SetPosition(pcbnew.VECTOR2I(0, 0))
            fp.BuildCourtyardCaches()
            cy = fp.GetCourtyard(pcbnew.B_CrtYd if bottom else pcbnew.F_CrtYd)
            box = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
            rect = (tomm(box.GetLeft()), tomm(box.GetTop()), tomm(box.GetRight()), tomm(box.GetBottom()))
            pads = []
            for p in fp.Pads():
                pp, pb = p.GetPosition(), p.GetBoundingBox()
                attr = p.GetAttribute()
                pads.append(dict(num=p.GetNumber(), net=p.GetNetname(), x=tomm(pp.x), y=tomm(pp.y),
                                 tht=attr in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH),
                                 npth=attr == pcbnew.PAD_ATTRIB_NPTH,
                                 rect=(tomm(pb.GetLeft()), tomm(pb.GetTop()), tomm(pb.GetRight()), tomm(pb.GetBottom()))))
            self.cache[key] = dict(rect=rect, pads=pads)
        return self.cache[key]

    def pad_xy(self, g, num, npth=False):
        ps = [p for p in g["pads"] if (p["npth"] if npth else p["num"] == num)]
        assert ps, f"no pad {num!r}"
        return sum(p["x"] for p in ps) / len(ps), sum(p["y"] for p in ps) / len(ps)

    def rot_for(self, ref, spec, bottom):
        if spec is None:
            return 0
        specs = spec if isinstance(spec, list) else [spec]
        best = None
        for rot in ROTS:
            g = self.geom(ref, rot, bottom)
            s = 0.0
            for a, b, d in specs:
                pa = centre(g["rect"]) if a is None else self.pad_xy(g, a)
                pb = self.pad_xy(g, b)
                vx, vy = pb[0] - pa[0], pb[1] - pa[1]
                s += (vx * DIRS[d][0] + vy * DIRS[d][1]) / (math.hypot(vx, vy) or 1)
            if best is None or s > best[0] + 1e-9:
                best = (s, rot)
        return best[1]

    # ------------------------------------------------------------------ placing / obstacles
    def hits(self, rect, side, gap, near=None):
        for o in (near if near is not None else self.obst[side]):
            if overlap(rect, o, gap):
                return o
        return None

    def put_origin(self, ref, rot, bottom, px, py):
        fp = self.fps[ref]
        self.set_side(fp, bottom)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pcbnew.VECTOR2I(mm(px + self.cx), mm(py + self.cy)))
        self.pos[ref] = (rot, bottom, px, py)
        g = self.geom(ref, rot, bottom)
        side, other = ("bottom", "top") if bottom else ("top", "bottom")
        self.obst[side].append((*shift(g["rect"], px, py), ref))
        for p in g["pads"]:
            if p["tht"]:
                self.obst[other].append((*shift(p["rect"], px - 0.2, py - 0.2)[:2],
                                         *shift(p["rect"], px + 0.2, py + 0.2)[2:], ref))
        # geom() of other rotations moved the footprint; restore the final state
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pcbnew.VECTOR2I(mm(px + self.cx), mm(py + self.cy)))

    def put_centre(self, ref, rot, bottom, x, y):
        r = self.geom(ref, rot, bottom)["rect"]
        c = centre(r)
        self.put_origin(ref, rot, bottom, x - c[0], y - c[1])

    def register_current(self, ref):
        fp = self.fps[ref]
        bottom = fp.IsFlipped()
        fp.BuildCourtyardCaches()
        cy = fp.GetCourtyard(pcbnew.B_CrtYd if bottom else pcbnew.F_CrtYd)
        box = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
        self.obst["bottom" if bottom else "top"].append((*self.to_board_rect(box), ref))
        p = fp.GetPosition()
        self.pos[ref] = (fp.GetOrientationDegrees(), bottom, tomm(p.x) - self.cx, tomm(p.y) - self.cy)

    def abs_pads(self, ref):
        rot, bottom, px, py = self.pos[ref]
        if ref in self.locked:
            fp = self.fps[ref]
            return [dict(num=p.GetNumber(), net=p.GetNetname(), x=tomm(p.GetPosition().x) - self.cx,
                         y=tomm(p.GetPosition().y) - self.cy, npth=p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH)
                    for p in fp.Pads()]
        return [dict(p, x=p["x"] + px, y=p["y"] + py) for p in self.geom(ref, rot, bottom)["pads"]]

    # ------------------------------------------------------------------ steps
    def place_fixed(self):
        half = self.L / 2
        for ref, x, y, spec, side in self.cfg["fixed"]:
            if ref in self.locked:
                continue
            bottom = side == "bottom"
            rot = self.rot_for(ref, spec, bottom)
            r = self.geom(ref, rot, bottom)["rect"]
            w = r[2] - r[0]
            if x == "W":
                x = -half + w / 2
            elif x == "E":
                x = half - w / 2
            c_r = (x - w / 2, y - (r[3] - r[1]) / 2, x + w / 2, y + (r[3] - r[1]) / 2)
            hit = self.hits(c_r, "bottom" if bottom else "top", 0.0)
            if hit:
                self.report.append(f"  ! fixed {ref} overlaps {hit[4]}")
            self.put_centre(ref, rot, bottom, x, y)
        for ref, host in self.cfg.get("aligned", []):
            if ref in self.locked:
                continue
            hx, hy = self.pad_xy({"pads": self.abs_pads(host)}, None, npth=True)
            ox, oy = self.pad_xy(self.geom(ref, 0, False), None, npth=True)
            self.put_origin(ref, 0, False, hx - ox, hy - oy)

    def place_b2b(self, power):
        """J971 (bottom) so that each of its pins sits on the mirrored J951 pin (2k-1 <-> 2k)."""
        ref, other = self.cfg["b2b"]
        if ref in self.locked:
            return
        off = power.L / 2 - self.L / 2  # control x = power x + off (rear edges aligned)
        target = {p["num"]: (p["x"] + off, p["y"]) for p in power.abs_pads(other)}
        mirror = lambda n: str(int(n) + 1 if int(n) % 2 else int(n) - 1)  # noqa: E731
        for rot in ROTS:
            g = self.geom(ref, rot, True)
            pads = {p["num"]: (p["x"], p["y"]) for p in g["pads"]}
            t = (target[mirror("1")][0] - pads["1"][0], target[mirror("1")][1] - pads["1"][1])
            if all(math.hypot(pads[n][0] + t[0] - target[mirror(n)][0], pads[n][1] + t[1] - target[mirror(n)][1])
                   < 0.01 for n in pads):
                self.put_origin(ref, rot, True, *t)
                self.report.append(f"  B2B: {ref} pins sit on the mirrored {other} pins (40/40)")
                return
        sys.exit(f"no rotation of {ref} matches {other}'s mirrored pinout")

    # ------------------------------------------------------------------ clusters
    def place_members(self, anchor, members, obst, bounds, frame_pos):
        """Pin-aware placement around an already positioned anchor. obst = list of rects (same frame);
        frame_pos(ref) -> pads in that frame. Returns {ref: (rot, px, py)}."""
        out = {}
        load = Counter()
        a_rect = next(o for o in obst if o[4] == anchor)
        a_c = centre(a_rect)
        remaining = list(members)
        nets_of = {m: {p["net"] for p in self.geom(m, 0, False)["pads"]} - GROUNDS for m in remaining}

        def placed_pads():
            yield from ((anchor, p) for p in frame_pos(anchor))
            for r, (rot, px, py) in out.items():
                yield from ((r, dict(p, x=p["x"] + px, y=p["y"] + py)) for p in self.geom(r, rot, False)["pads"])

        while remaining:
            pp = list(placed_pads())
            best_m, best_t = None, None
            for m in remaining:
                cands = [(r, p) for r, p in pp if p["net"] in nets_of[m]]
                if not cands:
                    continue
                on_anchor = [c for c in cands if c[0] == anchor]
                use = on_anchor or cands
                # the most specific net first (I2C pull-up -> its SCL pin, not one of the many 3V3 pins)
                count = Counter(p["net"] for _, p in use)
                use = [c for c in use if count[c[1]["net"]] == min(count.values())]
                tgt = min(use, key=lambda c: (load[(c[0], c[1]["num"])], c[1]["num"]))
                rank = (0 if on_anchor else 1)
                if best_m is None or rank < best_t[0]:
                    best_m, best_t = m, (rank, tgt)
                    if rank == 0:
                        break
            if best_m is None:  # nothing shared (ground-only part, or connected outside the cluster)
                best_m, tgt = remaining[0], None
            else:
                tgt = best_t[1]
            remaining.remove(best_m)

            if tgt:
                load[(tgt[0], tgt[1]["num"])] += 1
                tx, ty, net = tgt[1]["x"], tgt[1]["y"], tgt[1]["net"]
            else:
                tx, ty, net = a_c[0], a_c[1], None
            best = None
            for spiral_pts in (SPIRAL, SPIRAL_FAR):
                near = [o for o in obst if abs(centre(o)[0] - tx) < 45 and abs(centre(o)[1] - ty) < 45]
                for rot in ROTS:
                    g = self.geom(best_m, rot, False)
                    mp = [p for p in g["pads"] if net and p["net"] == net]
                    ox, oy = (mp[0]["x"], mp[0]["y"]) if mp else centre(g["rect"])
                    found = 0
                    for dx, dy in spiral_pts:
                        px, py = tx - ox + dx, ty - oy + dy
                        r = shift(g["rect"], px, py)
                        if bounds and not any(inside(r, b) for b in bounds):
                            continue
                        if self.hits(r, "top", GAP_IN, near):
                            continue
                        # close to its pin, but also hugging the anchor (keeps the cluster compact)
                        cost = math.hypot(dx, dy) + COMPACT * math.dist(centre(r), a_c)
                        if best is None or cost < best[0]:
                            best = (cost, rot, px, py, r)
                        found += 1
                        if found >= 60:
                            break
                if best:
                    break
            if not best:
                self.report.append(f"  ! no room for {best_m} next to {anchor}")
                continue
            _, rot, px, py, r = best
            out[best_m] = (rot, px, py)
            obst.append((*r, best_m))
        return out

    def place_cluster(self, name, area, anchor, members, target):
        members = [m for m in members if m not in self.locked and m not in self.pos]
        bounds = self.cfg["areas"].get(area) if area else None
        if anchor in self.pos:  # anchor fixed / locked: place the members directly on the board
            obst = self.obst["top"]
            if not any(o[4] == anchor for o in obst):  # bottom-side anchor: its THT pads are on top already
                rect = self.to_board_rect(self.fps[anchor].GetBoundingBox(False)) if anchor in self.locked else \
                    shift(self.geom(anchor, self.pos[anchor][0], self.pos[anchor][1])["rect"], *self.pos[anchor][2:])
                obst = obst + [(*rect, anchor)]
            out = self.place_members(anchor, members, list(obst), bounds, lambda r: self.abs_pads(r))
            for ref, (rot, px, py) in out.items():
                self.put_origin(ref, rot, False, px, py)
            self.report.append(f"  {name:32s} {len(out):3d} parts around the fixed {anchor}")
            self.group(name, list(out))
            return
        # build the cluster around the anchor at the origin, then move it as one block
        ga = self.geom(anchor, 0, False)
        obst = [(*ga["rect"], anchor)]
        out = self.place_members(anchor, members, obst, None, lambda r: self.geom(anchor, 0, False)["pads"])
        out[anchor] = (0, 0.0, 0.0)
        rects = [o[:4] for o in obst]
        bb = (min(r[0] for r in rects), min(r[1] for r in rects), max(r[2] for r in rects), max(r[3] for r in rects))
        bc = centre(bb)
        target = target or (0.0, 0.0)
        t = self.fit(bb, rects, bounds, target)
        where = "" if t else " (OUTSIDE its area)"
        if not t:
            t = self.fit(bb, rects, [(-self.L / 2, -self.W / 2, self.L / 2, self.W / 2)], target)
        if not t:
            self.report.append(f"  ! cluster {name}: no room anywhere")
            return
        for ref, (rot, px, py) in out.items():
            self.put_origin(ref, rot, False, px + t[0], py + t[1])
        dist = math.dist((bc[0] + t[0], bc[1] + t[1]), target)
        self.report.append(f"  {name:32s} {len(out):3d} parts {bb[2] - bb[0]:5.1f} x {bb[3] - bb[1]:5.1f} mm, "
                           f"{dist:4.1f} mm from target{where}")
        self.group(name, list(out))

    def fit(self, bb, rects, bounds, target, step=0.5):
        """Translation that puts the cluster (bbox bb, part rects) inside one of the bounds, as close to target as
        possible, with GAP_OUT around each part (clusters may interlock; only the parts must stay clear)."""
        cands = []
        bc = centre(bb)
        for box in bounds or []:
            nx = int(((box[2] - bb[2]) - (box[0] - bb[0])) / step) + 1
            ny = int(((box[3] - bb[3]) - (box[1] - bb[1])) / step) + 1
            for i in range(max(nx, 0)):
                for j in range(max(ny, 0)):
                    x, y = box[0] - bb[0] + i * step, box[1] - bb[1] + j * step
                    cands.append((math.hypot(bc[0] + x - target[0], bc[1] + y - target[1]), x, y))
        cands.sort()
        top = self.obst["top"]
        for _, x, y in cands:
            sb = shift(bb, x, y)
            near = [o for o in top if overlap(sb, o, GAP_OUT)]
            if not near or not any(self.hits(shift(r, x, y), "top", GAP_OUT, near) for r in rects):
                return x, y
        return None

    def group(self, name, refs):
        refs = [r for r in refs if self.fps[r].GetParentGroup() is None]
        if not refs:
            return
        g = pcbnew.PCB_GROUP(self.b)
        g.SetName(TAG + name)
        self.b.Add(g)
        for r in refs:
            g.AddItem(self.fps[r])

    def assign_leftovers(self, clusters):
        done = set(self.locked) | {f[0] for f in self.cfg["fixed"]} | {a[0] for a in self.cfg.get("aligned", [])}
        if "b2b" in self.cfg:
            done.add(self.cfg["b2b"][0])
        for c in clusters:
            done |= {c[2], *c[3]}
        left = sorted(set(self.fps) - done)
        nets = lambda r: {p.GetNetname() for p in self.fps[r].Pads()} - GROUNDS  # noqa: E731
        for ref in left:
            best = max(clusters, key=lambda c: len(nets(ref) & set().union(*(nets(r) for r in (c[2], *c[3])))))
            shared = nets(ref) & set().union(*(nets(r) for r in (best[2], *best[3])))
            if shared:
                best[3].append(ref)
                self.report.append(f"  + {ref} -> cluster '{best[0]}' (shares {', '.join(sorted(shared))})")
            else:
                clusters.append((ref, None, ref, [], (0, 0)))
                self.report.append(f"  + {ref}: no shared net, placed on its own")

    # ------------------------------------------------------------------ drawing
    def draw_frames(self, power=None):
        for g in list(self.b.Groups()):
            if g.GetName() == FRAME_TAG or (g.GetName().startswith(TAG) and not g.IsLocked()):
                items = [i.Cast() for i in g.GetItems()]
                g.RemoveAll()
                if g.GetName() == FRAME_TAG:
                    for it in items:
                        detach(self.b, it)
                detach(self.b, g)
        gf = pcbnew.PCB_GROUP(self.b)
        gf.SetName(FRAME_TAG)
        self.b.Add(gf)

        def add(item):
            self.b.Add(item)
            gf.AddItem(item)

        def P(x, y):
            return pcbnew.VECTOR2I(mm(x + self.cx), mm(y + self.cy))

        def text(s, x, y, size=1.0):
            t = pcbnew.PCB_TEXT(self.b)
            t.SetText(s)
            t.SetLayer(pcbnew.Cmts_User)
            t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
            t.SetTextThickness(mm(size * 0.15))
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_LEFT)
            t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_TOP)
            t.SetPosition(P(x, y))
            add(t)

        def seg(a, b, w=0.15):
            s = pcbnew.PCB_SHAPE(self.b)
            s.SetShape(pcbnew.SHAPE_T_SEGMENT)
            s.SetStart(P(*a))
            s.SetEnd(P(*b))
            s.SetLayer(pcbnew.Cmts_User)
            s.SetWidth(mm(w))
            add(s)

        for label, rects in self.cfg["areas"].items():
            for i, (x0, y0, x1, y1) in enumerate(rects):
                x0, y0, x1, y1 = x0 + 0.2, y0 + 0.2, x1 - 0.2, y1 - 0.2
                for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
                    seg(a, b)
                if i == 0:
                    text(label, x0 + 0.5, y1 - 1.6, 0.9)
        for x, y, s in self.cfg.get("notes", []):
            text(s, x, y, 0.9)
        for a, b, s in self.cfg.get("lines", []):
            seg(a, b, 0.3)
            text(s, a[0] + 0.5, a[1] + 3.5, 0.9)
        if power and self.cfg.get("tall_below"):
            off = power.L / 2 - self.L / 2
            for ref in self.cfg["tall_below"]:
                r = next(o for o in power.obst["top"] if o[4] == ref)  # courtyard, power-board coordinates
                r = (r[0] + off - 1, r[1] - 1, r[2] + off + 1, r[3] + 1)
                z = pcbnew.ZONE(self.b)
                z.SetIsRuleArea(True)
                z.SetZoneName(f"{FRAME_TAG}: {ref} on the power board below (tall)")
                ls = pcbnew.LSET()
                ls.AddLayer(pcbnew.B_Cu)
                z.SetLayerSet(ls)
                z.SetDoNotAllowFootprints(True)
                z.SetDoNotAllowTracks(False)
                z.SetDoNotAllowVias(False)
                z.SetDoNotAllowPads(False)
                z.SetDoNotAllowZoneFills(False)
                o = z.Outline()
                o.NewOutline()
                for x, y in ((r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3])):
                    o.Append(P(x, y))
                add(z)
                text(f"{ref} below", r[0] + 0.5, r[1] + 0.5, 0.9)
        # remove rule areas of earlier runs that lost their group
        for z in list(self.b.Zones()):
            if z.GetIsRuleArea() and z.GetZoneName().startswith(FRAME_TAG + ":") and z.GetParentGroup() is None:
                detach(self.b, z)
        gf.SetLocked(True)

    def silk(self):
        if not FP.SILK_HIDE_SMALL:
            return 0
        n = 0
        for ref, fp in self.fps.items():
            prefix = ref.rstrip("0123456789")
            fp.BuildCourtyardCaches()
            r = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd).BBox()
            area = tomm(r.GetWidth()) * tomm(r.GetHeight())
            keep = prefix in FP.SILK_KEEP_PREFIX or "led" in fp.GetFPIDAsString().lower() or area >= FP.SILK_MIN_AREA
            fp.Reference().SetVisible(keep)
            n += not keep
        return n

    # ------------------------------------------------------------------ main
    def run(self, power=None):
        clusters = [(n, a, an, list(m), t) for n, a, an, m, t in self.cfg["clusters"]]
        self.draw_frames(power)
        self.place_fixed()
        if power and "b2b" in self.cfg:
            self.place_b2b(power)
        self.assign_leftovers(clusters)
        # clusters on fixed anchors first (they need the space next to their anchor), then the big ones
        clusters.sort(key=lambda c: (0 if c[2] in self.pos else 1, -len(c[3])))
        for c in clusters:
            self.place_cluster(*c)
        hidden = self.silk()
        assert pcbnew.SaveBoard(str(self.path), self.b)
        print(f"supply_{self.name}: {len(self.pos)} footprints placed ({len(self.locked)} locked, untouched), "
              f"{hidden} small refs hidden on silk")
        for line in self.report:
            print(line)


def outline(board):
    xs, ys = [], []
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.Edge_Cuts:
            for p in (d.GetStart(), d.GetEnd()):
                xs.append(tomm(p.x))
                ys.append(tomm(p.y))
    return min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)


def locked_refs(board):
    """Footprints locked directly or through a locked group (GetParentGroup() returns an EDA_GROUP without
    IsLocked(), so walk the board's PCB_GROUPs instead)."""
    out = {f.GetReference() for f in board.GetFootprints() if f.IsLocked()}
    for g in board.Groups():
        if g.IsLocked():
            for it in g.GetItems():
                it = it.Cast()
                if isinstance(it, pcbnew.FOOTPRINT):
                    out.add(it.GetReference())
    return out


if __name__ == "__main__":
    names = sys.argv[1:] or ["power", "control"]
    if "power" in names:
        Placer("power").run()
    if "control" in names:
        power = Placer("power")  # read-only view of the saved power board: J951 and the tall parts
        for ref in power.fps:
            if ref not in power.locked:
                power.register_current(ref)
        power.locked = set(power.fps)
        Placer("control").run(power)
