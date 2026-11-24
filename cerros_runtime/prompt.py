"""Compose provider-neutral instructions for a component from the canonical layer.

The text is built only from the spec, the Core, the Knowledge layer and the runtime
policy, so the institutional rules stay in portable files, not in a vendor prompt
(Spec §18.2).
"""
from __future__ import annotations

from .catalog import Catalog
from .guards import effective_status
from .knowledge import KnowledgeLayer


def _lines(items) -> str:
    return "\n".join(f"- {x}" for x in items or []) or "- (no especificado)"


def _rules(spec: dict) -> str:
    out = []
    for rid, r in (spec.get("rules") or {}).items():
        if isinstance(r, dict):
            out.append(f"- {rid} [{r['title']}]: {r['text']}")
        else:
            out.append(f"- {rid}: {r}")
    return "\n".join(out)


def _procedure(spec: dict) -> str:
    out = []
    for ph in spec.get("procedure") or []:
        if isinstance(ph, dict):
            out.append(f"{ph['phase']}")
            out += [f"  - {s}" for s in ph.get("steps", [])]
        else:
            out.append(f"- {ph}")
    return "\n".join(out)


def _decisions(spec: dict) -> str:
    return "\n".join(f"- {d['if']} → {d['then']}" for d in spec.get("decision_logic") or [])


def _states(spec: dict) -> str:
    out = []
    for v in spec.get("validation_states") or []:
        out.append(f"- {v['state']}: {v.get('condition', '')}" if isinstance(v, dict) else f"- {v}")
    return "\n".join(out)


def _section(title: str, body: str) -> str:
    return f"## {title}\n{body}\n"


def compose(cat: Catalog, cid: str, specialization: str | None = None,
            knowledge: KnowledgeLayer | None = None) -> str:
    spec = cat.specs[cid]
    st = effective_status(cat, cid)
    kl = knowledge or KnowledgeLayer(cat)
    parts = [f"# Cerros AI · {cid} — {spec['name']}"]
    parts.append(_section("Reglas Core (prevalecen sobre todo lo demás)",
                          "\n".join(f"- {r['id']}: {r['rule']} ({r['implication']})" for r in cat.core_rules())))
    parts.append(_section("Estado y alcance",
                          f"- Estado presentado: {st.presented_lifecycle} (propio: {st.own_lifecycle})\n"
                          f"- Despliegue: {st.deployment_status} → {st.data_scope}\n"
                          f"- Autoridad humana: {cat.human_authority(specialization or cid)}"
                          + (f"\n- Pasos bloqueados: {st.blocked_steps}" if st.blocked_steps else "")))
    parts.append(_section("Propósito", spec.get("purpose") or "(no especificado)"))
    parts.append(_section("Reglas heredadas del componente", _lines(spec.get("core_rules_inherited"))))
    parts.append(_section("Reglas específicas", _rules(spec)))
    parts.append(_section("Procedimiento", _procedure(spec)))
    parts.append(_section("Lógica de decisión", _decisions(spec)))
    parts.append(_section("Acciones autónomas", _lines(spec.get("autonomous_actions"))))
    parts.append(_section("Acciones reservadas a la autoridad humana (detenerse y devolver la decisión)",
                          _lines(spec.get("human_reserved_actions"))))
    parts.append(_section("Acciones prohibidas", _lines(spec.get("forbidden_actions"))))
    parts.append(_section("Salidas", _lines(spec.get("outputs"))))
    parts.append(_section("Control de calidad antes de cerrar", _lines(spec.get("quality_checks"))))
    parts.append(_section("Estados de validación", _states(spec)))
    parts.append(_section("Condición de cierre", _lines(spec.get("completion_condition"))))

    if specialization:
        sp = cat.specs[specialization]
        parts.append(f"# Especialización activa: {specialization} — {sp['name']}\n"
                     "Las reglas de la especialización se aplican además de las del componente base; "
                     "en caso de conflicto, prevalece la más restrictiva.\n")
        for title, body in [("Propósito de la especialización", sp.get("purpose") or ""),
                            ("Reglas de la especialización", _rules(sp)),
                            ("Procedimiento de la especialización", _procedure(sp)),
                            ("Lógica de decisión de la especialización", _decisions(sp)),
                            ("Reservado a la autoridad humana", _lines(sp.get("human_reserved_actions"))),
                            ("Prohibido", _lines(sp.get("forbidden_actions"))),
                            ("Salidas", _lines(sp.get("outputs"))),
                            ("Control de calidad", _lines(sp.get("quality_checks")))]:
            parts.append(_section(title, body))

    packs = kl.for_component(cid) + (kl.for_component(specialization) if specialization else [])
    if packs:
        body = []
        for p in packs:
            body.append(f"- {p.knowledge_id} {p.name} · v{p.version} · {p.status}")
            if p.warning:
                body.append(f"  ⚠ {p.warning}")
            body += [f"  · Prohibido: {x}" for x in p.forbidden_reasoning]
        parts.append(_section("Knowledge Packs cargados", "\n".join(body)))
    else:
        parts.append(_section("Knowledge Packs cargados", "- Ninguno declarado."))

    parts.append(_section("Reglas de ejecución (runtime)",
                          "- Si tu procedimiento envía trabajo a otro componente o persona y no tienes una ruta "
                          "ejecutable hacia él, detente y recomienda a quién corresponde y por qué; no transfieras "
                          "nada (RT-03).\n"
                          "- Nunca declares VALIDADO por tu cuenta: propón el estado y espera la confirmación "
                          "humana (CORE-04, RT-01).\n"
                          "- Datos: solo casos ficticios en esta fase (RT-07)."))
    return "\n".join(parts)
