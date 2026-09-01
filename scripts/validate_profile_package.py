#!/usr/bin/env python3
"""Fail-closed validator for the public profile routing package."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import SplitResult, unquote, urlsplit
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
STRUCTURED_PRIVATE_ACCESS_URLS = {DAD_URL}
NARRATIVE_ONLY_ACCESS_URL_SHA256 = "4cf7299d0f996d643bbfda870e401a52c1f69c6881b57a729e5005dad0535f05"
GITHUB_OWNER = "lowelltwong-alt"
MAX_PYTHON_STATIC_PROJECTION_CHARS = 65_536
MAX_PYTHON_STATIC_EXPRESSION_DEPTH = 64
MAX_PYTHON_STATIC_BINDINGS = 2_048
MAX_PYTHON_STATIC_SEQUENCE_ITEMS = 2_048
MAX_PYTHON_STATIC_TOTAL_CHARS = 1_048_576
URL_CANDIDATE_PATTERN = re.compile(
    r"(?i)(?=((?:https?:|[\\/]{2})[^\s<>\[\]()\"'`]+))"
)
MARKDOWN_BACKSLASH_ESCAPE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]^_`{|}~])")
SERIALIZED_CODEPOINT_ESCAPES = (
    re.compile(r"\\x([0-9A-Fa-f]{2})"),
    re.compile(r"\\u([0-9A-Fa-f]{4})"),
    re.compile(r"\\U([0-9A-Fa-f]{8})"),
)
SERIALIZED_NUMERIC_ESCAPE_PREFIX = re.compile(r"\\+(?=[xuU][0-9A-Fa-f])")
YAML_ESCAPED_LINE_BREAK = re.compile(r"\\(?:\r\n?|\n)[ \t]*")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def route_key(route: dict) -> tuple[str, str, str]:
    return (route["sha"], route["canonical_path"], route["canonical_url"])


def tracked_utf8_text_files(errors: list[str]) -> list[tuple[Path, str]]:
    """Load every Git-tracked file as UTF-8 text or fail closed for explicit handling."""
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z", "--cached"],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        fail(errors, f"tracked-file inventory unavailable: {error}")
        return []

    tracked: list[tuple[Path, str]] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        try:
            relative = Path(raw_path.decode("utf-8"))
        except UnicodeDecodeError:
            fail(errors, "tracked-file inventory contains a non-UTF-8 path")
            continue
        if relative.is_absolute() or ".." in relative.parts:
            fail(errors, f"tracked-file inventory escaped the repository root: {relative}")
            continue
        path = ROOT / relative
        if path.is_symlink() or not path.is_file():
            fail(errors, f"tracked file requires explicit non-regular-file handling: {relative}")
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            fail(errors, f"tracked file is not UTF-8 text and requires explicit handling: {relative}")
            continue
        tracked.append((path, text))
    return tracked


def normalize_release_text(text: str, *, markdown_escapes: bool = True) -> str:
    """Normalize renderer- and serializer-level escapes before privacy checks."""
    previous = None
    while text != previous:
        previous = text
        text = YAML_ESCAPED_LINE_BREAK.sub("", text)
        text = SERIALIZED_NUMERIC_ESCAPE_PREFIX.sub(lambda _: "\\", text)
        for pattern in SERIALIZED_CODEPOINT_ESCAPES:
            text = pattern.sub(
                lambda match: (
                    chr(int(match.group(1), 16))
                    if int(match.group(1), 16) <= sys.maxunicode
                    else match.group(0)
                ),
                text,
            )
        text = unescape(text)
        if markdown_escapes:
            text = MARKDOWN_BACKSLASH_ESCAPE.sub(r"\1", text)
    return text


def normalize_percent_escapes(text: str) -> str:
    """Decode nested percent escapes to the representation a URL consumer can see."""
    previous = None
    while text != previous:
        previous = text
        text = unquote(text)
    return text


def normalize_url_candidate(url: str) -> str:
    """Apply browser-style separator handling for parsing without hiding raw spelling."""
    candidate = normalize_percent_escapes(url).replace("\\", "/")
    scheme_match = re.match(r"(?i)^(https?):(.*)$", candidate)
    if scheme_match is not None:
        candidate = f"{scheme_match.group(1)}://{scheme_match.group(2).lstrip('/')}"
    elif candidate.startswith("//"):
        candidate = f"https:{candidate}"
    return candidate


def owned_github_url_parts(url: str) -> tuple[SplitResult, list[str], bool] | None:
    """Parse a GitHub URL that resolves to this account, including encoded forms."""
    candidate = normalize_url_candidate(url)
    try:
        parsed = urlsplit(candidate)
    except ValueError:
        return None
    normalized_host = (parsed.hostname or "").rstrip(".").casefold()
    if normalized_host not in {"github.com", "www.github.com"}:
        return None

    normalized_segments: list[str] = []
    had_dot_segment = False
    for segment in unquote(parsed.path).split("/"):
        if not segment:
            continue
        if segment == ".":
            had_dot_segment = True
            continue
        if segment == "..":
            had_dot_segment = True
            if normalized_segments:
                normalized_segments.pop()
            continue
        normalized_segments.append(segment)
    if len(normalized_segments) < 2 or normalized_segments[0].casefold() != GITHUB_OWNER.casefold():
        return None
    return parsed, normalized_segments, had_dot_segment


def iter_owned_github_urls(text: str, *, normalize_serialized: bool = True):
    """Yield complete URL tokens that resolve to this GitHub account."""
    scan_texts = (
        (
            normalize_release_text(text),
            normalize_release_text(text, markdown_escapes=False),
        )
        if normalize_serialized
        else (text,)
    )
    seen_candidates: set[tuple[str, str, tuple[str, ...], str, str, bool]] = set()
    for scan_text in scan_texts:
        for match in URL_CANDIDATE_PATTERN.finditer(scan_text):
            url = match.group(1)
            start = match.start(1)
            if url.startswith(("//", "\\\\")):
                prefix = scan_text[max(0, start - 6):start].casefold()
                if prefix.endswith(("http:", "https:")):
                    continue
            parsed_result = owned_github_url_parts(url)
            if parsed_result is None:
                continue
            parsed, segments, had_dot_segment = parsed_result
            candidate_identity = (
                parsed.scheme.casefold(),
                parsed.netloc.casefold(),
                tuple(segments),
                parsed.query,
                parsed.fragment,
                had_dot_segment,
            )
            if candidate_identity in seen_candidates:
                continue
            seen_candidates.add(candidate_identity)
            yield url


def load_narrative_only_access_url(errors: list[str]) -> str | None:
    """Resolve the exact Markdown-only access route without copying its identifier."""
    source = (ROOT / "AI_FRONT_DOOR.md").read_text(encoding="utf-8")
    candidates = {
        url
        for url in iter_owned_github_urls(source)
        if hashlib.sha256(url.encode("utf-8")).hexdigest() == NARRATIVE_ONLY_ACCESS_URL_SHA256
    }
    if len(candidates) != 1:
        fail(errors, "Markdown-only access route is missing, duplicated, or changed")
        return None
    url = next(iter(candidates))
    parsed_result = owned_github_url_parts(url)
    if parsed_result is None:
        fail(errors, "Markdown-only access route is not a recognized GitHub URL")
        return None
    parsed, segments, had_dot_segment = parsed_result
    expected_root = f"https://github.com/{GITHUB_OWNER}/{segments[1]}"
    if had_dot_segment or len(segments) != 2 or url != expected_root or parsed.query or parsed.fragment:
        fail(errors, "Markdown-only access route must remain one exact canonical repository root")
        return None
    return url


def release_url_allowed(
    relative: Path,
    url: str,
    allowed_roots: set[str],
    narrative_only_root: str | None,
    structured_private_roots: set[str] | None = None,
) -> bool:
    """Allow public deep links, but require exact roots for access-controlled repos."""
    parsed_result = owned_github_url_parts(url)
    if parsed_result is None:
        return False
    parsed, segments, had_dot_segment = parsed_result
    if had_dot_segment:
        return False
    canonical_transport = (
        parsed.scheme.casefold() == "https"
        and parsed.netloc.casefold() == "github.com"
        and url[:8].casefold() == "https://"
    )
    if not canonical_transport:
        return False

    roots_by_name = {
        unquote(urlsplit(root).path).rstrip("/").rsplit("/", 1)[-1].casefold(): root
        for root in allowed_roots
    }
    canonical_root = roots_by_name.get(segments[1].casefold())
    if canonical_root is None:
        return False
    exact_root_only = (
        STRUCTURED_PRIVATE_ACCESS_URLS
        if structured_private_roots is None
        else structured_private_roots
    )
    if canonical_root in exact_root_only or canonical_root == narrative_only_root:
        if url != canonical_root:
            return False
        if canonical_root == narrative_only_root:
            return relative.suffix.lower() == ".md"
    return True


def has_noncanonical_narrative_identifier(
    text: str,
    narrative_only_root: str,
    *,
    normalize_serialized: bool = True,
) -> bool:
    release_text = normalize_release_text(text) if normalize_serialized else text
    normalized_text = normalize_percent_escapes(release_text)
    repository_name = unquote(urlsplit(narrative_only_root).path).rstrip("/").rsplit("/", 1)[-1]
    text_without_approved_root = normalized_text.replace(narrative_only_root, "")
    return repository_name.casefold() in text_without_approved_root.casefold()


def python_literal_projections(
    source: str,
    relative: Path,
    errors: list[str],
    *,
    protected_identifier: str | None = None,
) -> list[str]:
    """Return bounded Python-decoded static text without executing tracked source."""
    try:
        tree = ast.parse(source, filename=str(relative))
    except (SyntaxError, ValueError) as error:
        fail(errors, f"tracked Python source cannot be parsed for privacy checks: {relative}: {error}")
        return []

    safe_scalar_types = {
        str,
        bytes,
        int,
        float,
        complex,
        bool,
    }

    def projection_failure(message: str) -> None:
        full_message = f"tracked Python privacy projection failed: {relative}: {message}"
        if full_message not in errors:
            fail(errors, full_message)

    projections: set[str] = set()
    projection_chars = 0

    def is_safe_materialized(value: object, depth: int = 0) -> bool:
        if depth > MAX_PYTHON_STATIC_EXPRESSION_DEPTH:
            return False
        if type(value) in safe_scalar_types:
            return True
        return (
            isinstance(value, tuple)
            and len(value) <= MAX_PYTHON_STATIC_SEQUENCE_ITEMS
            and all(is_safe_materialized(item, depth + 1) for item in value)
        )

    def materialized_text_size(value: object) -> int:
        if isinstance(value, (str, bytes)):
            return len(value)
        if isinstance(value, tuple):
            return sum(materialized_text_size(item) for item in value)
        return 0

    def add_projection(value: object) -> None:
        nonlocal projection_chars
        if isinstance(value, tuple):
            for item in value:
                add_projection(item)
            return
        if isinstance(value, bytes):
            text = value.decode("latin-1")
        elif isinstance(value, str):
            text = value
        else:
            return
        if text in projections:
            return
        if projection_chars + len(text) > MAX_PYTHON_STATIC_TOTAL_CHARS:
            projection_failure("total static projections exceed the bounded character budget")
            return
        projections.add(text)
        projection_chars += len(text)

    def add_protected_literal_fragment_projection() -> None:
        """Conservatively backstop common static composition over decoded literals."""
        if protected_identifier is None:
            return
        target = protected_identifier.casefold()
        if len(target) < 6:
            projection_failure("protected Python identifier is too short for fragment analysis")
            return
        literals: list[str] = []
        literal_chars = 0
        for candidate in ast.walk(tree):
            literal_value: str | bytes | None = None
            if isinstance(candidate, ast.Constant) and isinstance(
                candidate.value, (str, bytes)
            ):
                literal_value = candidate.value
            elif (
                isinstance(candidate, ast.Call)
                and isinstance(candidate.func, ast.Name)
                and candidate.func.id == "chr"
            ):
                projected = static_value(candidate, {})
                if isinstance(projected, str):
                    literal_value = projected
            if literal_value is None:
                continue
            if len(literals) >= MAX_PYTHON_STATIC_SEQUENCE_ITEMS:
                projection_failure("decoded Python literal count exceeds the bounded fragment limit")
                return
            literal = (
                literal_value.decode("latin-1")
                if isinstance(literal_value, bytes)
                else literal_value
            )
            if len(literal) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                projection_failure("decoded Python literal exceeds the bounded fragment limit")
                return
            literal = normalize_percent_escapes(literal).casefold()
            literal_chars += len(literal)
            if literal_chars > MAX_PYTHON_STATIC_TOTAL_CHARS:
                projection_failure("decoded Python literals exceed the bounded fragment budget")
                return
            literals.append(literal)

        def matching_lengths(position: int, literal: str, *, anchored: bool) -> set[int]:
            lengths: set[int] = set()
            remaining = target[position:]
            for start in range(len(literal)):
                matched = 0
                while (
                    matched < len(remaining)
                    and start + matched < len(literal)
                    and literal[start + matched] == remaining[matched]
                ):
                    matched += 1
                if not matched:
                    continue
                minimum = 6 if not anchored else 3
                for length in range(minimum, matched + 1):
                    fragment = remaining[:length]
                    if not anchored or any(character.isalnum() for character in fragment):
                        lengths.add(length)
                if anchored:
                    for length in range(1, min(2, matched) + 1):
                        fragment = remaining[:length]
                        if all(not character.isalnum() for character in fragment):
                            lengths.add(length)
            return lengths

        reachable = {
            length
            for literal in literals
            for length in matching_lengths(0, literal, anchored=False)
        }
        pending = list(reachable)
        while pending:
            position = pending.pop()
            if position >= len(target):
                add_projection(protected_identifier)
                return
            for literal in literals:
                for length in matching_lengths(position, literal, anchored=True):
                    next_position = position + length
                    if next_position not in reachable:
                        reachable.add(next_position)
                        pending.append(next_position)

    def stored_text_size(environment: dict[str, object]) -> int:
        return sum(materialized_text_size(value) for value in environment.values())

    def static_sequence_multiplier(value: object) -> int | None:
        if type(value) in {int, bool}:
            return int(value)
        return None

    def bind_name(environment: dict[str, object], name: str, value: object) -> None:
        if not is_safe_materialized(value):
            environment.pop(name, None)
            return
        if materialized_text_size(value) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
            projection_failure("static binding exceeds the bounded projection limit")
            environment.pop(name, None)
            return
        if name not in environment and len(environment) >= MAX_PYTHON_STATIC_BINDINGS:
            projection_failure("static binding count exceeds the bounded environment limit")
            return
        previous = environment.get(name)
        environment[name] = value
        if stored_text_size(environment) > MAX_PYTHON_STATIC_TOTAL_CHARS:
            projection_failure("static bindings exceed the bounded character budget")
            if previous is None:
                environment.pop(name, None)
            else:
                environment[name] = previous

    def static_formatted_text(
        node: ast.FormattedValue,
        environment: dict[str, object],
        depth: int,
    ) -> str | None:
        value = static_value(node.value, environment, depth + 1)
        if type(value) not in safe_scalar_types:
            return None
        if node.conversion == ord("s"):
            value = str(value)
        elif node.conversion == ord("r"):
            value = repr(value)
        elif node.conversion == ord("a"):
            value = ascii(value)
        elif node.conversion != -1:
            return None
        format_spec = (
            ""
            if node.format_spec is None
            else static_value(node.format_spec, environment, depth + 1)
        )
        if not isinstance(format_spec, str):
            return None

        def exceeds_projection_bound(digits: str) -> bool:
            significant = digits.lstrip("0") or "0"
            maximum = str(MAX_PYTHON_STATIC_PROJECTION_CHARS)
            return len(significant) > len(maximum) or (
                len(significant) == len(maximum) and significant > maximum
            )

        if (
            len(format_spec) > MAX_PYTHON_STATIC_PROJECTION_CHARS
            or any(
                exceeds_projection_bound(digits)
                for digits in re.findall(r"[0-9]+", format_spec)
            )
        ):
            projection_failure("static format specification exceeds the bounded projection limit")
            return None
        try:
            rendered = format(value, format_spec)
        except MemoryError:
            projection_failure("static formatting exhausted the bounded projection budget")
            return None
        except (TypeError, ValueError):
            return None
        if len(rendered) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
            projection_failure("static formatted value exceeds the bounded projection limit")
            return None
        return rendered

    def static_value(
        node: ast.AST,
        environment: dict[str, object],
        depth: int = 0,
    ) -> object | None:
        if depth > MAX_PYTHON_STATIC_EXPRESSION_DEPTH:
            projection_failure("static expression exceeds the bounded evaluation depth")
            return None
        if isinstance(node, ast.Constant) and type(node.value) in {
            str,
            bytes,
            int,
            float,
            complex,
            bool,
        }:
            return node.value
        if isinstance(node, (ast.Tuple, ast.List)):
            if len(node.elts) > MAX_PYTHON_STATIC_SEQUENCE_ITEMS:
                projection_failure("static sequence exceeds the bounded item limit")
                return None
            values = tuple(
                static_value(item, environment, depth + 1)
                for item in node.elts
            )
            if all(is_safe_materialized(value) for value in values):
                return values
            return None
        if isinstance(node, ast.Name):
            return environment.get(node.id)
        if isinstance(node, ast.UnaryOp):
            operand = static_value(node.operand, environment, depth + 1)
            if isinstance(node.op, ast.Not) and is_safe_materialized(operand):
                return not bool(operand)
            if type(operand) in {int, bool}:
                normalized = int(operand)
                if isinstance(node.op, ast.UAdd):
                    return normalized
                if isinstance(node.op, ast.USub):
                    return -normalized
                if isinstance(node.op, ast.Invert):
                    return ~normalized
            return None
        if isinstance(node, ast.JoinedStr):
            values = [
                (static_formatted_text(value, environment, depth + 1) or "")
                if isinstance(value, ast.FormattedValue)
                else static_value(value, environment, depth + 1)
                for value in node.values
            ]
            if values and all(isinstance(value, str) for value in values):
                joined = "".join(value for value in values if isinstance(value, str))
                if len(joined) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                    projection_failure("static f-string exceeds the bounded projection limit")
                    return None
                return joined
            return None
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and len(node.args) == 1
            and not node.keywords
        ):
            argument = static_value(node.args[0], environment, depth + 1)
            if node.func.id == "chr" and type(argument) in {int, bool}:
                try:
                    return chr(int(argument))
                except (OverflowError, ValueError):
                    return None
            if node.func.id == "ord" and isinstance(argument, (str, bytes)) and len(argument) == 1:
                return ord(argument)
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "join"
            and len(node.args) == 1
            and not node.keywords
        ):
            separator = static_value(node.func.value, environment, depth + 1)
            values = static_value(node.args[0], environment, depth + 1)
            if isinstance(separator, str) and isinstance(values, tuple) and all(
                isinstance(value, str) for value in values
            ):
                joined_size = materialized_text_size(values) + max(
                    len(values) - 1, 0
                ) * len(separator)
                if joined_size > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                    projection_failure("static string join exceeds the bounded projection limit")
                    return None
                return separator.join(values)
            if isinstance(separator, bytes) and isinstance(values, tuple) and all(
                isinstance(value, bytes) for value in values
            ):
                joined_size = materialized_text_size(values) + max(
                    len(values) - 1, 0
                ) * len(separator)
                if joined_size > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                    projection_failure("static bytes join exceeds the bounded projection limit")
                    return None
                return separator.join(values)
            return None
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left = static_value(node.left, environment, depth + 1)
            right = static_value(node.right, environment, depth + 1)
            if isinstance(left, str) and isinstance(right, str):
                joined = left + right
                if len(joined) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                    projection_failure("static string addition exceeds the bounded projection limit")
                    return None
                return joined
            if isinstance(left, bytes) and isinstance(right, bytes):
                joined = left + right
                if len(joined) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                    projection_failure("static bytes addition exceeds the bounded projection limit")
                    return None
                return joined
            if isinstance(left, tuple) and isinstance(right, tuple):
                joined = left + right
                if (
                    len(joined) > MAX_PYTHON_STATIC_SEQUENCE_ITEMS
                    or materialized_text_size(joined) > MAX_PYTHON_STATIC_PROJECTION_CHARS
                ):
                    projection_failure("static tuple addition exceeds the bounded projection limit")
                    return None
                return joined
            numeric_types = {int, float, complex}
            if type(left) in numeric_types and type(right) in numeric_types:
                return left + right
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            left = static_value(node.left, environment, depth + 1)
            right = static_value(node.right, environment, depth + 1)
            right_multiplier = static_sequence_multiplier(right)
            left_multiplier = static_sequence_multiplier(left)
            left_is_sequence = isinstance(left, (str, bytes, tuple))
            right_is_sequence = isinstance(right, (str, bytes, tuple))
            if (left_is_sequence and right is None) or (
                right_is_sequence and left is None
            ):
                projection_failure("static sequence multiplication has an unresolved multiplier")
                return None
            if (right_multiplier is not None and left is None) or (
                left_multiplier is not None and right is None
            ):
                projection_failure("static multiplication has an unresolved sequence operand")
                return None
            if isinstance(left, (str, bytes)) and right_multiplier is not None:
                if right_multiplier <= 0 or not left:
                    return left[:0]
                if right_multiplier > MAX_PYTHON_STATIC_PROJECTION_CHARS // len(left):
                    projection_failure("static sequence multiplication exceeds the bounded projection limit")
                    return None
                return left * right_multiplier
            if left_multiplier is not None and isinstance(right, (str, bytes)):
                if left_multiplier <= 0 or not right:
                    return right[:0]
                if left_multiplier > MAX_PYTHON_STATIC_PROJECTION_CHARS // len(right):
                    projection_failure("static sequence multiplication exceeds the bounded projection limit")
                    return None
                return right * left_multiplier
            if isinstance(left, tuple) and right_multiplier is not None:
                if right_multiplier <= 0 or not left:
                    return ()
                text_size = materialized_text_size(left)
                if (
                    right_multiplier > MAX_PYTHON_STATIC_SEQUENCE_ITEMS // len(left)
                    or (
                        text_size
                        and right_multiplier > MAX_PYTHON_STATIC_PROJECTION_CHARS // text_size
                    )
                ):
                    projection_failure("static tuple multiplication exceeds the bounded projection limit")
                    return None
                return left * right_multiplier
            if left_multiplier is not None and isinstance(right, tuple):
                if left_multiplier <= 0 or not right:
                    return ()
                text_size = materialized_text_size(right)
                if (
                    left_multiplier > MAX_PYTHON_STATIC_SEQUENCE_ITEMS // len(right)
                    or (
                        text_size
                        and left_multiplier > MAX_PYTHON_STATIC_PROJECTION_CHARS // text_size
                    )
                ):
                    projection_failure("static tuple multiplication exceeds the bounded projection limit")
                    return None
                return right * left_multiplier
        if isinstance(node, ast.IfExp):
            condition = static_value(node.test, environment, depth + 1)
            if type(condition) in safe_scalar_types:
                branch = node.body if bool(condition) else node.orelse
                return static_value(branch, environment, depth + 1)
        if isinstance(node, ast.NamedExpr):
            return static_value(node.value, environment, depth + 1)
        return None

    nested_scopes = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)

    def inspect_expression(node: ast.AST | None, environment: dict[str, object]) -> None:
        if node is None:
            return
        named_expressions: list[ast.NamedExpr] = []

        def visit(candidate: ast.AST, depth: int, collect_named: bool) -> None:
            if depth > MAX_PYTHON_STATIC_EXPRESSION_DEPTH:
                projection_failure("expression traversal exceeds the bounded depth")
                return
            if isinstance(candidate, ast.Lambda):
                if not collect_named:
                    return
                for default in candidate.args.defaults:
                    inspect_expression(default, environment)
                for default in candidate.args.kw_defaults:
                    inspect_expression(default, environment)
                inspect_expression(candidate.body, {})
                return
            add_projection(static_value(candidate, environment, depth))
            if collect_named and isinstance(candidate, ast.NamedExpr):
                named_expressions.append(candidate)
            if depth and isinstance(candidate, nested_scopes):
                return
            for child in ast.iter_child_nodes(candidate):
                visit(child, depth + 1, collect_named)

        visit(node, 0, True)
        for candidate in named_expressions:
            if isinstance(candidate.target, ast.Name):
                value = static_value(candidate.value, environment)
                add_projection(value)
                bind_name(environment, candidate.target.id, value)
        visit(node, 0, False)

    def target_names(target: ast.AST) -> set[str]:
        if isinstance(target, ast.Name):
            return {target.id}
        if isinstance(target, ast.Starred):
            return target_names(target.value)
        if isinstance(target, (ast.Tuple, ast.List)):
            return set().union(*(target_names(item) for item in target.elts)) if target.elts else set()
        return set()

    def invalidate_target(environment: dict[str, object], target: ast.AST) -> None:
        for name in target_names(target):
            environment.pop(name, None)

    def bind_assignment_target(
        environment: dict[str, object],
        target: ast.AST,
        value: object,
    ) -> None:
        if isinstance(target, ast.Name):
            bind_name(environment, target.id, value)
            return
        if isinstance(target, ast.Starred):
            bind_assignment_target(environment, target.value, value)
            return
        if not isinstance(target, (ast.Tuple, ast.List)) or not isinstance(value, tuple):
            invalidate_target(environment, target)
            return
        starred_indexes = [
            index
            for index, item in enumerate(target.elts)
            if isinstance(item, ast.Starred)
        ]
        if not starred_indexes:
            if len(target.elts) != len(value):
                invalidate_target(environment, target)
                return
            for item, item_value in zip(target.elts, value):
                bind_assignment_target(environment, item, item_value)
            return
        if len(starred_indexes) != 1:
            invalidate_target(environment, target)
            return
        starred_index = starred_indexes[0]
        trailing_count = len(target.elts) - starred_index - 1
        if len(value) < starred_index + trailing_count:
            invalidate_target(environment, target)
            return
        for item, item_value in zip(target.elts[:starred_index], value[:starred_index]):
            bind_assignment_target(environment, item, item_value)
        bind_assignment_target(
            environment,
            target.elts[starred_index],
            value[starred_index:len(value) - trailing_count if trailing_count else None],
        )
        if trailing_count:
            for item, item_value in zip(
                target.elts[-trailing_count:],
                value[-trailing_count:],
            ):
                bind_assignment_target(environment, item, item_value)

    def merge_environments(environments: list[dict[str, object]]) -> dict[str, object]:
        if not environments:
            return {}
        common_names = set(environments[0])
        for environment in environments[1:]:
            common_names &= set(environment)
        return {
            name: environments[0][name]
            for name in common_names
            if all(
                type(environment[name]) is type(environments[0][name])
                and environment[name] == environments[0][name]
                for environment in environments[1:]
            )
        }

    def inspect_function_header(
        statement: ast.FunctionDef | ast.AsyncFunctionDef,
        environment: dict[str, object],
    ) -> None:
        for decorator in statement.decorator_list:
            inspect_expression(decorator, environment)
        positional = statement.args.posonlyargs + statement.args.args + statement.args.kwonlyargs
        for argument in positional:
            inspect_expression(argument.annotation, environment)
        if statement.args.vararg is not None:
            inspect_expression(statement.args.vararg.annotation, environment)
        if statement.args.kwarg is not None:
            inspect_expression(statement.args.kwarg.annotation, environment)
        for default in statement.args.defaults:
            inspect_expression(default, environment)
        for default in statement.args.kw_defaults:
            inspect_expression(default, environment)
        inspect_expression(statement.returns, environment)

    def analyze_block(
        statements: list[ast.stmt],
        initial_environment: dict[str, object],
    ) -> dict[str, object]:
        environment = dict(initial_environment)
        for statement in statements:
            if isinstance(statement, ast.Assign):
                inspect_expression(statement.value, environment)
                value = static_value(statement.value, environment)
                add_projection(value)
                for target in statement.targets:
                    bind_assignment_target(environment, target, value)
            elif isinstance(statement, ast.AnnAssign):
                inspect_expression(statement.annotation, environment)
                inspect_expression(statement.value, environment)
                value = static_value(statement.value, environment) if statement.value is not None else None
                add_projection(value)
                bind_assignment_target(environment, statement.target, value)
            elif isinstance(statement, ast.AugAssign):
                inspect_expression(statement.target, environment)
                inspect_expression(statement.value, environment)
                combined = ast.BinOp(left=statement.target, op=statement.op, right=statement.value)
                value = static_value(combined, environment)
                add_projection(value)
                if isinstance(statement.target, ast.Name):
                    bind_name(environment, statement.target.id, value)
                else:
                    invalidate_target(environment, statement.target)
            elif isinstance(statement, ast.Expr):
                inspect_expression(statement.value, environment)
            elif isinstance(statement, (ast.Return, ast.Yield, ast.YieldFrom)):
                inspect_expression(statement.value, environment)
            elif isinstance(statement, ast.Raise):
                inspect_expression(statement.exc, environment)
                inspect_expression(statement.cause, environment)
            elif isinstance(statement, ast.Assert):
                inspect_expression(statement.test, environment)
                inspect_expression(statement.msg, environment)
            elif isinstance(statement, ast.Delete):
                for target in statement.targets:
                    invalidate_target(environment, target)
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                inspect_function_header(statement, environment)
                analyze_block(statement.body, {})
                environment.pop(statement.name, None)
            elif isinstance(statement, ast.ClassDef):
                for base in statement.bases:
                    inspect_expression(base, environment)
                for keyword in statement.keywords:
                    inspect_expression(keyword.value, environment)
                for decorator in statement.decorator_list:
                    inspect_expression(decorator, environment)
                analyze_block(statement.body, {})
                environment.pop(statement.name, None)
            elif isinstance(statement, ast.If):
                inspect_expression(statement.test, environment)
                body_environment = analyze_block(statement.body, environment)
                else_environment = analyze_block(statement.orelse, environment)
                environment = merge_environments([body_environment, else_environment])
            elif isinstance(statement, (ast.For, ast.AsyncFor)):
                inspect_expression(statement.iter, environment)
                body_seed = dict(environment)
                invalidate_target(body_seed, statement.target)
                body_environment = analyze_block(statement.body, body_seed)
                else_environment = analyze_block(statement.orelse, environment)
                environment = merge_environments([environment, body_environment, else_environment])
            elif isinstance(statement, ast.While):
                inspect_expression(statement.test, environment)
                body_environment = analyze_block(statement.body, environment)
                else_environment = analyze_block(statement.orelse, environment)
                environment = merge_environments([environment, body_environment, else_environment])
            elif isinstance(statement, (ast.With, ast.AsyncWith)):
                body_seed = dict(environment)
                for item in statement.items:
                    inspect_expression(item.context_expr, environment)
                    if item.optional_vars is not None:
                        invalidate_target(body_seed, item.optional_vars)
                body_environment = analyze_block(statement.body, body_seed)
                environment = merge_environments([environment, body_environment])
            elif isinstance(statement, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                body_environment = analyze_block(statement.body, environment)
                exit_environments = [body_environment]
                for handler in statement.handlers:
                    handler_environment = dict(environment)
                    inspect_expression(handler.type, handler_environment)
                    if handler.name:
                        handler_environment.pop(handler.name, None)
                    exit_environments.append(analyze_block(handler.body, handler_environment))
                if statement.orelse:
                    exit_environments.append(analyze_block(statement.orelse, body_environment))
                merged = merge_environments(exit_environments)
                environment = analyze_block(statement.finalbody, merged)
            elif isinstance(statement, ast.Match):
                inspect_expression(statement.subject, environment)
                case_environments = [dict(environment)]
                for case in statement.cases:
                    case_environment = dict(environment)
                    inspect_expression(case.guard, case_environment)
                    case_environments.append(analyze_block(case.body, case_environment))
                environment = merge_environments(case_environments)
            elif isinstance(statement, (ast.Import, ast.ImportFrom)):
                for alias in statement.names:
                    environment.pop(alias.asname or alias.name.split(".", 1)[0], None)
            elif isinstance(statement, (ast.Global, ast.Nonlocal)):
                for name in statement.names:
                    environment.pop(name, None)
            else:
                for _, field_value in ast.iter_fields(statement):
                    if isinstance(field_value, ast.expr):
                        inspect_expression(field_value, environment)
                    elif isinstance(field_value, list):
                        for item in field_value:
                            if isinstance(item, ast.expr):
                                inspect_expression(item, environment)
        return environment

    analyze_block(tree.body, {})
    add_protected_literal_fragment_projection()
    return sorted(projections)


def validate_access_url_policy(errors: list[str], narrative_only_root: str | None) -> None:
    if narrative_only_root is None:
        return
    public_root = "https://github.com/lowelltwong-alt/public-example"
    allowed_roots = {public_root, narrative_only_root} | STRUCTURED_PRIVATE_ACCESS_URLS
    repository_name = narrative_only_root.rsplit("/", 1)[-1]
    encoded_repository_name = repository_name.replace("-", "%2D")
    html_encoded_deep_url = (
        narrative_only_root.replace("https://", "https:&#47;&#47;").replace("-", "&#45;")
        + "&#47;tree&#47;secret"
    )
    backslash_escaped_deep_url = narrative_only_root.replace("/", r"\/") + r"\/tree\/secret"
    unicode_encoded_deep_url = "".join(
        f"\\u{ord(character):04x}" for character in f"{narrative_only_root}/tree/secret"
    )
    mixed_case_unicode_deep_url = "".join(
        f"\\u{ord(character):04X}" for character in f"{narrative_only_root}/tree/secret"
    )
    nested_unicode_deep_url = unicode_encoded_deep_url.replace(r"\u002f", r"\u005cu002f")
    yaml_hex_encoded_deep_url = "".join(
        f"\\x{ord(character):02x}" for character in f"{narrative_only_root}/tree/secret"
    )
    mixed_case_yaml_hex_deep_url = "".join(
        f"\\x{ord(character):02X}" for character in f"{narrative_only_root}/tree/secret"
    )
    nested_yaml_hex_deep_url = yaml_hex_encoded_deep_url.replace(r"\x2f", r"\x5cx2f")
    yaml_long_unicode_deep_url = "".join(
        f"\\U{ord(character):08x}" for character in f"{narrative_only_root}/tree/secret"
    )
    mixed_yaml_numeric_deep_url = "".join(
        (
            f"\\x{ord(character):02x}"
            if index % 3 == 0
            else f"\\u{ord(character):04x}"
            if index % 3 == 1
            else f"\\U{ord(character):08x}"
        )
        for index, character in enumerate(f"{narrative_only_root}/tree/secret")
    )
    cross_family_nested_deep_url = yaml_hex_encoded_deep_url.replace(
        r"\x2f",
        r"\u005cx2f",
    )
    escaped_numeric_prefix_deep_url = yaml_hex_encoded_deep_url.replace(r"\x", r"\\x")
    line_split = f"{narrative_only_root}/tree/secret".index("github.com") + 3
    yaml_line_continued_deep_url = (
        f"{narrative_only_root}/tree/secret"[:line_split]
        + "\\\n    "
        + f"{narrative_only_root}/tree/secret"[line_split:]
    )
    encoded_name = repository_name.replace("-", "%2D", 1)
    backslash_separator_deep_url = (
        f"https:\\\\github.com\\{GITHUB_OWNER}\\{encoded_name}\\tree\\secret"
    )
    single_backslash_scheme_deep_url = (
        f"https:\\github.com\\{GITHUB_OWNER}\\{encoded_name}\\tree\\secret"
    )
    scheme_without_slashes_deep_url = (
        f"https:github.com\\{GITHUB_OWNER}\\{encoded_name}\\tree\\secret"
    )
    percent_backslash_deep_url = backslash_separator_deep_url.replace("\\", "%5C")
    nested_percent_backslash_deep_url = percent_backslash_deep_url.replace("%", "%25")
    protocol_relative_backslash_deep_url = (
        f"\\\\github.com\\{GITHUB_OWNER}\\{encoded_name}\\tree\\secret"
    )
    cases = (
        (Path("README.md"), narrative_only_root, True, "narrative-only Markdown disclosure"),
        (Path("registry/example.json"), narrative_only_root, False, "narrative-only structured disclosure"),
        (Path("example.txt"), narrative_only_root, False, "narrative-only text disclosure"),
        (Path("example.toml"), narrative_only_root, False, "narrative-only TOML disclosure"),
        (Path("example.html"), narrative_only_root, False, "narrative-only HTML disclosure"),
        (Path("example.rst"), narrative_only_root, False, "narrative-only reStructuredText disclosure"),
        (Path("README.md"), f"{narrative_only_root}/tree/secret-review-branch", False, "narrative-only branch suffix"),
        (Path("README.md"), f"{narrative_only_root}/blob/secret/private.md", False, "narrative-only blob suffix"),
        (Path("README.md"), f"{narrative_only_root}?ref=secret", False, "narrative-only query suffix"),
        (Path("README.md"), f"{narrative_only_root}#secret", False, "narrative-only fragment suffix"),
        (Path("README.md"), f"{narrative_only_root}%2Ftree%2Fsecret", False, "narrative-only encoded path suffix"),
        (Path("README.md"), f"{narrative_only_root}.git", False, "narrative-only git suffix"),
        (Path("README.md"), f"https://GITHUB.com/{GITHUB_OWNER}/{encoded_repository_name}/tree/secret", False, "narrative-only encoded alternate form"),
        (Path("README.md"), html_encoded_deep_url, False, "narrative-only HTML character-reference form"),
        (Path("README.md"), backslash_escaped_deep_url, False, "narrative-only Markdown backslash-escaped form"),
        (Path("README.md"), unicode_encoded_deep_url, False, "narrative-only serialized Unicode form"),
        (Path("README.md"), mixed_case_unicode_deep_url, False, "narrative-only mixed-case Unicode form"),
        (Path("README.md"), nested_unicode_deep_url, False, "narrative-only nested Unicode form"),
        (Path("README.md"), yaml_hex_encoded_deep_url, False, "narrative-only YAML hex form"),
        (Path("README.md"), mixed_case_yaml_hex_deep_url, False, "narrative-only mixed-case YAML hex form"),
        (Path("README.md"), nested_yaml_hex_deep_url, False, "narrative-only nested YAML hex form"),
        (Path("README.md"), yaml_long_unicode_deep_url, False, "narrative-only YAML long Unicode form"),
        (Path("README.md"), mixed_yaml_numeric_deep_url, False, "narrative-only mixed YAML numeric form"),
        (Path("README.md"), cross_family_nested_deep_url, False, "narrative-only cross-family nested form"),
        (Path("README.md"), escaped_numeric_prefix_deep_url, False, "narrative-only escaped numeric prefix form"),
        (Path("README.md"), yaml_line_continued_deep_url, False, "narrative-only YAML line continuation form"),
        (Path("README.md"), backslash_separator_deep_url, False, "narrative-only browser backslash separators"),
        (Path("README.md"), single_backslash_scheme_deep_url, False, "narrative-only single backslash scheme separator"),
        (Path("README.md"), scheme_without_slashes_deep_url, False, "narrative-only missing scheme separators"),
        (Path("README.md"), percent_backslash_deep_url, False, "narrative-only percent-encoded backslash separators"),
        (Path("README.md"), nested_percent_backslash_deep_url, False, "narrative-only nested percent backslash separators"),
        (Path("README.md"), protocol_relative_backslash_deep_url, False, "narrative-only protocol-relative backslash separators"),
        (Path("README.md"), narrative_only_root.replace("https://github.com", "https://www.github.com") + "/tree/secret", False, "narrative-only www host alias"),
        (Path("README.md"), narrative_only_root.replace("github.com", "github.com.:443") + "/tree/secret", False, "narrative-only host authority variant"),
        (Path("README.md"), narrative_only_root.removeprefix("https:") + "/tree/secret", False, "narrative-only protocol-relative form"),
        (Path("README.md"), narrative_only_root.replace("https://", "http://") + "/tree/secret", False, "narrative-only insecure scheme"),
        (Path("README.md"), f"{narrative_only_root}/", False, "narrative-only trailing slash"),
        (Path("registry/example.json"), DAD_URL, True, "DAD structured private route"),
        (Path("README.md"), f"{public_root}/blob/abc123/README.md", True, "public repository blob path"),
        (Path("README.md"), f"{public_root}/tree/main", True, "public repository tree path"),
        (Path("README.md"), f"{public_root}-evil/tree/main", False, "repository segment boundary"),
        (Path("README.md"), f"{public_root}/../{repository_name}/tree/secret", False, "dot-segment private route"),
        (Path("README.md"), "https://github.com/lowelltwong-alt/unknown-private", False, "unknown private route"),
    )
    for relative, url, expected, label in cases:
        extracted = list(iter_owned_github_urls(f"prefix {url} suffix"))
        normalized_url = normalize_release_text(url)
        if extracted != [normalized_url]:
            fail(errors, f"access URL extraction regression: {label}")
        elif release_url_allowed(relative, extracted[0], allowed_roots, narrative_only_root) is not expected:
            fail(errors, f"access URL policy regression: {label}")
    structured_private_example = "https://github.com/lowelltwong-alt/private-access-example"
    structured_private_deep = f"{structured_private_example}/tree/secret-review-branch"
    if release_url_allowed(
        Path("registry/example.json"),
        structured_private_deep,
        allowed_roots | {structured_private_example},
        narrative_only_root,
        {structured_private_example},
    ):
        fail(errors, "structured private deep-route policy regression")
    encoded_identifier = "".join(f"\\u{ord(character):04x}" for character in repository_name)
    if not has_noncanonical_narrative_identifier(encoded_identifier, narrative_only_root):
        fail(errors, "serialized narrative-only identifier regression")
    yaml_encoded_identifier = "".join(f"\\x{ord(character):02x}" for character in repository_name)
    if not has_noncanonical_narrative_identifier(yaml_encoded_identifier, narrative_only_root):
        fail(errors, "YAML-serialized narrative-only identifier regression")
    percent_encoded_identifier = "".join(
        f"%{ord(character):02X}" for character in repository_name
    )
    if not has_noncanonical_narrative_identifier(percent_encoded_identifier, narrative_only_root):
        fail(errors, "percent-encoded narrative-only identifier regression")
    if normalize_release_text(r"\U00110000") != r"\U00110000":
        fail(errors, "out-of-range serialized Unicode regression")

    private_deep_url = f"{narrative_only_root}/tree/secret"
    octal_parts = [f"\\{ord(character):03o}" for character in private_deep_url]
    octal_deep_url = "".join(octal_parts)
    octal_split = len(octal_parts) // 2
    first_octal_half = "".join(octal_parts[:octal_split])
    second_octal_half = "".join(octal_parts[octal_split:])
    named_unicode_deep_url = private_deep_url.replace("-", r"\N{HYPHEN-MINUS}")
    character_call_source = (
        'dash = chr(45)\n' + 'candidate = "'
        + private_deep_url.replace("-", '" + dash + "')
        + '"'
    )
    python_literal_cases = (
        (f'candidate = "{octal_deep_url}"', "Python octal string"),
        (f'candidate = b"{octal_deep_url}"', "Python octal bytes"),
        (f'candidate = f"{octal_deep_url}"', "Python octal static f-string"),
        (
            f'candidate = "{first_octal_half}" "{second_octal_half}"',
            "Python adjacent octal strings",
        ),
        (
            f'candidate = "{first_octal_half}" + "{second_octal_half}"',
            "Python constant octal concatenation",
        ),
        (
            'candidate = f"'
            + first_octal_half
            + "{''}"
            + second_octal_half
            + '"',
            "Python constant-field octal f-string",
        ),
        (
            'candidate = f"'
            + first_octal_half
            + "{'' + ''}"
            + second_octal_half
            + '"',
            "Python constant-expression octal f-string",
        ),
        (
            'candidate = f"'
            + first_octal_half
            + "{runtime_value}"
            + second_octal_half
            + '"',
            "Python conservatively empty dynamic-field f-string",
        ),
        (
            f'first = "{first_octal_half}"\n'
            + 'middle = ""\n'
            + f'second = "{second_octal_half}"\n'
            + 'candidate = first + middle + second',
            "Python name-bound constant concatenation",
        ),
        (
            'first = "superseded"\n'
            + f'first = "{first_octal_half}"\n'
            + f'second = "{second_octal_half}"\n'
            + 'candidate = first + second',
            "Python latest-assignment concatenation",
        ),
        (
            f'first = "{first_octal_half}"\n'
            + 'alias = first\n'
            + f'second = "{second_octal_half}"\n'
            + 'candidate = alias + second',
            "Python materialized alias concatenation",
        ),
        (
            f'first = "{first_octal_half}"\n'
            + 'if runtime_condition:\n    middle = ""\nelse:\n    middle = ""\n'
            + f'second = "{second_octal_half}"\n'
            + 'candidate = first + middle + second',
            "Python identical-branch concatenation",
        ),
        (
            f'first = "{first_octal_half}"\n'
            + f'second = "{second_octal_half}"\n'
            + 'candidate = f"{first}{second}"',
            "Python name-bound f-string",
        ),
        (
            f'first = "{first_octal_half}"\n'
            + 'poison = lambda: (first := "superseded")\n'
            + f'second = "{second_octal_half}"\n'
            + 'candidate = first + second',
            "Python lambda-local walrus isolation",
        ),
        (
            'build = lambda: ('
            + f'(first := "{first_octal_half}"), '
            + f'(second := "{second_octal_half}"), '
            + 'first + second)',
            "Python lambda walrus descendant reprojection",
        ),
        (
            'first = ""\n'
            + 'build = lambda ignored=('
            + f'first := "superseded" if first else "{first_octal_half}"'
            + '): ignored\n'
            + f'second = "{second_octal_half}"\n'
            + 'candidate = first + second',
            "Python single-evaluation lambda default",
        ),
        (
            f'prefix = "{first_octal_half}"\n'
            + f'suffix = "{second_octal_half}"\n'
            + 'first, second = (prefix, suffix)\n'
            + 'candidate = first + second',
            "Python tuple-unpacked constant concatenation",
        ),
        (
            f'pair = ("{first_octal_half}", "{second_octal_half}") * 1\n'
            + 'first, second = pair\n'
            + 'candidate = first + second',
            "Python multiplied tuple-unpacked concatenation",
        ),
        (
            f'parts = ("{first_octal_half}", "{second_octal_half}")\n'
            + 'candidate = "".join(parts)',
            "Python name-bound constant string join",
        ),
        (
            f'parts = [b"{first_octal_half}", b"{second_octal_half}"]\n'
            + 'candidate = b"".join(parts)',
            "Python name-bound constant bytes join",
        ),
        (
            f'pair = ("{first_octal_half}", "{second_octal_half}") * True\n'
            + 'first, second = pair\n'
            + 'candidate = first + second',
            "Python Boolean-right-multiplied tuple concatenation",
        ),
        (
            f'pair = True * ("{first_octal_half}", "{second_octal_half}")\n'
            + 'first, second = pair\n'
            + 'candidate = first + second',
            "Python Boolean-left-multiplied tuple concatenation",
        ),
        (
            f'first = "{first_octal_half}" * True\n'
            + f'second = "{second_octal_half}"\n'
            + 'candidate = first + second',
            "Python Boolean-right-multiplied string concatenation",
        ),
        (
            f'first = True * "{first_octal_half}"\n'
            + f'second = "{second_octal_half}"\n'
            + 'candidate = first + second',
            "Python Boolean-left-multiplied string concatenation",
        ),
        (
            f'pair = ("{first_octal_half}", "{second_octal_half}") * +1\n'
            + 'first, second = pair\n'
            + 'candidate = first + second',
            "Python unary-plus-right-multiplied tuple concatenation",
        ),
        (
            f'pair = +1 * ("{first_octal_half}", "{second_octal_half}")\n'
            + 'first, second = pair\n'
            + 'candidate = first + second',
            "Python unary-plus-left-multiplied tuple concatenation",
        ),
        (
            f'pair = ("{first_octal_half}", "{second_octal_half}") * +True\n'
            + 'first, second = pair\n'
            + 'candidate = first + second',
            "Python unary-plus-Boolean tuple concatenation",
        ),
        (
            f'pair = ("{first_octal_half}", "{second_octal_half}") * (not False)\n'
            + 'first, second = pair\n'
            + 'candidate = first + second',
            "Python Boolean-not tuple concatenation",
        ),
        (
            f'pair = ("{first_octal_half}", "{second_octal_half}") * ~(-2)\n'
            + 'first, second = pair\n'
            + 'candidate = first + second',
            "Python bitwise-invert tuple concatenation",
        ),
        (character_call_source, "Python static-character concatenation"),
        (f'candidate = "{named_unicode_deep_url}"', "Python named-Unicode string"),
    )
    for source, label in python_literal_cases:
        parse_errors: list[str] = []
        projections = python_literal_projections(source, Path("example.py"), parse_errors)
        if parse_errors or private_deep_url not in projections:
            fail(errors, f"Python literal privacy projection regression: {label}")

    protected_split = 6
    protected_first = repository_name[:protected_split]
    protected_rest = repository_name[protected_split:]
    protected_words = repository_name.split("-")
    character_fragment_source = (
        'dash = chr(45)\nparts = ('
        + ", ".join(f'"{word}"' for word in protected_words)
        + ',)\ncandidate = "{}".format(dash).join(parts)'
    )
    protected_fragment_cases = (
        (
            f'parts = ("{protected_first}", "{protected_rest}")\n'
            + 'candidate = "".join(item for item in parts)',
            "generator join",
        ),
        (
            f'parts = ("{protected_first}", "{protected_rest}")\n'
            + 'candidate = "".join(*[parts])',
            "starred join argument",
        ),
        (
            f'parts = ("{protected_first}", "{protected_rest}")\n'
            + 'candidate = "".join(parts[:])',
            "sliced join iterable",
        ),
        (
            f'candidate = "{{}}{{}}".format("{protected_first}", "{protected_rest}")',
            "string format call",
        ),
        (
            'candidate = "{left}{right}".format_map('
            + f'{{"left": "{protected_first}", "right": "{protected_rest}"}})',
            "string format-map call",
        ),
        (
            f'candidate = "%s%s" % ("{protected_first}", "{protected_rest}")',
            "percent formatting",
        ),
        (
            f'candidate = "{protected_first}X{protected_rest}".replace("X", "")',
            "string replacement",
        ),
        (
            f'parts = ("{protected_first}", "{protected_rest}")\n'
            + 'candidate = parts[0].__add__(parts[1])',
            "indexed direct-add call",
        ),
        (
            f'first = "{protected_first}"\n'
            + f'second = "{protected_rest}"\n'
            + 'candidate = (first if 1 == 1 else "") + (second or "")',
            "comparison and Boolean selection",
        ),
        (character_fragment_source, "static character through formatted join"),
    )
    for source, label in protected_fragment_cases:
        fragment_errors: list[str] = []
        fragment_projections = python_literal_projections(
            source,
            Path("example.py"),
            fragment_errors,
            protected_identifier=repository_name,
        )
        if fragment_errors or repository_name not in fragment_projections:
            fail(errors, f"Python protected-fragment projection regression: {label}")

    raw_encoded_identifier = "".join(
        f"\\x{ord(character):02x}" for character in repository_name
    )
    raw_fragment_source = f'candidate = r"{raw_encoded_identifier}"'
    raw_fragment_projections = python_literal_projections(
        raw_fragment_source,
        Path("example.py"),
        errors,
        protected_identifier=repository_name,
    )
    if repository_name in raw_fragment_projections:
        fail(errors, "Python raw literal component-projection regression")
    if not has_noncanonical_narrative_identifier(
        raw_fragment_source,
        narrative_only_root,
    ):
        fail(errors, "Python raw literal conservative source-policy regression")

    huge_multiplier = "18446744073709551616"
    for source, label in (
        (f"candidate = () * {huge_multiplier}", "empty tuple multiplied on the right"),
        (f"candidate = {huge_multiplier} * ()", "empty tuple multiplied on the left"),
    ):
        parse_errors = []
        python_literal_projections(source, Path("example.py"), parse_errors)
        if parse_errors:
            fail(errors, f"Python bounded multiplication regression: {label}")

    huge_character = "9" * 100
    for source, label in (
        (f"candidate = chr({huge_character})", "oversized positive character"),
        (f"candidate = chr(-{huge_character})", "oversized negative character"),
    ):
        character_errors: list[str] = []
        python_literal_projections(source, Path("example.py"), character_errors)
        if character_errors:
            fail(errors, f"Python bounded character regression: {label}")

    unresolved_multiplier_source = (
        f'pair = ("{first_octal_half}", "{second_octal_half}") * (2 ** 0)\n'
        + 'first, second = pair\n'
        + 'candidate = first + second'
    )
    unresolved_errors: list[str] = []
    unresolved_projections = python_literal_projections(
        unresolved_multiplier_source,
        Path("example.py"),
        unresolved_errors,
    )
    if not unresolved_errors and private_deep_url not in unresolved_projections:
        fail(errors, "Python unresolved sequence multiplier fail-closed regression")

    raw_projections = python_literal_projections(
        f'candidate = r"{octal_deep_url}"',
        Path("example.py"),
        errors,
    )
    if private_deep_url in raw_projections:
        fail(errors, "Python raw-string privacy projection regression")
    scope_control_cases = (
        (
            f'first = "{first_octal_half}"\n'
            + 'def build(first):\n'
            + f'    second = "{second_octal_half}"\n'
            + '    candidate = first + second',
            "function parameter shadow",
        ),
        (
            'def first_scope():\n'
            + f'    first = "{first_octal_half}"\n'
            + 'def second_scope():\n'
            + f'    second = "{second_octal_half}"\n'
            + '    candidate = first + second',
            "sibling function isolation",
        ),
        (
            'first = second\nsecond = first\ncandidate = first + second',
            "forward-reference cycle",
        ),
    )
    for source, label in scope_control_cases:
        control_errors: list[str] = []
        projections = python_literal_projections(source, Path("example.py"), control_errors)
        if control_errors or private_deep_url in projections:
            fail(errors, f"Python scope isolation regression: {label}")
    malformed_errors: list[str] = []
    python_literal_projections(
        r'candidate = "\N{NOT A UNICODE NAME}"',
        Path("example.py"),
        malformed_errors,
    )
    if not malformed_errors:
        fail(errors, "malformed Python literal must fail closed")
    oversized_format_errors: list[str] = []
    python_literal_projections(
        'candidate = f"{\'\':'
        + str(MAX_PYTHON_STATIC_PROJECTION_CHARS + 1)
        + '}"',
        Path("example.py"),
        oversized_format_errors,
    )
    if not oversized_format_errors:
        fail(errors, "oversized Python static format must fail closed")


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
    fail_if(len(private_routes) != 1, "DAD must remain the sole structured private evidence route")
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


def validate_markdown_projection(
    registry: dict,
    narrative_only_root: str | None,
    errors: list[str],
) -> None:
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
    markers = ["AI_FRONT_DOOR.md", DAD_URL, "Deterministic validation"]
    if narrative_only_root is not None:
        markers.append(narrative_only_root)
    for marker in markers:
        if marker not in readme:
            fail(errors, f"README missing required synchronized marker: {marker}")


def validate_release_text(
    registry: dict,
    narrative_only_root: str | None,
    errors: list[str],
) -> None:
    tracked_texts = tracked_utf8_text_files(errors)
    forbidden = [re.compile(pattern) for pattern in (r"\b[A-Z]:[\\/]", r"/Users/", r"\\\\Users\\", r"\.agent-governance", r"refs/heads/", r"scratch/[A-Za-z0-9_.-]+", r"(?i:(?:api[_-]?key|secret|token)\s*[:=])")]
    bounded_terms = {"deployed": ("no ", "not ", "unasserted", "does not"), "production": ("no ", "not ", "unasserted", "non-production"), "autonomous": ("no ", "not ", "never", "bounded", "unasserted"), "headless": ("authorized", "unasserted", "private"), "swarm": ("bounded", "never", "no ", "not "), "implemented": ("only if", "source-owned"), "tested": ("source-owned", "not ", "no ")}
    public_surface_paths = [
        ROOT / "README.md", ROOT / "AI_FRONT_DOOR.md", ROOT / "PUBLIC_REPO_MAP.md", ROOT / "PORTABILITY_MAP.md",
        ROOT / "ai" / "AI_PORTFOLIO_TOC.md", ROOT / "ai" / "BUILD_PHILOSOPHY.md", REGISTRY_PATH, CAPABILITIES_PATH,
        *sorted(RELEASES_DIR.glob("*.json")),
    ]
    hidden_lane_phrases = ("protected local", "local candidate", "unpublished Intake", "unpublished local", "public-main source")
    for public_path in public_surface_paths:
        public_text = normalize_release_text(public_path.read_text(encoding="utf-8"))
        for phrase in hidden_lane_phrases:
            if re.search(re.escape(phrase), public_text, re.I):
                fail(errors, f"public surface hidden-lane hint '{phrase}' in {public_path.relative_to(ROOT)}")
    allowed_roots = (
        {repo["canonical_url"] for repo in registry["repositories"]}
        | STRUCTURED_PRIVATE_ACCESS_URLS
    )
    if narrative_only_root is not None:
        allowed_roots.add(narrative_only_root)
    private_roots = set(STRUCTURED_PRIVATE_ACCESS_URLS)
    if narrative_only_root is not None:
        private_roots.add(narrative_only_root)
    private_roots_by_name = {
        unquote(urlsplit(root).path).rstrip("/").rsplit("/", 1)[-1].casefold(): root
        for root in private_roots
    }
    narrative_only_identifier = (
        unquote(urlsplit(narrative_only_root).path).rstrip("/").rsplit("/", 1)[-1]
        if narrative_only_root is not None
        else None
    )
    meta_language_paths = {Path("scripts/validate_profile_package.py")}
    for path, text in tracked_texts:
        relative = path.relative_to(ROOT)
        is_meta_language = relative in meta_language_paths or relative.parts[:2] == ("registry", "schemas")
        normalized_text = normalize_release_text(text)
        urls = list(iter_owned_github_urls(text))
        # The raw-source view is intentionally conservative: serialized private
        # identifiers remain prohibited even when they occur inside Python raw literals.
        privacy_views = [(text, True)]
        if relative.suffix.lower() == ".py":
            python_projections = python_literal_projections(
                text,
                relative,
                errors,
                protected_identifier=narrative_only_identifier,
            )
            if python_projections:
                privacy_views.append(("\n".join(python_projections), False))
        for privacy_text, normalize_serialized in privacy_views:
            normalized_privacy_text = (
                normalize_release_text(privacy_text)
                if normalize_serialized
                else privacy_text
            )
            privacy_urls = list(
                iter_owned_github_urls(
                    privacy_text,
                    normalize_serialized=normalize_serialized,
                )
            )
            for url in privacy_urls:
                parsed_result = owned_github_url_parts(url)
                if parsed_result is None:
                    continue
                _, segments, _ = parsed_result
                private_root = private_roots_by_name.get(segments[1].casefold())
                if private_root is not None and not release_url_allowed(
                    relative,
                    url,
                    allowed_roots,
                    narrative_only_root,
                ):
                    fail(errors, f"tracked text violates a private repository boundary: {relative}")
            if "Digital-Assett-Directory" in normalized_privacy_text and DAD_URL not in normalized_privacy_text:
                fail(errors, f"release text has a non-canonical DAD identifier: {relative}")
            if narrative_only_root is not None and has_noncanonical_narrative_identifier(
                privacy_text,
                narrative_only_root,
                normalize_serialized=normalize_serialized,
            ):
                fail(errors, f"release text has a non-canonical narrative-only identifier: {relative}")
        if is_meta_language:
            continue  # Private boundaries apply above; claim fixtures remain meta-language.
        for pattern in forbidden:
            if pattern.search(normalized_text):
                fail(errors, f"release text privacy scan: {relative} matched {pattern.pattern}")
        for url in urls:
            if not release_url_allowed(relative, url, allowed_roots, narrative_only_root):
                fail(errors, f"release text has undisclosed repository URL: {relative}")
        if relative in {REGISTRY_PATH.relative_to(ROOT), CAPABILITIES_PATH.relative_to(ROOT), Path("registry/portable-workflow-patterns.json")}:
            continue  # Structured DAD and swarm constraints are enforced by schema and cross-reference checks.
        for term, contexts in bounded_terms.items():
            for match in re.finditer(term, normalized_text, re.I):
                window = normalized_text[max(0, match.start() - 120): match.end() + 120].lower()
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
    narrative_only_root = load_narrative_only_access_url(errors)
    validate_access_url_policy(errors, narrative_only_root)
    validate_cross_references(registry, capabilities, receipt, receipts, errors)
    validate_markdown_projection(registry, narrative_only_root, errors)
    validate_release_text(registry, narrative_only_root, errors)
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
