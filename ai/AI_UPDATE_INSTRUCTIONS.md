# Profile Update Instructions

## Evidence-first update procedure

1. Query the anonymous GitHub API for the complete public inventory; record the observation time and each default-branch SHA.
2. Inspect source-owned public README/front-door evidence before changing a claim. Do not use local candidates, private artifacts, or generated reports as public proof.
3. Update `registry/profile-repo-routing-registry.json` first, then synchronize `PUBLIC_REPO_MAP.md` and `ai/AI_PORTFOLIO_TOC.md`.
4. Keep every repository in one delivery class: `public_proof`, `private_on_request`, `implementation`, `prototype`, `scaffold`, `planned`, or `archive`.
5. Keep the approved non-claims intact: synthetic/public-source boundaries, unasserted maturity/deployment, bounded autonomy, and no LLM probabilistic evaluation claim.

## Private boundary

DAD is the only private-by-request disclosure at `https://github.com/lowelltwong-alt/Digital-Assett-Directory`. Its approved description is limited to a private local-first governed asset graph; a headless-capable daemon/scheduler with runtime/deployment unasserted; and, after authorized access, a local stdio MCP source at `src/digital_asset_directory/mcp_server.py`, read-only by default with narrow receipt recording and no execution authority. Do not add any other private work, local path, branch, artifact, test result, source record, or capability claim.

## Required checks

```text
python scripts/validate_profile_package.py
python <approved-privacy-boundary-script> audit --repo <worktree> --scan-content
```

Report changed paths, anonymous-inventory count, source observation time, README word count, checks, assumptions, and unresolved evidence gaps. A passing content check is not release authorization.
