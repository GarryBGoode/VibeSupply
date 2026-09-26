"""
Generate symbols/supply1.kicad_sym (KiCad symbol library) from the pin tables in design/parts.py.

Symbols are plain rectangles: first half of the pin table on the left, second half on the right,
in datasheet pin order. Good enough for review and for the netlist; tidy them in KiCad if you like.
"""

import os

from skidl.pin import pin_types as T

KICAD_PIN_TYPE = {
    T.INPUT: "input", T.OUTPUT: "output", T.BIDIR: "bidirectional", T.TRISTATE: "tri_state",
    T.PASSIVE: "passive", T.UNSPEC: "unspecified", T.PWRIN: "power_in", T.PWROUT: "power_out",
    T.OPENCOLL: "open_collector", T.OPENEMIT: "open_emitter", T.NOCONNECT: "no_connect", T.FREE: "free",
}
PITCH = 2.54
PIN_LEN = 2.54


def _esc(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _prop(name, value, x, y, hide=False):
    h = " (hide yes)" if hide else ""
    return (f'\t\t(property "{name}" "{_esc(value)}"\n\t\t\t(at {x:.2f} {y:.2f} 0)\n'
            f'\t\t\t(effects (font (size 1.27 1.27)){h})\n\t\t)\n')


def symbol(name, d):
    pins = d["pins"]
    n_left = (len(pins) + 1) // 2
    left, right = pins[:n_left], pins[n_left:]
    rows = max(len(left), len(right))
    longest = max(len(p[1]) for p in pins)
    half_w = max(7.62, round((longest * 1.27 + 2.54) / PITCH) * PITCH)
    top = (rows + 1) * PITCH / 2
    top = round(top / PITCH) * PITCH + PITCH
    out = [f'\t(symbol "{name}"\n\t\t(pin_names (offset 1.016))\n\t\t(exclude_from_sim no)\n'
           f'\t\t(in_bom yes)\n\t\t(on_board yes)\n']
    out.append(_prop("Reference", d["ref_prefix"], 0, top + 1.27))
    out.append(_prop("Value", name, 0, -top - 1.27))
    out.append(_prop("Footprint", d["footprint"], 0, -top - 3.81, hide=True))
    out.append(_prop("Datasheet", "", 0, 0, hide=True))
    out.append(_prop("Description", d.get("desc", ""), 0, 0, hide=True))
    if d.get("lcsc"):
        out.append(_prop("LCSC", d["lcsc"], 0, 0, hide=True))
    out.append(f'\t\t(symbol "{name}_0_1"\n\t\t\t(rectangle (start {-half_w:.2f} {top - PITCH / 2:.2f}) '
               f'(end {half_w:.2f} {-top + PITCH / 2:.2f})\n\t\t\t\t(stroke (width 0.254) (type default))\n'
               f'\t\t\t\t(fill (type background))\n\t\t\t)\n\t\t)\n')
    out.append(f'\t\t(symbol "{name}_1_1"\n')
    for side, plist in (("L", left), ("R", right)):
        for i, (num, pname, ptype) in enumerate(plist):
            y = top - PITCH * (i + 1)
            x = -half_w - PIN_LEN if side == "L" else half_w + PIN_LEN
            ang = 0 if side == "L" else 180
            out.append(f'\t\t\t(pin {KICAD_PIN_TYPE[ptype]} line\n\t\t\t\t(at {x:.2f} {y:.2f} {ang})\n'
                       f'\t\t\t\t(length {PIN_LEN})\n'
                       f'\t\t\t\t(name "{_esc(pname)}" (effects (font (size 1.27 1.27))))\n'
                       f'\t\t\t\t(number "{num}" (effects (font (size 1.27 1.27))))\n\t\t\t)\n')
    out.append("\t\t)\n\t\t(embedded_fonts no)\n\t)\n")
    return "".join(out)


def write_symbol_lib(defs, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    body = ['(kicad_symbol_lib\n\t(version 20241209)\n\t(generator "supply1_symgen")\n\t(generator_version "1.0")\n']
    for name, d in defs.items():
        body.append(symbol(name, d))
    body.append(")\n")
    text = "".join(body)
    try:
        with open(path, encoding="utf-8") as f:
            if f.read() == text:
                return
    except FileNotFoundError:
        pass
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
