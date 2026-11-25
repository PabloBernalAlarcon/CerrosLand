"""Interactive pilot: talk to one Cerros AI component from the terminal.

    python -m cerros_runtime chat SP-C01      # school journalism (runs on FL-C02)
    python -m cerros_runtime chat FL-C02      # writing feedback

Nothing typed here is saved by Cerros AI. Fictitious data only (RT-07).
"""
from __future__ import annotations

from typing import Callable

from .catalog import Catalog
from .guards import NotInvocable, effective_status
from .prompt import compose
from .providers import Provider, ProviderError, ProviderNotConfigured
from .session import Session

HELP = """Comandos:
  /estado      estado del componente y de la validación
  /siguiente   qué pasos siguientes permite el mapa (y si están disponibles)
  /validar     registrar tu confirmación humana y marcar el producto como VALIDADO
  /nuevo       empezar una conversación nueva con el mismo componente
  /ayuda       ver estos comandos
  /salir       terminar
Escribe un texto: pega el trabajo del estudiante (ficticio) y di qué revisión necesitas,
incluyendo el nivel del estudiante y el propósito o género del texto."""


def _banner(cat: Catalog, s: Session) -> str:
    cid, sp = s.active, s.specialization
    st = effective_status(cat, cid)
    name = cat.specs[sp or cid]["name"]
    base = f" (sobre {cid} — {cat.specs[cid]['name']})" if sp else ""
    return (f"\nCerros AI · {sp or cid} — {name}{base}\n"
            f"Estado: {st.presented_lifecycle} · {st.deployment_status}\n"
            f"Autoridad humana: {cat.human_authority(sp or cid)}\n"
            f"⚠ Solo datos ficticios (RT-07). Cerros AI no guarda esta conversación.\n"
            f"Escribe /ayuda para ver los comandos.\n")


def run_chat(cat: Catalog, component: str, provider: Provider,
             input_fn: Callable[[str], str] = input, print_fn: Callable[[str], None] = print) -> Session:
    s = Session(cat)
    try:
        s.start(component)
    except NotInvocable as e:
        print_fn(f"✗ No se puede iniciar {component}: {e}")
        return s
    system = compose(cat, s.active, specialization=s.specialization)
    messages: list[dict] = []
    authority = cat.human_authority(s.specialization or s.active)
    print_fn(_banner(cat, s))

    while True:
        try:
            text = input_fn("tú › ").strip()
        except (EOFError, KeyboardInterrupt):
            print_fn("\nHasta luego.")
            return s
        if not text:
            continue
        cmd = text.lower()
        if cmd in ("/salir", "/exit", "/quit"):
            print_fn("Hasta luego.")
            return s
        if cmd == "/ayuda":
            print_fn(HELP)
            continue
        if cmd == "/estado":
            print_fn(f"Componente: {s.specialization or s.active} · validación: {s.validation_state} · "
                     f"confirmaciones humanas: {len(s.human_confirmations)} · turnos: {len(messages) // 2}")
            continue
        if cmd == "/siguiente":
            offers = s.next_steps()
            if not offers:
                print_fn("Este componente no tiene pasos siguientes en el mapa: el resultado vuelve a ti.")
            for o in offers:
                state = "disponible" if o.available_now else f"no disponible ({o.why_not})"
                print_fn(f"- {o.edge_id} → {o.target} [{o.kind}, {o.rule}] {state}: {o.reason}")
            continue
        if cmd == "/nuevo":
            messages.clear()
            s.start(component)
            print_fn("Conversación nueva.")
            continue
        if cmd == "/validar":
            if not messages:
                print_fn("Todavía no hay un producto que validar.")
                continue
            answer = input_fn(f"¿Confirmas, como {authority}, que este resultado queda VALIDADO? (s/n) › ")
            if answer.strip().lower() in ("s", "si", "sí", "y", "yes"):
                s.confirm_human("Validar el resultado de la revisión", by=authority)
                s.set_validation("VALIDADO", confirmed_by_human=True)
                print_fn(f"✓ VALIDADO por {authority}.")
            else:
                print_fn("Sin cambios: el resultado sigue como PRELIMINAR.")
            continue
        if cmd.startswith("/"):
            print_fn("Comando desconocido. Escribe /ayuda.")
            continue

        messages.append({"role": "user", "content": text})
        print_fn("… pensando")
        try:
            reply = provider.complete(system, messages)
        except (ProviderError, ProviderNotConfigured) as e:
            messages.pop()
            print_fn(f"✗ {e}")
            continue
        messages.append({"role": "assistant", "content": reply})
        if s.validation_state == "VALIDADO":
            s.set_validation("PRELIMINAR")  # new content after validation needs a new confirmation
        print_fn(f"\nCerros AI › {reply}\n")

