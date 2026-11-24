"""Orchestration session: one active component, explicit human checkpoints,
and transitions governed by the runtime policy (RT-01 … RT-07).

The session never decides pedagogy. It only enforces who may run, when control may
move, and what must be recorded for traceability (Spec §18.1).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .catalog import Catalog, Edge
from .guards import NotInvocable, effective_status, invocability, require_invocable

STATES = ("PRELIMINAR", "NO VALIDADO", "VALIDADO")


class TransitionRefused(Exception):
    pass


@dataclass
class Offer:
    edge_id: str
    target: str
    kind: str          # handoff | call | auto
    rule: str          # RT-01 / RT-02 / AUTO
    reason: str        # map note shown to the user
    target_presented_lifecycle: str
    available_now: bool
    why_not: str = ""


@dataclass
class Event:
    at: str
    kind: str
    detail: dict


@dataclass
class Session:
    cat: Catalog
    active: str | None = None
    specialization: str | None = None
    validation_state: str | None = None
    human_confirmations: list[dict] = field(default_factory=list)
    trace: list[Event] = field(default_factory=list)

    # ---------- helpers ----------
    def _log(self, kind: str, **detail):
        self.trace.append(Event(datetime.now(timezone.utc).isoformat(timespec="seconds"), kind, detail))

    def _require_active(self) -> str:
        if not self.active:
            raise TransitionRefused("no active component")
        return self.active

    # ---------- start ----------
    def start(self, cid: str) -> dict:
        """Start a component. A SPECIALIZATION runs on top of the component it specializes."""
        require_invocable(self.cat, cid)
        base, spec = cid, None
        if self.cat.specs[cid]["component_type"] == "SPECIALIZATION":
            targets = [e.target for e in self.cat.out_edges(cid, "STRUCTURAL") if e.semantics == "SPECIALIZES"]
            if len(targets) != 1:
                raise NotInvocable(f"{cid}: cannot resolve the component it specializes")
            require_invocable(self.cat, targets[0])
            base, spec = targets[0], cid
        self.active, self.specialization = base, spec
        self.validation_state, self.human_confirmations = "PRELIMINAR", []
        st = effective_status(self.cat, base)
        self._log("start", component=base, specialization=spec, presented_lifecycle=st.presented_lifecycle,
                  blocked_steps=st.blocked_steps, data_scope=st.data_scope)
        return {"component": base, "specialization": spec, "status": st}

    # ---------- human checkpoints ----------
    def confirm_human(self, action: str, by: str) -> None:
        """Record a human decision (a human_reserved_action or approval of the output)."""
        cid = self._require_active()
        self.human_confirmations.append({"component": cid, "action": action, "by": by})
        self._log("human_confirmation", component=cid, action=action, by=by)

    def set_validation(self, state: str, *, confirmed_by_human: bool = False) -> None:
        """VALIDADO always needs a human confirmation (CORE-04): every component reserves decisions."""
        if state not in STATES:
            raise ValueError(state)
        cid = self._require_active()
        if state == "VALIDADO" and not confirmed_by_human:
            raise TransitionRefused(f"{cid}: VALIDADO requires confirmation by "
                                    f"{self.cat.human_authority(self.specialization or cid)}")
        self.validation_state = state
        self._log("validation", component=cid, state=state, confirmed_by_human=confirmed_by_human)

    # ---------- what can happen next ----------
    def next_steps(self) -> list[Offer]:
        cid = self._require_active()
        offers = []
        for e in self.cat.out_edges(cid, "ORCHESTRATION"):
            if e.governed_by in (None, "RT-05"):
                continue  # non-executable, dormant (RT-05)
            ok, why = invocability(self.cat, e.target)
            tgt = effective_status(self.cat, e.target).presented_lifecycle if ok else "—"
            kind = {"RT-01": "handoff", "RT-02": "call", "AUTO": "auto"}[e.governed_by]
            available, reason = ok, why if not ok else ""
            if ok and e.governed_by == "RT-01" and self.validation_state != "VALIDADO":
                available, reason = False, "source not VALIDADO yet (RT-01)"
            offers.append(Offer(e.edge_id, e.target, kind, e.governed_by, e.note, tgt, available, reason))
        return offers

    # ---------- transitions ----------
    def _edge_from_active(self, edge_id: str) -> Edge:
        cid = self._require_active()
        e = self.cat.edge(edge_id)
        if e.source != cid:
            raise TransitionRefused(f"{edge_id} does not start at {cid}")
        if e.edge_class != "ORCHESTRATION":
            raise TransitionRefused(f"{edge_id} is {e.edge_class}: it never transfers control")
        if e.governed_by is None:
            raise TransitionRefused(f"{edge_id} is not executable")
        if e.governed_by == "RT-05":
            raise TransitionRefused(f"{edge_id} is dormant (RT-05)")
        ok, why = invocability(self.cat, e.target)
        if not ok:
            raise TransitionRefused(why)
        return e

    def handoff(self, edge_id: str, *, user_consented: bool) -> dict:
        """RT-01: transfer control only after VALIDADO and with the user's consent."""
        e = self._edge_from_active(edge_id)
        if e.governed_by != "RT-01":
            raise TransitionRefused(f"{edge_id} is a call, not a handoff")
        if self.validation_state != "VALIDADO":
            raise TransitionRefused(f"{e.source} is {self.validation_state}; handoff needs VALIDADO (RT-01)")
        if not user_consented:
            raise TransitionRefused("the user has not requested or accepted the next step (RT-01)")
        self._log("handoff", edge=edge_id, source=e.source, target=e.target)
        return self.start(e.target)

    def call(self, edge_id: str, *, user_consented: bool = False) -> dict:
        """AUTO runs as part of the procedure; RT-02 asks first. Control stays with the caller."""
        e = self._edge_from_active(edge_id)
        if e.governed_by == "RT-01":
            raise TransitionRefused(f"{edge_id} is a handoff, not a call")
        if e.governed_by == "RT-02" and not user_consented:
            raise TransitionRefused(f"{edge_id} is a conditional call: ask the user first (RT-02)")
        st = effective_status(self.cat, e.target)
        blocked = self.cat.registry[e.target]["deployment_status"]
        self._log("call", edge=edge_id, caller=e.source, callee=e.target, rule=e.governed_by,
                  callee_presented_lifecycle=st.presented_lifecycle, callee_deployment=blocked)
        return {"caller": e.source, "callee": e.target, "control_stays_with": e.source, "callee_status": st}

    def recommend(self, target: str, reason: str) -> dict:
        """RT-03: stop and recommend a component or human authority; nothing is transferred."""
        cid = self._require_active()
        ok, why = invocability(self.cat, target)
        self._log("recommendation", source=cid, target=target, reason=reason,
                  target_invocable=ok, note=None if ok else why)
        return {"source": cid, "recommended": target, "reason": reason, "transferred": False,
                "target_invocable": ok, "note": None if ok else why}
