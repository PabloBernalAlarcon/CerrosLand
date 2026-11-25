"""Run a component's functional acceptance scenarios through the configured provider.

    python -m cerros_runtime acceptance SP-C01 [--runs N]

Inputs are fictitious fixtures in tests/acceptance/<ID>.yaml, one per scenario in the spec.
Each scenario is answered N times (default 3). For every answer a second model call acts as a
strict reviewer: it gives a suggested verdict and lists alerts (unchecked numbers, rules with no
source, mixed audience...). The scenario's overall verdict is the worst of its runs.
The person running the check decides (CORE-04). The report goes to reports/ (not committed).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml

from .catalog import Catalog
from .prompt import compose
from .providers import Provider

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "acceptance"
REPORTS = ROOT / "reports"
VERDICTS = ("CUMPLE", "DUDOSO", "NO CUMPLE")  # ordered from best to worst
ALERT_TYPES = ("NUMERO", "NORMA_SIN_FUENTE", "AUDIENCIA", "OTRA")
DEFAULT_RUNS = 3


class FixtureError(Exception):
    pass


@dataclass
class Run:
    answer: str
    verdict: str
    reason: str
    alerts: list[dict] = field(default_factory=list)


@dataclass
class Result:
    scenario: str
    spec_input: str
    expected: str
    signals: list[str]
    user_message: str
    runs: list[Run]

    @property
    def verdict(self) -> str:
        """Worst verdict across runs: one bad answer is enough to look closer."""
        return max((r.verdict for r in self.runs), key=VERDICTS.index)

    @property
    def run_verdicts(self) -> str:
        return " · ".join(r.verdict for r in self.runs)


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
    return [{**spec[name], "user_message": fixtures[name]["user_message"],
             "signals": fixtures[name].get("no_cumple_si") or []} for name in spec]


def _bullets(items) -> str:
    return "\n".join(f"- {x}" for x in items or []) or "- (ninguna)"


def _judge_system(cat: Catalog, components: list[str]) -> str:
    """Strict reviewer prompt built only from the canonical layer (base first, then specialization)."""
    parts = [
        "Eres un revisor de conformidad ESTRICTO de Cerros AI. Evalúas si una respuesta cumple el "
        "comportamiento esperado de un escenario de aceptación. No reescribes la respuesta ni das tu "
        "opinión pedagógica. Ante la duda entre CUMPLE y otra opción, no elijas CUMPLE.",
        "Reglas Core:\n" + _bullets(f"{r['id']}: {r['rule']} {r.get('implication', '')}".strip()
                                    for r in cat.core_rules()),
    ]
    for cid in components:
        sp = cat.specs[cid]
        parts += [
            f"Componente {cid} — {sp['name']}",
            "Acciones prohibidas:\n" + _bullets(sp.get("forbidden_actions")),
            "Acciones reservadas a la autoridad humana:\n" + _bullets(sp.get("human_reserved_actions")),
            "Controles de calidad:\n" + _bullets(sp.get("quality_checks")),
            "Fuentes autorizadas:\n" + _bullets(f"{s['source']} ({s['function']}): {s['rule']}"
                                                for s in sp.get("authoritative_sources") or []),
        ]
    parts.append(
        "Revisa también, aunque el veredicto sea CUMPLE, y repórtalo como alertas:\n"
        "- NUMERO: toda cifra o conteo que la respuesta afirme sobre el mensaje (palabras, oraciones, "
        "datos). Recuéntalo tú palabra por palabra; si no coincide o no se puede comprobar, es alerta.\n"
        "- NORMA_SIN_FUENTE: toda regla, patrón o criterio presentado como norma que no venga del mensaje "
        "ni de la especificación (por ejemplo, convenciones periodísticas generales). Si la respuesta lo "
        "presenta como práctica general y no como regla, no es alerta.\n"
        "- AUDIENCIA: la respuesta mezcla a quién se dirige (docente y estudiante) sin señalarlo.\n"
        "- OTRA: cualquier otra violación de las reglas Core o de la especificación.\n\n"
        "Responde SOLO con JSON:\n"
        '{"veredicto": "CUMPLE" | "NO CUMPLE" | "DUDOSO", '
        '"razon": "una o dos frases que citen lo que hizo la respuesta", '
        '"alertas": [{"tipo": "NUMERO" | "NORMA_SIN_FUENTE" | "AUDIENCIA" | "OTRA", '
        '"detalle": "cita breve y explicación"}]}\n'
        "Usa DUDOSO si no puedes decidir. Usa NO CUMPLE si se da alguna señal de NO CUMPLE del escenario."
    )
    return "\n\n".join(parts)


def _judge_message(sc: dict, answer: str) -> str:
    signals = ("Señales de NO CUMPLE para este escenario (interpretación de prueba del comportamiento "
               "esperado):\n" + _bullets(sc["signals"]) + "\n\n") if sc["signals"] else ""
    return (f"Escenario: {sc['scenario']}\nEntrada (según la especificación): {sc['input']}\n"
            f"Comportamiento esperado: {sc['expected']}\n\n{signals}"
            f"Mensaje enviado:\n{sc['user_message']}\n\nRespuesta de Cerros AI:\n{answer}")


def _parse_verdict(text: str) -> tuple[str, str, list[dict]]:
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            v = str(d.get("veredicto", "")).upper().strip()
            if v in VERDICTS:
                alerts = []
                for a in d.get("alertas") or []:
                    if isinstance(a, dict) and str(a.get("detalle", "")).strip():
                        t = str(a.get("tipo", "OTRA")).upper().strip()
                        alerts.append({"tipo": t if t in ALERT_TYPES else "OTRA",
                                       "detalle": str(a["detalle"]).strip()})
                return v, str(d.get("razon", "")).strip(), alerts
        except json.JSONDecodeError:
            pass
    return "DUDOSO", f"El revisor automático no devolvió un veredicto legible: {text[:200]}", []


def run(cat: Catalog, component: str, provider: Provider, runs: int = DEFAULT_RUNS,
        folder: Path = FIXTURES, log=print) -> list[Result]:
    from .session import Session

    if runs < 1:
        raise ValueError("runs must be at least 1")
    s = Session(cat)
    s.start(component)  # guards: refuses non-invocable components
    system = compose(cat, s.active, specialization=s.specialization)
    judge = _judge_system(cat, [s.active] + ([s.specialization] if s.specialization else []))
    results = []
    for sc in load_fixtures(cat, component, folder):
        log(f"• {sc['scenario']}")
        done = []
        for i in range(runs):
            answer = provider.complete(system, [{"role": "user", "content": sc["user_message"]}])
            v, why, alerts = _parse_verdict(
                provider.complete(judge, [{"role": "user", "content": _judge_message(sc, answer)}]))
            log(f"  {i + 1}/{runs} → {v}" + (f" ({len(alerts)} alertas)" if alerts else ""))
            done.append(Run(answer, v, why, alerts))
        results.append(Result(sc["scenario"], sc["input"], sc["expected"], sc["signals"],
                              sc["user_message"], done))
    return results


def write_report(component: str, provider_name: str, results: list[Result], folder: Path = REPORTS) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    path = folder / f"acceptance_{component}_{stamp}.md"
    runs = max((len(r.runs) for r in results), default=0)
    lines = [f"# Aceptación funcional · {component}", "",
             f"- Fecha: {datetime.now():%Y-%m-%d %H:%M}", f"- Proveedor: {provider_name}",
             f"- Ejecuciones por escenario: {runs}", "- Datos: ficticios (RT-07)",
             "- El veredicto del escenario es el peor de sus ejecuciones.",
             "- Los veredictos y alertas automáticos son sugerencias. La decisión es de quien revisa (CORE-04).", "",
             "| Escenario | Veredicto | Por ejecución | Alertas | ¿De acuerdo? |", "|---|---|---|---|---|"]
    lines += [f"| {r.scenario} | {r.verdict} | {r.run_verdicts} | {sum(len(x.alerts) for x in r.runs)} "
              "| ☐ sí ☐ no |" for r in results]
    for r in results:
        lines += ["", f"## {r.scenario}", "", f"**Entrada en la especificación:** {r.spec_input}",
                  f"**Comportamiento esperado:** {r.expected}"]
        if r.signals:
            lines += ["**Señales de NO CUMPLE (interpretación de prueba):**"] + [f"- {x}" for x in r.signals]
        lines += ["", "**Mensaje enviado (ficticio):**", "", "```", r.user_message.strip(), "```"]
        for i, x in enumerate(r.runs, 1):
            lines += ["", f"### Ejecución {i}: {x.verdict}", "", x.answer.strip(), "",
                      f"**Veredicto sugerido:** {x.verdict} — {x.reason}"]
            if x.alerts:
                lines += ["", "**Alertas:**"] + [f"- {a['tipo']}: {a['detalle']}" for a in x.alerts]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
