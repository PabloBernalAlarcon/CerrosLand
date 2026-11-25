# Cerros AI v1.0 — Implementation issue register (Phase 0 — CLOSED 2026-11-24)

**Date:** 2026-11-24 · **Scope:** all canonical artifacts (manifest, contract, schema, registry, dependency map, migration report, 39 component specs) · **Method:** automated cross-checks + manual reading. Nothing has been corrected; every item below is reported for decision (CORE-01, CORE-06; Handoff §3).

## Decision log
| Date | Item | Decision | Applied |
|---|---|---|---|
| 2026-11-24 | C4 + C3 (FLUFFY) + C2 (notes) | Restore rule titles, per-component validation states and source-hierarchy notes from the v0.1 DOCX fichas | Yes — specs v1.0.1 (working copy); rule texts unchanged; schema still passes 39/39 |
| 2026-11-24 | C3 (PERSONA + INSTITUCIONAL, 18 components) | Use the general definitions from Continuidad v0.11 §9.4 | Yes — each state carries its source |
| 2026-11-24 | E1 Knowledge layer | No v1 exists; the v0.1 KP registry + 16 manifests are the working Knowledge layer | Yes — names, statuses and authority classes match the v1 manifest for all 16 packs |
| 2026-11-24 | A1 Unconditional TRANSFER_CONTROL | Option A — global rule RT-01: transfer only after source is VALIDADO and the user requests/accepts the next step | Yes — `runtime_policy_v1.yaml` (map unchanged) |
| 2026-11-24 | A2 Conditional edges without condition | RT-01 covers conditional handoffs (map note = reason shown); RT-02: conditional internal calls ask the user first | Yes — delegated by user |
| 2026-11-24 | A3 "Derivar" | RT-03: without an executable edge, stop and recommend; nothing is transferred | Yes — delegated by user |
| 2026-11-24 | A4 Edge direction | RT-04: QUALITY read reviewer→reviewed (E017, E018, E021 normalized in loader); RT-05: E042–E044 treated as dormant, TX-P01 review offered by the product under RT-03 (reversible) | Yes — delegated by user; map author unavailable |
| 2026-11-24 | Overlap check | All 42 executable edges are governed by exactly one rule: RT-01 (14), AUTO (20), RT-02 (5), RT-05 (3) | `edge_behavior_v1.yaml` |
| 2026-11-24 | C1 KP dependencies | Filled in 37 specs from the map (FL-C02 and SP-C01 have none) | Yes — specs |
| 2026-11-24 | B1 Mandatory provisional/blocked callees | RT-06: effective status inherits from mandatory callees; registry untouched; promotion stays institutional | Yes — runtime policy |
| 2026-11-24 | B2/B3 Blocking criteria | RT-07: statuses honored as written; dev/pilot with fictitious data only; criteria go to the institution | Yes — runtime policy |
| 2026-11-24 | C5 Knowledge inside rules | Kept in rules for v1; listed as v1.1 candidates to move into Knowledge Packs | Logged |
| 2026-11-24 | C6 Spec dependencies without edges | Informational only; RT-03 covers "derivar"; no edges added | Logged |
| 2026-11-24 | C7 Domain spellings | RT-08: family taken from the manifest | Yes — runtime policy |
| 2026-11-24 | D1 HUM-FAMILIA | RT-09: family commitments stay PENDING until the teacher records acceptance | Yes — runtime policy |
| 2026-11-24 | **Phase 0 closed** | Schema 39/39 · cross-check 0 errors · every executable edge governed by exactly one rule · 13 remaining spec warnings all covered by RT-01/02/03/05 | — |
| 2026-11-24 | **Phase 1 skeleton** | `cerros_runtime` package: loader + schema validation, guards (RT-06), Knowledge layer by dependency, orchestration session (RT-01…RT-05), provider-neutral instruction composer. 21/21 structural tests pass. Pilot slice FL-C02 + SP-C01 composes cleanly (ACTIVE, no blocked steps). | Built |
| 2026-11-24 | Access model and repository | Each user signs in with their own Claude account (ClaudeCodeProvider, `claude -p`); no shared credentials; API/institutional provider later by configuration. Code moved to private repo `PabloBernalAlarcon/CerrosLand` with CI, CODEOWNERS and a checksum guard on `spec/delivered/` | `docs/ACCESS_AND_PROVIDERS.md` |
| 2026-11-25 | Windows support and personal-settings limitation | Claude Code provider passes instructions in a UTF-8 file (`--system-prompt-file`), runs with `--safe-mode`, no tools and no session persistence; `doctor` checks sign-in via `claude auth status`. Removes the limitation that personal Claude Code settings could influence answers | Code + `docs/ACCESS_AND_PROVIDERS.md` |

