"""
EXPERIMENTAL: skidl automatic KiCad schematic generation.
Currently crashes inside skidl 2.3's placer (schematics/place.py similarity_force: pin.part is None) for
both boards, so the netlist -> PCB path is the one to use. Kept here to retry after a skidl update.

Usage: .venv/Scripts/python tools/gen_schematic.py main|ui
"""
import builtins, sys
sys.path.insert(0, ".")
from skidl import KICAD10, generate_schematic

board = sys.argv[1] if len(sys.argv) > 1 else "main"
if board == "main":
    import supply_design as d
    d.build(); d.assign_refs()
else:
    import ui_design as d
    d.build()
    builtins.default_circuit.rmv_nets(*[n for n in builtins.default_circuit.nets if not n.pins and n is not builtins.NC])
generate_schematic(tool=KICAD10, filepath=f"out/sch_{board}", top_name=f"supply_{board}", retries=3, auto_stub=True)
