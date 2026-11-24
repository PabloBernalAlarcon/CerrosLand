"""Cerros AI — validate component specs against schema v1, registry and map.

Reports only; never edits a spec. Works on a partial folder (lists missing specs).
Usage: python3 validate_specs.py <canonical_dir>
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

STATUS = ["component_type", "lifecycle_status", "architecture_status",
          "implementation_status", "deployment_status", "name"]
ID_RE = re.compile(r"\b(?:FL|TX|WF|PR|IN|SP)-[A-Z][0-9]{2}\b")
# rules whose text has no explicit subject — candidates for lost context
SUBJECTLESS = re.compile(r"^(Debe|Deben|Nunca|Solo|Son|Pueden|Máximo|≥|≤|[0-9])", re.I)

out = defaultdict(list)


def main(canon: Path):
    schema = json.loads((canon / "cerros_component_contract_v1.schema.json").read_text())
    validator = Draft202012Validator(schema)
    reg = yaml.safe_load((canon / "component_readiness_registry_v1.yaml").read_text())["components"]
    cmap = yaml.safe_load((canon / "master_dependency_map_v1.yaml").read_text())
    nodes = {n["id"]: n for n in cmap["nodes"]}
    orch_out = defaultdict(set)
    orch_in = defaultdict(set)
    for e in cmap["edges"]:
        if e["edge_class"] == "ORCHESTRATION":
            orch_out[e["from"]].add(e["to"])
            orch_in[e["to"]].add(e["from"])

    specs = {}
    for p in sorted((canon / "component_specs_normalized").glob("*.yaml")):
        s = yaml.safe_load(p.read_text(encoding="utf-8"))
        specs[s["component_id"]] = (p.name, s)

    missing = sorted(set(reg) - set(specs))
    extra = sorted(set(specs) - set(reg))
    shapes = Counter()

    for cid, (fname, s) in sorted(specs.items()):
        if not fname.startswith(cid):
            out[cid].append(("ERROR", f"file name {fname} does not match component_id"))
        for err in validator.iter_errors(s):
            loc = "/".join(map(str, err.path)) or "(root)"
            out[cid].append(("ERROR", f"schema: {loc}: {err.message}"))
        r = reg.get(cid)
        if r:
            for f in STATUS:
                if s.get(f) != r.get(f):
                    out[cid].append(("ERROR", f"{f}: spec={s.get(f)!r} registry={r.get(f)!r}"))
            if sorted(s.get("traits", [])) != sorted(r.get("traits", [])):
                out[cid].append(("ERROR", f"traits: spec={s['traits']} registry={r['traits']}"))
        n = nodes.get(cid, {})
        kp_map = sorted(n.get("knowledge_dependencies", []))
        kp_spec = sorted(s.get("knowledge_dependencies") or [])
        if kp_spec != kp_map:
            out[cid].append(("WARN", f"knowledge_dependencies: spec={kp_spec} map={kp_map}"))
        # empty structural fields
        for f in ["source_hierarchy", "validation_states", "handoff_conditions", "authoritative_sources"]:
            if not s.get(f):
                shapes[f"{f} empty"] += 1
        # handoff_conditions that name components without an ORCHESTRATION edge
        for h in s.get("handoff_conditions") or []:
            text = json.dumps(h, ensure_ascii=False)
            for tgt in set(ID_RE.findall(text)):
                if tgt != cid and tgt not in orch_out.get(cid, set()):
                    out[cid].append(("WARN", f"handoff_conditions names {tgt} but map has no "
                                     f"ORCHESTRATION edge {cid}->{tgt}"))
        # conditional ORCHESTRATION edges out of this component without a stated condition
        cond = [e for e in cmap["edges"] if e["from"] == cid and e["edge_class"] == "ORCHESTRATION"
                and e["conditional"] and e["executable"]]
        if cond and not s.get("handoff_conditions"):
            out[cid].append(("WARN", "conditional executable edges " +
                             ", ".join(f"{e['edge_id']}->{e['to']}" for e in cond) +
                             " but spec has no handoff_conditions"))
        # rules with no explicit subject (possible context loss in normalization)
        for rid, txt in (s.get("rules") or {}).items():
            if isinstance(txt, str) and SUBJECTLESS.match(txt.strip()):
                out[cid].append(("INFO", f"rule {rid} may have lost its subject: {txt!r}"))
        # representation style
        proc = s.get("procedure") or []
        shapes["procedure as phase objects" if proc and isinstance(proc[0], dict) else "procedure as strings"] += 1
        shapes[f"domain={s.get('domain')!r}"] += 1
        shapes[f"head={s.get('head')!r}"] += 1

    print(f"Specs present: {len(specs)} / {len(reg)}")
    if missing:
        print(f"Missing: {', '.join(missing)}")
    if extra:
        print(f"Not in registry: {', '.join(extra)}")
    print()
    sev = Counter(x[0] for v in out.values() for x in v)
    print(f"Findings: {sev['ERROR']} errors, {sev['WARN']} warnings, {sev['INFO']} info\n")
    for cid in sorted(out):
        for lvl, msg in sorted(out[cid], key=lambda x: {"ERROR": 0, "WARN": 1, "INFO": 2}[x[0]]):
            print(f"[{lvl}] {cid}: {msg}")
    print("\nRepresentation summary:")
    for k, v in sorted(shapes.items()):
        print(f"  {v:>3}  {k}")
    return 1 if sev["ERROR"] else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
