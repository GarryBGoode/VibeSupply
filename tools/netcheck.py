"""Quick netlist reviewer: prints single-pin nets and the pins on selected nets. Usage: python tools/netcheck.py out/supply_power.net [NET ...]"""
import re, sys
from pathlib import Path

def parse(path):
    txt = Path(path).read_text(encoding="utf-8")
    nets = {}
    for m in re.finditer(r'\(net\s+\(code "?\d+"?\)\s+\(name "([^"]*)"\)(.*?)(?=\(net\s+\(code|\Z)', txt, re.S):
        nets[m.group(1)] = re.findall(r'\(ref "([^"]+)"\)\s*\(pin "([^"]+)"\)', m.group(2))
    return nets

if __name__ == "__main__":
    nets = parse(sys.argv[1])
    single = {n: v for n, v in nets.items() if len(v) == 1}
    print(f"nets: {len(nets)}  single-pin nets: {len(single)}")
    for n, v in single.items():
        print("  ", n, v)
    for key in sys.argv[2:]:
        print(f"{key:12s}", " ".join(f"{r}.{p}" for r, p in nets.get(key, [])))
