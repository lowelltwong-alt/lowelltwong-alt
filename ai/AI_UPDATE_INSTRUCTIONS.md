# AI Update Instructions

This file is intentionally separate from the human-facing `README.md`.

Use it when an AI assistant, coding agent, or maintainer needs to update the profile repo.

---

## Update principle

The README should stay polished, concise, and high-signal for humans.

Maintenance logic belongs here, not in the README.

---

## Files in this profile package

| File | Purpose |
|---|---|
| `README.md` | Human-facing landing page. Keep concise and visually clean. |
| `AI_FRONT_DOOR.md` | AI routing entrypoint. |
| `ai/AI_PORTFOLIO_TOC.md` | AI-readable explanation of repo families and differences. |
| `ai/BUILD_PHILOSOPHY.md` | Explains the design grammar and how Lowell builds systems. |
| `PUBLIC_REPO_MAP.md` | Public repo inventory. |
| `registry/profile-repo-routing-registry.json` | Machine-readable route registry. |
| `AGENTS.md` | Standing coding-agent instructions. |
| `ai/AI_UPDATE_INSTRUCTIONS.md` | This maintenance file. |

---

## Before updating

Inspect:

```text
README.md
AI_FRONT_DOOR.md
ai/AI_PORTFOLIO_TOC.md
ai/BUILD_PHILOSOPHY.md
PUBLIC_REPO_MAP.md
registry/profile-repo-routing-registry.json
AGENTS.md
```

Then inspect the target repo being referenced.

For LawFirm OS, inspect:

```text
LawFirm-os-semantic-substrate/registry/ai-front-door-registry.json
LawFirm-os-semantic-substrate/AI_TABLE_OF_CONTENTS.md
LawFirm-os-semantic-substrate/governance/CROSS_REPO_MAP.md
LawFirm-os-semantic-substrate/ENDPOINTS_AND_COMMANDS.md
```

For Logos, inspect:

```text
logos-fractal-theological-architecture/README.md
logos-fractal-theological-architecture/docs/governance/
logos-fractal-theological-architecture/docs/roadmap/
```

For AIRCA, inspect:

```text
airca-fractal-decision-architecture/README.md
```

---

## README rules

Do:

- keep the README readable in under one minute;
- preserve clean tables;
- make the flagship architecture obvious;
- include only a small AI entrypoint section;
- emphasize architecture, governance, trust, and systems thinking;
- avoid long update checklists.

Do not:

- add maintenance instructions to README;
- over-explain internal housekeeping;
- call AIRCA the flagship;
- claim production readiness without source support;
- expose private repos;
- turn the README into a full table of contents;
- write as if aimed overtly at employers or recruiters.

The README should signal depth without saying what audience it is trying to impress.

---

## Repo classification rules

| Repo/system | Classification |
|---|---|
| `LawFirm-os-semantic-substrate` | Flagship LawFirm OS control plane. |
| LawFirm OS sibling repos | Active public architecture planes. |
| `logos-fractal-theological-architecture` | Primary source architecture for Logos AI. |
| `lowelltwong-alt` profile repo | Noesis-style profile router. |
| `airca-fractal-decision-architecture` | Supporting public draft, not flagship. |
| `lairca-logos-grounded-theological-model` | Archive / legacy. |

---

## Synchronization checklist

When routing changes, update:

```text
README.md
AI_FRONT_DOOR.md
ai/AI_PORTFOLIO_TOC.md
PUBLIC_REPO_MAP.md
registry/profile-repo-routing-registry.json
```

When maintenance instructions change, update:

```text
ai/AI_UPDATE_INSTRUCTIONS.md
AGENTS.md
```

When architecture interpretation changes, update:

```text
ai/BUILD_PHILOSOPHY.md
AI_FRONT_DOOR.md
```

---

## Validation checklist

At minimum:

```bash
python -m json.tool registry/profile-repo-routing-registry.json > /tmp/profile-repo-routing-registry.validated.json
```

Also check:

| Check | Pass condition |
|---|---|
| README remains human-clean | No long maintenance checklist in README. |
| AIRCA classification | Supporting, not flagship. |
| LawFirm OS authority | Routes through Semantic Substrate. |
| Logos authority | Routes through Logos repo. |
| Noesis status | Profile-level router unless a public Noesis repo exists. |
| Private repo safety | No private repo details exposed. |
| Markdown links | Relative links match actual files. |
| JSON registry | Parses successfully. |

---

## Required final report format for future AI

```text
Files changed:
Sources inspected:
Checks run:
Tests not run:
Confirmed:
Inferred:
Assumed:
Unknown:
Remaining risks:
```
