"""
Simplified 3D bodies for KiCad footprints: a box (or cylinder) over the F.Fab body outline, as tall as the part.

Height, in order of precedence:
  1. BY_REF override (part-specific: the chosen MPN differs from the generic package; refs are locked, see design/reflock.py)
  2. BY_FPID override (whole footprint, or "Library:" prefix)
  3. the KiCad 3D model's bounding box (cached in out/model_extents.json)
  4. FALLBACK_HEIGHT, drawn magenta -> add an override
THT parts also get their leads on the solder side (model z-min, at least LEAD_PROTRUSION_MIN).

Input is one footprint record of out/mech_<board>.json (tools/export_mech.py); output is in the board frame
(see mech_design.py): origin at the board centre on its bottom face, Z up.
"""

import json
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import build123d as bd

ROOT = Path(__file__).resolve().parents[1]
KICAD_3DMODEL_DIR = os.environ.get("KICAD10_3DMODEL_DIR", "C:/Program Files/KiCad/10.0/share/kicad/3dmodels")
MODEL_CACHE = ROOT / "out/model_extents.json"

FALLBACK_HEIGHT = 5.0
LEAD_PROTRUSION_MIN = 1.5  # hand-soldered THT leads, trimmed
LEAD_MAX_DRILL = 2.5  # bigger plated holes are not leads (mounting, wire relief)


@dataclass(frozen=True)
class Body:
    height: float | None = None  # body top above the board surface; None -> from the KiCad model
    shape: str = "box"  # "box" | "cyl" | "header" (plastic base + pins up to `height`) | "none" (pads only)
    size: tuple[float, float] | None = None  # footprint-local X/Y size, replaces the F.Fab size (same centre)
    base: float = 2.5  # "header": plastic base height
    color: str | None = None
    note: str = ""  # where the numbers come from
    estimate: bool = False  # height not checked against a datasheet -> listed by the assembly report


BY_FPID = {
    "TestPoint:": Body(shape="none"),
    "MountingHole:": Body(shape="none"),
    "supply1:L_Coilcraft_SER2918H": Body(height=17.78, note="Coilcraft SER2900 datasheet, max"),
    "Package_TO_SOT_THT:TO-247-2_Horizontal_TabDown": Body(height=5.0, note="no KiCad model; LTO100 body", estimate=True),
    "Capacitor_SMD:CP_Elec_10x12.6": Body(shape="cyl"),
    "Capacitor_THT:CP_Radial_D10.0mm_P5.00mm": Body(shape="cyl"),
    "Connector_PinHeader_2.54mm:": Body(shape="header", base=2.5),
    "Connector_PinHeader_1.27mm:": Body(shape="header", base=1.5),
    # right-angle headers: one box over body + pins (F.Fab), without the plug
    "Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Horizontal": Body(note="right-angle, pins included"),
    "Connector_PinHeader_2.54mm:PinHeader_2x10_P2.54mm_Horizontal": Body(note="right-angle, pins included"),
    # KiCad 10 library has no model file for these
    "Connector_Wire:": Body(shape="none", note="wires leave the board"),
    "Package_SON:Infineon_PG-TDSON-8_6.15x5.15mm": Body(height=1.1, note="PG-TDSON-8 max"),
    "Package_SON:WSON-12-1EP_3x3mm_P0.5mm_EP1.5x2.5mm": Body(height=0.8, note="WSON-12 max"),
    "Inductor_SMD:L_Bourns-SRN8040_8x8.15mm": Body(height=4.0, note="Bourns SRN8040 8x8x4"),
    "Package_SO:TI_SO-PowerPAD-8_ThermalVias": Body(height=1.7, note="TI DDA (HSOIC-8) max"),
    "Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12": Body(height=3.3, note="16P top-mount", estimate=True),
}

# Power and control board in one table (power: 1xx-4xx, 9xx; control: 5xx-7xx, 971). The UI board numbers from 1:
# its overrides go by footprint (BY_FPID)
BY_REF = {
    "C217": Body(height=14.0, note="LKME1402A101MF D10xL14, LCSC C443138 seated max"),
    "C223": Body(height=13.5, note="SPZ1JM101G12O00RAXXX D10xL12 +1.5 sleeve", estimate=True),
    "C228": Body(height=12.7, note="PCR1J101MCL1GS, LCSC C5154285 seated max"),
    "F401": Body(height=17.5, note="Keystone 3568 holder 7.37 mm + inserted mini blade fuse", estimate=True),
    "PS601": Body(height=10.2, size=(6.0, 11.6), color="#202020", note="Mornsun B0505S-1WR3 SIP-4 11.6x6.0x10.16"),
}

# footprint id prefix -> colour (first match wins)
COLORS = [
    ("Capacitor_SMD:CP_Elec", "#b8bcc2"),
    ("Capacitor_THT:CP_Radial", "#2a3f8f"),
    ("Capacitor_SMD:", "#c8a675"),
    ("Resistor_SMD:", "#1e1e1e"),
    ("Connector_USB:", "#c0c0c0"),
    ("Mounting_Wuerth:", "#c0c0c0"),
    ("Fuse:", "#3060c0"),
    ("LED_SMD:", "#e03030"),
    ("Inductor_SMD:", "#3a3a3a"),
    ("supply1:L_", "#3a3a3a"),
    ("", "#262626"),
]
FALLBACK_COLOR = "#ff00ff"
LEAD_COLOR = "#d0d0d0"


@dataclass
class ComponentInfo:
    ref: str
    fpid: str
    value: str
    side: str
    height: float  # above the mounting surface
    source: str  # "ref" | "fpid" | "model" | "fallback" | "none" (not drawn)
    note: str = ""
    estimate: bool = False
    shapes: list = field(default_factory=list)  # body (+ leads), in the frame they were last placed in


