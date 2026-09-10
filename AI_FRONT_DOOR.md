# AI Front Door

This is the machine-navigation entrypoint for the public `lowelltwong-alt` portfolio. Start with the human summary in `README.md`, then use this file, `ai/AI_PORTFOLIO_TOC.md`, `PUBLIC_REPO_MAP.md`, and `registry/profile-repo-routing-registry.json`.

The profile is a router, not canonical authority for target-repository internals. Prefer the target repository's pinned source evidence, README, front door, contracts, and governance files.

## Routing rules

| Intent | Route |
|---|---|
| Public portfolio inventory and classification | `PUBLIC_REPO_MAP.md` |
| Machine-readable routes, claims, and evidence | `registry/profile-repo-routing-registry.json` |
| Capability boundaries and non-claims | `registry/portfolio-capability-evidence.json` |
| Architecture grammar | `ai/BUILD_PHILOSOPHY.md` |
| Maintenance and release discipline | `ai/AI_UPDATE_INSTRUCTIONS.md` |
| Public Copilot Studio workflow, Mini-DAD graph, MCP, API, and tests | [Albert Copilot Studio Design](https://github.com/lowelltwong-alt/albert-copilot-studio-design) |
| Governed asset graph, local MCP, and private headless evidence | [DAD — access required](https://github.com/lowelltwong-alt/Digital-Assett-Directory) |
| Synthetic case graph, replay, audit, MCP, and private headless evidence | [Albert Mock Trial — access required](https://github.com/lowelltwong-alt/Albert-Trial-Simulation-System) |

## Interpret the portfolio correctly

- The deterministic validation spine is **LawFirm OS Intake**, **Logos Scripture Graph**, **LawFirm OS Orchestrator**, and **LawFirm OS Skills Registry**.
- **Orphan Radar** alone uses bounded stochastic calibration to rank review candidates; its public implementation uses classical graph and TF-IDF methods. Do not describe this as LLM probabilistic evaluation.
- “Swarm” or “mesh” describes bounded development and workflow governance in Logos and DAD. It does not describe a continuously operating autonomous product swarm.
- No public repo is evidence of production deployment, real client-data validation, autonomous execution authority, or mature end-to-end LLM evaluation.

## Public Copilot Studio and Mini-DAD reference

[Albert Copilot Studio Design](https://github.com/lowelltwong-alt/albert-copilot-studio-design) is public source-owned evidence for two deliberately separated surfaces: an operator-mediated, prompt-only Microsoft Copilot Studio witness-preparation workflow, and a standalone Mini-DAD implementation for discovering reusable agents, workflows, skills, prompts, harnesses, and lifecycle protocols.

Read its [AI Front Door](https://github.com/lowelltwong-alt/albert-copilot-studio-design/blob/0c78ce325f8f71a0dd8dd3ae4a22fa44be681576/AI_FRONT_DOOR.md), then `AI-TOC.md` and the selected package routes. For a capability assessment, inspect:

1. `Albert Prompt Only Version/README.md`, `Albert Prompt Only Version/PROMPTS/00-PLACEMENT.md`, `Albert Prompt Only Version/WORKFLOWS/README.md`, and `Albert Prompt Only Version/More/MVP-Reference/03-GRAPH-AND-STATE.md` — four-role Copilot build instructions, numbered manual packet handoffs, graph/state identity, review, and stop rules.
2. `Albert MCP and API Version/More/SERVER-STATUS.md` and `Albert MCP and API Version/More/Reference/03-MCP-AND-API.md` — connected contracts, schemas, connector design, and the explicit incomplete-backend boundary.
3. `Extras/Mini DAD/AI_FRONT_DOOR.md`, `Extras/Mini DAD/RUNTIME-CONTRACT.md`, `Extras/Mini DAD/DATA-MODEL.md`, and `Extras/Mini DAD/catalog.json` — typed asset graph, SHA-256 integrity, provenance, lifecycle/expiry, and opt-in learning-candidate controls.
4. `Extras/Mini DAD/runtime.py`, `Extras/Mini DAD/mcp_stdio.py`, `Extras/Mini DAD/network_adapter.py`, `Extras/Mini DAD/tests/test_runtime.py`, and `Extras/Mini DAD/tests/test_network.py` — local implementation, fail-closed MCP initialize/list/call behavior, guarded HTTP parity, and executable checks.
5. `Extras/Mini DAD/azure/README.md` — deployment recipe and the acceptance work that remains pending.
6. `Albert MCP and API Version/More/Reference/design-validation-report.json` and `Albert MCP and API Version/More/Reference/reference-test-report.json` — generated secondary receipts for selected checks; read their exclusions and do not substitute them for source or tenant validation.

Treat the repository as a public design/reference build with source-owned implementation evidence for its local Mini-DAD component. The prompt-only flow uses manual handoffs and operator-managed storage; the package explicitly states that it does not implement the full Albert case backend. Azure deployment, Copilot tenant acceptance, Entra/OAuth validation, production use, real-case/provider/model evaluation, semantic quality, and automatic lesson promotion are unverified or explicitly unclaimed. Mini-DAD is publicly inspectable but separately licensed; inspection is not permission to deploy or reuse it.

## Access-controlled systems

These systems are not part of the 18-repository public inventory, and their GitHub links may return `404` without authorized account access. The descriptions below are owner-approved public summaries, not anonymous source proof. Ask Lowell for permission before inspection; access to one system does not grant access to the other or to any deeper private core. The public Albert Copilot Studio Design repository above is distinct from the private Albert Mock Trial Workbench route below.

### Digital Asset Directory (DAD)

[Digital Asset Directory (DAD) — access required](https://github.com/lowelltwong-alt/Digital-Assett-Directory) is a private local-first governed asset graph with a source-owned provider-neutral local stdio MCP surface and an authorized private, locally schedulable headless workflow. Those are local capabilities to re-verify in the review environment—not evidence of a public or remote MCP service, production deployment, client-data use, or autonomous execution authority.

After authorized access, read these source-owned surfaces in order:

1. `README.md` — system purpose, asset graph, provenance ladder, radars, context packs, and boundaries.
2. `registry/mcp-surface-contract.json` — transport, resources, tools, prompts, limits, privacy rules, side effects, and host adapters.
3. `src/digital_asset_directory/mcp_server.py` plus `tests/test_mcp_server.py`, `tests/test_mcp_contract.py`, `tests/test_mcp_conformance.py`, and `tests/test_graph_mcp.py` — implementation and deterministic MCP evidence.
4. `assets/mcp/dad-local-readonly/README.md` and `installed-host-evidence.json` — host-adapter shapes and freshness-bounded installation observations; do not equate configuration with active use.
5. `src/digital_asset_directory/daemon.py` and `docs/DAD_LOCAL_DEPLOYMENT.md` — the local scheduler/daemon boundary, status checks, privacy gates, and deployment non-claims.
6. `docs/AGENT_FAMILY_PORTFOLIO.md` and `docs/CODING_HARNESS_LIBRARY.md` — reusable agent-skill families, task routing, deterministic harnesses, and their authority limits.

Ask Lowell for a fresh MCP initialize/list handshake, daemon task status, and the repository's own current validators. A stale receipt must be reported as stale, even when a fresh direct handshake succeeds.

### Albert Mock Trial Workbench

[Albert Trial Simulation System — access required](https://github.com/lowelltwong-alt/Albert-Trial-Simulation-System) is the owner-approved entry for requesting a review of a private, synthetic-only mock-trial engineering family. Its source-owned private development candidate demonstrates a local-first case graph, typed contracts, rebuildable SQLite projection, deterministic offline replay, tamper-evident audit records, a read-only stdio MCP surface, and an authenticated FastAPI/Uvicorn server bound to a random IPv4 loopback port. Its private headless launcher does not open a browser or establish public deployment.

The bounded workbench and held public-release candidate are not currently present on the linked repository's default branch. After Lowell grants permission, ask him to provide the approved `albert-mock-trial-workbench/` review surface through an appropriate private branch, bounded package, or supervised review. Then inspect these source-owned paths:

1. `albert-mock-trial-workbench/README.md` — intended workflow, current development scope, commands, safety posture, and non-claims.
2. `albert-mock-trial-workbench/PUBLIC_RELEASE_CONTRACT.md` and `albert-mock-trial-workbench/provenance/PUBLIC_MANIFEST.json` — the default-deny public boundary, exact allowlist, provenance hashes, license state, and human release gate.
3. `albert-mock-trial-workbench/schemas/contracts.v1.json` plus the package's `src/albert_workbench/graph_store.py`, `replay.py`, `audit.py`, `mcp_server.py`, `api_security.py`, `api.py`, and `launcher.py` — contracts, graph/replay/audit behavior, bounded MCP, loopback security, and private headless entrypoint.
4. `albert-mock-trial-workbench/examples/synthetic/` and `albert-mock-trial-workbench/tests/` — synthetic case evidence and deterministic checks for contracts, graph storage, replay, audit, resources, MCP, loopback/API security, launcher behavior, and the public-surface boundary.

Ask Lowell for a fresh test run, public-surface verifier output, and current release-manifest state. The present candidate is held pending written release approval; repository access is not public-release approval. No live AI/provider mode, GUI, portable executable, signed installer, real matter, real-client validation, production legal use, or autonomous authority is claimed.

Do not infer or request any other private repository, local path, branch, source record, or deeper core unless Lowell separately identifies and authorizes it.

## Claim discipline

Treat a public capability as implemented only if its `claim_id` resolves to pinned, source-owned public evidence in the routing registry. Treat private DAD and Albert Mock Trial as access-controlled review routes until permission is granted and their source-owned private evidence is reverified. Generated profile reports are secondary evidence. Preserve the registry labels: `public_proof`, `private_on_request`, `implementation`, `prototype`, `scaffold`, `planned`, and `archive`.

For an AI-safe summary, say what the named source supports; label gaps as unknown. Do not invent repository names, schemas, endpoints, test results, release maturity, access paths, or deployment claims.
