"""Provider tests that never call a real model. A fake `claude` program stands in for Claude Code.

The fake works on Windows (claude.cmd + a Python script) and on macOS/Linux (an executable script).
"""
import os
import stat
import sys
import textwrap

import pytest

from cerros_runtime.providers import (ClaudeCodeProvider, EchoProvider, ProviderError, ProviderNotConfigured,
                                      claude_auth_status, from_env)


def _fake_claude(tmp_path, body: str, monkeypatch):
    """Create a `claude` command that runs `body` with Python, and put it first on PATH."""
    script = tmp_path / "fake_claude.py"
    script.write_text(textwrap.dedent(body), encoding="utf-8")
    if os.name == "nt":
        (tmp_path / "claude.cmd").write_text(f'@echo off\r\n"{sys.executable}" "{script}" %*\r\n', encoding="utf-8")
    else:
        exe = tmp_path / "claude"
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n', encoding="utf-8")
        exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")


def test_default_provider_is_per_user_claude_code():
    assert from_env({}).name == "claude_code"
    assert from_env({"CERROS_PROVIDER": "echo"}).name == "echo"
    with pytest.raises(ProviderNotConfigured):
        from_env({"CERROS_PROVIDER": "anthropic_api"})  # no key: refuses instead of guessing


def test_command_uses_own_login_and_answers_only():
    cmd = ClaudeCodeProvider(model="sonnet")._cmd("prompt.md")
    assert "--bare" not in cmd                      # bare mode ignores the user's own login
    assert "--system-prompt" not in cmd             # instructions travel in a file (Windows limits)
    assert cmd[cmd.index("--system-prompt-file") + 1] == "prompt.md"
    assert "--safe-mode" in cmd                     # personal Claude Code customizations off
    assert cmd[cmd.index("--tools") + 1] == ""      # no built-in tools
    assert cmd[cmd.index("--disallowedTools") + 1] == "mcp__*"
    assert "--no-session-persistence" in cmd
    assert cmd[cmd.index("--model") + 1] == "sonnet"


def test_system_prompt_file_and_accents_round_trip(tmp_path, monkeypatch):
    _fake_claude(tmp_path, """
        import json, sys
        args = sys.argv[1:]
        system = open(args[args.index("--system-prompt-file") + 1], encoding="utf-8").read()
        prompt = sys.stdin.buffer.read().decode("utf-8")
        sys.stdout.buffer.write(json.dumps({"result": prompt[:9] + "|" + system, "is_error": False},
                                           ensure_ascii=False).encode("utf-8"))
    """, monkeypatch)
    out = ClaudeCodeProvider().complete("Reglas: autoría, señalar vacíos", [{"role": "user", "content": "Revisión ñ"}])
    assert out == "Revisión |Reglas: autoría, señalar vacíos"


def test_reports_login_problem_instead_of_hiding_it(tmp_path, monkeypatch):
    _fake_claude(tmp_path, """
        import json
        print(json.dumps({"result": "Not logged in", "is_error": True}))
    """, monkeypatch)
    with pytest.raises(ProviderError, match="Not logged in"):
        ClaudeCodeProvider().complete("sys", [{"role": "user", "content": "x"}])


def test_auth_status_reads_method_without_credentials(tmp_path, monkeypatch):
    _fake_claude(tmp_path, """
        import json
        print(json.dumps({"loggedIn": True, "authMethod": "claude.ai", "email": "someone@example.com"}))
    """, monkeypatch)
    st = claude_auth_status()
    assert st == {"installed": True, "logged_in": True, "auth_method": "claude.ai"}  # email is not kept


def test_missing_claude_code_is_reported(monkeypatch, tmp_path):
    monkeypatch.setenv("PATH", str(tmp_path))  # empty folder: no claude anywhere
    assert claude_auth_status()["installed"] is False
    with pytest.raises(ProviderNotConfigured):
        ClaudeCodeProvider().complete("s", [{"role": "user", "content": "x"}])


def test_echo_provider_offline():
    assert "hola" in EchoProvider().complete("s", [{"role": "user", "content": "hola"}])
