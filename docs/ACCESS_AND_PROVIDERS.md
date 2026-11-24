# Access model and model providers

**Decision (2026-11-24, functional owner):** in the personal-computer phase, every user signs in with their own Claude account. There is no budget yet; expected use is about 5 users, occasionally; scalability matters.

## Why per-user sign-in
Claude Code's legal and compliance page (https://code.claude.com/docs/en/legal-and-compliance) states that each end user must authenticate with their own API key, Claude plan credentials or cloud-provider credential. It also says third-party developers may not route requests through Free, Pro, Max or Ultra plan credentials on behalf of their users. Running Cerros AI on one computer and letting several people use it through one person's plan is therefore not allowed.

## How it works now
- Each person installs Claude Code on their own computer and signs in once (`claude` → `/login`).
- `ClaudeCodeProvider` calls `claude -p` with Cerros AI's composed instructions as the system prompt. It runs in an empty temporary folder with `--permission-mode dontAsk`, so the model answers but cannot read or change files.
- It does **not** use `--bare`: bare mode ignores the subscription login and requires an API key.
- Usage counts against each person's own plan. As of November 2026 the Claude Help Center says Agent SDK and `claude -p` usage draws from the plan's usage limits. Anthropic announced and then paused a change to this in June 2026, so check https://support.claude.com/en/articles/15036540 before the pilot.
- Cerros AI never stores, receives or forwards credentials.

## Known limitation
Without `--bare`, `claude -p` still loads the user's own Claude Code configuration (user-level CLAUDE.md, hooks, MCP servers). The composed system prompt replaces Claude Code's default prompt, but personal settings can still influence answers. Users should not add personal Claude Code settings that conflict with Cerros AI, or a later phase can move to the API provider, where the system prompt is the only instruction.

## Scaling later
The provider is one small class behind `Provider.complete(system, messages)`. Moving to an API key, an institutional Claude plan or a cloud provider (Bedrock, Vertex, Foundry) is a configuration change (`CERROS_PROVIDER`). The canonical layer, runtime rules and tests do not change. A shared server for many users requires one of those options, not personal plans.
