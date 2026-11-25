"""Offline tests for the pilot chat and the acceptance runner (no model is called)."""
from pathlib import Path

import pytest

from cerros_runtime import load_catalog
from cerros_runtime.acceptance import _parse_verdict, load_fixtures, run, write_report
from cerros_runtime.chat import run_chat
from cerros_runtime.providers import ProviderError

CANON = Path(__file__).resolve().parents[1] / "spec" / "working"


@pytest.fixture(scope="module")
def cat():
    return load_catalog(CANON)


class Scripted:
    """Returns queued replies and records every call."""
    name = "scripted"

    def __init__(self, replies):
        self.replies, self.calls = list(replies), []

    def complete(self, system, messages):
        self.calls.append((system, [dict(m) for m in messages]))
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


def _run(cat, component, inputs, provider):
    it, out = iter(inputs), []
    session = run_chat(cat, component, provider, input_fn=lambda _p: next(it), print_fn=out.append)
    return session, "\n".join(out)


def test_chat_specialization_validation_needs_human(cat):
    p = Scripted(["Fortalezas: … Oportunidades: …"])
    s, out = _run(cat, "SP-C01", ["Revisa este lead (ficticio)", "/validar", "s", "/salir"], p)
    assert "Solo datos ficticios (RT-07)" in out and "HUM-EDITOR" in out
    system, msgs = p.calls[0]
    assert "R-SPC01-10" in system and "R-FLC02-01" in system  # specialization + base
    assert msgs == [{"role": "user", "content": "Revisa este lead (ficticio)"}]
    assert s.validation_state == "VALIDADO"
    assert s.human_confirmations[0]["by"] == "HUM-EDITOR"


def test_chat_declined_validation_stays_preliminary(cat):
    s, _ = _run(cat, "FL-C02", ["texto", "/validar", "n", "/salir"], Scripted(["ok"]))
    assert s.validation_state == "PRELIMINAR" and not s.human_confirmations


def test_chat_new_content_after_validation_resets_state(cat):
    s, _ = _run(cat, "FL-C02", ["a", "/validar", "s", "b", "/salir"], Scripted(["r1", "r2"]))
    assert s.validation_state == "PRELIMINAR"


def test_chat_nothing_to_validate_yet(cat):
    s, out = _run(cat, "FL-C02", ["/validar", "/salir"], Scripted([]))
    assert "Todavía no hay" in out and s.validation_state == "PRELIMINAR"


def test_chat_keeps_history_and_survives_provider_error(cat):
    p = Scripted([ProviderError("Not logged in"), "respuesta"])
    _, out = _run(cat, "FL-C02", ["uno", "dos", "/salir"], p)
    assert "Not logged in" in out
    assert p.calls[1][1] == [{"role": "user", "content": "dos"}]  # failed turn was not kept


def test_chat_shows_no_next_steps_for_fl_c02(cat):
    _, out = _run(cat, "FL-C02", ["/siguiente", "/salir"], Scripted([]))
    assert "no tiene pasos siguientes" in out


def test_chat_refuses_disabled_component(cat):
    _, out = _run(cat, "FL-D04", ["/salir"], Scripted([]))
    assert "No se puede iniciar FL-D04" in out


@pytest.mark.parametrize("component,count", [("FL-C02", 3), ("SP-C01", 4)])
def test_fixtures_match_spec_scenarios(cat, component, count):
    fx = load_fixtures(cat, component)
    assert len(fx) == count and all(f["user_message"].strip() for f in fx)


def test_acceptance_repeats_and_takes_worst_verdict(cat, tmp_path):
    ok = '{"veredicto": "CUMPLE", "razon": "reconduce a feedback", "alertas": []}'
    alert = ('{"veredicto": "CUMPLE", "razon": "ok", "alertas": '
             '[{"tipo": "NUMERO", "detalle": "dice 5 palabras; son 6"}]}')
    bad = '{"veredicto": "NO CUMPLE", "razon": "lista mejoras no pedidas"}'
    judged = [ok, ok, ok, ok, alert, ok, ok, bad, ok]  # 3 scenarios x 3 runs
    replies = [x for j in judged for x in ("respuesta de prueba", j)]
    p = Scripted(replies)
    results = run(cat, "FL-C02", p, runs=3, log=lambda *_: None)
    assert len(p.calls) == 18
    assert [r.verdict for r in results] == ["CUMPLE", "CUMPLE", "NO CUMPLE"]
    assert results[2].run_verdicts == "CUMPLE · NO CUMPLE · CUMPLE"
    path = write_report("FL-C02", "scripted", results, folder=tmp_path)
    text = path.read_text(encoding="utf-8")
    assert "Ejecuciones por escenario: 3" in text and "☐ sí ☐ no" in text and "CORE-04" in text
    assert "NUMERO: dice 5 palabras; son 6" in text and "### Ejecución 3" in text


def test_judge_prompt_covers_base_and_specialization(cat):
    p = Scripted(["r", '{"veredicto": "CUMPLE", "razon": "x"}'] * 4)
    run(cat, "SP-C01", p, runs=1, log=lambda *_: None)
    judge_system, judge_msgs = p.calls[1]
    assert "CORE-01" in judge_system and "NORMA_SIN_FUENTE" in judge_system
    assert "Componente FL-C02" in judge_system and "Componente SP-C01" in judge_system
    assert "Inventar datos, fuentes o citas." in judge_system  # SP-C01 forbidden action
    assert "Señales de NO CUMPLE" in judge_msgs[0]["content"]
    answer_system, _ = p.calls[0]
    assert "NORMA_SIN_FUENTE" not in answer_system  # the answering prompt is unchanged


def test_runs_must_be_positive(cat):
    with pytest.raises(ValueError):
        run(cat, "FL-C02", Scripted([]), runs=0, log=lambda *_: None)


def test_unreadable_verdict_becomes_dudoso():
    assert _parse_verdict("no sé")[0] == "DUDOSO"
    assert _parse_verdict('{"veredicto": "NO CUMPLE", "razon": "x"}') == ("NO CUMPLE", "x", [])
    v = _parse_verdict('{"veredicto": "CUMPLE", "razon": "x", "alertas": [{"tipo": "raro", "detalle": "d"}, {"tipo": "NUMERO"}]}')
    assert v[2] == [{"tipo": "OTRA", "detalle": "d"}]  # unknown type kept as OTRA, empty detail dropped
