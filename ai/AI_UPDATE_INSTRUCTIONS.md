# Profile Update Instructions

## Evidence-first update procedure

1. Query the anonymous GitHub API for the complete public inventory; record the observation time and each default-branch SHA.
2. Inspect source-owned public README/front-door evidence before changing a claim. Do not use local candidates, private artifacts, or generated reports as public proof.
3. Update `registry/profile-repo-routing-registry.json` first, then synchronize `PUBLIC_REPO_MAP.md` and `ai/AI_PORTFOLIO_TOC.md`.
4. Keep every repository in one delivery class: `public_proof`, `private_on_request`, `implementation`, `prototype`, `scaffold`, `planned`, or `archive`.
5. Keep the approved non-claims intact: synthetic/public-source boundaries, unasserted maturity/deployment, bounded autonomy, and no LLM probabilistic evaluation claim.

## Access-controlled boundary

Exactly two private systems have owner-approved public summaries:

1. DAD at `https://github.com/lowelltwong-alt/Digital-Assett-Directory`. It remains the sole structured private evidence route in the machine registry. Its approved description is limited to a private local-first governed asset graph; an authorized private headless-capable daemon/scheduler; and, after Lowell grants access, source-owned local stdio MCP evidence that is read-only by default with narrow receipt recording and no execution authority.
2. Albert Mock Trial at `https://github.com/lowelltwong-alt/Albert-Trial-Simulation-System`. It is an access-controlled Markdown route only. The URL is an access-request entry; do not imply that the bounded `albert-mock-trial-workbench/` candidate is present on its current default branch. Its approved description is limited to a synthetic-only local case graph, typed contracts, deterministic offline replay, tamper-evident audit, read-only stdio MCP, authenticated random-port IPv4 loopback API, private headless launcher, tests, and a public-release manifest that remains held pending written approval. After permission, Lowell may provide the bounded surface through an approved private branch, package, or supervised review.

Do not add Albert to the public evidence registries unless source-owned public evidence is separately released and reviewed. Do not expose local absolute paths, private payloads, real matters, a deeper core, or any other private repository. Do not turn either access route into a claim of public deployment, production/client-data use, live provider use, autonomous authority, legal qualification, or release approval.

## Required checks

```text
python scripts/validate_profile_package.py
python scripts/validate_profile_package.py --verify-remote
python <approved-privacy-boundary-script> audit --repo <worktree> --scan-content
```

Report changed paths, anonymous-inventory count, source observation time, README word count, checks, assumptions, and unresolved evidence gaps. A passing content check is not release authorization.