**Working-copy note:** the delivered files are kept untouched in `spec/delivered/` (checked by `tools/check_delivered.py` in CI). The working layer is `spec/working/`; approved restorations are recorded in `docs/restorations_v1.0.1.yaml`. Only four fields changed in the specs: `rules` (now `{title, text}`), `validation_states`, `source_hierarchy` and `knowledge_dependencies`.

## Update — Drive folder review (2026-11-24)
- The delivery folder `Entrega_Final_Cerros_AI_v1.0_Ingeniero` on Drive is identical to the files validated above (sizes and bytes match; the v1 specs inside `Paquete_Handoff_Cerros_AI_v0.15.zip` are byte-identical).
- The development archive (112 files) contains the v0.1 DOCX fichas, which resolve **C4** and most of **C2/C3** without inference (see below).
- **New finding E1 — the delivery package has no Knowledge layer.** Master spec §21.1 lists "Knowledge Pack registry y manifests" in the engineer's reading order, but `Entrega_Final…` contains neither the registry, the 16 KP manifests, nor any source document. They exist only in the archive: `knowledge_pack_registry_v0.1.yaml` + `KP-001…KP-016_manifest_v0.1.yaml` (inside the v0.15 package) and the Handbook / Plan Estratégico / KP-016 PDFs (in `01_FUENTES_BASE`). **Decision needed:** confirm the v0.1 registry and manifests are the current Knowledge layer, or provide a v1 version.

## What passed

- All 39 specs validate against `cerros_component_contract_v1.schema.json` (0 errors).
- Type, traits and the four status fields of every component agree across specs, registry, manifest and map.
- Counts match the manifest (39 components, 27/11/1, 1 GAP, 16 KP, 11 HUM, 67 nodes, 156 edges).
- Every edge's class matches its semantics; only ORCHESTRATION edges are executable (42 of 156); no executable edge touches FL-D04 or GAP-C01; E020 is correctly dormant.
- The master spec's "Handoffs/autoridad" column matches the map for all 39 components.

---

## A. Orchestration semantics — must be decided before the router is built (Handoff Phase 3)

### A1. Unconditional TRANSFER_CONTROL edges vs. gates described in the specs — *RESOLVED: RT-01 (2026-11-24)*
Eleven executable edges are marked `conditional: false`. A literal router would always hand control to the target, but the notes and specs describe a gate (validation, sufficiency, or a user intent):

| Edge | From → To | Gate stated in note/spec |
|---|---|---|
| E001 | FL-P01 → FL-P02 | "Arquitectura anual **validada**" |
| E002 | FL-P02 → FL-P03 | "Unidad **validada**" |
| E022 | TX-D02 → FL-D02 | "**Si** la práctica se convierte en evaluación formal" |
| E033 | WF-P01 → WF-P02 | "PPI **puede** alimentar PIAE" |
| E034 | PR-S01 → PR-S02 | PR-S01 spec: "**cuando** se requiere formalizar ajuste" |
| E035 | PR-S02 → PR-S04 | "Ajustes **implementados**" (implies time passes) |
| E047 | IN-S01 → IN-S02 | IN-S01 completion: "Caso **listo o no listo** para clasificación" |
| E049 | IN-S02 → IN-S03 | IN-S02 spec: "Redacción de reporte **después de validación**" |
| E055 | IN-S04 → WF-I04 | WF-I04: no definitive report if IN-S04 = NO VALIDADO |
| E058 | FL-P03 → FL-D01 | "Planificación cerrada **puede** producir guía" |
| E059 | FL-P03 → FL-D02 | "Planificación cerrada **puede** producir evaluación" |

