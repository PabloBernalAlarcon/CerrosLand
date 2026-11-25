"""Command line.

    python -m cerros_runtime doctor               check this computer is ready
    python -m cerros_runtime chat [COMPONENT]     talk to a component (default SP-C01)
    python -m cerros_runtime acceptance COMPONENT [--runs N]
                                                  run the spec's acceptance scenarios (default 3 runs)
"""
from __future__ import annotations

import sys
from pathlib import Path

from . import effective_status, load_catalog
from .providers import claude_auth_status, from_env

SPEC = Path(__file__).resolve().parents[1] / "spec" / "working"
PILOT = ("FL-C02", "SP-C01")


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def doctor() -> int:
    ok = True
    try:
        cat = load_catalog(SPEC)
        print(f"✓ Canonical layer loaded: {len(cat.specs)} components, {len(cat.edges)} edges")
    except Exception as e:  # report, don't hide
        print(f"✗ Canonical layer failed to load: {e}")
        return 1
    for cid in PILOT:
        st = effective_status(cat, cid)
        print(f"✓ Pilot {cid}: {st.presented_lifecycle}, blocked steps: {st.blocked_steps or 'none'}")
    provider_name = None
    try:
        provider_name = from_env().name
        print(f"✓ Provider: {provider_name}")
    except Exception as e:
        ok = False
        print(f"✗ Provider: {e}")
    if provider_name != "claude_code":
        return 0 if ok else 1
    auth = claude_auth_status()
    if not auth["installed"]:
        ok = False
        print("✗ Claude Code not found. Install it, then run `claude` and `/login` with YOUR OWN Claude account.")
    elif auth["logged_in"] is None:
        print("• Claude Code found, but its sign-in status could not be read. Run `claude auth status`.")
    elif not auth["logged_in"]:
        ok = False
        print("✗ Claude Code is installed but not signed in. Run `claude`, then `/login` with your own account.")
    elif auth["auth_method"] == "claude.ai":
        print("✓ Claude Code signed in with a Claude plan (usage counts against your own plan).")
    else:
        print(f"• Claude Code signed in with method '{auth['auth_method']}'. Cerros AI expects your own Claude "
              "plan ('claude.ai'); other methods may bill an API account.")
    return 0 if ok else 1


def _pilot_only(component: str) -> bool:
    if component not in PILOT:
        print(f"Por ahora el piloto solo incluye {', '.join(PILOT)}. {component} queda para una fase posterior.")
        return False
    return True


def chat(component: str) -> int:
    from .chat import run_chat
    if not _pilot_only(component):
        return 2
    run_chat(load_catalog(SPEC), component, from_env())
    return 0


def acceptance(component: str, runs: int) -> int:
    from .acceptance import load_fixtures, run, write_report
    if not _pilot_only(component):
        return 2
    if runs < 1:
        print("--runs debe ser 1 o más.")
        return 2
    cat, provider = load_catalog(SPEC), from_env()
    calls = 2 * runs * len(load_fixtures(cat, component))
    print(f"Ejecutando escenarios de aceptación de {component} con {provider.name}: {runs} ejecución(es) "
          f"por escenario, unas {calls} llamadas al modelo en total…")
    results = run(cat, component, provider, runs=runs)
    path = write_report(component, provider.name, results)
    counts = {v: sum(r.verdict == v for r in results) for v in ("CUMPLE", "NO CUMPLE", "DUDOSO")}
    alerts = sum(len(x.alerts) for r in results for x in r.runs)
    print(f"Listo: {counts}, {alerts} alertas. Revisa y marca tu acuerdo en: {path}")
    return 0


def _runs_arg(args: list[str]) -> int | None:
    from .acceptance import DEFAULT_RUNS
    if "--runs" not in args:
        return DEFAULT_RUNS
    i = args.index("--runs")
    try:
        return int(args[i + 1])
    except (IndexError, ValueError):
        return None


def main(argv: list[str]) -> int:
    _utf8_console()
    if argv[:1] == ["doctor"]:
        return doctor()
    if argv[:1] == ["chat"]:
        return chat(argv[1] if len(argv) > 1 else "SP-C01")
    if argv[:1] == ["acceptance"] and len(argv) > 1:
        runs = _runs_arg(argv[2:])
        if runs is None:
            print("Uso: python -m cerros_runtime acceptance COMPONENTE [--runs N]")
            return 2
        return acceptance(argv[1], runs)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
