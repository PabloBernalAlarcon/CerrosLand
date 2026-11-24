"""Load and validate the canonical layer of Cerros AI v1.

Everything the runtime knows comes from files in `canonical/`. Nothing here
fills gaps: missing values stay missing (CORE-01).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

INVOCABLE_LIFECYCLE = {"ACTIVE", "PROVISIONAL"}
REVIEWERS = {"TX-A02", "TX-P01"}  # RT-04


class CatalogError(Exception):
    pass


@dataclass(frozen=True)
class Edge:
    edge_id: str
    source: str
    target: str
    edge_class: str
    semantics: str
    conditional: bool
    executable: bool
    note: str
    governed_by: str | None = None  # RT-01 / RT-02 / RT-05 / AUTO, for executable ORCHESTRATION edges


@dataclass
class Catalog:
    root: Path
    specs: dict[str, dict]
    registry: dict[str, dict]
    gaps: dict[str, dict]
    nodes: dict[str, dict]
    edges: list[Edge]
    manifest: dict
    family: dict[str, str]
    knowledge_registry: dict[str, dict]
    policy: dict
    load_report: list[str] = field(default_factory=list)

    # ---------- lookups ----------
    def node_kind(self, node_id: str) -> str | None:
        n = self.nodes.get(node_id)
        return n["node_kind"] if n else None

    def out_edges(self, cid: str, edge_class: str | None = None) -> list[Edge]:
        return [e for e in self.edges if e.source == cid and (edge_class is None or e.edge_class == edge_class)]

    def edge(self, edge_id: str) -> Edge:
        for e in self.edges:
            if e.edge_id == edge_id:
                return e
        raise KeyError(edge_id)

    def human_authority(self, cid: str) -> str | None:
        return self.nodes.get(cid, {}).get("human_authority")

    def core_rules(self) -> list[dict]:
        return self.manifest["core_rules"]


def _load_yaml(p: Path):
    with p.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _govern(e: dict, dormant: set[str]) -> str | None:
    if e["edge_class"] != "ORCHESTRATION" or not e["executable"]:
        return None
    if e["edge_id"] in dormant:
        return "RT-05"
    if e["semantics"] == "TRANSFER_CONTROL":
        return "RT-01"
    if e["semantics"] == "CALL_COMPONENT":
        return "RT-02" if e["conditional"] else "AUTO"
    return None


def load_catalog(root: str | Path, knowledge_root: str | Path | None = None) -> Catalog:
    """root = spec/working; knowledge_root defaults to <repo>/knowledge."""
    root = Path(root).resolve()
    knowledge_root = Path(knowledge_root).resolve() if knowledge_root else root.parents[1] / "knowledge"
    report: list[str] = []

    schema = json.loads((root / "cerros_component_contract_v1.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    specs: dict[str, dict] = {}
    for p in sorted((root / "component_specs_normalized").glob("*.yaml")):
        s = _load_yaml(p)
        errors = list(validator.iter_errors(s))
        if errors:
            raise CatalogError(f"{p.name}: {errors[0].message}")
        specs[s["component_id"]] = s

    reg = _load_yaml(root / "component_readiness_registry_v1.yaml")
    registry, gaps = reg["components"], reg.get("gaps", {})
    if set(registry) != set(specs):
        raise CatalogError(f"registry/spec mismatch: {sorted(set(registry) ^ set(specs))}")
    for cid, r in registry.items():
        for f in ("lifecycle_status", "architecture_status", "implementation_status", "deployment_status"):
            if r[f] != specs[cid][f]:
                raise CatalogError(f"{cid}.{f} differs between registry and spec")

    cmap = _load_yaml(root / "master_dependency_map_v1.yaml")
    nodes = {n["id"]: n for n in cmap["nodes"]}
    policy = _load_yaml(root / "runtime_policy_v1.yaml")
    dormant = set(policy["rules"]["RT-05"]["edges_treated_as_dormant"])

    edges: list[Edge] = []
    for e in cmap["edges"]:
        src, tgt = e["from"], e["to"]
        if e["edge_class"] == "QUALITY" and tgt in REVIEWERS and src not in REVIEWERS:
            src, tgt = tgt, src  # RT-04: normalize to reviewer -> reviewed
            report.append(f"RT-04 normalized {e['edge_id']} to {src}->{tgt}")
        edges.append(Edge(e["edge_id"], src, tgt, e["edge_class"], e["semantics"], bool(e["conditional"]),
                          bool(e["executable"]), e.get("note", ""), _govern(e, dormant)))

    manifest = _load_yaml(root / "master_spec_manifest_v1.yaml")
    family = {cid: fam for fam, ids in manifest["domains"].items() for cid in ids}  # RT-08

    kreg = _load_yaml(knowledge_root / "knowledge_pack_registry_v0.1.yaml")
    knowledge_registry = {p["knowledge_id"]: p for p in kreg["packs"]}

    return Catalog(root, specs, registry, gaps, nodes, edges, manifest, family, knowledge_registry, policy, report)