def lookup(table: dict, fpid: str) -> Body | None:
    if fpid in table:
        return table[fpid]
    return table.get(fpid.split(":")[0] + ":")


def color_for(fpid: str) -> str:
    return next(c for prefix, c in COLORS if fpid.startswith(prefix))


# --- KiCad 3D models ----------------------------------------------------------------------------------------------------

_model_cache: dict | None = None


def model_extents(fp: dict) -> tuple[float, ...] | None:
    """(xmin, xmax, ymin, ymax, zmin, zmax) of the first shown model, footprint-local, KiCad model frame (z=0 = board
    surface, z up). None if there is no model or the file is missing."""
    global _model_cache
    if _model_cache is None:
        _model_cache = json.loads(MODEL_CACHE.read_text()) if MODEL_CACHE.exists() else {}
    model = next((m for m in fp["models"] if m["show"]), None)
    if model is None:
        return None
    path = re.sub(r"\$\{KICAD\d+_3DMODEL_DIR\}", KICAD_3DMODEL_DIR.replace("\\", "/"), model["file"])
    if path not in _model_cache:
        candidates = [path] + [str(Path(path).with_suffix(s)) for s in (".step", ".stp")]
        found = next((p for p in candidates if Path(p).is_file()), None)
        if found:
            bb = bd.import_step(found).bounding_box()
            _model_cache[path] = [bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.min.Z, bb.max.Z]
        else:
            _model_cache[path] = None
        MODEL_CACHE.parent.mkdir(exist_ok=True)
        MODEL_CACHE.write_text(json.dumps(_model_cache, indent=1))
    ext = _model_cache[path]
    if ext is None:
        return None
    (ox, oy, oz), (sx, sy, sz) = model["offset"], model["scale"]
    return (ox + ext[0] * sx, ox + ext[1] * sx, oy + ext[2] * sy, oy + ext[3] * sy, oz + ext[4] * sz, oz + ext[5] * sz)


# --- geometry ----------------------------------------------------------------------------------------------------------

def local_bbox(fp: dict, points: list) -> tuple[float, float, float, float]:
    """Bounding box (cx, cy, w, h) of KiCad board points in the footprint's rotated frame (Y up, mirrored as placed)."""
    fx, fy = fp["xy"]
    th = math.radians(fp["rot"])
    c, s = math.cos(th), math.sin(th)
    lx, ly = [], []
    for px, py in points:
        dx, dy = px - fx, -(py - fy)
        lx.append(dx * c + dy * s)
        ly.append(-dx * s + dy * c)
    return ((min(lx) + max(lx)) / 2, (min(ly) + max(ly)) / 2, max(lx) - min(lx), max(ly) - min(ly))


def create_component(fp: dict, thickness: float) -> ComponentInfo:
    """Body (+ THT leads) of one footprint record, in the board frame."""
    fpid, ref = fp["fpid"], fp["ref"]
    spec, source = BY_REF.get(ref), "ref"
    if spec is None:
        spec, source = lookup(BY_FPID, fpid), "fpid"
    if spec is None:
        spec = Body()
    ext = model_extents(fp)
    height = spec.height
    if height is None:
        height, source = (ext[5], "model") if ext else (FALLBACK_HEIGHT, "fallback")
    info = ComponentInfo(ref, fpid, fp["value"], fp["side"], height, source, spec.note, spec.estimate)
    if spec.shape == "none":
        info.source = "none"
        return info

    points = fp["fab"] or fp["courtyard"]
    if not points:
        info.source = "fallback"
        return info
    cx, cy, w, h = local_bbox(fp, points)
    if spec.size:
        w, h = spec.size
    bottom = fp["side"] == "bottom"
    z_align = bd.Align.MAX if bottom else bd.Align.MIN
    align = (bd.Align.CENTER, bd.Align.CENTER, z_align)
    body_h = spec.base if spec.shape == "header" else height
    if spec.shape == "cyl":
        body = bd.Cylinder(min(w, h) / 2, body_h, align=align)
    else:
        body = bd.Box(w, h, body_h, align=align)
    surface = 0.0 if bottom else thickness
    fx, fy = fp["xy"]
    body = bd.Pos(fx, -fy, surface) * bd.Rot(0, 0, fp["rot"]) * bd.Pos(cx, cy, 0) * body
    body.color = bd.Color(FALLBACK_COLOR if info.source == "fallback" else spec.color or color_for(fpid))
    body.label = ref
    info.shapes.append(body)

    # pins standing above a header body, leads through the board on the solder side
    leads = []
    for pad in fp["pads"]:
        d = min(pad["drill"])
        if not pad["plated"] or d >= LEAD_MAX_DRILL or fp["mount"] != "tht":
            continue
        px, py = pad["xy"][0], -pad["xy"][1]
        pin = min(0.65 * d, 0.64)
        protrusion = max((-ext[4] - thickness) if ext else 0.0, LEAD_PROTRUSION_MIN)
        if bottom:
            leads.append(bd.Pos(px, py, thickness) * bd.Box(pin, pin, protrusion, align=(bd.Align.CENTER,) * 2 + (bd.Align.MIN,)))
        else:
            leads.append(bd.Pos(px, py, 0) * bd.Box(pin, pin, protrusion, align=(bd.Align.CENTER,) * 2 + (bd.Align.MAX,)))
        if spec.shape == "header":
            above = bd.Box(pin, pin, height, align=align)
            leads.append(bd.Pos(px, py, surface) * above)
    if leads:
        lead_shape = bd.Compound(leads, label=f"{ref} leads")
        lead_shape.color = bd.Color(LEAD_COLOR)
        info.shapes.append(lead_shape)
    return info
