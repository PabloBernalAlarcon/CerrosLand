"""Provider tests that never call a real model. A fake `claude` executable stands in for Claude Code."""
import os
import stat
import textwrap

import pytest

from cerros_runtime.providers import (ClaudeCodeProvider, EchoProvider, ProviderError, ProviderNotConfigured,
                                      from_env)


def _fake_claude(tmp_path, body: str):
    exe = tmp_path / "claude"
    exe.write_text("#!/usr/bin/env python3\n" + textwrap.dedent(body))
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    return tmp_path


def test_default_provider_is_per_user_claude_code():
    assert from_env({}).name == "claude_code"
    assert from_env({"CERROS_PROVIDER": "echo"}).name == "echo"
    with pytest.raises(ProviderNotConfigured):
        from_env({"CERROS_PROVIDER": "anthropic_api"})  # no key: refuses instead of guessing


def test_command_uses_login_not_bare_and_denies_tools():
    cmd = ClaudeCodeProvider(model="sonnet")._cmd("SYSTEM")
    assert "--bare" not in cmd  # bare mode ignores the user's own login
    assert cmd[cmd.index("--system-prompt") + 1] == "SYSTEM"
    assert cmd[cmd.index("--permission-mode") + 1] == "dontAsk"
    assert cmd[cmd.index("--model") + 1] == "sonnet"


def test_parses_result_from_fake_claude(tmp_path, monkeypatch):
    d = _fake_claude(tmp_path, """
        import json, sys
        prompt = sys.stdin.read()
        print(json.dumps({"result": "OK: " + prompt[:5], "is_error": False, "total_cost_usd": 0.0}))
    """)
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")
    out = ClaudeCodeProvider().complete("sys", [{"role": "user", "content": "Hola mundo"}])
    assert out == "OK: Hola "


def test_reports_login_problem_instead_of_hiding_it(tmp_path, monkeypatch):
    d = _fake_claude(tmp_path, """
        import json
        print(json.dumps({"result": "Not logged in", "is_error": True}))
    """)
    monkeypatch.setenv("PATH", f"{d}{os.pathsep}{os.environ['PATH']}")
    with pytest.raises(ProviderError, match="Not logged in"):
        ClaudeCodeProvider().complete("sys", [{"role": "user", "content": "x"}])


def test_echo_provider_offline():
    assert "hola" in EchoProvider().complete("s", [{"role": "user", "content": "hola"}])
