"""Model providers behind one small interface, so Cerros AI stays provider-neutral (Spec §18.2).

Access model (decision 2026-11-24): every person signs in with THEIR OWN Claude account on
their own computer. Cerros AI never stores, receives or shares anyone's credentials, and never
routes one person's requests through another person's plan.

- ClaudeCodeProvider  -> uses the local Claude Code login of whoever runs the app (default).
- AnthropicAPIProvider -> uses an API key, for a future funded or institutional deployment.
- EchoProvider        -> offline stand-in for tests and demos; no model is called.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from typing import Protocol


class Provider(Protocol):
    name: str

    def complete(self, system: str, messages: list[dict]) -> str: ...


class ProviderNotConfigured(Exception):
    pass


class ProviderError(Exception):
    pass


class EchoProvider:
    name = "echo"

    def complete(self, system: str, messages: list[dict]) -> str:
        last = messages[-1]["content"] if messages else ""
        return f"[echo · {len(system)} chars of instructions] {last}"


def _render(messages: list[dict]) -> str:
    """Flatten a conversation into one prompt for a stateless CLI call."""
    if len(messages) == 1:
        return messages[0]["content"]
    lines = []
    for m in messages:
        who = "Usuario" if m["role"] == "user" else "Cerros AI"
        lines.append(f"[{who}]\n{m['content']}")
    lines.append("[Responde ahora como Cerros AI al último mensaje del usuario.]")
    return "\n\n".join(lines)


@dataclass
class ClaudeCodeProvider:
    """Calls `claude -p` with the signed-in user's own Claude plan.

    Each person installs Claude Code once and signs in with `claude` → `/login`.
    Flags (see https://code.claude.com/docs/en/cli-reference):
    - not `--bare`: bare mode ignores the subscription login and needs an API key;
    - `--safe-mode`: personal CLAUDE.md, skills, hooks, MCP servers and memory do not load,
      while login and model selection work normally;
    - `--system-prompt-file`: Cerros AI's instructions replace the default prompt; a file
      avoids Windows command-line length limits and quoting problems;
    - `--tools ""` and `--disallowedTools "mcp__*"`: no tools, so the model can only answer;
    - `--no-session-persistence`: the conversation is not saved to disk by Claude Code.
    The call runs in an empty temporary folder.
    """
    model: str | None = None
    timeout_s: int = 300
    name: str = "claude_code"
    _last_cost: float | None = field(default=None, repr=False)

    @staticmethod
    def executable() -> str | None:
        return shutil.which("claude")  # resolves claude.exe / claude.cmd on Windows

    @classmethod
    def available(cls) -> bool:
        return cls.executable() is not None

    def _cmd(self, system_file: str, exe: str = "claude") -> list[str]:
        cmd = [exe, "-p", "--output-format", "json", "--system-prompt-file", system_file,
               "--safe-mode", "--tools", "", "--disallowedTools", "mcp__*",
               "--no-session-persistence", "--permission-mode", "dontAsk"]
        if self.model:
            cmd += ["--model", self.model]
        return cmd

    def complete(self, system: str, messages: list[dict]) -> str:
        exe = self.executable()
        if not exe:
            raise ProviderNotConfigured("Claude Code is not installed. Install it, run `claude`, then `/login` "
                                        "with your own Claude account.")
        with tempfile.TemporaryDirectory(prefix="cerros_") as cwd:
            system_file = os.path.join(cwd, "cerros_system_prompt.md")
            with open(system_file, "w", encoding="utf-8") as f:
                f.write(system)
            try:
                r = subprocess.run(self._cmd(system_file, exe), input=_render(messages), capture_output=True,
                                   text=True, encoding="utf-8", errors="replace", cwd=cwd, timeout=self.timeout_s)
            except subprocess.TimeoutExpired as e:
                raise ProviderError(f"Claude Code did not answer within {self.timeout_s}s") from e
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            hint = (" If it mentions an unknown option, run `claude update`."
                    if "unknown option" in (r.stderr or "").lower() else "")
            raise ProviderError(f"Unexpected output from Claude Code: {(r.stdout or r.stderr)[:300]}{hint}") from e
        if data.get("is_error") or r.returncode != 0:
            raise ProviderError(f"Claude Code error: {data.get('result') or r.stderr[:300]}")
        self._last_cost = data.get("total_cost_usd")
        return data.get("result", "")


def claude_auth_status() -> dict:
    """Ask Claude Code whether this computer is signed in. Never reads or returns credentials."""
    exe = ClaudeCodeProvider.executable()
    if not exe:
        return {"installed": False, "logged_in": False, "auth_method": None}
    try:
        r = subprocess.run([exe, "auth", "status"], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=30)
        data = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return {"installed": True, "logged_in": None, "auth_method": None}
    return {"installed": True, "logged_in": r.returncode == 0, "auth_method": data.get("authMethod")}


class AnthropicAPIProvider:
    """API-key provider for a future funded deployment. Not used in the personal-computer phase."""
    name = "anthropic_api"

    def __init__(self, model: str | None = None, api_key: str | None = None):
        if not (model and api_key):
            raise ProviderNotConfigured("CERROS_MODEL and ANTHROPIC_API_KEY are required for the API provider")
        import anthropic  # lazy: the runtime works without this package
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(self, system: str, messages: list[dict]) -> str:
        r = self._client.messages.create(model=self._model, max_tokens=4000, system=system, messages=messages)
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")


def from_env(env: dict | None = None) -> Provider:
    """Pick the provider from environment variables (see .env.example)."""
    import os
    env = os.environ if env is None else env
    kind = env.get("CERROS_PROVIDER", "claude_code")
    model = env.get("CERROS_MODEL") or None
    if kind == "echo":
        return EchoProvider()
    if kind == "claude_code":
        return ClaudeCodeProvider(model=model)
    if kind == "anthropic_api":
        return AnthropicAPIProvider(model=model, api_key=env.get("ANTHROPIC_API_KEY"))
    raise ProviderNotConfigured(f"Unknown CERROS_PROVIDER: {kind}")
