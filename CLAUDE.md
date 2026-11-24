# Working in this repository

This is the runtime for Cerros AI v1.0, a frozen institutional architecture. Read `README.md` and `docs/ISSUE_REGISTER_v1.md` before changing anything.

## Hard rules
- Never edit `spec/delivered/`. It is the delivery exactly as received.
- Never change the meaning of anything in `spec/working/` or `knowledge/` without an approved decision recorded in `docs/ISSUE_REGISTER_v1.md` (decision log). Representation-only fixes still need a log entry.
- Do not fill institutional gaps with general knowledge (CORE-01). Missing sources, thresholds, formats or approvals go to "Open questions for the institution" in the register.
- Never invoke DISABLED components or GAP nodes. Never promote PROVISIONAL to ACTIVE.
- Runtime rules may only restrict what the dependency map allows (see `spec/working/runtime_policy_v1.yaml`).
- Fictitious data only. Never commit real personal data, `.env` files, API keys or the contents of `knowledge/sources/`.
- Each user authenticates with their own Claude account. Never add code that stores, forwards or shares credentials.

## Before every commit
```bash
python3 -m pytest -q
python3 tools/validate_specs.py spec/working
python3 tools/validate_phase0.py spec/working
python3 tools/build_edge_behavior.py spec/working   # must report "edges with zero or multiple rules: none"
```
