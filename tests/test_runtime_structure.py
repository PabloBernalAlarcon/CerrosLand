"""Structural tests required by Handoff §11 and the runtime policy (RT-01 … RT-09).

These test the architecture, not model behaviour: who may run, when control moves,
what is loaded, and what is recorded. Model-behaviour tests come from each spec's
functional_acceptance_criteria once a provider is configured.
"""
from pathlib import Path

import pytest

from cerros_runtime import (KnowledgeLayer, NotInvocable, Session, TransitionRefused, compose,
                            effective_status, invocability, load_catalog)

CANON = Path(__file__).resolve().parents[1] / "spec" / "working"


@pytest.fixture(scope="module")
def cat():
    return load_catalog(CANON)


# ---------- Phase 0: contract and metadata ----------
def test_all_specs_load_and_match_registry(cat):
    assert len(cat.specs) == 39
    life = [s["lifecycle_status"] for s in cat.specs.values()]
    assert (life.count("ACTIVE"), life.count("PROVISIONAL"), life.count("DISABLED")) == (27, 11, 1)


def test_every_executable_edge_has_exactly_one_rule(cat):
    gov = [e.governed_by for e in cat.edges if e.edge_class == "ORCHESTRATION" and e.executable]
    assert len(gov) == 42 and None not in gov
    assert {g: gov.count(g) for g in set(gov)} == {"RT-01": 14, "AUTO": 20, "RT-02": 5, "RT-05": 3}


def test_rule_titles_restored(cat):
    r = cat.specs["FL-P04"]["rules"]
    assert [r[k]["title"] for k in ("R-FLP04-04", "R-FLP04-05", "R-FLP04-06")] == ["ALTA", "MEDIA", "BAJA"]
    assert cat.specs["IN-S04"]["rules"]["R-INS04-06"]["title"] == "Resultado"


# ---------- Guards: DISABLED / GAP / non-components ----------
@pytest.mark.parametrize("node", ["FL-D04", "GAP-C01", "HUM-PROFESOR", "KP-001"])
def test_non_invocable_nodes_cannot_start(cat, node):
    ok, _ = invocability(cat, node)
    assert not ok
    with pytest.raises(NotInvocable):
        Session(cat).start(node)


def test_dormant_edge_to_disabled_is_never_offered(cat):
    s = Session(cat)
    s.start("FL-D02")
    assert "E020" not in [o.edge_id for o in s.next_steps()]
    with pytest.raises(TransitionRefused):
        s.call("E020", user_consented=True)


# ---------- QA never transfers control ----------
def test_quality_edges_never_transfer_control(cat):
    s = Session(cat)
    s.start("TX-A02")
    with pytest.raises(TransitionRefused, match="never transfers control"):
        s.handoff("E006", user_consented=True)


def test_quality_direction_normalized(cat):
    e = cat.edge("E017")
    assert (e.source, e.target) == ("TX-A02", "FL-D01")


# ---------- RT-01: handoffs need VALIDADO + consent ----------
def test_handoff_requires_validation_then_consent(cat):
    s = Session(cat)
    s.start("FL-P01")
    offer = next(o for o in s.next_steps() if o.edge_id == "E001")
    assert offer.kind == "handoff" and not offer.available_now
    with pytest.raises(TransitionRefused, match="VALIDADO"):
        s.handoff("E001", user_consented=True)
    with pytest.raises(TransitionRefused, match="requires confirmation by HUM-PROFESOR"):
        s.set_validation("VALIDADO")  # no human confirmation
    s.confirm_human("Aprobar secuencia final de unidades.", by="HUM-PROFESOR")
    s.set_validation("VALIDADO", confirmed_by_human=True)
    with pytest.raises(TransitionRefused, match="user"):
        s.handoff("E001", user_consented=False)
    s.handoff("E001", user_consented=True)
    assert s.active == "FL-P02" and s.validation_state == "PRELIMINAR"


# ---------- RT-02 and AUTO: calls keep control with the caller ----------
def test_conditional_call_asks_first(cat):
    s = Session(cat)
    s.start("FL-C01")
    with pytest.raises(TransitionRefused, match="ask the user first"):
        s.call("E023")
    r = s.call("E023", user_consented=True)
    assert r["control_stays_with"] == "FL-C01" and s.active == "FL-C01"


def test_auto_call_runs_without_asking(cat):
    s = Session(cat)
    s.start("FL-D01")
    r = s.call("E015")  # FL-D01 -> TX-D01
    assert r["callee"] == "TX-D01" and s.active == "FL-D01"


# ---------- RT-05: TX-P01 never takes control ----------
def test_tx_p01_edges_are_dormant(cat):
    s = Session(cat)
    s.start("TX-P01")
    assert not s.next_steps()
    with pytest.raises(TransitionRefused, match="dormant"):
        s.handoff("E043", user_consented=True)


# ---------- RT-03: recommend without transfer ----------
def test_derivar_without_edge_recommends_only(cat):
    s = Session(cat)
    s.start("FL-P03")
    r = s.recommend("FL-P02", "Falta planificación curricular suficiente")
    assert r["transferred"] is False and s.active == "FL-P03"


# ---------- RT-06: effective status ----------
def test_status_inherits_from_mandatory_provisional_callee(cat):
    st = effective_status(cat, "WF-I01")
    assert st.own_lifecycle == "ACTIVE" and st.presented_lifecycle == "PROVISIONAL"
    assert set(st.inherited_from) == {"TX-I02", "TX-I03"}
    assert cat.registry["WF-I01"]["lifecycle_status"] == "ACTIVE"  # registry untouched


def test_blocked_mandatory_callee_blocks_that_step(cat):
    st = effective_status(cat, "WF-A01")
    assert ("E013", "FL-D03 is BLOCKED_BY_KNOWLEDGE") in st.blocked_steps


# ---------- Knowledge layer ----------
def test_knowledge_loaded_only_by_dependency(cat):
    kl = KnowledgeLayer(cat)
    assert kl.for_component("FL-C02") == []
    packs = {p.knowledge_id: p for p in kl.for_component("FL-D01")}
    assert set(packs) == {"KP-001", "KP-002", "KP-005"}
    assert packs["KP-001"].complete and packs["KP-005"].warning


# ---------- Pilot slice: FL-C02 + SP-C01 ----------
def test_pilot_slice_is_clean(cat):
    for cid in ("FL-C02", "SP-C01"):
        st = effective_status(cat, cid)
        assert st.presented_lifecycle == "ACTIVE" and not st.blocked_steps


def test_specialization_runs_on_its_base(cat):
    s = Session(cat)
    r = s.start("SP-C01")
    assert (r["component"], r["specialization"]) == ("FL-C02", "SP-C01")
    with pytest.raises(TransitionRefused, match="HUM-EDITOR"):
        s.set_validation("VALIDADO")


def test_composed_instructions_contain_base_and_specialization(cat):
    text = compose(cat, "FL-C02", specialization="SP-C01")
    for must in ("CORE-01", "R-FLC02-01 [Autoría]", "R-SPC01-10", "HUM-EDITOR", "RT-03", "Ninguno declarado"):
        assert must in text, must
