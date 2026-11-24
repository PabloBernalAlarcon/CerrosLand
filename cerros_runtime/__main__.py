"""Command line: `python -m cerros_runtime doctor` checks this computer is ready."""
from __future__ import annotations

import sys
from pathlib import Path

from . import effective_status, load_catalog
from .providers import ClaudeCodeProvider, from_env

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
    try:
        p = from_env()
        print(f"✓ Provider: {p.name}")
    except Exception as e:
        ok = False
        print(f"✗ Provider: {e}")
    if ClaudeCodeProvider.available():
        print("✓ Claude Code found. If you haven't yet, run `claude` and `/login` with YOUR OWN Claude account.")
    else:
        print("• Claude Code not found. Install it to use your own Claude plan (see README).")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    if argv[:1] == ["doctor"]:
        return doctor()
    print("usage: python -m cerros_runtime doctor")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
