# Cerros AI — Handoff Final al Ingeniero v1.0

## Start here
1. `Handoff_Final_Ingeniero_Cerros_AI_v1.0.docx`
2. `Especificacion_Maestra_Cerros_AI_v1.0.docx`
3. `NORMALIZACION_PRE_V1/cerros_component_contract_v1.schema.json`
4. `NORMALIZACION_PRE_V1/component_readiness_registry_v1.yaml`
5. `NORMALIZACION_PRE_V1/master_dependency_map_v1.yaml`
6. `NORMALIZACION_PRE_V1/component_specs_normalized/`

## Golden rules
- Technology adapts to Cerros AI; do not redesign Cerros AI for platform convenience.
- Execute only `ORCHESTRATION` edges with `executable=true`.
- Never invoke `DISABLED` or `GAP`.
- Never promote `PROVISIONAL` to `ACTIVE` without institutional approval.
- Keep Knowledge Packs versioned and separate from component logic.
- Human authority is a hard architectural boundary.
- `BLOCKED_BY_GOVERNANCE` and `BLOCKED_BY_KNOWLEDGE` are real blockers.
- Convert `functional_acceptance_criteria` into technical tests.

## Inventory
- 39 functional components
- 27 ACTIVE
- 11 PROVISIONAL
- 1 DISABLED
- 1 GAP
- 16 Knowledge nodes
- 11 human-authority nodes

## Do not infer
Missing source, policy, threshold, format, approval or data-governance decisions must return to the institution.
