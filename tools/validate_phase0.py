"""Cerros AI — Phase 0 cross-check of the canonical layer.

Checks that registry, dependency map, master-spec manifest, normalization
migration report and (optionally) the master-spec text agree with each other.
It reports discrepancies; it never corrects them (CORE-01 / CORE-06).

Usage: python3 validate_phase0.py <canonical_dir> [master_spec.txt]
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

ORCH_SEMANTICS = {"TRANSFER_CONTROL", "CALL_COMPONENT"}
INVOCABLE_LIFECYCLE = {"ACTIVE", "PROVISIONAL"}
STATUS_FIELDS = ["lifecycle_status", "architecture_status",
                 "implementation_status", "deployment_status"]

findings = []  # (severity, area, message)


def add(sev, area, msg):
    findings.append((sev, area, msg))


def load(p):
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main(canon: Path, spec_txt: Path | None):
    reg = load(canon / "component_readiness_registry_v1.yaml")
    cmap = load(canon / "master_dependency_map_v1.yaml")
    man = load(canon / "master_spec_manifest_v1.yaml")
    mig = load(canon / "normalization_migration_report_v1.yaml")
    contract = load(canon / "component_contract_v1.yaml")

    rc = reg["components"]
    mc = man["components"]
    nodes = {n["id"]: n for n in cmap["nodes"]}
    edges = cmap["edges"]
    catalog = cmap["edge_semantics_catalog"]

    # ---------- counts ----------
    life = Counter(c["lifecycle_status"] for c in rc.values())
    counts = man["counts"]
    for key, val in [("components", len(rc)), ("active", life["ACTIVE"]),
                     ("provisional", life["PROVISIONAL"]),
                     ("disabled", life["DISABLED"]), ("gaps", len(reg["gaps"])),
                     ("knowledge_packs", len(man["knowledge_packs"])),
                     ("human_authorities", len(man["human_authorities"])),
                     ("map_nodes", len(nodes)), ("map_edges", len(edges))]:
        if counts.get(key) != val:
            add("ERROR", "counts", f"{key}: manifest says {counts.get(key)}, actual {val}")
    if len({e["edge_id"] for e in edges}) != len(edges):
        add("ERROR", "map", "duplicate edge_id values")

    # ---------- enums ----------
    enums = {
        "component_type": set(contract["component_type_enum"]),
        "lifecycle_status": set(contract["lifecycle_status_enum"]),
        "architecture_status": set(contract["architecture_status_enum"]),
        "implementation_status": set(contract["implementation_status_enum"]),
        "deployment_status": set(contract["deployment_status_enum"]),
    }
    traits_enum = set(contract["trait_enum"])
    for cid, c in rc.items():
        for f, allowed in enums.items():
            if c.get(f) not in allowed:
                add("ERROR", "registry", f"{cid}.{f}={c.get(f)} not in contract enum")
        for t in c.get("traits", []):
            if t not in traits_enum:
                add("ERROR", "registry", f"{cid} trait {t} not in enum")

    # ---------- registry vs manifest vs map node ----------
    domains = {cid: d for d, ids in man["domains"].items() for cid in ids}
    ids_reg, ids_man = set(rc), set(mc)
    ids_map = {i for i, n in nodes.items() if n["node_kind"] == "COMPONENT"}
    for a, b, an, bn in [(ids_reg, ids_man, "registry", "manifest"),
                         (ids_reg, ids_map, "registry", "map")]:
        if a - b:
            add("ERROR", "ids", f"in {an} not {bn}: {sorted(a - b)}")
        if b - a:
            add("ERROR", "ids", f"in {bn} not {an}: {sorted(b - a)}")
    if set(domains) != ids_reg:
        add("ERROR", "domains", f"manifest domain lists differ from registry: "
            f"{sorted(set(domains) ^ ids_reg)}")

    for cid in sorted(ids_reg & ids_man & ids_map):
        r, m, n = rc[cid], mc[cid], nodes[cid]
        for f in ["name", "component_type"] + STATUS_FIELDS:
            vals = {"registry": r.get(f), "manifest": m.get(f), "map": n.get(f)}
            if len(set(map(str, vals.values()))) > 1:
                add("ERROR", "status", f"{cid}.{f} disagrees: {vals}")
        if sorted(r["traits"]) != sorted(m["traits"]) or sorted(r["traits"]) != sorted(n["traits"]):
            add("ERROR", "traits", f"{cid} traits disagree: reg={r['traits']} "
                f"man={m['traits']} map={n['traits']}")
        if m["family"] != domains.get(cid):
            add("WARN", "family", f"{cid} family={m['family']} but listed under {domains.get(cid)}")
        if n.get("domain") != m["family"]:
            add("INFO", "family", f"{cid} map domain={n.get('domain')} vs manifest family={m['family']}")
        if sorted(n["knowledge_dependencies"]) != sorted(m["knowledge_dependencies"]):
            add("ERROR", "knowledge", f"{cid} KP deps: map={n['knowledge_dependencies']} "
                f"manifest={m['knowledge_dependencies']}")
        if n["human_authority"] != m["human_authority"]:
            add("ERROR", "authority", f"{cid}: map={n['human_authority']} manifest={m['human_authority']}")

    # ---------- migration report vs registry ----------
    for t in mig["type_migrations"]:
        cid = t["component_id"]
        if rc[cid]["component_type"] != t["to"] or sorted(rc[cid]["traits"]) != sorted(t["traits"]):
            add("ERROR", "migration", f"{cid} registry != migration report")
        if nodes[cid].get("kind") != t["from"]:
            add("INFO", "migration", f"{cid} map legacy kind={nodes[cid].get('kind')} vs from={t['from']}")

    # ---------- edges ----------
    def node_invocable(i):
        n = nodes.get(i)
        return bool(n) and n["node_kind"] == "COMPONENT" and n["lifecycle_status"] in INVOCABLE_LIFECYCLE

    sem_to_class = {}
    for name, s in catalog.items():
        sem_to_class.setdefault(s["semantics"], set()).add(s["edge_class"])

    kp_edges, auth_edges = defaultdict(set), defaultdict(set)
    for e in edges:
        eid, frm, to = e["edge_id"], e["from"], e["to"]
        for end in (frm, to):
            if end not in nodes:
                add("ERROR", "edges", f"{eid} references unknown node {end}")
        if e["edge_class"] not in sem_to_class.get(e["semantics"], set()):
            add("ERROR", "edges", f"{eid} class {e['edge_class']} incompatible with {e['semantics']}")
        if e["executable"] and e["edge_class"] != "ORCHESTRATION":
            add("ERROR", "edges", f"{eid} executable but class {e['edge_class']}")
        if e["edge_class"] == "ORCHESTRATION":
            if e["executable"] and not node_invocable(to):
                add("ERROR", "guard", f"{eid} executable into non-invocable {to}")
            if e["executable"] and not node_invocable(frm):
                add("ERROR", "guard", f"{eid} executable from non-invocable {frm}")
            if not e["executable"]:
                add("INFO", "dormant", f"{eid} {frm}->{to} dormant ({e.get('state_guard')})")
            if e["executable"] and e.get("state_guard") != "target_must_be_invocable":
                add("WARN", "guard", f"{eid} executable without target_must_be_invocable guard")
        if e["edge_class"] == "KNOWLEDGE":
            kp_edges[frm].add(to)
        if e["edge_class"] == "AUTHORITY" and e["semantics"] == "RESERVES_DECISION_TO":
            auth_edges[frm].add(to)

    for cid, n in nodes.items():
        if n["node_kind"] not in ("COMPONENT", "GAP"):
            continue
        if set(n.get("knowledge_dependencies", [])) != kp_edges.get(cid, set()):
            add("ERROR", "knowledge", f"{cid} node KP deps {n.get('knowledge_dependencies')} "
                f"vs KNOWLEDGE edges {sorted(kp_edges.get(cid, []))}")
        ha = n.get("human_authority")
        if ha and {ha} != auth_edges.get(cid, set()):
            add("ERROR", "authority", f"{cid} human_authority {ha} vs AUTHORITY edges "
                f"{sorted(auth_edges.get(cid, []))}")
    for h in man["human_authorities"]:
        if not any(e["to"] == h for e in edges):
            add("INFO", "authority", f"{h} has no edges (no component reserves decisions to it)")

    # QUALITY edge direction convention
    q = [e for e in edges if e["edge_class"] == "QUALITY"]
    reviewer_first = [e["edge_id"] for e in q if "qa" in nodes.get(e["from"], {}).get("traits", [])
                      or nodes.get(e["from"], {}).get("component_type") == "MICRO_SKILL"]
    reviewed_first = [e["edge_id"] for e in q if e["edge_id"] not in reviewer_first]
    if reviewer_first and reviewed_first:
        add("WARN", "direction", "QUALITY edges use two directions. reviewer->reviewed: "
            f"{reviewer_first}; reviewed->reviewer: {reviewed_first}")

    # ---------- master spec text: handoff column vs ORCHESTRATION edges ----------
    if spec_txt and spec_txt.exists():
        orch = defaultdict(set)
        for e in edges:
            if e["edge_class"] in ("ORCHESTRATION", "AUTHORITY") and e["semantics"] != "TRANSFER_TO_HUMAN":
                orch[e["from"]].add((e["semantics"], e["to"]))
        row = re.compile(r"^\s{2}([A-Z]{2}-[A-Z][0-9]{2})\s{2,}.*(?:TRANSFER_CONTROL|CALL_COMPONENT|RESERVES_DECISION_TO)")
        rel = re.compile(r"(TRANSFER_CONTROL|CALL_COMPONENT|RESERVES_DECISION_TO)\s*→\s*([A-Z]{2,3}-[A-Z0-9]+)")
        seen = set()
        for line in spec_txt.read_text(encoding="utf-8").splitlines():
            m = row.match(line)
            if not m:
                continue
            cid = m.group(1)
            seen.add(cid)
            spec_rels = set(rel.findall(line))
            map_rels = orch.get(cid, set())
            # dormant edges (executable false) appear in spec? compare against all orchestration+authority
            if spec_rels != map_rels:
                add("WARN", "spec-vs-map", f"{cid}: only in spec {sorted(spec_rels - map_rels)}; "
                    f"only in map {sorted(map_rels - spec_rels)}")
        missing = ids_reg - seen
        if missing:
            add("INFO", "spec-vs-map", f"no family-table row parsed for {sorted(missing)}")

    # ---------- report ----------
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    findings.sort(key=lambda f: (order[f[0]], f[1]))
    c = Counter(f[0] for f in findings)
    print(f"Phase 0 cross-check: {c['ERROR']} errors, {c['WARN']} warnings, {c['INFO']} info\n")
    for sev, area, msg in findings:
        print(f"[{sev}] {area}: {msg}")
    executable = [e for e in edges if e["executable"]]
    print(f"\nExecutable ORCHESTRATION edges: {len(executable)} of {len(edges)}")
    return 1 if c["ERROR"] else 0


if __name__ == "__main__":
    canon = Path(sys.argv[1])
    spec = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    sys.exit(main(canon, spec))
