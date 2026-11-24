"""Cerros AI — dependency/readiness analysis across map, registry, specs and KP status.
Reports only. Usage: python3 analyze_dependencies.py <canonical_dir>
"""
import re
import sys
from pathlib import Path

import yaml

ID_RE = re.compile(r"\b(?:FL|TX|WF|PR|IN|SP)-[A-Z][0-9]{2}\b")


def main(canon: Path):
    cmap = yaml.safe_load((canon / "master_dependency_map_v1.yaml").read_text())
    man = yaml.safe_load((canon / "master_spec_manifest_v1.yaml").read_text())
    nodes = {n["id"]: n for n in cmap["nodes"]}
    specs = {}
    for p in (canon / "component_specs_normalized").glob("*.yaml"):
        s = yaml.safe_load(p.read_text(encoding="utf-8"))
        specs[s["component_id"]] = s
    kp_status = {k: v["status"] for k, v in man["knowledge_packs"].items()}
    orch = [e for e in cmap["edges"] if e["edge_class"] == "ORCHESTRATION" and e["executable"]]

    print("== 1. Mandatory (non-conditional) executable edges into PROVISIONAL or knowledge/governance-blocked targets")
    for e in sorted(orch, key=lambda e: e["edge_id"]):
        t, f = nodes[e["to"]], nodes[e["from"]]
        flags = []
        if t["lifecycle_status"] == "PROVISIONAL":
            flags.append("target PROVISIONAL")
        if t["deployment_status"] in ("BLOCKED_BY_KNOWLEDGE", "BLOCKED_BY_GOVERNANCE"):
            flags.append(f"target {t['deployment_status']}")
        if flags and not e["conditional"]:
            print(f"  {e['edge_id']} {e['from']}({f['lifecycle_status']}) -{e['semantics']}-> {e['to']}: {', '.join(flags)}")

    print("\n== 2. Non-conditional TRANSFER_CONTROL edges (would always hand over control)")
    for e in orch:
        if e["semantics"] == "TRANSFER_CONTROL" and not e["conditional"]:
            print(f"  {e['edge_id']} {e['from']} -> {e['to']}: {e['note']}")

    print("\n== 3. Components named in spec.dependencies with no ORCHESTRATION/QUALITY/SUPPORT/DATA edge either way")
    linked = set()
    for e in cmap["edges"]:
        linked.add((e["from"], e["to"]))
        linked.add((e["to"], e["from"]))
    for cid, s in sorted(specs.items()):
        named = set()
        for d in s.get("dependencies") or []:
            txt = d if isinstance(d, str) else str(d.get("dependency", ""))
            named |= set(ID_RE.findall(txt))
            # expand shorthand like PR-S01/02/03 or FL-P01-P03
            m = re.match(r"([A-Z]{2}-[A-Z])(\d{2})((?:/\d{2})+)", txt.replace(" ", ""))
            if m:
                named |= {f"{m.group(1)}{n}" for n in m.group(3).split("/")[1:]}
        for tgt in sorted(named - {cid}):
            if (cid, tgt) not in linked:
                print(f"  {cid} lists {tgt} but map has no edge between them")

    print("\n== 4. Deployment status vs Knowledge Pack completeness")
    for cid, n in sorted((i, n) for i, n in nodes.items() if n["node_kind"] == "COMPONENT"):
        kps = n.get("knowledge_dependencies", [])
        incomplete = [k for k in kps if not kp_status[k].startswith(("FUENTE", "FUENTES"))]
        print(f"  {cid:7} {n['deployment_status']:22} KPs={kps} incomplete={incomplete}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
