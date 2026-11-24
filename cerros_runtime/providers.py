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
    Not `--bare`: bare mode ignores the subscription login and needs an API key.
    The call runs in an empty temporary folder with tools denied, so the model only
    answers; it cannot read or change files.
    """
    model: str | None = None
    timeout_s: int = 300
    name: str = "claude_code"
    _last_cost: float | None = field(default=None, repr=False)

    @staticmethod
    def available() -> bool:
        return shutil.which("claude") is not None

    def _cmd(self, system: str) -> list[str]:
        cmd = ["claude", "-p", "--output-format", "json", "--system-prompt", system,
               "--permission-mode", "dontAsk"]
        if self.model:
            cmd += ["--model", self.model]
        return cmd

    def complete(self, system: str, messages: list[dict]) -> str:
        if not self.available():
            raise ProviderNotConfigured("Claude Code is not installed. Install it, run `claude`, then `/login` "
                                        "with your own Claude account.")
        with tempfile.TemporaryDirectory(prefix="cerros_") as cwd:
            try:
                r = subprocess.run(self._cmd(system), input=_render(messages), capture_output=True, text=True,
                                   cwd=cwd, timeout=self.timeout_s)
            except subprocess.TimeoutExpired as e:
                raise ProviderError(f"Claude Code did not answer within {self.timeout_s}s") from e
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError as e:
            raise ProviderError(f"Unexpected output from Claude Code: {r.stdout[:300] or r.stderr[:300]}") from e
        if data.get("is_error") or r.returncode != 0:
            raise ProviderError(f"Claude Code error: {data.get('result') or r.stderr[:300]}")
        self._last_cost = data.get("total_cost_usd")
        return data.get("result", "")


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