**Options:** (a) global runtime rule: a TRANSFER_CONTROL edge fires only after the source's `completion_condition` (including human validation) is met **and** the user asks for the next step; (b) mark each edge conditional and write its condition. Option (a) changes no artifact but is a semantic decision the institution must confirm.

### A2. Conditional executable edges with no condition defined anywhere — *RESOLVED: RT-01 + RT-02 (2026-11-24)*
E014 (WF-A01→PR-S02), E023 (FL-C01→FL-C02), E031/E032 (WF-P01→PR-S03/PR-S02), E042–E044 (TX-P01→FL-P03/FL-D01/FL-D02), E048 (IN-S01→TX-I01), E051 (IN-S03→TX-I01), E052 (TX-I01→WF-P01), E060 (FL-P02→WF-A01). The map note gives a hint, but no spec has `handoff_conditions` for them (38 of 39 specs have that field empty). **Needed:** the condition text for each edge.

### A3. Handoffs in specs that have no edge in the map — *RESOLVED: RT-03 (2026-11-24)*
- **FL-P03** `handoff_conditions` names five targets with no FL-P03 → target ORCHESTRATION edge: FL-P01, FL-P02, TX-P01, PR-S02, WF-A01. Under the execution rule all five would be blocked.
- "Derivar a PLANIFICA" (FL-D01 R-01), "derivar a FL-D02" (TX-D02), "remitir a autoridad/comité" (WF-I04) use the same verb.

**Question:** does "derivar" mean TRANSFER_CONTROL (needs an edge) or *stop and tell the user where to go* (a redirect that transfers nothing)? If the latter, the runtime can implement it without edges, but the term needs a defined meaning.

### A4. Edge direction — *RESOLVED: RT-04 + RT-05 (2026-11-24)*
- QUALITY edges use both directions: reviewer→reviewed (E005–E007, from TX-A02) and reviewed→reviewer (E017, E018, E021).
- E042–E044 make **TX-P01 transfer control to** FL-P03, FL-D01 and FL-D02. TX-P01's spec describes a reviewer that proposes, never approves, and must not redesign (R-TXP01-03, authoritative_sources limit). This looks like the same inversion (the product should call TX-P01).

**Needed:** canonical direction for QUALITY edges, and confirmation of E042–E044.

---

## B. Readiness and deployment policy

### B1. Mandatory dependencies on PROVISIONAL or blocked components
Continuity doc v0.9: *"Los componentes PROVISIONALES/PENDIENTES no deben convertirse en dependencias obligatorias de producción sin decisión posterior."* Sixteen non-conditional executable edges do exactly that (13 of them start from an ACTIVE component):

- **TX-I02 (PROVISIONAL)** is a mandatory call from WF-I01, IN-S03, WF-I02, WF-I04 and IN-S04 (E046, E050, E054, E057, E056) — almost the whole INSTITUCIONAL family depends on it.
- **TX-I03 (PROVISIONAL)** ← WF-I01 (E045).
- **TX-D02 (PROVISIONAL)** ← FL-D01 (E016) and WF-A01 (E011).
- **FL-D02 (PROVISIONAL)** ← WF-A01 (E012, final verification), FL-P03 (E059), TX-D02 (E022).
- **IN-S02 (PROVISIONAL)** ← IN-S01 (E047); **WF-P02 (PROVISIONAL)** ← WF-P01 (E033).
- **Blocked targets:** FL-P02 → FL-P03 (E002, BLOCKED_BY_KNOWLEDGE); WF-A01 and FL-D02 → FL-D03 (E013, E019, BLOCKED_BY_KNOWLEDGE).

