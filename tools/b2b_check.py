"""Cross-board check of the power <-> control B2B header and of ref uniqueness.

Usage: .venv/Scripts/python tools/b2b_check.py   (after power_design.py and control_design.py)
- every power-board header pin n must carry the same net as control-board pin mirrored(n) (design/interconnect.py)
- no reference designator may appear on both boards
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from netcheck import parse  # noqa: E402


def mirrored(pin):  # same as design/interconnect.py (not imported: that pulls in skidl)
    return pin + 1 if pin % 2 else pin - 1


def header(nets, prefix):
    """{pin: net} of the J9xx header whose ref starts with prefix (J95x power, J97x control)."""
    pins = {}
    for net, conns in nets.items():
        for ref, pin in conns:
            if ref.startswith(prefix):
                pins[int(pin)] = net
    return pins


def refs(nets):
    return {ref for conns in nets.values() for ref, _ in conns}


if __name__ == "__main__":
    pw = parse(ROOT / "out/supply_power.net")
    ct = parse(ROOT / "out/supply_control.net")
    hp, hc = header(pw, "J95"), header(ct, "J97")
    bad = [(n, hp.get(n), hc.get(mirrored(n))) for n in range(1, 41) if hp.get(n) != hc.get(mirrored(n))]
    for n, a, b in bad:
        print(f"  MISMATCH power pin {n}: {a}  <->  control pin {mirrored(n)}: {b}")
    dup = sorted(refs(pw) & refs(ct))
    if dup:
        print("  refs on both boards:", " ".join(dup))
    print(f"B2B: {40 - len(bad)}/40 pins match; duplicate refs: {len(dup)}")
    sys.exit(1 if bad or dup else 0)
