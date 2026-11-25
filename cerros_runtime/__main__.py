"""Command line: `python -m cerros_runtime doctor` checks this computer is ready."""
from __future__ import annotations

import sys
from pathlib import Path

from . import effective_status, load_catalog
from .providers import claude_auth_status, from_env

SPEC = Path(__file__).resolve().parents[1] / "spec" / "working"


def doctor() -> int:
    ok = True
    try:
        cat = load_catalog(SPEC)
        print(f"✓ Canonical layer loaded: {len(cat.specs)} components, {len(cat.edges)} edges")
    except Exception as e:  # report, don't hide
        print(f"✗ Canonical layer failed to load: {e}")
        return 1
    for cid in ("FL-C02", "SP-C01"):
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


def main(argv: list[str]) -> int:
    if argv[:1] == ["doctor"]:
        return doctor()
    print("usage: python -m cerros_runtime doctor")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