**Options:** (a) a caller inherits the most restrictive status of its mandatory callees at runtime; (b) the institution promotes specific micro-skills (TX-I02 is the obvious candidate: its only KP, KP-001, is complete); (c) the caller degrades or stops at that step.

### B2. Criterion for BLOCKED_BY_KNOWLEDGE
36 of 39 components depend on at least one PARCIAL/INCOMPLETO Knowledge Pack, but only FL-P03 and FL-D03 are BLOCKED_BY_KNOWLEDGE. PR-S05 (KP-013 INCOMPLETO) and WF-I03 (KP-012 INCOMPLETO) are PILOT_OR_BLOCKED. Handoff §8: *"Un pack incompleto bloquea el despliegue fiel de sus consumidores."* **Needed:** the rule that decides when a partial pack blocks.

Components whose knowledge is fully available today: **FL-C02, SP-C01** (no KP), **TX-I02** (KP-001).

### B3. Criterion for BLOCKED_BY_GOVERNANCE
Only WF-C01 is governance-blocked. IN-S01–S03 (*"Muy sensible: menores, convivencia"*), PR-S03 (*"Altamente sensible: salud, clínica"*), PR-S06/S07 and WF-P03 are PILOT_OR_BLOCKED. If the reason is that WF-C01's primary user is a student, that rule should be stated.

---

## C. Spec content gaps (likely normalization artifacts)

### C1. `knowledge_dependencies` empty in all 39 specs
The map, manifest and master spec give KP dependencies for 37 components. Handoff §2 ranks component specs (3) **above** registry (4) and map (5), so read literally, the empty spec field wins and no KP would load. **Proposal:** fill the spec field from the map (mechanical, no content change) after approval.

### C2. `source_hierarchy` empty in 38 specs — *partly resolved (4 restored); rest stays "unresolved → surface tension"*
Only FL-P03 has one. The v0.1 DOCX fichas carry prose hierarchy notes that the YAML dropped: FL-D01 (*"No existe tabla formal exhaustiva de prelación…"*), FL-P04 (open precedence risk between ALTA/MEDIA/BAJA), WF-A01 (contradictions must be escalated), WF-P03 (explicit five-level hierarchy; the Ficha Rápida must not prevail over Matriz/Handbook). These are in `v1_restorations_PROPOSED.yaml`. Elsewhere the field stays empty → "hierarchy unresolved → surface tension" (CORE-02).

### C3. `validation_states` — *RESOLVED (2026-11-24)*
- **FLUFFY (21 components):** every v0.1 ficha has a §13 table defining VALIDADO / PRELIMINAR / NO VALIDADO *for that component*. The YAML export dropped it. Restorable verbatim (see proposal file).
- **PERSONA and INSTITUCIONAL (18 components):** the v0.1 fichas never had that table, yet IN-S04, WF-I04 and WF-P03 decide on NO VALIDADO. **Decision needed:** apply the Continuity doc §9.4 definitions as defaults, or define per component.

### C4. Rules whose subject was lost — *RESOLVED (2026-11-24)*
The v0.1 rule tables have three columns (ID · **Regla** · Especificación); the YAML kept only the third. All 39 fichas were parsed; every rule text matches the v1 YAML exactly (0 differences), so the titles can be restored without inference:

| Rule | Restored title | Text |
|---|---|---|
| FL-P03 R-03 / R-04 / R-05 | **Grade / Subject / Length** | "Debe ser confirmado." / "Nunca se infiere." / "Solo 35 o 40 minutos…" |
| FL-P03 R-08 / R-19 | **Calidad del objetivo / Datos administrativos** | |
| FL-P04 R-04 / R-05 / R-06 | **ALTA / MEDIA / BAJA** | the three threshold sets |
| FL-D01 R-05 / R-06 | **Estructura temática / Explicación + lectura** | |
| FL-D03 R-04 | **Distractores** | |
| IN-S04 R-06 | **Resultado** | (my earlier guess, "intervention/factor", was wrong) |
| TX-I03 R-02 / R-03 | **Responsable / Fecha** | |
| WF-I01 R-04 | **Metas** | |
| WF-C01 R-06 | **Pregunta** | |
| WF-I04 R-03 | **Conclusión** | |

