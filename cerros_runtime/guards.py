"""State guards: who may run, and how a component is presented (RT-06, RT-07)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .catalog import INVOCABLE_LIFECYCLE, Catalog

BLOCKED_DEPLOYMENT = {"BLOCKED_BY_KNOWLEDGE", "BLOCKED_BY_GOVERNANCE"}
_RANK = {"ACTIVE": 0, "PROVISIONAL": 1}


class NotInvocable(Exception):
    pass


def invocability(cat: Catalog, node_id: str) -> tuple[bool, str]:
    """Return (invocable, reason). GAP, DISABLED, human-authority and knowledge nodes never run."""
    kind = cat.node_kind(node_id)
    if kind is None:
        return False, f"{node_id} is not a known node"
    if kind == "GAP":
        return False, f"{node_id} is a GAP: no executable component exists"
    if kind != "COMPONENT":
        return False, f"{node_id} is a {kind} node, not a component"
    r = cat.registry[node_id]
    if r["lifecycle_status"] not in INVOCABLE_LIFECYCLE:
        return False, f"{node_id} is {r['lifecycle_status']}"
    if r["implementation_status"] == "NOT_IMPLEMENTABLE":
        return False, f"{node_id} is NOT_IMPLEMENTABLE"
    return True, "ok"


def require_invocable(cat: Catalog, node_id: str) -> None:
    ok, why = invocability(cat, node_id)
    if not ok:
        raise NotInvocable(why)


@dataclass
class EffectiveStatus:
    component_id: str
    own_lifecycle: str
    presented_lifecycle: str
    deployment_status: str
    data_scope: str
    inherited_from: list[str] = field(default_factory=list)
    blocked_steps: list[tuple[str, str]] = field(default_factory=list)  # (edge_id, reason)


def effective_status(cat: Catalog, cid: str, _seen: set[str] | None = None) -> EffectiveStatus:
    """RT-06: most restrictive of own status and every mandatory (AUTO) callee, transitively."""
    _seen = set() if _seen is None else _seen
    _seen.add(cid)
    r = cat.registry[cid]
    st = EffectiveStatus(cid, r["lifecycle_status"], r["lifecycle_status"], r["deployment_status"],
                         "development/pilot with fictitious data only (RT-07)")
    for e in cat.out_edges(cid, "ORCHESTRATION"):
        if e.governed_by != "AUTO":
            continue
        ok, why = invocability(cat, e.target)
        tgt = cat.registry.get(e.target, {})
        if not ok:
            st.blocked_steps.append((e.edge_id, why))
            continue
        if tgt["deployment_status"] in BLOCKED_DEPLOYMENT:
            st.blocked_steps.append((e.edge_id, f"{e.target} is {tgt['deployment_status']}"))
        if tgt["lifecycle_status"] != "ACTIVE" and e.target not in st.inherited_from:
            st.inherited_from.append(e.target)
        if _RANK[tgt["lifecycle_status"]] > _RANK[st.presented_lifecycle]:
            st.presented_lifecycle = tgt["lifecycle_status"]
        if e.target not in _seen:
            sub = effective_status(cat, e.target, _seen)
            if _RANK[sub.presented_lifecycle] > _RANK[st.presented_lifecycle]:
                st.presented_lifecycle = sub.presented_lifecycle
            st.inherited_from += [x for x in sub.inherited_from if x not in st.inherited_from]
            st.blocked_steps += [b for b in sub.blocked_steps if b not in st.blocked_steps]
    return st

