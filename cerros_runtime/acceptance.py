"""Run a component's functional acceptance scenarios through the configured provider.

    python -m cerros_runtime acceptance SP-C01

Inputs are fictitious fixtures in tests/acceptance/<ID>.yaml, one per scenario in the spec.
A second model call gives a suggested verdict; the person running the check decides (CORE-04).
The report is written to reports/ (not committed to Git).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from .catalog import Catalog
from .prompt import compose
from .providers import Provider

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "acceptance"
REPORTS = ROOT / "reports"
VERDICTS = ("CUMPLE", "NO CUMPLE", "DUDOSO")


class FixtureError(Exception):
    pass


@dataclass
class Result:
    scenario: str
    spec_input: str
    expected: str
    user_message: str
    answer: str
    verdict: str
    reason: str


def load_fixtures(cat: Catalog, component: str, folder: Path = FIXTURES) -> list[dict]:
    """Pair each spec scenario with exactly one fixture; refuse if they drift apart."""
    f = folder / f"{component}.yaml"
    if not f.exists():
        raise FixtureError(f"No fixtures for {component} ({f.name})")
    data = yaml.safe_load(f.read_text(encoding="utf-8"))
    fixtures = {x["scenario"]: x for x in data["scenarios"]}
    spec = {x["scenario"]: x for x in cat.specs[component]["functional_acceptance_criteria"]}
    if set(fixtures) != set(spec):
        raise FixtureError(f"{component}: spec scenarios {sorted(spec)} ≠ fixtures {sorted(fixtures)}")
    return [{**spec[name], "user_message": fixtures[name]["user_message"]} for name in spec]


def _judge_system(cat: Catalog, component: str) -> str:
    sp = cat.specs[component]
    return (
        "Eres un revisor de conformidad de Cerros AI. Evalúas si una respuesta cumple el comportamiento "
        "esperado de un escenario de aceptación. No reescribes la respuesta ni das tu opinión pedagógica.\n"
        f"Componente: {component} — {sp['name']}\n"
        "Acciones prohibidas del componente:\n" + "\n".join(f"- {x}" for x in sp.get("forbidden_actions") or []) +
        "\nAcciones reservadas a la autoridad humana:\n" +
        "\n".join(f"- {x}" for x in sp.get("human_reserved_actions") or []) +
        "\n\nResponde SOLO con JSON: {\"veredicto\": \"CUMPLE\" | \"NO CUMPLE\" | \"DUDOSO\", "
        "\"razon\": \"una o dos frases que citen lo que hizo la respuesta\"}. Usa DUDOSO si no puedes decidir."
    )


def _parse_verdict(text: str) -> tuple[str, str]:
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            v = str(d.get("veredicto", "")).upper().strip()
            if v in VERDICTS:
                return v, str(d.get("razon", "")).strip()
        except json.JSONDecodeError:
            pass
    return "DUDOSO", f"El revisor automático no devolvió un veredicto legible: {text[:200]}"


def run(cat: Catalog, component: str, provider: Provider, folder: Path = FIXTURES,
        log=print) -> list[Result]:
    from .session import Session

    s = Session(cat)
    s.start(component)  # guards: refuses non-invocable components
    system = compose(cat, s.active, specialization=s.specialization)
    judge = _judge_system(cat, component)
    results = []
    for sc in load_fixtures(cat, component, folder):
        log(f"• {sc['scenario']} …")
        answer = provider.complete(system, [{"role": "user", "content": sc["user_message"]}])
        verdict_raw = provider.complete(judge, [{"role": "user", "content": (
            f"Escenario: {sc['scenario']}\nEntrada (según la especificación): {sc['input']}\n"
            f"Comportamiento esperado: {sc['expected']}\n\nMensaje enviado:\n{sc['user_message']}\n\n"
            f"Respuesta de Cerros AI:\n{answer}")}])
        v, why = _parse_verdict(verdict_raw)
        log(f"  → {v}")
        results.append(Result(sc["scenario"], sc["input"], sc["expected"], sc["user_message"], answer, v, why))
    return results


def write_report(component: str, provider_name: str, results: list[Result], folder: Path = REPORTS) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    path = folder / f"acceptance_{component}_{stamp}.md"
    lines = [f"# Aceptación funcional · {component}", "",
             f"- Fecha: {datetime.now():%Y-%m-%d %H:%M}", f"- Proveedor: {provider_name}",
             "- Datos: ficticios (RT-07)",
             "- El veredicto automático es una sugerencia. La decisión es de quien revisa (CORE-04).", "",
             "| Escenario | Veredicto sugerido | ¿De acuerdo? |", "|---|---|---|"]
    lines += [f"| {r.scenario} | {r.verdict} | ☐ sí ☐ no |" for r in results]
    for r in results:
        lines += ["", f"## {r.scenario}", "", f"**Entrada en la especificación:** {r.spec_input}",
                  f"**Comportamiento esperado:** {r.expected}", "", "**Mensaje enviado (ficticio):**", "",
                  "```", r.user_message.strip(), "```", "", "**Respuesta de Cerros AI:**", "", r.answer.strip(),
                  "", f"**Veredicto sugerido:** {r.verdict} — {r.reason}"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
