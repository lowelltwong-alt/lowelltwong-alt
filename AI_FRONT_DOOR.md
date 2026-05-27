# AI Front Door — lowelltwong-alt Profile

This is the AI entrypoint for the public `lowelltwong-alt` GitHub profile.

The profile README is optimized for human scanning. This file is optimized for AI routing.

Use this file to determine:

- what the public repos do;
- which repo owns which architectural concern;
- which table of contents or front door to read next;
- what is flagship versus supporting;
- how to avoid inventing authority;
- where future update instructions live.

---

## Required read order for AI systems

```text
1. README.md
2. AI_FRONT_DOOR.md
3. ai/AI_PORTFOLIO_TOC.md
4. PUBLIC_REPO_MAP.md
5. registry/profile-repo-routing-registry.json
6. target repo README / AI front door / governance docs
```

For maintenance or future updates, continue to:

```text
ai/AI_UPDATE_INSTRUCTIONS.md
AGENTS.md
```

---

## Authority boundary

This profile repo is a **router**, not the canonical source for every project.

| Surface | Role |
|---|---|
| `README.md` | Human landing page and professional signal surface. |
| `AI_FRONT_DOOR.md` | AI entrypoint and routing index. |
| `ai/AI_PORTFOLIO_TOC.md` | AI-readable explanation of repo families and what makes them distinct. |
| `ai/BUILD_PHILOSOPHY.md` | How to understand the architecture style and design grammar. |
| `PUBLIC_REPO_MAP.md` | Public repository inventory. |
| `registry/profile-repo-routing-registry.json` | Machine-readable route map. |
| Target repo files | Canonical authority for that target repo. |

Do not treat profile-level descriptions as canon when a target repo has a more specific README, registry, governance doc, schema, or AI front door.

---

## Top-level routing

| Intent | Route |
|---|---|
| Understand the public portfolio | `README.md` → `PUBLIC_REPO_MAP.md` |
| Understand how Lowell builds systems | `ai/BUILD_PHILOSOPHY.md` |
| Understand repo families and differences | `ai/AI_PORTFOLIO_TOC.md` |
| Analyze LawFirm OS | `LawFirm-os-semantic-substrate/registry/ai-front-door-registry.json` |
| Analyze Logos AI | `logos-fractal-theological-architecture/README.md` |
| Analyze Noesis-style routing | This profile repo: `AI_FRONT_DOOR.md`, `PUBLIC_REPO_MAP.md`, routing registry |
| Analyze AIRCA / LAIRCA | `airca-fractal-decision-architecture/README.md`, then Logos for theological/source-architecture context |
| Update the profile package | `ai/AI_UPDATE_INSTRUCTIONS.md` and `AGENTS.md` |

---

## Flagship versus supporting

| Classification | Repos / systems |
|---|---|
| **Flagship** | LawFirm OS, anchored by `LawFirm-os-semantic-substrate`. |
| **Primary source architecture** | Logos AI, anchored by `logos-fractal-theological-architecture`. |
| **Profile-level AI router** | Noesis-style routing in the `lowelltwong-alt` profile repo. |
| **Supporting decision architecture** | AIRCA / LAIRCA via `airca-fractal-decision-architecture`; useful context, not flagship. |
| **Archive / legacy** | `lairca-logos-grounded-theological-model`. |

---

## LawFirm OS routing

For any LawFirm OS claim, start in the Semantic Substrate.

```text
LawFirm-os-semantic-substrate/registry/ai-front-door-registry.json
-> LawFirm-os-semantic-substrate/AI_TABLE_OF_CONTENTS.md
-> LawFirm-os-semantic-substrate/governance/CROSS_REPO_MAP.md
-> LawFirm-os-semantic-substrate/ENDPOINTS_AND_COMMANDS.md
-> target sibling repo
```

LawFirm OS repo roles:

| Plane | Repo | Role |
|---|---|---|
| Control | `LawFirm-os-semantic-substrate` | Canonical schemas, registries, governance, route/event authority, roadmap, endpoint maps. |
| Execution | `LawFirm-os-orchestrator` | Contract-locked orchestration and evidence packet generation. |
| Evidence | `LawFirm-os-exceptions-lake-runtime` | Append-only runtime records and audit evidence. |
| Legal knowledge | `LawFirm-os-legal-knowledge-runtime` | Synthetic legal ingestion, retrieval planning, Legal Context Bundle assembly. |
| Skills / trust | `LawFirm-os-skills-registry` | Skill discovery, quarantine, scanning, grading, approval gates, and trust records. |

---

## Logos / Noesis / AIRCA routing

| System | What it means here | Route |
|---|---|---|
| **Logos AI** | Theological / ultimate-frame source architecture and Logos-grounded governance. | `logos-fractal-theological-architecture` |
| **Noesis AI** | Portfolio-level intelligence router: helps AI know which repo to inspect and why. | This profile repo, especially `AI_FRONT_DOOR.md` and `ai/AI_PORTFOLIO_TOC.md` |
| **AIRCA** | Supporting decision architecture: Architect, Inform, Rank, Commit, Act. | `airca-fractal-decision-architecture` |
| **LAIRCA** | Logos-grounded Christian instantiation context. | Logos repo first; LAIRCA archive only for legacy/attribution context. |

No separate public Noesis repo is assumed here. If one is created later, add it to the registry and repo map.

---

## Claim discipline

Use these labels when answering from this profile:

| Label | Meaning |
|---|---|
| **Confirmed** | Directly supported by current repo files, public repo metadata, or inspected source text. |
| **Inferred** | Logically derived from confirmed structure, but not directly stated. |
| **Assumed** | A working assumption used to proceed. |
| **Unknown** | Not available from current public evidence. |

Do not invent:

- repo names;
- endpoint IDs;
- schemas;
- route IDs;
- event classes;
- canonical registries;
- production-readiness claims;
- private repo details;
- authority boundaries not stated in the target repo.

---

## Maintenance note

Housekeeping and future-update instructions intentionally live outside the human landing page.

Use:

```text
ai/AI_UPDATE_INSTRUCTIONS.md
AGENTS.md
```

Do not add long maintenance checklists to `README.md`.
