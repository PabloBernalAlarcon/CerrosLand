# Access model and model providers

**Decision (2026-11-24, functional owner):** in the personal-computer phase, every user signs in with their own Claude account. There is no budget yet; expected use is about 5 users, occasionally; scalability matters.

## Why per-user sign-in
Claude Code's legal and compliance page (https://code.claude.com/docs/en/legal-and-compliance) states that each end user must authenticate with their own API key, Claude plan credentials or cloud-provider credential. It also says third-party developers may not route requests through Free, Pro, Max or Ultra plan credentials on behalf of their users. Running Cerros AI on one computer and letting several people use it through one person's plan is therefore not allowed.

## How it works now
- Each person installs Claude Code on their own computer and signs in once (`claude` → `/login`).
- `python -m cerros_runtime doctor` checks the sign-in with `claude auth status` and shows only whether it succeeded and which method was used (`claude.ai` = your own Claude plan). It never reads or keeps the email or any credential.
- `ClaudeCodeProvider` calls `claude -p` with these options (reference: https://code.claude.com/docs/en/cli-reference):
  - `--system-prompt-file`: Cerros AI's composed instructions replace Claude Code's default prompt. A file avoids Windows command-line length limits and quoting problems; it is written in UTF-8 to a temporary folder and deleted after the call.
  - `--safe-mode`: the user's personal CLAUDE.md, skills, plugins, hooks, MCP servers and auto memory do not load, while sign-in and model selection work normally.
  - `--tools ""` and `--disallowedTools "mcp__*"`: no tools, so the model can only answer.
  - `--no-session-persistence`: Claude Code does not save the conversation to disk.
  - not `--bare`: bare mode ignores the subscription login and requires an API key.
- Verified on Claude Code 2.1.332: all options are accepted, and an unsigned-in machine returns a clear error that Cerros AI shows to the user.
- Usage counts against each person's own plan. As of November 2026 the Claude Help Center says Agent SDK and `claude -p` usage draws from the plan's usage limits. Anthropic announced and then paused a change to this in June 2026, so check https://support.claude.com/en/articles/15036540 before the pilot.
- Cerros AI never stores, receives or forwards credentials.

## Requirement
A recent Claude Code version (`--safe-mode` and `claude auth status` must exist). If Claude Code reports an unknown option, run `claude update`.

## Scaling later
The provider is one small class behind `Provider.complete(system, messages)`. Moving to an API key, an institutional Claude plan or a cloud provider (Bedrock, Vertex, Foundry) is a configuration change (`CERROS_PROVIDER`). The canonical layer, runtime rules and tests do not change. A shared server for many users requires one of those options, not personal plans.
