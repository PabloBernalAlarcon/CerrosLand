"""Build the runtime behaviour of every executable ORCHESTRATION edge and check that
exactly one runtime rule governs each one. Usage: python3 build_edge_behavior.py <canonical_dir>"""
import sys
from pathlib import Path
import yaml

canon = Path(sys.argv[1])
cmap = yaml.safe_load((canon / "master_dependency_map_v1.yaml").read_text())
pol = yaml.safe_load((canon / "runtime_policy_v1.yaml").read_text())["rules"]
dormant = set(pol["RT-05"]["edges_treated_as_dormant"])
nodes = {n["id"]: n for n in cmap["nodes"]}
rows, problems = [], []
for e in cmap["edges"]:
    if e["edge_class"] != "ORCHESTRATION" or not e["executable"]:
        continue
    rules = []
    if e["edge_id"] in dormant:
        rules.append("RT-05")
    if e["semantics"] == "TRANSFER_CONTROL" and e["edge_id"] not in dormant:
        rules.append("RT-01")
    if e["semantics"] == "CALL_COMPONENT" and e["conditional"]:
        rules.append("RT-02")
    if e["semantics"] == "CALL_COMPONENT" and not e["conditional"]:
        rules.append("AUTO")
    if len(rules) != 1:
        problems.append((e["edge_id"], rules))
    t = nodes[e["to"]]
    rows.append({"edge_id": e["edge_id"], "from": e["from"], "to": e["to"], "semantics": e["semantics"],
                 "conditional": e["conditional"], "governed_by": rules[0] if rules else None,
                 "target_lifecycle": t["lifecycle_status"], "target_deployment": t["deployment_status"],
                 "offer_reason": e.get("note", "")})
out = canon / "edge_behavior_v1.yaml"
yaml.safe_dump({"generated_from": ["master_dependency_map_v1.yaml", "runtime_policy_v1.yaml"], "edges": rows},
               out.open("w"), allow_unicode=True, sort_keys=False, width=120)
from collections import Counter
print("executable edges:", len(rows), "| by rule:", dict(Counter(r["governed_by"] for r in rows)))
print("edges with zero or multiple rules:", problems or "none")
