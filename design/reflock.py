"""
Stable reference designators across schematic edits: refs.lock.json next to the board script.

Why: KiCad's "Update PCB from Netlist" keeps a footprint's placement and tracks when the reference (or the UUID,
which skidl derives from the tag = ref) is unchanged. Numbering parts in code order renumbers everything after an
inserted or deleted part, and KiCad then silently keeps footprints at positions that now belong to other parts.

How: every part gets an identity = (block, ref prefix, library part, value, net on each pin). The lock file maps
identities to refs.
  1. exact match            -> same ref (identical parallel parts, e.g. 6 MLCCs, are matched in code order)
  2. close match            -> same ref, reported as "changed" (a value change, a swapped part, a re-wired pin)
  3. no match (new part)    -> next unused number in its block; numbers are never reused
  4. lock entry not matched -> retired (the part was deleted); its number stays reserved
Auto-named nets (N$12 ...) only count as "connected", because skidl renumbers them when code order changes.

First run without a lock file: the refs come from `seed` (the old numbering), so an existing board stays valid.
Delete the lock file only if you want a full renumber (and then re-place the board).
"""

import json
import re
from pathlib import Path

AUTO_NET = re.compile(r"^(N\$\d+|NET_\d+)$")
MIN_SCORE = 3.5            # below this a lock entry is not considered the same part


def _pin_nets(part):
    out = {}
    for pin in part.pins:
        n = pin.net
        if n is None:
            continue
        name = "NC" if type(n).__name__ == "NCNet" else n.name
        out[str(pin.num)] = "~" if AUTO_NET.match(name) else name
    return out


def _identity(part, block):
    return dict(block=block, prefix=part.ref_prefix, part=part.name, value=str(part.value), nets=_pin_nets(part))


def _same(a, b):
    return all(a[k] == b[k] for k in ("block", "prefix", "part", "value", "nets"))


def _score(cur, old):
    if cur["block"] != old["block"] or cur["prefix"] != old["prefix"]:
        return -1.0
    s = 3.0 * (cur["part"] == old["part"]) + 1.0 * (cur["value"] == old["value"])
    for pin, net in cur["nets"].items():
        if old["nets"].get(pin) == net and net != "~":
            s += 0.5 if net in ("GND", "NC") else 2.0
    return s


def _num(ref):
    m = re.search(r"(\d+)$", ref)
    return int(m.group(1)) if m else 0


def assign(parts, block_of, num_range, lock_path, seed):
    """parts: skidl parts; block_of(part) -> block name; num_range(block) -> (first, limit) for new numbers;
    seed(parts) -> {id(part): ref} used only when there is no lock file yet. Sets part.ref and part.tag."""
    lock_path = Path(lock_path)
    ids = {id(p): _identity(p, block_of(p)) for p in parts}

    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        entries, retired = lock.get("parts", []), set(lock.get("retired", []))
        refs, pool = {}, list(entries)
        # 1. exact
        for p in parts:
            hit = next((e for e in pool if _same(ids[id(p)], e)), None)
            if hit:
                refs[id(p)] = hit["ref"]
                pool.remove(hit)
        # 2. close (greedy, best score first)
        cand = sorted(((_score(ids[id(p)], e), i, j) for i, p in enumerate(parts) if id(p) not in refs
                       for j, e in enumerate(pool)), reverse=True)
        used_e, changed = set(), []
        for sc, i, j in cand:
            p = parts[i]
            if sc < MIN_SCORE or id(p) in refs or j in used_e:
                continue
            refs[id(p)] = pool[j]["ref"]
            used_e.add(j)
            changed.append((pool[j], ids[id(p)]))
        gone = [e for j, e in enumerate(pool) if j not in used_e]
        retired |= {e["ref"] for e in gone}
        # 3. new parts: next number never used in the block
        taken = {e["ref"] for e in entries} | retired
        new = []
        for p in parts:
            if id(p) in refs:
                continue
            first, limit = num_range(ids[id(p)]["block"])
            prefix = p.ref_prefix
            n = max([_num(r) for r in taken if re.fullmatch(rf"{re.escape(prefix)}\d+", r)
                     and first <= _num(r) < limit] + [first - 1]) + 1
            assert n < limit, f"block {ids[id(p)]['block']}: no free {prefix} numbers left"
            refs[id(p)] = f"{prefix}{n}"
            taken.add(refs[id(p)])
            new.append(refs[id(p)])
        report = dict(changed=changed, new=new, gone=gone)
    else:
        refs = seed(parts)                          # {id(part): ref}
        retired, report = set(), None

    for i, p in enumerate(parts):                  # temp refs first: avoid collisions while renaming
        p.ref = f"TMP{i}"
    for p in parts:
        p.ref = refs[id(p)]
        p.tag = p.ref

    out = sorted(({"ref": p.ref, **ids[id(p)]} for p in parts), key=lambda e: (re.sub(r"\d", "", e["ref"]), _num(e["ref"])))
    lock_path.write_text(json.dumps({"parts": out, "retired": sorted(retired, key=lambda r: (re.sub(r"\d", "", r), _num(r)))},
                                    indent=1), encoding="utf-8")

    if report is None:
        print(f"refs: no lock file yet -> seeded {len(parts)} refs from the current numbering into {lock_path.name}")
        return
    print(f"refs ({lock_path.name}): {len(parts) - len(report['changed']) - len(report['new'])} unchanged, "
          f"{len(report['changed'])} changed, {len(report['new'])} new, {len(report['gone'])} removed")
    for old, cur in report["changed"]:
        diff = [f"{k}: {old[k]} -> {cur[k]}" for k in ("part", "value") if old[k] != cur[k]]
        pins = sorted(k for k in set(old["nets"]) | set(cur["nets"]) if old["nets"].get(k) != cur["nets"].get(k))
        if pins:
            diff.append("pins " + ", ".join(f"{k}: {old['nets'].get(k)} -> {cur['nets'].get(k)}" for k in pins))
        print(f"  changed {old['ref']}: " + "; ".join(diff))
    for r in report["new"]:
        print(f"  new     {r}  (place it after the PCB update)")
    for e in report["gone"]:
        print(f"  removed {e['ref']} ({e['part']} {e['value']}): number retired")
