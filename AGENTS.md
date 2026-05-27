# AGENTS.md — Profile Repo Instructions

This repo is the public profile and AI routing surface for `lowelltwong-alt`.

Do not treat it as canonical authority for all target repos.

---

## Read first

```text
README.md
AI_FRONT_DOOR.md
ai/AI_PORTFOLIO_TOC.md
ai/BUILD_PHILOSOPHY.md
PUBLIC_REPO_MAP.md
registry/profile-repo-routing-registry.json
ai/AI_UPDATE_INSTRUCTIONS.md
```

---

## Editing rules

- Keep the README clean, polished, and human-facing.
- Keep housekeeping in `ai/AI_UPDATE_INSTRUCTIONS.md` and this file.
- Keep AI routing in `AI_FRONT_DOOR.md`, `ai/AI_PORTFOLIO_TOC.md`, and the registry.
- Do not call AIRCA the flagship.
- Do not invent repo names, schemas, endpoints, route IDs, event classes, or policy IDs.
- Do not expose private repos.
- Do not claim production readiness unless a target repo explicitly supports it.
- Defer LawFirm OS authority to `LawFirm-os-semantic-substrate`.
- Defer Logos/theological source authority to `logos-fractal-theological-architecture`.

---

## Authority routes

| Topic | Route |
|---|---|
| Public profile summary | `README.md` |
| AI portfolio routing | `AI_FRONT_DOOR.md` |
| Repo semantics | `ai/AI_PORTFOLIO_TOC.md` |
| Build philosophy | `ai/BUILD_PHILOSOPHY.md` |
| Public repo inventory | `PUBLIC_REPO_MAP.md` |
| Machine-readable routing | `registry/profile-repo-routing-registry.json` |
| Maintenance | `ai/AI_UPDATE_INSTRUCTIONS.md` |
| LawFirm OS | `LawFirm-os-semantic-substrate` |
| Logos AI | `logos-fractal-theological-architecture` |
| AIRCA | `airca-fractal-decision-architecture`, supporting only |

---

## Minimum validation

```bash
python -m json.tool registry/profile-repo-routing-registry.json > /tmp/profile-repo-routing-registry.validated.json
```

Report tests run and tests not run.
