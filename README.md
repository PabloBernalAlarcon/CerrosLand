# CerrosLand — Cerros AI runtime

Implementation of the **Cerros AI v1.0** architecture (Especificación Maestra v1.0 + Handoff Final al Ingeniero).
The architecture is frozen. This code loads it, checks it and enforces it; it does not redesign it.

**Status:** Phase 0 (canonical layer) closed · Phase 1 runtime skeleton built · first pilot slice: **FL-C02 + SP-C01** (writing feedback / school journalism).

## Repository layout
| Path | What it is | Who may change it |
|---|---|---|
| `spec/delivered/` | The v1.0 delivery exactly as received (YAML, JSON, DOCX). **Never edited.** | Nobody |
| `spec/working/` | Working canonical layer: delivered files + approved restorations, `runtime_policy_v1.yaml`, `edge_behavior_v1.yaml` | Functional owner (CODEOWNERS) |
| `knowledge/` | Knowledge Pack registry + 16 manifests (v0.1 — no v1 exists yet) | Functional owner |
| `knowledge/sources/` | Source documents (Handbook, Plan Estratégico…). **Kept local, never committed.** | — |
| `cerros_runtime/` | Python package: loader, guards, knowledge, orchestration, instruction composer, providers | Engineering |
| `tests/` | Structural tests (Handoff §11 + runtime policy) and provider tests | Engineering |
| `tools/` | Validators and analysis scripts | Engineering |
| `docs/` | Issue register, decision log, restorations, access model | Functional owner + engineering |

The full development archive (v0.1 fichas, matrices, historical packages) stays in Google Drive (`Cerros AI/CERROS_AI_ARCHIVO_DESARROLLO_v1.0`).

## Quick start (personal computer)
```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest -q                            # 39 tests
python3 tools/validate_specs.py spec/working    # schema + registry + map
python3 tools/validate_phase0.py spec/working   # manifest/registry/map consistency
python3 tools/build_edge_behavior.py spec/working
python3 -m cerros_runtime doctor                # is this computer ready?
```

## Pilot: FL-C02 + SP-C01
```bash
python -m cerros_runtime chat SP-C01            # school journalism (runs on FL-C02)
python -m cerros_runtime chat FL-C02            # writing feedback
python -m cerros_runtime acceptance SP-C01      # the spec's acceptance scenarios -> reports/ (not committed)
```
In the chat, paste a fictitious student text and say what review you need (level, purpose or genre).
Commands: `/estado`, `/siguiente`, `/validar` (records your human confirmation), `/nuevo`, `/ayuda`, `/salir`.
Cerros AI does not save the conversation. The acceptance runner uses two model calls per scenario
(answer + suggested verdict); you decide whether you agree with each verdict.

## Access model: everyone uses their own Claude account
Each person runs Cerros AI on their own computer and signs in to Claude Code with **their own** Claude account:
1. Install Claude Code by following the instructions for your system at https://code.claude.com/docs/en/setup (Windows, macOS or Linux).
2. Open a new terminal, run `claude`, then `/login`, and sign in with your own account. Type `/exit` to leave.
3. Copy `.env.example` to `.env` (default provider: `claude_code`).
4. Run `python -m cerros_runtime doctor`. Every line should show ✓.

On Windows, use `python` instead of `python3` in the commands above.

Cerros AI never stores, receives or shares anyone's credentials, and never routes one person's requests through another person's plan. Anthropic's terms require each end user to authenticate with their own credentials. Usage counts against each person's own plan. Cerros AI runs Claude Code with personal customizations off (`--safe-mode`) and without tools, so the model can only answer. When there is a budget, switching to an API key or an institutional plan is a configuration change (`CERROS_PROVIDER=anthropic_api`); the specs, rules and tests stay the same. See `docs/ACCESS_AND_PROVIDERS.md`.

## Runtime rules (full text: `spec/working/runtime_policy_v1.yaml`)
- **RT-01** handoffs only after the source is VALIDADO (human-confirmed) and the user asks or accepts.
- **RT-02** conditional internal calls ask first. **AUTO** unconditional calls run inside the caller's procedure.
- **RT-03** "derivar" with no edge = stop and recommend; nothing transferred.
- **RT-04** QUALITY edges read reviewer → reviewed. **RT-05** E042–E044 dormant (TX-P01 never takes control).
- **RT-06** effective status inherits from mandatory callees. **RT-07** dev/pilot with fictitious data only.
- **RT-08** family taken from the manifest. **RT-09** family commitments pending until the teacher records acceptance.

## Data rule
Fictitious cases only until the institution approves a data policy (GOV-01). Never commit real student, family or staff data.