All 284 rule titles for the 39 components are in `v1_restorations_PROPOSED.yaml`.

**Origin of the loss:** it did not happen in the pre-v1 normalization. The v0.1 YAML files already lack the titles, states and notes; the loss occurred when the v0.1 DOCX fichas were exported to YAML, and normalization inherited it.

### C5. Versionable knowledge written into component rules
Handoff §3 forbids hard-coding versionable knowledge in component logic. These values sit in `rules`:
FL-P04 thresholds (R-04–R-06) · FL-D03 34/43/23 distribution and content/context categories (R-09, R-10) · FL-P03 Length 35/40 and max 2 objectives · WF-I01 mandatory subject list · WF-I04 2–4 recommendations · IN-S04 max 3 factors (and the 4.5 threshold in open issues) · WF-A01 3+3+1 model.
**Options:** keep them in the frozen v1 rules and version them with the component, or move them to the corresponding KP / product spec.

### C6. Dependencies listed in specs with no edge in the map (22)
For example WF-A01 → FL-D01, WF-P02 → PR-S01/S02/S03, IN-S03 ← IN-S01, TX-A01 ↔ TX-A02, FL-P01 → FL-P04. Several are probably DATA or SUPPORT relations the map doesn't model. **Question:** is the map meant to be complete for non-executable relations?

### C7. Representation inconsistencies (no content impact)
`domain` has six spellings ("Académico", "academic", "INSTITUTIONAL", "Académico / gestión"…), `head` is free text or null, and FL-P03 uses a different style (English snake_case IDs, procedure as strings). **Default unless you object:** the runtime takes the family from the manifest and leaves spec fields untouched.

---

## D. Human authority

### D1. HUM-FAMILIA has no edges
WF-I01 reserves "Acordar metas/compromisos" and TX-I03 reserves "Aceptar responsabilidad/plazo". In a family meeting, some of those decisions belong to the family, but both components' only authority edge points to HUM-PROFESOR.

---

## Consequence for the first MVP slice
- The previously suggested slice (FL-P02, FL-D01, FL-C02, PR-S02, WF-I01) depends on provisional components: FL-D01 → TX-D02, and WF-I01 → TX-I02/TX-I03.
- The cleanest slice by status, knowledge and dependencies is **FL-C02 + SP-C01** (writing feedback / school journalism). It is ACTIVE, has no KP dependencies, has no mandatory provisional callees, and its only reserved authority is HUM-PROFESOR / HUM-EDITOR.
- Before Phase 3, decisions are needed on A1–A4. Before any data-bearing pilot, decisions are needed on B1–B3 and GOV-01.

---

## Open questions for the institution (do not block development)
1. **B2** — Criterion that decides when a partial Knowledge Pack makes a component BLOCKED_BY_KNOWLEDGE.
2. **B3** — Criterion that decides BLOCKED_BY_GOVERNANCE (why only WF-C01).
3. **B1** — Whether to promote TX-I02 (its only pack, KP-001, is complete) and other provisional micro-skills that many components depend on.
4. **GOV-01** — Data policy before any real personal data.
5. **RT-05** — Confirm the direction of E042–E044 (currently dormant).
6. **E1** — Produce a v1 Knowledge layer (registry + manifests) when ready.
7. **SP-C01 references** — SP-C01 cites the *Manual básico de redacción periodística* (Páez) and a *Guía práctica de escritura y redacción* as references, but no Knowledge Pack contains them; the pilot runs without them unless they are added.
8. **v1.1 candidates (C5)** — Move FL-P04 thresholds, FL-D03 distribution, FL-P03 Length/objective limits, WF-I01 subject list, WF-I04 2–4 recommendations, IN-S04 factor limit/4.5 threshold and WF-A01 3+3+1 into Knowledge Packs.
