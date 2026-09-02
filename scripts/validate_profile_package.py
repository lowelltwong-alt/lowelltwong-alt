#!/usr/bin/env python3
"""Fail-closed validator for the public profile routing package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as error:  # pragma: no cover - explicit operator failure
    raise SystemExit(f"jsonschema with Draft202012Validator is required: {error}")


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "registry" / "profile-repo-routing-registry.json"
CAPABILITIES_PATH = ROOT / "registry" / "portfolio-capability-evidence.json"
RECEIPT_PATH = ROOT / "registry" / "releases" / "content-candidate-public-safe.json"
RELEASES_DIR = ROOT / "registry" / "releases"
PORTABLE_PATH = ROOT / "registry" / "portable-workflow-patterns.json"
PORTABLE_SCHEMA_PATH = ROOT / "registry" / "schemas" / "portable-workflow-patterns.schema.json"
SCHEMA_PATHS = {
    REGISTRY_PATH: ROOT / "registry" / "schemas" / "profile-routing.schema.json",
    CAPABILITIES_PATH: ROOT / "registry" / "schemas" / "portfolio-capability.schema.json",
    PORTABLE_PATH: PORTABLE_SCHEMA_PATH,
}
EXPECTED_ALIASES = [
    "graph_engineering", "knowledge_graphs", "mcp_server", "headless_ai_operations",
    "multi_agent_workflows", "agent_mesh", "agent_swarm_workflows", "deterministic_harnesses",
    "probabilistic_evaluation", "end_to_end_build", "ai_governance", "skill_supply_chain",
]
DAD_URL = "https://github.com/lowelltwong-alt/Digital-Assett-Directory"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def route_key(route: dict) -> tuple[str, str, str]:
    return (route["sha"], route["canonical_path"], route["canonical_url"])


def validate_schema_documents(errors: list[str]) -> tuple[dict, dict, dict, list[dict]]:
    schemas_dir = ROOT / "registry" / "schemas"
    for schema_path in sorted(schemas_dir.glob("*.json")):
        try:
            Draft202012Validator.check_schema(read_json(schema_path))
        except Exception as error:  # jsonschema reports the exact invalid schema location
            fail(errors, f"invalid Draft 2020-12 schema {schema_path.name}: {error}")

    documents = {path: read_json(path) for path in SCHEMA_PATHS}
    for document_path, schema_path in SCHEMA_PATHS.items():
        schema = read_json(schema_path)
        validator = Draft202012Validator(schema, format_checker=FormatChecker())
        for issue in sorted(validator.iter_errors(documents[document_path]), key=lambda item: list(item.absolute_path)):
            location = "/".join(str(part) for part in issue.absolute_path) or "<root>"
            fail(errors, f"{document_path.name}:{location}: {issue.message}")

    receipt_paths = sorted(RELEASES_DIR.glob("*.json"))
    if RECEIPT_PATH not in receipt_paths:
        fail(errors, f"required candidate receipt is missing: {RECEIPT_PATH.name}")
    receipt_schema = read_json(ROOT / "registry" / "schemas" / "release-receipt.schema.json")
    receipt_validator = Draft202012Validator(receipt_schema, format_checker=FormatChecker())
    receipts: list[dict] = []
    candidate: dict = {}
    for receipt_path in receipt_paths:
        receipt = read_json(receipt_path)
        receipts.append(receipt)
        if receipt_path == RECEIPT_PATH:
            candidate = receipt
        for issue in sorted(receipt_validator.iter_errors(receipt), key=lambda item: list(item.absolute_path)):
            location = "/".join(str(part) for part in issue.absolute_path) or "<root>"
            fail(errors, f"{receipt_path.name}:{location}: {issue.message}")
    return documents[REGISTRY_PATH], documents[CAPABILITIES_PATH], candidate, receipts


def validate_cross_references(registry: dict, capabilities: dict, receipt: dict, receipts: list[dict], errors: list[str]) -> None:
    repos = registry["repositories"]
    names = [repo["name"] for repo in repos]
    name_set = set(names)
    fail_if = lambda condition, message: fail(errors, message) if condition else None
    fail_if(registry["public_inventory_count"] != len(repos), "public inventory count does not equal registry cardinality")
    fail_if(len(names) != len(name_set), "public repository names are not unique")
    fail_if(registry["controlled_aliases"] != EXPECTED_ALIASES, "routing registry controlled aliases differ from the exact set")
    fail_if(capabilities["controlled_aliases"] != EXPECTED_ALIASES, "capability registry controlled aliases differ from the exact set")
    cap_aliases = [item["alias"] for item in capabilities["capabilities"]]
    fail_if(sorted(cap_aliases) != sorted(EXPECTED_ALIASES) or len(cap_aliases) != len(set(cap_aliases)), "capability aliases do not equal the exact controlled set")
    if not receipt:
        fail(errors, "required candidate receipt could not be loaded")
    else:
        fail_if(receipt["public_inventory_count"] != len(repos), "candidate receipt inventory count does not match registry cardinality")
        fail_if(receipt["release_authorized"] is not False, "candidate receipt must remain non-authorizing")
    for release in receipts:
        fail_if(release.get("public_inventory_count") != len(repos), "release receipt inventory count does not match registry cardinality")
        fail_if(release.get("release_authorized") is not False, "release receipt must remain non-authorizing")
        if release.get("status") == "final_closure_public_safe":
            required_final_fields = {
                "content_pr", "source_shas", "public_checks", "inventory_observation", "privacy_result", "lane_dispositions",
            }
            fail_if(not required_final_fields.issubset(release), "final closure receipt lacks required public-safe closure fields")

    repo_by_name = {repo["name"]: repo for repo in repos}
    owned_routes = {}
    for repo in repos:
        expected_root = f"https://github.com/lowelltwong-alt/{repo['name']}"
        fail_if(repo["canonical_url"] != expected_root, f"{repo['name']}: canonical URL/name mismatch")
        for route in repo["evidence_routes"]:
            fail_if(route["repository"] != repo["name"], f"{repo['name']}: evidence repository owner mismatch")
            owned_routes[route_key(route)] = route
            expected_url = f"{expected_root}/blob/{repo['pinned_public_sha']}/{route['canonical_path']}"
            fail_if(route["sha"] != repo["pinned_public_sha"], f"{repo['name']}: evidence SHA differs from pinned public SHA")
            fail_if(route["canonical_url"] != expected_url, f"{repo['name']}: evidence URL/path/SHA mismatch")
            fail_if(route["evidence_class"] != "source_owned_public" or not route["source_owned"] or route["generated"], f"{repo['name']}: public evidence must be source-owned and non-generated")
            fail_if(route["access_level"] != "anonymous_public", f"{repo['name']}: public evidence access must be anonymous_public")
        expected_pin = "self_referential_ancestor" if repo["name"] == "lowelltwong-alt" else "exact_default_head"
        fail_if(repo["pin_policy"] != expected_pin, f"{repo['name']}: invalid pin policy")
    private_routes = registry["private_routes"]
    fail_if(len(private_routes) != 1, "DAD must remain the sole private exception")
    dad = private_routes[0]
    fail_if(dad["canonical_url"] != DAD_URL or dad["visibility"] != "private_owner_approved_reference" or dad["access"] != "after_authorized_access", "DAD private boundary is not exact")
    fail_if(dad["pinned_public_sha"] != "not_public", "DAD must not claim anonymous public proof")
    for route in dad["evidence_routes"]:
        fail_if(route["repository"] != dad["name"], "DAD evidence repository owner mismatch")
        owned_routes[route_key(route)] = route
        fail_if(route["canonical_url"] != DAD_URL or route["access_level"] != "after_authorized_access" or route["evidence_class"] != "owner_approved_private_reference", "DAD evidence boundary is not exact")

    claims = {claim["id"]: claim for claim in registry["claims"]}
    for record in repos + private_routes:
        for claim_id in record["claim_ids"]:
            fail_if(claim_id not in claims, f"{record['name']}: dangling claim id {claim_id}")
            if claim_id in claims:
                fail_if(record["name"] not in claims[claim_id]["source_repositories"], f"{record['name']}: missing reverse claim source reference")
    allowed_sources = name_set | {dad["name"]}
    for claim in claims.values():
        fail_if(not set(claim["source_repositories"]).issubset(allowed_sources), f"{claim['id']}: unknown source repository")
        for source in claim["source_repositories"]:
            owner = dad if source == dad["name"] else repo_by_name[source]
            fail_if(claim["id"] not in owner["claim_ids"], f"{claim['id']}: missing reverse repository claim reference")
        for route in claim["evidence_routes"]:
            fail_if(route["repository"] not in claim["source_repositories"], f"{claim['id']}: route repository is undeclared")
            fail_if(route_key(route) not in owned_routes or owned_routes[route_key(route)] != route, f"{claim['id']}: route is not an exact owned duplicate")
        route_sources = {route["repository"] for route in claim["evidence_routes"]}
        fail_if(route_sources != set(claim["source_repositories"]), f"{claim['id']}: declared sources and evidence route sources must match exactly")
    for capability in capabilities["capabilities"]:
        fail_if(not set(capability["claim_ids"]).issubset(claims), f"{capability['alias']}: dangling claim reference")
        fail_if(not set(capability["source_repositories"]).issubset(allowed_sources), f"{capability['alias']}: unknown source repository")
        route_sources = {route["repository"] for route in capability["evidence_routes"]}
        fail_if(not set(capability["source_repositories"]).issubset(route_sources), f"{capability['alias']}: declared source without evidence route")
        for route in capability["evidence_routes"]:
            fail_if(route["repository"] not in capability["source_repositories"], f"{capability['alias']}: route repository is undeclared")
            fail_if(route_key(route) not in owned_routes or owned_routes[route_key(route)] != route, f"{capability['alias']}: route is not an exact owned duplicate")
            if route["access_level"] == "anonymous_public":
                fail_if(route["evidence_class"] != "source_owned_public" or not route["source_owned"] or route["generated"], f"{capability['alias']}: public evidence must be source-owned")
            else:
                fail_if(route["canonical_url"] != DAD_URL or route["sha"] != "not_public", f"{capability['alias']}: private evidence must be DAD-only")
    probability = next(item for item in capabilities["capabilities"] if item["alias"] == "probabilistic_evaluation")
    fail_if(probability["source_repositories"] != ["orphan-radar"], "probabilistic_evaluation must route only to Orphan Radar")
    fail_if("LLM" not in " ".join(probability["non_claims"] + [route_note for route in probability["evidence_routes"] for route_note in route["non_claims"]]), "probabilistic_evaluation must explicitly reject LLM evaluation")


def validate_markdown_projection(registry: dict, errors: list[str]) -> None:
    public_map = (ROOT / "PUBLIC_REPO_MAP.md").read_text(encoding="utf-8")
    toc = (ROOT / "ai" / "AI_PORTFOLIO_TOC.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    count = len(registry["repositories"])
    rows = [line for line in public_map.splitlines() if line.startswith("| [`")]
    row_pattern = re.compile(r"^\| \[`(?P<name>[^`]+)`\]\((?P<url>[^)]+)\) \| `(?P<delivery>[^`]+)` \| `(?P<maturity>[^`]+)` \| `(?P<priority>[^`]+)` \|")
    parsed = [row_pattern.match(row) for row in rows]
    if len(rows) != count or any(row is None for row in parsed):
        fail(errors, "public map repository rows are malformed or do not match registry cardinality")
    else:
        table = {row["name"]: row.groupdict() for row in parsed}
        if len(table) != count or set(table) != {repo["name"] for repo in registry["repositories"]}:
            fail(errors, "public map has duplicate, extra, or missing repository rows")
        for repo in registry["repositories"]:
            row = table[repo["name"]]
            expected = (repo["canonical_url"], repo["delivery"], repo["maturity"], repo["priority"]["value"])
            actual = (row["url"], row["delivery"], row["maturity"], row["priority"])
            if actual != expected:
                fail(errors, f"public map row diverges from registry: {repo['name']}")
    if f"{count} public repositories" not in public_map or f"All {count} public repositories" not in toc:
        fail(errors, "Markdown inventory count is out of sync with registry cardinality")
    for marker in ("AI_FRONT_DOOR.md", DAD_URL, "Deterministic validation"):
        if marker not in readme:
            fail(errors, f"README missing required synchronized marker: {marker}")


def validate_release_text(registry: dict, errors: list[str]) -> None:
    # Generated Pages output is a projection of already-scanned sources.
    text_paths = [
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix.lower() in {".md", ".json", ".py", ".yaml", ".yml"}
        and path.relative_to(ROOT).parts[0] != "site"
    ]
    forbidden = [re.compile(pattern) for pattern in (r"\b[A-Z]:[\\/]", r"/Users/", r"\\\\Users\\", r"\.agent-governance", r"refs/heads/", r"scratch/[A-Za-z0-9_.-]+", r"(?i:(?:api[_-]?key|secret|token)\s*[:=])")]
    bounded_terms = {"deployed": ("no ", "not ", "unasserted", "does not"), "production": ("no ", "not ", "unasserted", "non-production"), "autonomous": ("no ", "not ", "never", "bounded", "unasserted"), "headless": ("authorized", "unasserted", "private"), "swarm": ("bounded", "never", "no ", "not "), "implemented": ("only if", "source-owned"), "tested": ("source-owned", "not ", "no ")}
    public_surface_paths = [
        ROOT / "README.md", ROOT / "AI_FRONT_DOOR.md", ROOT / "PUBLIC_REPO_MAP.md", ROOT / "PORTABILITY_MAP.md",
        ROOT / "ai" / "AI_PORTFOLIO_TOC.md", ROOT / "ai" / "BUILD_PHILOSOPHY.md", REGISTRY_PATH, CAPABILITIES_PATH,
        *sorted(RELEASES_DIR.glob("*.json")),
    ]
    hidden_lane_phrases = ("protected local", "local candidate", "unpublished Intake", "unpublished local", "public-main source")
    for public_path in public_surface_paths:
        public_text = public_path.read_text(encoding="utf-8")
        for phrase in hidden_lane_phrases:
            if re.search(re.escape(phrase), public_text, re.I):
                fail(errors, f"public surface hidden-lane hint '{phrase}' in {public_path.relative_to(ROOT)}")
    allowed_roots = {repo["canonical_url"] for repo in registry["repositories"]} | {DAD_URL}
    for path in text_paths:
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        if relative == Path("scripts/validate_profile_package.py") or relative.parts[:2] == ("registry", "schemas"):
            continue  # Validator rules and schemas are meta-language, not release claims.
        for pattern in forbidden:
            if pattern.search(text):
                fail(errors, f"release text privacy scan: {path.relative_to(ROOT)} matched {pattern.pattern}")
        for url in re.findall(r"https://github\\.com/lowelltwong-alt/[A-Za-z0-9-]+", text):
            if url not in allowed_roots:
                fail(errors, f"release text has undisclosed repository URL: {relative}")
        if "Digital-Assett-Directory" in text and DAD_URL not in text:
            fail(errors, f"release text has a non-canonical DAD identifier: {path.relative_to(ROOT)}")
        if relative in {REGISTRY_PATH.relative_to(ROOT), CAPABILITIES_PATH.relative_to(ROOT), Path("registry/portable-workflow-patterns.json")}:
            continue  # Structured DAD and swarm constraints are enforced by schema and cross-reference checks.
        for term, contexts in bounded_terms.items():
            for match in re.finditer(term, text, re.I):
                window = text[max(0, match.start() - 120): match.end() + 120].lower()
                if not any(context in window for context in contexts):
                    fail(errors, f"unsupported unbounded term '{term}' in {path.relative_to(ROOT)}")


def fetch_json(url: str) -> object:
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "lowelltwong-alt-profile-validator"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_status(url: str) -> int:
    request = Request(url, headers={"User-Agent": "lowelltwong-alt-profile-validator"}, method="HEAD")
    try:
        with urlopen(request, timeout=20) as response:
            return response.status
    except HTTPError as error:
        if error.code != 405:
            raise
    request = Request(url, headers={"User-Agent": "lowelltwong-alt-profile-validator"})
    with urlopen(request, timeout=20) as response:
        return response.status


def verify_remote(registry: dict, errors: list[str]) -> None:
    try:
        inventory = fetch_json(registry["inventory_source"])
        remote = {item["name"]: item for item in inventory}
        expected = {repo["name"] for repo in registry["repositories"]}
        if set(remote) != expected:
            fail(errors, f"remote inventory mismatch: expected {len(expected)}, received {len(remote)}")
        for repo in registry["repositories"]:
            remote_repo = remote.get(repo["name"])
            if not remote_repo or remote_repo.get("visibility") != "public":
                fail(errors, f"remote public repository unavailable: {repo['name']}")
                continue
            head = fetch_json(f"https://api.github.com/repos/lowelltwong-alt/{repo['name']}/commits/{remote_repo['default_branch']}")
            if repo["pin_policy"] == "exact_default_head" and head.get("sha") != repo["pinned_public_sha"]:
                fail(errors, f"remote default head differs from pinned SHA: {repo['name']}")
            if repo["pin_policy"] == "self_referential_ancestor":
                comparison = fetch_json(f"https://api.github.com/repos/lowelltwong-alt/{repo['name']}/compare/{repo['pinned_public_sha']}...{head.get('sha')}")
                if comparison.get("status") not in {"identical", "ahead"}:
                    fail(errors, f"profile pin is not an ancestor of the remote default head: {repo['name']}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        fail(errors, f"anonymous remote verification unavailable: {error}")
        return

    evidence_urls = sorted({
        route["canonical_url"]
        for repo in registry["repositories"]
        for route in repo["evidence_routes"]
    })

    def check_evidence_url(url: str) -> tuple[str, str | None]:
        try:
            status = fetch_status(url)
            if status != 200:
                return url, f"HTTP {status}"
            return url, None
        except (HTTPError, URLError, TimeoutError) as error:
            return url, str(error)
        except Exception as error:  # Fail closed while allowing every URL to be reported.
            return url, f"unexpected {type(error).__name__}: {error}"

    results: list[tuple[str, str | None]] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(check_evidence_url, url) for url in evidence_urls]
        for future in as_completed(futures):
            results.append(future.result())
    for url, error in sorted(results):
        if error is not None:
            fail(errors, f"remote evidence URL did not resolve: {url}: {error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-remote", action="store_true", help="anonymously verify inventory, default heads, and evidence URLs")
    args = parser.parse_args()
    errors: list[str] = []
    registry, capabilities, receipt, receipts = validate_schema_documents(errors)
    validate_cross_references(registry, capabilities, receipt, receipts, errors)
    validate_markdown_projection(registry, errors)
    validate_release_text(registry, errors)
    if args.verify_remote:
        verify_remote(registry, errors)
    if errors:
        print("PROFILE PACKAGE VALIDATION FAILED")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    mode = "remote and offline" if args.verify_remote else "offline"
    print(f"PROFILE PACKAGE VALIDATION PASSED ({mode}): {len(registry['repositories'])} public repositories; {len(registry['claims'])} claims.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
