#!/usr/bin/env python3
"""Fail-closed validator for the public profile routing package."""

from __future__ import annotations

import argparse
import ast
import base64
import binascii
import hashlib
import json
import re
import string
import subprocess
import sys
import unicodedata
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
MAX_STATIC_LANGUAGE_PROJECTION_CHARS = 65_536
MAX_STATIC_LANGUAGE_ENCODED_CHARS = 131_072
MAX_STATIC_LANGUAGE_BASE64_CHARS = 87_384
MAX_EXACT_JAVASCRIPT_INTEGER = 9_007_199_254_740_991
URL_CANDIDATE_PATTERN = re.compile(
    r"(?i)(?=((?:https?:|[\\/]{2})[^\s<>\[\]()\"'`]+))"
)
MARKDOWN_BACKSLASH_ESCAPE = re.compile(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]^_`{|}~])")
SERIALIZED_CODEPOINT_ESCAPES = (
    re.compile(r"\\x([0-9A-Fa-f]{2})"),
    re.compile(r"\\u([0-9A-Fa-f]{4})"),
    re.compile(r"\\U([0-9A-Fa-f]{8})"),
)
SERIALIZED_NUMERIC_ESCAPE_PREFIX = re.compile(
    r"\\+(?=(?:[xuU][0-9A-Fa-f]|u\{[0-9A-Fa-f]))"
)
SERIALIZED_NAMED_UNICODE_ESCAPE = re.compile(r"\\N\{([^{}]{1,256})\}")
SERIALIZED_OCTAL_ESCAPE = re.compile(r"\\([0-7]{1,3})")
SERIALIZED_BRACED_UNICODE_ESCAPE = re.compile(r"\\u\{([0-9A-Fa-f]{1,6})\}")
POWERSHELL_BRACED_UNICODE_ESCAPE = re.compile(r"`u\{([0-9A-Fa-f]{1,6})\}")
POWERSHELL_ESCAPED_LINE_BREAK = re.compile(r"`(?:\r\n?|\n)[ \t]*")
POWERSHELL_BACKTICK_ESCAPE = re.compile(r"`(.)", re.S)
YAML_ESCAPED_LINE_BREAK = re.compile(r"\\(?:\r\n?|\n)[ \t]*")
QUOTED_TEXT_LITERAL = re.compile(
    r'''(?s)"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'|`((?:\\.|[^`\\])*)`'''
)

STATIC_JS_CHAR_CALL = re.compile(
    r"(?is)\bString\s*\.\s*(fromCharCode|fromCodePoint)\s*\(([^()]*)\)"
)
STATIC_JS_APPLY_CALL = re.compile(
    r"(?is)\bString\s*\.\s*(fromCharCode|fromCodePoint)\s*\.\s*apply\s*"
    r"\(\s*[^,()]{1,256},\s*\[([^\[\]()]*)\]\s*\)"
)
STATIC_JS_ATOB_CALL = re.compile(
    r"(?is)\batob\s*\(\s*(['\"\x60])(.*?)\1\s*\)"
)
STATIC_JS_BUFFER_CALL = re.compile(
    r"(?is)\bBuffer\s*\.\s*from\s*\(\s*(['\"\x60])(.*?)\1\s*,\s*"
    r"(['\"\x60])(base64|base64url|hex)\3\s*\)"
)
STATIC_JS_TEXT_DECODER_CALL = re.compile(
    r"(?s)\bnew\s+TextDecoder\s*\(\s*(?:(['\"])([^'\"]{0,64})\1)?\s*\)"
    r"\s*\.\s*decode\s*\(\s*new\s+"
    r"(Uint8Array|Uint8ClampedArray|Int8Array)\s*\(\s*\[([^\[\]()]*)\]\s*\)\s*\)"
)
STATIC_JS_TEXT_DECODER_MARKER = re.compile(
    r"(?s)\bTextDecoder\b"
)
STATIC_PS_CHAR_ARRAY = re.compile(
    r"(?is)\[\s*char\s*\[\s*\]\s*\]\s*(?:@\s*)?\(\s*([^()]*)\s*\)"
)
STATIC_PS_CHAR_CAST = re.compile(
    r"(?is)\[\s*char\s*\](?!\s*\[)\s*([^\s+|;,)]+)"
)
STATIC_PS_ENCODING_CALL = re.compile(
    r"(?is)\[\s*(?:System\.)?Text\.Encoding\s*\]::\s*(ASCII|UTF8)\s*\.\s*"
    r"GetString\s*\(\s*\[\s*byte\s*\[\s*\]\s*\]\s*(?:@\s*)?"
    r"\(\s*([^()]*)\s*\)\s*\)"
)
STATIC_PS_BASE64_CALL = re.compile(
    r"(?is)\[\s*(?:System\.)?Convert\s*\]::\s*FromBase64String\s*"
    r"\(\s*(['\"])(.*?)\1\s*\)"
)
STATIC_PS_CHAR_MARKER = re.compile(r"(?is)\[\s*char(?:\s*\[\s*\])?\s*\]")
STATIC_PS_BYTE_ARRAY_MARKER = re.compile(r"(?is)\[\s*byte\s*\[\s*\]\s*\]")


def executable_code_mask(
    text: str,
    language: str,
    lexical_errors: list[str] | None = None,
) -> bytearray:
    """Mark code starts while excluding bounded comments and literal documentation."""
    mask = bytearray(len(text))
    for position in range(len(mask)):
        mask[position] = 1

    def hide(start: int, end: int) -> None:
        for position in range(start, end):
            mask[position] = 0

    def skip_javascript_string(start: int, delimiter: str) -> int:
        position = start + 1
        while position < len(text):
            if text[position] == "\\":
                position = min(position + 2, len(text))
                continue
            if text[position] == delimiter:
                return position + 1
            position += 1
        return len(text)

    def javascript_closing_parenthesis_is_control_header(
        position: int,
        scope_start: int,
    ) -> bool:
        depth = 1
        cursor = position - 1
        while cursor >= scope_start:
            if text[cursor] == ")":
                depth += 1
            elif text[cursor] == "(":
                depth -= 1
                if depth == 0:
                    prefix = text[scope_start:cursor].rstrip()
                    keyword_match = re.search(
                        r"([A-Za-z_$][A-Za-z0-9_$]*)$",
                        prefix,
                    )
                    return bool(
                        keyword_match
                        and keyword_match.group(1) in {
                            "catch", "for", "if", "switch", "while", "with",
                        }
                    )
            cursor -= 1
        return False

    def javascript_slash_role(position: int, scope_start: int) -> str:
        previous = position - 1
        while previous >= scope_start and text[previous].isspace():
            previous -= 1
        if previous < scope_start:
            return "regex"
        if text[previous] in "([{:;,=!?&|+-*%^~<>":
            return "regex"
        prefix = text[scope_start:position].rstrip()
        keyword_match = re.search(r"([A-Za-z_$][A-Za-z0-9_$]*)$", prefix)
        if (
            keyword_match
            and keyword_match.group(1) in {
                "await", "case", "delete", "do", "else", "in", "instanceof",
                "new", "of", "return", "throw", "typeof", "void", "yield",
            }
        ):
            return "regex"
        if text[previous] == ")":
            return (
                "regex"
                if javascript_closing_parenthesis_is_control_header(previous, scope_start)
                else "division"
            )
        if text[previous] == "}":
            return "ambiguous"
        if text[previous].isalnum() or text[previous] in "_$]'\"":
            return "division"
        return "ambiguous"

    def javascript_regex_end(start: int) -> int | None:
        position = start + 1
        in_character_class = False
        while position < len(text):
            character = text[position]
            if character in {"\r", "\n"}:
                return None
            if character == "\\":
                position = min(position + 2, len(text))
                continue
            if character == "[":
                in_character_class = True
            elif character == "]" and in_character_class:
                in_character_class = False
            elif character == "/" and not in_character_class:
                position += 1
                while position < len(text) and text[position].isalpha():
                    position += 1
                return position
            position += 1
        return None

    def javascript_template_expression_end(start: int) -> int | None:
        depth = 1
        position = start
        while position < len(text):
            if text.startswith("//", position):
                end = text.find("\n", position + 2)
                position = len(text) if end < 0 else end
                continue
            if text.startswith("/*", position):
                end = text.find("*/", position + 2)
                position = len(text) if end < 0 else end + 2
                continue
            if text[position] in {"'", '"'}:
                position = skip_javascript_string(position, text[position])
                continue
            if ord(text[position]) == 96:
                position = skip_javascript_string(position, text[position])
                continue
            if text[position] == "/":
                slash_role = javascript_slash_role(position, start)
                if slash_role == "division":
                    position += 1
                    continue
                if slash_role == "ambiguous" and lexical_errors is not None:
                    lexical_errors.append("ambiguous JavaScript slash expression")
                regex_end = javascript_regex_end(position)
                if regex_end is None:
                    if lexical_errors is not None:
                        lexical_errors.append("ambiguous JavaScript regex literal")
                    return None
                position = regex_end
                continue
            if text[position] == "{":
                depth += 1
            elif text[position] == "}":
                depth -= 1
                if depth == 0:
                    return position
            position += 1
        return None

    index = 0
    while index < len(text):
        if language == "javascript" and ord(text[index]) == 96:
            hide(index, index + 1)
            cursor = index + 1
            raw_start = cursor
            while cursor < len(text):
                if text[cursor] == "\\":
                    cursor = min(cursor + 2, len(text))
                    continue
                if ord(text[cursor]) == 96:
                    hide(raw_start, cursor + 1)
                    index = cursor + 1
                    break
                if text.startswith("${", cursor):
                    hide(raw_start, cursor + 2)
                    expression_start = cursor + 2
                    expression_end = javascript_template_expression_end(expression_start)
                    if expression_end is None:
                        if lexical_errors is not None:
                            lexical_errors.append("ambiguous JavaScript template expression")
                        index = len(text)
                        break
                    expression_mask = executable_code_mask(
                        text[expression_start:expression_end],
                        language,
                        lexical_errors,
                    )
                    mask[expression_start:expression_end] = expression_mask
                    hide(expression_end, expression_end + 1)
                    cursor = expression_end + 1
                    raw_start = cursor
                    continue
                cursor += 1
            else:
                hide(raw_start, len(text))
                index = len(text)
            continue
        if language == "javascript" and text.startswith("//", index):
            end = text.find("\n", index + 2)
            end = len(text) if end < 0 else end
            hide(index, end)
            index = end
            continue
        if language == "javascript" and text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = len(text) if end < 0 else end + 2
            hide(index, end)
            index = end
            continue
        if (
            language == "javascript"
            and text[index] == "/"
        ):
            slash_role = javascript_slash_role(index, 0)
            if slash_role == "division":
                index += 1
                continue
            if slash_role == "ambiguous" and lexical_errors is not None:
                lexical_errors.append("ambiguous JavaScript slash expression")
            regex_end = javascript_regex_end(index)
            if regex_end is None:
                if lexical_errors is not None:
                    lexical_errors.append("ambiguous JavaScript regex literal")
                index += 1
                continue
            hide(index, regex_end)
            index = regex_end
            continue
        if language == "powershell" and text.startswith("<#", index):
            end = text.find("#>", index + 2)
            end = len(text) if end < 0 else end + 2
            hide(index, end)
            index = end
            continue
        if language == "powershell" and text[index] == "#":
            end = text.find("\n", index + 1)
            end = len(text) if end < 0 else end
            hide(index, end)
            index = end
            continue
        quote = text[index]
        if quote not in {"'", '"'}:
            index += 1
            continue
        end = index + 1
        while end < len(text):
            if language == "javascript" and text[end] == "\\":
                end = min(end + 2, len(text))
                continue
            if language == "powershell" and quote == '"' and ord(text[end]) == 96:
                end = min(end + 2, len(text))
                continue
            if text[end] == quote:
                if language == "powershell" and end + 1 < len(text) and text[end + 1] == quote:
                    end += 2
                    continue
                end += 1
                break
            end += 1
        literal = text[index:end]
        if not (language == "powershell" and quote == '"' and "$" in literal):
            hide(index, end)
        index = end
    return mask


def parse_static_integer(token: str, *, language: str) -> int:
    """Parse one bounded JS/PowerShell integer literal without evaluating code."""
    token = token.strip().replace("_", "")
    if len(token) > 64:
        raise ValueError
    pattern = (
        r"[+-]?(?:0[xX][0-9A-Fa-f]+|0[bB][01]+|0[oO][0-7]+|[0-9]+)"
        if language == "javascript"
        else r"[+-]?(?:0[xX][0-9A-Fa-f]+|[0-9]+)"
    )
    if re.fullmatch(pattern, token) is None:
        raise ValueError
    sign = -1 if token.startswith("-") else 1
    unsigned = token.lstrip("+-")
    if unsigned.lower().startswith("0x"):
        value = sign * int(unsigned[2:], 16)
    elif language == "javascript" and unsigned.lower().startswith("0b"):
        value = sign * int(unsigned[2:], 2)
    elif language == "javascript" and unsigned.lower().startswith("0o"):
        value = sign * int(unsigned[2:], 8)
    else:
        value = sign * int(unsigned, 10)
    if language == "javascript" and abs(value) > MAX_EXACT_JAVASCRIPT_INTEGER:
        raise ValueError
    return value


def parse_static_integer_sequence(payload: str, *, language: str) -> list[int]:
    """Parse an explicitly bounded comma-separated literal sequence."""
    if len(payload) > MAX_STATIC_LANGUAGE_PROJECTION_CHARS:
        raise ValueError
    payload = payload.strip()
    if language == "javascript" and payload.startswith("..."):
        spread = re.fullmatch(r"\.\.\.\s*\[([^\[\]]*)\]", payload, re.S)
        if spread is None:
            raise ValueError
        payload = spread.group(1)
    if not payload or payload.count(",") >= MAX_PYTHON_STATIC_SEQUENCE_ITEMS:
        raise ValueError
    tokens = payload.split(",")
    if len(tokens) > MAX_PYTHON_STATIC_SEQUENCE_ITEMS or any(not token.strip() for token in tokens):
        raise ValueError
    return [parse_static_integer(token, language=language) for token in tokens]


def decode_bounded_static_payload(payload: str, encoding: str) -> str:
    """Decode one bounded Base64/Base64url/hex literal before allocating output."""
    if len(payload) > MAX_STATIC_LANGUAGE_ENCODED_CHARS:
        raise ValueError
    if encoding.casefold() == "hex":
        compact = re.sub(r"[\x09\x0a\x0c\x0d\x20]", "", payload)
        if len(compact) > MAX_STATIC_LANGUAGE_ENCODED_CHARS:
            raise ValueError
        raw = bytes.fromhex(compact)
    else:
        compact = re.sub(r"[\x09\x0a\x0c\x0d\x20]", "", payload)
        if encoding.casefold() == "base64url":
            compact = compact.replace("-", "+").replace("_", "/")
        if len(compact) > MAX_STATIC_LANGUAGE_BASE64_CHARS:
            raise ValueError
        compact = compact.ljust(len(compact) + (-len(compact) % 4), "=")
        padding = len(compact) - len(compact.rstrip("="))
        quartets = len(compact) // 4
        maximum_decoded = quartets + quartets + quartets - padding
        if maximum_decoded > MAX_STATIC_LANGUAGE_PROJECTION_CHARS:
            raise ValueError
        raw = base64.b64decode(compact, validate=True)
    if len(raw) > MAX_STATIC_LANGUAGE_PROJECTION_CHARS:
        raise ValueError
    return raw.decode("utf-8")


def decode_static_quoted_payload(payload: str, language: str) -> str:
    """Decode bounded language escapes that can hide static decoder whitespace."""
    if len(payload) > MAX_STATIC_LANGUAGE_ENCODED_CHARS:
        raise ValueError
    payload = normalize_quoted_fragment(payload, language=language)
    if len(payload) > MAX_STATIC_LANGUAGE_ENCODED_CHARS:
        raise ValueError
    if language != "javascript":
        return payload
    controls = {
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "f": "\f",
        "v": "\v",
        "\\": "\\",
        "'": "'",
        '"': '"',
    }
    return re.sub(
        r"\\([nrtfv\\'\"])",
        lambda match: controls[match.group(1)],
        payload,
    )


def static_language_projections(text: str, relative: Path, errors: list[str]) -> list[str]:
    """Project bounded executable JS/TS and PowerShell constant text in source order."""
    language = quoted_fragment_language(relative)
    if language not in {"javascript", "powershell"}:
        return []
    lexical_errors: list[str] = []
    code_mask = executable_code_mask(text, language, lexical_errors)
    for lexical_error in lexical_errors:
        fail(errors, f"{lexical_error}: {relative}")
    positioned: list[tuple[int, str]] = []
    covered_spans: list[tuple[int, int]] = []
    projection_chars = 0
    projection_bound_failed = False

    def executable(match: re.Match[str]) -> bool:
        return match.start() < len(code_mask) and bool(code_mask[match.start()])

    def add(match: re.Match[str], value: str) -> None:
        nonlocal projection_chars, projection_bound_failed
        if (
            len(value) > MAX_STATIC_LANGUAGE_PROJECTION_CHARS
            or len(positioned) >= MAX_PYTHON_STATIC_SEQUENCE_ITEMS
            or projection_chars > MAX_STATIC_LANGUAGE_PROJECTION_CHARS - len(value)
        ):
            projection_bound_failed = True
            raise ValueError
        positioned.append((match.start(), value))
        covered_spans.append(match.span())
        projection_chars += len(value)

    def add_error(message: str) -> None:
        fail(errors, f"{message}: {relative}")

    if language == "javascript":
        for pattern, is_apply in (
            (STATIC_JS_APPLY_CALL, True),
            (STATIC_JS_CHAR_CALL, False),
        ):
            for match in pattern.finditer(text):
                if not executable(match):
                    continue
                try:
                    kind = match.group(1).casefold()
                    values = parse_static_integer_sequence(match.group(2), language=language)
                    if kind == "fromcharcode":
                        value = "".join(chr(item & 0xFFFF) for item in values)
                    elif all(0 <= item <= 0x10FFFF for item in values):
                        value = "".join(chr(item) for item in values)
                    else:
                        raise ValueError
                    add(match, value)
                except (ValueError, UnicodeError):
                    add_error("recognized JavaScript character constructor is unresolved or malformed")
        for match in STATIC_JS_ATOB_CALL.finditer(text):
            if not executable(match):
                continue
            try:
                payload = decode_static_quoted_payload(match.group(2), language)
                add(match, decode_bounded_static_payload(payload, "base64"))
            except (ValueError, UnicodeDecodeError, binascii.Error):
                add_error("recognized JavaScript Base64 decoder is unresolved or malformed")
        for match in STATIC_JS_BUFFER_CALL.finditer(text):
            if not executable(match):
                continue
            try:
                payload = decode_static_quoted_payload(match.group(2), language)
                add(match, decode_bounded_static_payload(payload, match.group(4)))
            except (ValueError, UnicodeDecodeError, binascii.Error):
                add_error("recognized JavaScript buffer decoder is unresolved or malformed")
        for match in STATIC_JS_TEXT_DECODER_CALL.finditer(text):
            if not executable(match):
                continue
            try:
                encoding = (match.group(2) or "utf-8").casefold().replace("_", "-")
                if encoding not in {"utf8", "utf-8"}:
                    raise ValueError
                values = parse_static_integer_sequence(match.group(4), language=language)
                if match.group(3).casefold() == "uint8clampedarray":
                    raw = bytes(min(255, max(0, value)) for value in values)
                else:
                    raw = bytes(value & 0xFF for value in values)
                add(match, raw.decode("utf-8", errors="replace"))
            except (ValueError, UnicodeDecodeError):
                add_error("recognized JavaScript typed-array decoder is unresolved or malformed")
        for marker in STATIC_JS_TEXT_DECODER_MARKER.finditer(text):
            if not executable(marker):
                continue
            if not any(start <= marker.start() < end for start, end in covered_spans):
                add_error("recognized JavaScript text decoder is unresolved or malformed")
    else:
        for match in STATIC_PS_CHAR_ARRAY.finditer(text):
            if not executable(match):
                continue
            try:
                values = parse_static_integer_sequence(match.group(1), language=language)
                if any(item < 0 or item > 0xFFFF for item in values):
                    raise ValueError
                add(match, "".join(chr(item) for item in values))
            except (ValueError, UnicodeError):
                add_error("recognized PowerShell character array is unresolved or malformed")
        for match in STATIC_PS_CHAR_CAST.finditer(text):
            if not executable(match):
                continue
            try:
                value = parse_static_integer(match.group(1), language=language)
                if value < 0 or value > 0xFFFF:
                    raise ValueError
                add(match, chr(value))
            except (ValueError, UnicodeError):
                add_error("recognized PowerShell character cast is unresolved or malformed")
        for match in STATIC_PS_ENCODING_CALL.finditer(text):
            if not executable(match):
                continue
            try:
                values = parse_static_integer_sequence(match.group(2), language=language)
                if any(item < 0 or item > 255 for item in values):
                    raise ValueError
                codec = "ascii" if match.group(1).casefold() == "ascii" else "utf-8"
                add(match, bytes(values).decode(codec))
            except (ValueError, UnicodeDecodeError):
                add_error("recognized PowerShell byte decoder is unresolved or malformed")
        for match in STATIC_PS_BASE64_CALL.finditer(text):
            if not executable(match):
                continue
            try:
                payload = decode_static_quoted_payload(match.group(2), language)
                add(match, decode_bounded_static_payload(payload, "base64"))
            except (ValueError, UnicodeDecodeError, binascii.Error):
                add_error("recognized PowerShell Base64 decoder is unresolved or malformed")
        for marker_pattern in (STATIC_PS_CHAR_MARKER, STATIC_PS_BYTE_ARRAY_MARKER):
            for marker in marker_pattern.finditer(text):
                if not executable(marker):
                    continue
                if not any(start <= marker.start() < end for start, end in covered_spans):
                    add_error("recognized PowerShell text constructor is unresolved or malformed")

    positioned.sort(key=lambda item: item[0])
    if projection_bound_failed:
        add_error("static language projections exceed the bounded total")
        return []
    values = [value for _, value in positioned]
    if len(values) > 1:
        values.append("".join(values))
    return values


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def route_key(route: dict) -> tuple[str, str, str]:
    return (route["sha"], route["canonical_path"], route["canonical_url"])


def tracked_utf8_text_files(errors: list[str]) -> list[tuple[Path, str]]:
    """Load worktree and divergent index views as UTF-8 release-candidate text."""
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "ls-files", "-z", "--cached"],
            check=True,
            capture_output=True,
        )
        divergent_result = subprocess.run(
            [
                "git",
                "-C",
                str(ROOT),
                "diff",
                "--no-ext-diff",
                "--name-only",
                "-z",
                "--",
            ],
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        fail(errors, f"tracked-file inventory unavailable: {error}")
        return []

    divergent_paths = {
        raw_path
        for raw_path in divergent_result.stdout.split(b"\0")
        if raw_path
    }
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
        else:
            try:
                text = path.read_text(encoding="utf-8-sig")
            except UnicodeDecodeError:
                fail(errors, f"tracked file is not UTF-8 text and requires explicit handling: {relative}")
            else:
                tracked.append((path, text))
        if raw_path not in divergent_paths:
            continue
        try:
            index_result = subprocess.run(
                ["git", "-C", str(ROOT), "show", f":{relative.as_posix()}"],
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as error:
            fail(errors, f"staged index blob is unavailable for {relative}: {error}")
            continue
        try:
            index_text = index_result.stdout.decode("utf-8-sig")
        except UnicodeDecodeError:
            fail(errors, f"staged index blob is not UTF-8 text: {relative}")
            continue
        tracked.append((path, index_text))
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
        text = SERIALIZED_NAMED_UNICODE_ESCAPE.sub(
            lambda match: _decode_named_unicode_escape(match),
            text,
        )
        text = SERIALIZED_OCTAL_ESCAPE.sub(
            lambda match: chr(int(match.group(1), 8)),
            text,
        )
        text = unescape(text)
        if markdown_escapes:
            text = MARKDOWN_BACKSLASH_ESCAPE.sub(r"\1", text)
    return text


def _decode_named_unicode_escape(match: re.Match[str]) -> str:
    """Decode one bounded Python-style named Unicode escape if it is valid."""
    try:
        return unicodedata.lookup(match.group(1))
    except KeyError:
        return match.group(0)


def normalize_percent_escapes(text: str) -> str:
    """Decode nested percent escapes to the representation a URL consumer can see."""
    previous = None
    while text != previous:
        previous = text
        text = unquote(text)
    return text


def normalize_privacy_text(text: str, *, markdown_escapes: bool = True) -> str:
    """Alternate serializer and percent decoding until their joint fixed point."""
    previous = None
    while text != previous:
        previous = text
        text = normalize_release_text(text, markdown_escapes=markdown_escapes)
        text = normalize_percent_escapes(text)
    return text


def privacy_normalization_closure(text: str) -> list[str]:
    """Return the bounded fixed point of serializer and percent normalizers."""
    pending = [text]
    seen = {text}
    while pending:
        candidate = pending.pop()
        for normalized in (
            normalize_privacy_text(candidate),
            normalize_privacy_text(candidate, markdown_escapes=False),
        ):
            if normalized in seen:
                continue
            if (
                len(normalized) > MAX_PYTHON_STATIC_PROJECTION_CHARS
                or len(seen) >= 64
            ):
                raise ValueError("privacy normalization exceeds its bounded closure")
            seen.add(normalized)
            pending.append(normalized)
    return sorted(seen)


def normalize_quoted_fragment(text: str, *, language: str | None = None) -> str:
    """Normalize bounded JavaScript and PowerShell escapes inside quoted text."""
    powershell_controls = {
        "0": "\0",
        "a": "\a",
        "b": "\b",
        "e": "\x1b",
        "f": "\f",
        "n": "\n",
        "r": "\r",
        "t": "\t",
        "v": "\v",
    }

    def decode_braced_codepoint(match: re.Match[str]) -> str:
        codepoint = int(match.group(1), 16)
        return chr(codepoint) if codepoint <= sys.maxunicode else match.group(0)

    def decode_powershell_escape(match: re.Match[str]) -> str:
        escaped = match.group(1)
        return powershell_controls.get(escaped, escaped)

    previous = None
    while text != previous:
        previous = text
        text = normalize_privacy_text(text)
        if language == "javascript":
            text = SERIALIZED_BRACED_UNICODE_ESCAPE.sub(decode_braced_codepoint, text)
        elif language == "powershell":
            text = POWERSHELL_BRACED_UNICODE_ESCAPE.sub(decode_braced_codepoint, text)
            text = POWERSHELL_ESCAPED_LINE_BREAK.sub("", text)
            text = POWERSHELL_BACKTICK_ESCAPE.sub(decode_powershell_escape, text)
    return text


def quoted_fragments_cover_identifier(
    text: str,
    protected_identifier: str,
    *,
    language: str | None = None,
) -> bool:
    """Conservatively detect a protected identifier assembled from quoted text."""
    target = protected_identifier.casefold()
    if len(target) < 6:
        raise ValueError("protected identifier is too short for fragment analysis")
    literals: list[str] = []
    literal_chars = 0
    for match in QUOTED_TEXT_LITERAL.finditer(text):
        literal = next(group for group in match.groups() if group is not None)
        literal = normalize_quoted_fragment(literal, language=language).casefold()
        relevant = any(
            target[index:index + 3] in literal
            for index in range(max(len(target) - 2, 0))
        ) or (
            len(literal) <= 2
            and any(character in target for character in literal)
        )
        if not relevant:
            continue
        if len(literal) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
            raise ValueError("quoted literal exceeds the bounded fragment limit")
        literal_chars += len(literal)
        if (
            len(literals) >= MAX_PYTHON_STATIC_SEQUENCE_ITEMS
            or literal_chars > MAX_PYTHON_STATIC_TOTAL_CHARS
        ):
            raise ValueError("quoted literals exceed the bounded fragment budget")
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
            return True
        for literal in literals:
            for length in matching_lengths(position, literal, anchored=True):
                next_position = position + length
                if next_position not in reachable:
                    reachable.add(next_position)
                    pending.append(next_position)
    return False


def quoted_fragment_language(path: Path) -> str | None:
    """Select only the escape semantics owned by the tracked file family."""
    suffix = path.suffix.casefold()
    if suffix in {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}:
        return "javascript"
    if suffix in {".ps1", ".psm1", ".psd1"}:
        return "powershell"
    return None


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
            normalize_privacy_text(text),
            normalize_privacy_text(text, markdown_escapes=False),
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
    scan_quoted_fragments: bool = True,
    quoted_language: str | None = None,
) -> bool:
    normalized_text = normalize_privacy_text(text) if normalize_serialized else text
    repository_name = unquote(urlsplit(narrative_only_root).path).rstrip("/").rsplit("/", 1)[-1]
    text_without_approved_root = normalized_text.replace(narrative_only_root, "")
    if repository_name.casefold() in text_without_approved_root.casefold():
        return True
    if not normalize_serialized or not scan_quoted_fragments:
        return False
    try:
        return quoted_fragments_cover_identifier(
            text.replace(narrative_only_root, ""),
            repository_name,
            language=quoted_language,
        )
    except ValueError:
        return True


def python_literal_projections(
    source: str,
    relative: Path,
    errors: list[str],
    *,
    protected_identifier: str | None = None,
) -> list[str]:
    """Return bounded decoded Python content without executing tracked source.

    Serialized private-route payloads are release content even when unreachable.
    This privacy rule intentionally does not attempt to prove Python execution.
    """
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

    def add_serialized_payload_projections() -> None:
        """Decode bounded printable serialization layers independent of reachability."""
        if protected_identifier is None:
            return
        protected = protected_identifier.casefold()
        literal_seeds = {
            (
                candidate.value.decode("latin-1")
                if isinstance(candidate.value, bytes)
                else candidate.value
            )
            for candidate in ast.walk(tree)
            if isinstance(candidate, ast.Constant)
            and isinstance(candidate.value, (str, bytes))
        }
        pending = [(candidate, 0) for candidate in projections | literal_seeds]
        seen = {candidate for candidate, _ in pending}
        generated_chars = sum(len(candidate) for candidate in seen)

        def padded(value: bytes, multiple: int) -> bytes:
            padding = -len(value) % multiple
            return value.ljust(len(value) + padding, b"=")

        while pending:
            candidate, decode_depth = pending.pop()
            if len(candidate) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                projection_failure(
                    "serialized Python payload exceeds the bounded input limit"
                )
                return
            try:
                normalized_candidates = privacy_normalization_closure(candidate)
            except ValueError:
                projection_failure(
                    "serialized Python payload exceeds the bounded normalization closure"
                )
                return
            for normalized in normalized_candidates:
                if protected in normalized.casefold():
                    add_projection(normalized)
                if normalized not in seen:
                    seen.add(normalized)
                    generated_chars += len(normalized)
                    pending.append((normalized, decode_depth))
            if decode_depth >= 4:
                continue
            for normalized in normalized_candidates:
                try:
                    encoded = normalized.encode("ascii")
                except UnicodeEncodeError:
                    continue
                compact = re.sub(rb"[\t\n\r ]+", b"", encoded)
                decoder_inputs = {encoded, compact}
                for decoder_input in decoder_inputs:
                    decoders = (
                        lambda value: base64.a85decode(value),
                        lambda value: base64.b16decode(value, casefold=True),
                        lambda value: base64.b32decode(padded(value, 8), casefold=True),
                        lambda value: base64.b32hexdecode(padded(value, 8), casefold=True),
                        lambda value: base64.b64decode(padded(value, 4), validate=True),
                        lambda value: base64.b85decode(value),
                        lambda value: base64.b64decode(
                            padded(value, 4),
                            altchars=b"-_",
                            validate=True,
                        ),
                    )
                    for decoder in decoders:
                        try:
                            decoded = decoder(decoder_input)
                        except (
                            binascii.Error,
                            OverflowError,
                            TypeError,
                            UnicodeError,
                            ValueError,
                        ):
                            continue
                        if (
                            not decoded
                            or len(decoded) > MAX_PYTHON_STATIC_PROJECTION_CHARS
                            or not all(
                                byte in {9, 10, 13} or 32 <= byte <= 126
                                for byte in decoded
                            )
                        ):
                            continue
                        text = decoded.decode("ascii")
                        if text in seen:
                            continue
                        seen.add(text)
                        generated_chars += len(text)
                        pending.append((text, decode_depth + 1))
                        if (
                            len(seen) > MAX_PYTHON_STATIC_SEQUENCE_ITEMS
                            or generated_chars > MAX_PYTHON_STATIC_TOTAL_CHARS
                        ):
                            projection_failure(
                                "serialized Python payloads exceed the bounded decode budget"
                            )
                            return

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

    def static_format_text_allowed(format_text: str) -> bool:
        return len(format_text) <= MAX_PYTHON_STATIC_PROJECTION_CHARS

    def static_format_value_allowed(value: object) -> bool:
        if type(value) in {int, bool}:
            return int(value).bit_length() <= MAX_PYTHON_STATIC_PROJECTION_CHARS
        if isinstance(value, tuple):
            return (
                materialized_text_size(value) <= MAX_PYTHON_STATIC_PROJECTION_CHARS
                and all(static_format_value_allowed(item) for item in value)
            )
        return (
            is_safe_materialized(value)
            and materialized_text_size(value) <= MAX_PYTHON_STATIC_PROJECTION_CHARS
        )

    def static_render_field(
        value: object,
        format_spec: str,
        conversion: str | None = None,
    ) -> str | None:
        """Render one bounded field before any aggregate string allocation."""
        if not static_format_value_allowed(value):
            projection_failure("static format value exceeds the bounded projection limit")
            return None
        if (
            not static_format_text_allowed(format_spec)
            or "{" in format_spec
            or "}" in format_spec
        ):
            projection_failure("static format specification is outside the bounded policy")
            return None
        maximum = str(MAX_PYTHON_STATIC_PROJECTION_CHARS)
        for digits in re.findall(r"[0-9]+", format_spec):
            significant = digits.lstrip("0") or "0"
            if len(significant) > len(maximum) or (
                len(significant) == len(maximum) and significant > maximum
            ):
                projection_failure("static format width exceeds the bounded projection limit")
                return None
        if conversion == "s":
            value = str(value)
        elif conversion == "r":
            value = repr(value)
        elif conversion == "a":
            value = ascii(value)
        elif conversion is not None:
            projection_failure("static format conversion is outside the bounded policy")
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

    def static_render_format(
        template: str,
        arguments: tuple[object, ...],
        keyword_arguments: dict[str, object],
        *,
        format_map: bool = False,
    ) -> str | None:
        """Render simple static format fields with a cumulative preallocation bound."""
        if not static_format_text_allowed(template):
            projection_failure("static format template exceeds the bounded projection limit")
            return None
        try:
            parsed_fields = list(string.Formatter().parse(template))
        except ValueError:
            return None
        rendered_parts: list[str] = []
        rendered_size = 0
        automatic_index = 0
        for literal, field_name, format_spec, conversion in parsed_fields:
            rendered_size += len(literal)
            if rendered_size > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                projection_failure("static format output exceeds the bounded projection limit")
                return None
            rendered_parts.append(literal)
            if field_name is None:
                continue
            if format_map:
                if not field_name.isidentifier() or field_name not in keyword_arguments:
                    projection_failure("static format-map field is outside the bounded policy")
                    return None
                value = keyword_arguments[field_name]
            elif field_name == "":
                if automatic_index >= len(arguments):
                    return None
                value = arguments[automatic_index]
                automatic_index += 1
            elif field_name.isdecimal():
                field_index = int(field_name)
                if field_index >= len(arguments):
                    return None
                value = arguments[field_index]
            elif field_name.isidentifier() and field_name in keyword_arguments:
                value = keyword_arguments[field_name]
            else:
                projection_failure("static format field is outside the bounded policy")
                return None
            rendered_field = static_render_field(value, format_spec, conversion)
            if rendered_field is None:
                return None
            rendered_size += len(rendered_field)
            if rendered_size > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                projection_failure("static format output exceeds the bounded projection limit")
                return None
            rendered_parts.append(rendered_field)
        return "".join(rendered_parts)

    percent_field = re.compile(
        r"%[#0\- +]*(?:[0-9]+)?(?:\.[0-9]+)?[hlL]?[diouxXeEfFgGcrsab]"
    )

    def static_render_percent(
        template: str | bytes,
        values: object,
    ) -> str | bytes | None:
        """Render bounded positional percent fields one at a time."""
        template_text = template.decode("latin-1") if isinstance(template, bytes) else template
        if not static_format_text_allowed(template_text):
            projection_failure("static percent template exceeds the bounded projection limit")
            return None
        arguments = list(values) if isinstance(values, tuple) else [values]
        argument_index = 0
        rendered_parts: list[str | bytes] = []
        rendered_size = 0
        literal_start = 0
        position = 0
        while position < len(template_text):
            if template_text[position] != "%":
                position += 1
                continue
            literal = template_text[literal_start:position]
            if literal:
                literal_value = literal.encode("latin-1") if isinstance(template, bytes) else literal
                rendered_parts.append(literal_value)
                rendered_size += len(literal_value)
            if position + 1 < len(template_text) and template_text[position + 1] == "%":
                percent_value = b"%" if isinstance(template, bytes) else "%"
                rendered_parts.append(percent_value)
                rendered_size += 1
                position += 2
                literal_start = position
                continue
            match = percent_field.match(template_text, position)
            if match is None or argument_index >= len(arguments):
                projection_failure("static percent field is outside the bounded policy")
                return None
            specifier = match.group(0)
            maximum = str(MAX_PYTHON_STATIC_PROJECTION_CHARS)
            for digits in re.findall(r"[0-9]+", specifier):
                significant = digits.lstrip("0") or "0"
                if len(significant) > len(maximum) or (
                    len(significant) == len(maximum) and significant > maximum
                ):
                    projection_failure("static percent width exceeds the bounded projection limit")
                    return None
            value = arguments[argument_index]
            argument_index += 1
            if not static_format_value_allowed(value):
                projection_failure("static percent value exceeds the bounded projection limit")
                return None
            native_specifier = (
                specifier.encode("latin-1") if isinstance(template, bytes) else specifier
            )
            try:
                rendered_field = native_specifier % value
            except MemoryError:
                projection_failure("static percent format exhausted the bounded projection budget")
                return None
            except (OverflowError, TypeError, ValueError):
                return None
            rendered_size += len(rendered_field)
            if rendered_size > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                projection_failure("static percent-format output exceeds the bounded projection limit")
                return None
            rendered_parts.append(rendered_field)
            position = match.end()
            literal_start = position
        trailing = template_text[literal_start:]
        if trailing:
            trailing_value = trailing.encode("latin-1") if isinstance(template, bytes) else trailing
            rendered_parts.append(trailing_value)
            rendered_size += len(trailing_value)
        if rendered_size > MAX_PYTHON_STATIC_PROJECTION_CHARS:
            projection_failure("static percent-format output exceeds the bounded projection limit")
            return None
        if argument_index != len(arguments):
            return None
        return (b"" if isinstance(template, bytes) else "").join(rendered_parts)

    def static_formatted_text(
        node: ast.FormattedValue,
        environment: dict[str, object],
        depth: int,
    ) -> str | None:
        value = static_value(node.value, environment, depth + 1)
        if type(value) not in safe_scalar_types:
            return None
        format_spec = (
            ""
            if node.format_spec is None
            else static_value(node.format_spec, environment, depth + 1)
        )
        if not isinstance(format_spec, str):
            return None
        conversion = None if node.conversion == -1 else chr(node.conversion)
        return static_render_field(value, format_spec, conversion)

    def static_comprehension_sequence(
        node: ast.GeneratorExp | ast.ListComp,
        environment: dict[str, object],
        depth: int,
    ) -> tuple[object, ...] | None:
        """Materialize bounded deterministic comprehensions used by static joins."""
        results: list[object] = []
        result_chars = 0

        def expand(generator_index: int, current: dict[str, object]) -> bool:
            nonlocal result_chars
            if generator_index == len(node.generators):
                value = static_value(node.elt, current, depth + generator_index + 1)
                if not is_safe_materialized(value):
                    return False
                if len(results) >= MAX_PYTHON_STATIC_SEQUENCE_ITEMS:
                    projection_failure("static comprehension exceeds the bounded item limit")
                    return False
                result_chars += materialized_text_size(value)
                if result_chars > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                    projection_failure("static comprehension exceeds the bounded projection limit")
                    return False
                results.append(value)
                return True
            generator = node.generators[generator_index]
            if generator.is_async:
                projection_failure("asynchronous static comprehension is outside the bounded policy")
                return False
            iterable = static_value(
                generator.iter,
                current,
                depth + generator_index + 1,
            )
            if not isinstance(iterable, tuple):
                return False
            for item in iterable:
                item_environment = dict(current)
                bind_assignment_target(item_environment, generator.target, item)
                if not target_names(generator.target) <= set(item_environment):
                    return False
                include = True
                for condition_node in generator.ifs:
                    condition = static_value(
                        condition_node,
                        item_environment,
                        depth + generator_index + 1,
                    )
                    if type(condition) not in safe_scalar_types:
                        return False
                    if not bool(condition):
                        include = False
                        break
                if include and not expand(generator_index + 1, item_environment):
                    return False
            return True

        if not expand(0, dict(environment)):
            return None
        return tuple(results)

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
        if isinstance(node, (ast.GeneratorExp, ast.ListComp)):
            return static_comprehension_sequence(node, environment, depth + 1)
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
        if isinstance(node, ast.BoolOp):
            if not node.values:
                return None
            last_value: object | None = None
            for value_node in node.values:
                last_value = static_value(value_node, environment, depth + 1)
                if type(last_value) not in safe_scalar_types:
                    return None
                if isinstance(node.op, ast.And) and not bool(last_value):
                    return last_value
                if isinstance(node.op, ast.Or) and bool(last_value):
                    return last_value
            return last_value
        if isinstance(node, ast.Compare):
            left = static_value(node.left, environment, depth + 1)
            if not is_safe_materialized(left):
                return None
            for operator, comparator_node in zip(node.ops, node.comparators):
                right = static_value(comparator_node, environment, depth + 1)
                if not is_safe_materialized(right):
                    return None
                try:
                    if isinstance(operator, ast.Eq):
                        matched = left == right
                    elif isinstance(operator, ast.NotEq):
                        matched = left != right
                    elif isinstance(operator, ast.Lt):
                        matched = left < right
                    elif isinstance(operator, ast.LtE):
                        matched = left <= right
                    elif isinstance(operator, ast.Gt):
                        matched = left > right
                    elif isinstance(operator, ast.GtE):
                        matched = left >= right
                    elif isinstance(operator, ast.In):
                        matched = left in right
                    elif isinstance(operator, ast.NotIn):
                        matched = left not in right
                    elif isinstance(operator, ast.Is):
                        matched = left is right
                    elif isinstance(operator, ast.IsNot):
                        matched = left is not right
                    else:
                        return None
                except (TypeError, ValueError):
                    return None
                if not matched:
                    return False
                left = right
            return True
        if isinstance(node, ast.JoinedStr):
            values: list[str] = []
            joined_size = 0
            for item in node.values:
                if isinstance(item, ast.FormattedValue):
                    value = static_formatted_text(item, environment, depth + 1)
                    if value is None:
                        value = ""
                else:
                    value = static_value(item, environment, depth + 1)
                if not isinstance(value, str):
                    return None
                joined_size += len(value)
                if joined_size > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                    projection_failure("static f-string exceeds the bounded projection limit")
                    return None
                values.append(value)
            return "".join(values)
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
            if (
                node.func.id == "ord"
                and isinstance(argument, (str, bytes))
                and len(argument) == 1
            ):
                return ord(argument)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            attribute = node.func.attr
            if (
                attribute == "fromhex"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id in {"bytes", "bytearray"}
                and len(node.args) == 1
                and not node.keywords
            ):
                encoded = static_value(node.args[0], environment, depth + 1)
                if isinstance(encoded, str):
                    if len(encoded) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                        projection_failure("static hexadecimal input exceeds the bounded projection limit")
                        return None
                    try:
                        decoded = bytes.fromhex(encoded)
                    except ValueError:
                        return None
                    if len(decoded) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                        projection_failure("static hexadecimal output exceeds the bounded projection limit")
                        return None
                    return decoded
            if attribute in {"decode", "encode"}:
                receiver = static_value(node.func.value, environment, depth + 1)
                receiver_matches = (
                    attribute == "decode" and isinstance(receiver, bytes)
                ) or (attribute == "encode" and isinstance(receiver, str))
                if receiver_matches:
                    if len(receiver) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                        projection_failure("static codec input exceeds the bounded projection limit")
                        return None
                    if len(node.args) > 2:
                        projection_failure("static codec call has unsupported positional arguments")
                        return None
                    options: dict[str, str] = {"encoding": "utf-8", "errors": "strict"}
                    option_names = ("encoding", "errors")
                    explicit_options: set[str] = set()
                    for index, argument_node in enumerate(node.args):
                        option = static_value(argument_node, environment, depth + 1)
                        if not isinstance(option, str):
                            projection_failure("static codec call has an unresolved option")
                            return None
                        option_name = option_names[index]
                        options[option_name] = option
                        explicit_options.add(option_name)
                    for keyword in node.keywords:
                        if keyword.arg not in options:
                            projection_failure("static codec call has an unsupported keyword")
                            return None
                        if keyword.arg in explicit_options:
                            projection_failure("static codec call repeats an explicit option")
                            return None
                        option = static_value(keyword.value, environment, depth + 1)
                        if not isinstance(option, str):
                            projection_failure("static codec call has an unresolved option")
                            return None
                        options[keyword.arg] = option
                        explicit_options.add(keyword.arg)
                    encoding = options["encoding"].casefold().replace("_", "-")
                    if encoding not in {
                        "ascii",
                        "iso-8859-1",
                        "latin-1",
                        "latin1",
                        "utf-8",
                        "utf8",
                    } or options["errors"] != "strict":
                        projection_failure("static codec call is outside the bounded codec policy")
                        return None
                    try:
                        transformed = (
                            receiver.decode(options["encoding"], options["errors"])
                            if isinstance(receiver, bytes)
                            else receiver.encode(options["encoding"], options["errors"])
                        )
                    except (LookupError, UnicodeError):
                        return None
                    if len(transformed) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                        projection_failure("static codec output exceeds the bounded projection limit")
                        return None
                    return transformed
            receiver = static_value(node.func.value, environment, depth + 1)
            if attribute == "format" and isinstance(receiver, str):
                arguments = tuple(
                    static_value(argument, environment, depth + 1)
                    for argument in node.args
                )
                keyword_arguments = {
                    keyword.arg: static_value(keyword.value, environment, depth + 1)
                    for keyword in node.keywords
                    if keyword.arg is not None
                }
                if (
                    len(keyword_arguments) != len(node.keywords)
                ):
                    projection_failure("static format keyword expansion is outside the bounded policy")
                    return None
                return static_render_format(
                    receiver,
                    arguments,
                    keyword_arguments,
                )
            if (
                attribute == "format_map"
                and isinstance(receiver, str)
                and len(node.args) == 1
                and not node.keywords
                and isinstance(node.args[0], ast.Dict)
                and not any(key is None for key in node.args[0].keys)
            ):
                mapping: dict[str, object] = {}
                for key_node, value_node in zip(
                    node.args[0].keys,
                    node.args[0].values,
                ):
                    key = static_value(key_node, environment, depth + 1)
                    value = static_value(value_node, environment, depth + 1)
                    if not isinstance(key, str):
                        projection_failure("static format-map key is outside the bounded policy")
                        return None
                    mapping[key] = value
                return static_render_format(
                    receiver,
                    (),
                    mapping,
                    format_map=True,
                )
            if attribute == "replace" and isinstance(receiver, (str, bytes)):
                if len(node.args) not in {2, 3} or node.keywords:
                    return None
                old = static_value(node.args[0], environment, depth + 1)
                new = static_value(node.args[1], environment, depth + 1)
                count = (
                    -1
                    if len(node.args) == 2
                    else static_value(node.args[2], environment, depth + 1)
                )
                if len(node.args) == 3 and count is None:
                    projection_failure("static replacement count is unresolved")
                    return None
                if (
                    type(old) is not type(receiver)
                    or type(new) is not type(receiver)
                    or type(count) not in {int, bool}
                ):
                    return None
                count = int(count)
                replacements = receiver.count(old)
                if old == receiver[:0]:
                    replacements = len(receiver) + 1
                if count >= 0:
                    replacements = min(replacements, count)
                output_size = len(receiver) + replacements * (len(new) - len(old))
                if output_size > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                    projection_failure("static replacement output exceeds the bounded projection limit")
                    return None
                return receiver.replace(old, new, count)
            if attribute == "__add__" and len(node.args) == 1 and not node.keywords:
                other = static_value(node.args[0], environment, depth + 1)
                if isinstance(receiver, str) and isinstance(other, str):
                    combined = receiver + other
                elif isinstance(receiver, bytes) and isinstance(other, bytes):
                    combined = receiver + other
                else:
                    return None
                if len(combined) > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                    projection_failure("static direct-add output exceeds the bounded projection limit")
                    return None
                return combined
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
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
            template = static_value(node.left, environment, depth + 1)
            values = static_value(node.right, environment, depth + 1)
            if isinstance(template, (str, bytes)):
                return static_render_percent(template, values)
        if isinstance(node, ast.BinOp) and isinstance(
            node.op,
            (
                ast.Sub,
                ast.Mult,
                ast.FloorDiv,
                ast.Mod,
                ast.Pow,
                ast.LShift,
                ast.RShift,
                ast.BitOr,
                ast.BitXor,
                ast.BitAnd,
            ),
        ):
            left = static_value(node.left, environment, depth + 1)
            right = static_value(node.right, environment, depth + 1)
            if type(left) in {int, bool} and type(right) in {int, bool}:
                left_integer = int(left)
                right_integer = int(right)
                if isinstance(node.op, ast.Pow):
                    if right_integer < 0:
                        return None
                    estimated_bits = (
                        1
                        if left_integer in {-1, 0, 1}
                        else max(abs(left_integer).bit_length(), 1) * right_integer
                    )
                    if estimated_bits > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                        projection_failure("static integer power exceeds the bounded projection limit")
                        return None
                if isinstance(node.op, (ast.LShift, ast.RShift)):
                    if right_integer < 0:
                        return None
                    if (
                        right_integer > MAX_PYTHON_STATIC_PROJECTION_CHARS
                        or (
                            isinstance(node.op, ast.LShift)
                            and abs(left_integer).bit_length() + right_integer
                            > MAX_PYTHON_STATIC_PROJECTION_CHARS
                        )
                    ):
                        projection_failure("static integer shift exceeds the bounded projection limit")
                        return None
                try:
                    if isinstance(node.op, ast.Sub):
                        result = left_integer - right_integer
                    elif isinstance(node.op, ast.Mult):
                        if (
                            abs(left_integer).bit_length()
                            + abs(right_integer).bit_length()
                            > MAX_PYTHON_STATIC_PROJECTION_CHARS + 1
                        ):
                            projection_failure("static integer multiplication exceeds the bounded projection limit")
                            return None
                        result = left_integer * right_integer
                    elif isinstance(node.op, ast.FloorDiv):
                        result = left_integer // right_integer
                    elif isinstance(node.op, ast.Mod):
                        result = left_integer % right_integer
                    elif isinstance(node.op, ast.Pow):
                        result = left_integer ** right_integer
                    elif isinstance(node.op, ast.LShift):
                        result = left_integer << right_integer
                    elif isinstance(node.op, ast.RShift):
                        result = left_integer >> right_integer
                    elif isinstance(node.op, ast.BitOr):
                        result = left_integer | right_integer
                    elif isinstance(node.op, ast.BitXor):
                        result = left_integer ^ right_integer
                    else:
                        result = left_integer & right_integer
                except (OverflowError, ZeroDivisionError):
                    return None
                if abs(result).bit_length() > MAX_PYTHON_STATIC_PROJECTION_CHARS:
                    projection_failure("static integer result exceeds the bounded projection limit")
                    return None
                return result
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
    add_serialized_payload_projections()
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
        if len(extracted) != 1:
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
    hexadecimal_deep_url = private_deep_url.encode("utf-8").hex()
    private_deep_bytes = private_deep_url.encode("utf-8")
    serialized_private_payloads = {
        "Ascii85": base64.a85encode(private_deep_bytes).decode("ascii"),
        "Base16": base64.b16encode(private_deep_bytes).decode("ascii"),
        "Base32": base64.b32encode(private_deep_bytes).decode("ascii"),
        "Base32hex": base64.b32hexencode(private_deep_bytes).decode("ascii"),
        "Base64": base64.b64encode(private_deep_bytes).decode("ascii"),
        "Base85": base64.b85encode(private_deep_bytes).decode("ascii"),
        "URL-safe Base64": base64.urlsafe_b64encode(private_deep_bytes).decode("ascii"),
        "nested Base64": base64.b64encode(
            base64.b64encode(private_deep_bytes)
        ).decode("ascii"),
        "HTML-normalized Base64": base64.b64encode(
            html_encoded_deep_url.encode("utf-8")
        ).decode("ascii"),
        "Unicode-normalized Base64": base64.b64encode(
            unicode_encoded_deep_url.encode("utf-8")
        ).decode("ascii"),
        "Markdown-normalized Base64": base64.b64encode(
            backslash_escaped_deep_url.encode("utf-8")
        ).decode("ascii"),
        "line-continuation Base64": base64.b64encode(
            yaml_line_continued_deep_url.encode("utf-8")
        ).decode("ascii"),
        "percent-normalized Base64": base64.b64encode(
            private_deep_url.replace("-", "%2D").encode("utf-8")
        ).decode("ascii"),
        "nested-percent Base64": base64.b64encode(
            private_deep_url.replace("-", "%252D").encode("utf-8")
        ).decode("ascii"),
    }
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
        (
            f'candidate = bytes.fromhex("{hexadecimal_deep_url}").decode()',
            "Python static hexadecimal bytes decoding",
        ),
        (
            f'candidate = bytearray.fromhex("{hexadecimal_deep_url}").decode(encoding="utf-8")',
            "Python static hexadecimal bytearray decoding",
        ),
        (f'candidate = "{named_unicode_deep_url}"', "Python named-Unicode string"),
    )
    for source, label in python_literal_cases:
        parse_errors: list[str] = []
        projections = python_literal_projections(source, Path("example.py"), parse_errors)
        if parse_errors or private_deep_url not in projections:
            fail(errors, f"Python literal privacy projection regression: {label}")

    for label, payload in serialized_private_payloads.items():
        serialized_errors: list[str] = []
        serialized_projections = python_literal_projections(
            "if False:\n    payload = " + json.dumps(payload),
            Path("example.py"),
            serialized_errors,
            protected_identifier=repository_name,
        )
        if serialized_errors or private_deep_url not in serialized_projections:
            fail(
                errors,
                f"Python serialized-content privacy regression: {label}",
            )
    aliased_base64_source = (
        "import base64 as codec\n"
        + "candidate = codec.b64decode("
        + json.dumps(serialized_private_payloads["Base64"])
        + ").decode()"
    )
    aliased_base64_errors: list[str] = []
    aliased_base64_projections = python_literal_projections(
        aliased_base64_source,
        Path("example.py"),
        aliased_base64_errors,
        protected_identifier=repository_name,
    )
    if aliased_base64_errors or private_deep_url not in aliased_base64_projections:
        fail(errors, "Python serialized-content alias regression")

    base64_payload = serialized_private_payloads["Base64"]
    payload_split = len(base64_payload) // 2
    payload_first = base64_payload[:payload_split]
    payload_second = base64_payload[payload_split:]
    serialized_composition_cases = (
        (
            f'first = {json.dumps(payload_first)}\n'
            + f'second = {json.dumps(payload_second)}\n'
            + 'candidate = "{}{}".format(first, second)',
            "string format",
        ),
        (
            f'first = {json.dumps(payload_first)}\n'
            + f'second = {json.dumps(payload_second)}\n'
            + 'candidate = "{}{}".format(first, second, "unused")',
            "string format with unused argument",
        ),
        (
            f'first = {json.dumps(payload_first)}\n'
            + f'second = {json.dumps(payload_second)}\n'
            + 'candidate = "%s%s" % (first, second)',
            "percent format",
        ),
        (
            'candidate = "{left}{right}".format_map('
            + '{"left": '
            + json.dumps(payload_first)
            + ', "right": '
            + json.dumps(payload_second)
            + '})',
            "format map",
        ),
        (
            f'parts = ({json.dumps(payload_first)}, {json.dumps(payload_second)})\n'
            + 'candidate = "".join(item for item in parts)',
            "generator join",
        ),
        (
            'candidate = '
            + json.dumps(payload_first + "~" + payload_second)
            + '.replace("~", "")',
            "string replacement",
        ),
    )
    for source, label in serialized_composition_cases:
        composition_errors: list[str] = []
        composition_projections = python_literal_projections(
            source,
            Path("example.py"),
            composition_errors,
            protected_identifier=repository_name,
        )
        if composition_errors or private_deep_url not in composition_projections:
            fail(
                errors,
                f"Python serialized-content composition regression: {label}",
            )

    for source, label in (
        (
            "match runtime_value:\n    case "
            + json.dumps(base64_payload)
            + ":\n        pass",
            "value pattern",
        ),
        (
            "match runtime_value:\n    case {"
            + json.dumps(base64_payload)
            + ": _}:\n        pass",
            "mapping-key pattern",
        ),
    ):
        pattern_errors: list[str] = []
        pattern_projections = python_literal_projections(
            source,
            Path("example.py"),
            pattern_errors,
            protected_identifier=repository_name,
        )
        if pattern_errors or private_deep_url not in pattern_projections:
            fail(errors, f"Python serialized-content match regression: {label}")

    normalized_inner_base64 = base64_payload.replace(
        base64_payload[0],
        f"&#{ord(base64_payload[0])};",
        1,
    )
    mixed_serialized_payloads = {
        "percent then HTML": private_deep_url.replace("-", "%26%2345%3B"),
        "percent then Unicode": private_deep_url.replace("-", r"%5Cu002d"),
        "percent then Markdown": private_deep_url.replace("-", r"%5C-"),
        "named Unicode": private_deep_url.replace("-", r"\N{HYPHEN-MINUS}"),
        "octal": private_deep_url.replace("-", r"\055"),
        "normalized intermediate Base64": normalized_inner_base64,
    }
    for label, serialized_text in mixed_serialized_payloads.items():
        payload = base64.b64encode(serialized_text.encode("utf-8")).decode("ascii")
        mixed_errors: list[str] = []
        mixed_projections = python_literal_projections(
            "if False:\n    payload = " + json.dumps(payload),
            Path("example.py"),
            mixed_errors,
            protected_identifier=repository_name,
        )
        if mixed_errors or private_deep_url not in mixed_projections:
            fail(errors, f"Python serialized normalization-closure regression: {label}")

    serialized_comprehension_cases = (
        (
            f'parts = ({json.dumps(payload_first)}, {json.dumps(payload_second)})\n'
            + 'candidate = "".join(item for item in parts if True)',
            "filtered generator",
        ),
        (
            f'parts = ({json.dumps(payload_first)}, {json.dumps(payload_second)})\n'
            + 'candidate = "".join(item for item in parts if item != "")',
            "comparison-filtered generator",
        ),
        (
            f'parts = ({json.dumps(payload_first)}, {json.dumps(payload_second)})\n'
            + 'candidate = "".join(item for item in parts if True and item)',
            "boolean-filtered generator",
        ),
        (
            'parts = (('
            + json.dumps(payload_first)
            + ',), ('
            + json.dumps(payload_second)
            + ',))\n'
            + 'candidate = "".join(item for group in parts for item in group)',
            "nested generator",
        ),
        (
            'parts = (('
            + json.dumps(payload_first)
            + ',), ('
            + json.dumps(payload_second)
            + ',))\n'
            + 'candidate = "".join(item for (item,) in parts)',
            "tuple-destructuring generator",
        ),
        (
            f'parts = ({json.dumps(payload_first)}, {json.dumps(payload_second)})\n'
            + 'candidate = "".join([item for item in parts])',
            "list comprehension",
        ),
        (
            f'parts = ({json.dumps(payload_first)}, {json.dumps(payload_second)})\n'
            + 'candidate = "".join([item for item in parts if item != ""])',
            "comparison-filtered list comprehension",
        ),
        (
            'candidate = '
            + json.dumps(payload_first + "~" + payload_second)
            + '.replace("~", "", True)',
            "boolean replacement count",
        ),
        (
            'candidate = '
            + json.dumps(payload_first + "~" + payload_second)
            + '.replace("~", "", 2 ** 0)',
            "power replacement count",
        ),
        (
            'candidate = '
            + json.dumps(payload_first + "~" + payload_second)
            + '.replace("~", "", 3 // 2)',
            "floor-division replacement count",
        ),
        (
            'candidate = '
            + json.dumps(payload_first + "~" + payload_second)
            + '.replace("~", "", 1 | 0)',
            "bitwise replacement count",
        ),
    )
    for source, label in serialized_comprehension_cases:
        comprehension_errors: list[str] = []
        comprehension_projections = python_literal_projections(
            source,
            Path("example.py"),
            comprehension_errors,
            protected_identifier=repository_name,
        )
        if comprehension_errors or private_deep_url not in comprehension_projections:
            fail(errors, f"Python serialized comprehension regression: {label}")

    private_hexadecimal_integer = int(private_deep_bytes.hex(), 16)
    for source, label in (
        (
            f'candidate = "{{:X}}".format({private_hexadecimal_integer})',
            "integer string format",
        ),
        (
            f'candidate = "%X" % {private_hexadecimal_integer}',
            "integer percent format",
        ),
    ):
        integer_format_errors: list[str] = []
        integer_format_projections = python_literal_projections(
            source,
            Path("example.py"),
            integer_format_errors,
            protected_identifier=repository_name,
        )
        if integer_format_errors or private_deep_url not in integer_format_projections:
            fail(errors, f"Python serialized integer-format regression: {label}")

    for source, label in (
        ('candidate = "reference 9999999".format()', "literal digits in format"),
        (
            'candidate = "reference 9999999".format_map({})',
            "literal digits in format map",
        ),
    ):
        benign_format_errors: list[str] = []
        benign_format_projections = python_literal_projections(
            source,
            Path("example.py"),
            benign_format_errors,
            protected_identifier=repository_name,
        )
        if benign_format_errors or "reference 9999999" not in benign_format_projections:
            fail(errors, f"Python bounded benign-format regression: {label}")

    for source, label in (
        (
            'candidate = "ordinary".format(runtime_value)',
            "unused unresolved positional argument without fields",
        ),
        (
            'candidate = "{}".format("ordinary", runtime_value)',
            "unused unresolved automatic positional argument",
        ),
        (
            'candidate = "{0}".format("ordinary", runtime_value)',
            "unused unresolved manual positional argument",
        ),
        (
            'candidate = "{value}".format(value="ordinary", unused=runtime_value)',
            "unused unresolved keyword argument",
        ),
        (
            'candidate = "{value}".format_map('
            + '{"value": "ordinary", "unused": runtime_value})',
            "unused unresolved format-map entry",
        ),
    ):
        unused_format_errors: list[str] = []
        unused_format_projections = python_literal_projections(
            source,
            Path("example.py"),
            unused_format_errors,
            protected_identifier=repository_name,
        )
        if unused_format_errors or "ordinary" not in unused_format_projections:
            fail(errors, f"Python unused-format-argument regression: {label}")

    for source, label in (
        (
            f'candidate = "{{0}}{{0}}".format("x" * {MAX_PYTHON_STATIC_PROJECTION_CHARS})',
            "aggregate string format",
        ),
        (
            f'candidate = "%s%s" % (("x" * {MAX_PYTHON_STATIC_PROJECTION_CHARS}), '
            + f'("x" * {MAX_PYTHON_STATIC_PROJECTION_CHARS}))',
            "aggregate percent format",
        ),
    ):
        bounded_format_errors: list[str] = []
        python_literal_projections(
            source,
            Path("example.py"),
            bounded_format_errors,
            protected_identifier=repository_name,
        )
        if not bounded_format_errors:
            fail(errors, f"Python bounded format-preallocation regression: {label}")

    protected_split = 6
    protected_first = repository_name[:protected_split]
    protected_rest = repository_name[protected_split:]
    protected_words = repository_name.split("-")
    javascript_fragment_source = (
        "const owner = "
        + json.dumps(f"https://github.com/{GITHUB_OWNER}/")
        + ";\nconst repository = ["
        + ", ".join(json.dumps(word) for word in protected_words)
        + '].join("-");\n'
        + 'const candidate = owner + repository + "/tree/secret";'
    )
    if not has_noncanonical_narrative_identifier(
        javascript_fragment_source,
        narrative_only_root,
    ):
        fail(errors, "generic quoted-fragment privacy regression: JavaScript join")
    javascript_braced_words = [
        "".join(f"\\u{{{ord(character):x}}}" for character in word)
        for word in protected_words
    ]
    powershell_braced_words = [
        "".join(f"`u{{{ord(character):x}}}" for character in word)
        for word in protected_words
    ]
    powershell_ordinary_words = list(protected_words)
    powershell_ordinary_words[0] = (
        "`" + protected_words[0][0] + "`" + protected_words[0][1:]
    )
    for label, words, separator, language in (
        ("JavaScript braced Unicode", javascript_braced_words, r"\u{2d}", "javascript"),
        ("PowerShell braced Unicode", powershell_braced_words, "`u{2d}", "powershell"),
        ("PowerShell ordinary backtick", powershell_ordinary_words, "-", "powershell"),
    ):
        escaped_fragment_source = (
            "const pieces = ["
            + ", ".join(json.dumps(word) for word in words)
            + "].join("
            + json.dumps(separator)
            + ");"
        )
        if not has_noncanonical_narrative_identifier(
            escaped_fragment_source,
            narrative_only_root,
            quoted_language=language,
        ):
            fail(errors, f"generic escaped-fragment privacy regression: {label}")
    powershell_uppercase_words = [
        "".join(f"`U{{{ord(character):x}}}" for character in word)
        for word in protected_words
    ]
    powershell_uppercase_source = (
        "$parts = @(("
        + ", ".join(json.dumps(word) for word in powershell_uppercase_words)
        + ')); $candidate = $parts -join "`U{2d}"'
    )
    if has_noncanonical_narrative_identifier(
        powershell_uppercase_source,
        narrative_only_root,
        quoted_language="powershell",
    ):
        fail(errors, "generic escaped-fragment PowerShell uppercase control regression")
    cross_language_backtick_source = (
        "const pieces = ["
        + ", ".join(json.dumps(word) for word in powershell_ordinary_words)
        + '].join("-");'
    )
    for language in ("javascript", None):
        if has_noncanonical_narrative_identifier(
            cross_language_backtick_source,
            narrative_only_root,
            quoted_language=language,
        ):
            fail(errors, "generic escaped-fragment cross-language backtick regression")
    if has_noncanonical_narrative_identifier(
        'const words = ["ordinary", "public", "repository"].join("-");',
        narrative_only_root,
    ):
        fail(errors, "generic quoted-fragment ordinary-text regression")

    def static_language_policy_result(source: str, suffix: str) -> tuple[bool, list[str]]:
        projection_errors: list[str] = []
        relative = Path(f"example{suffix}")
        projections = static_language_projections(source, relative, projection_errors)
        projected_values = [source]
        projected_values.extend(json.dumps(value) for value in projections)
        projected_source = "\n".join(projected_values)
        blocked = bool(projection_errors) or has_noncanonical_narrative_identifier(
            projected_source,
            narrative_only_root,
            quoted_language=quoted_fragment_language(relative),
        )
        for url in iter_owned_github_urls(projected_source):
            parsed_result = owned_github_url_parts(url)
            if parsed_result is None:
                continue
            _, segments, _ = parsed_result
            if (
                segments[1].casefold() == repository_name.casefold()
                and not release_url_allowed(
                    relative,
                    url,
                    {narrative_only_root},
                    narrative_only_root,
                )
            ):
                blocked = True
        return blocked, projection_errors

    private_codes = [ord(character) for character in private_deep_url]
    private_code_text = ", ".join(str(value) for value in private_codes)
    split_index = len(private_codes) // 2
    first_code_text = ", ".join(str(value) for value in private_codes[:split_index])
    second_code_text = ", ".join(str(value) for value in private_codes[split_index:])
    wrapped_code_text = ", ".join(str(value + 0x10000) for value in private_codes)
    private_base64 = base64.b64encode(private_deep_bytes).decode("ascii")
    spaced_private_base64 = " \n".join(
        private_base64[index:index + 8]
        for index in range(0, len(private_base64), 8)
    )
    private_hexadecimal = private_deep_bytes.hex()
    template_delimiter = chr(96)
    clamped_negative_code_text = ", ".join(
        str(value - 256) for value in private_codes
    )
    clamped_positive_code_text = ", ".join(
        str(value + 256) for value in private_codes
    )

    static_language_attacks = (
        (
            f"const candidate = String.fromCharCode({private_code_text});",
            ".js",
            "JavaScript direct fromCharCode",
        ),
        (
            "const candidate = "
            + template_delimiter
            + "${String.fromCharCode("
            + private_code_text
            + ")}"
            + template_delimiter
            + ";",
            ".js",
            "JavaScript template interpolation",
        ),
        (
            "const candidate = "
            + template_delimiter
            + "${/}/.source && String.fromCharCode("
            + private_code_text
            + ")}"
            + template_delimiter
            + ";",
            ".js",
            "JavaScript template regex brace",
        ),
        (
            "const candidate = "
            + template_delimiter
            + "${/\\}/.source && String.fromCharCode("
            + private_code_text
            + ")}"
            + template_delimiter
            + ";",
            ".js",
            "JavaScript template escaped regex brace",
        ),
        (
            "const candidate = "
            + template_delimiter
            + "${/[}]/.source && String.fromCharCode("
            + private_code_text
            + ")}"
            + template_delimiter
            + ";",
            ".js",
            "JavaScript template regex character-class brace",
        ),
        (
            "const candidate = "
            + template_delimiter
            + "${(()=>{if(false){}else /}/.source;return true})()&&String.fromCharCode("
            + private_code_text
            + ")}"
            + template_delimiter
            + ";",
            ".js",
            "JavaScript template regex after else",
        ),
        (
            "const candidate = "
            + template_delimiter
            + "${(()=>{if(false)/}/.source;return true})()&&String.fromCharCode("
            + private_code_text
            + ")}"
            + template_delimiter
            + ";",
            ".js",
            "JavaScript template regex after control header",
        ),
        (
            "const candidate = "
            + template_delimiter
            + "${(()=>{do /}/.source;while(false);return true})()&&String.fromCharCode("
            + private_code_text
            + ")}"
            + template_delimiter
            + ";",
            ".js",
            "JavaScript template regex after do",
        ),
        (
            f"const first = String.fromCharCode({first_code_text});\n"
            + f"const second = String.fromCharCode({second_code_text});",
            ".ts",
            "JavaScript source-ordered constructor recomposition",
        ),
        (
            f"const candidate = String.fromCodePoint.apply(null, [{private_code_text}]);",
            ".js",
            "JavaScript fromCodePoint apply",
        ),
        (
            f"const candidate = String.fromCharCode(...[{private_code_text}]);",
            ".tsx",
            "JavaScript spread character construction",
        ),
        (
            f"const candidate = String.fromCharCode({wrapped_code_text});",
            ".mjs",
            "JavaScript fromCharCode 16-bit conversion",
        ),
        (
            f"const codes = [{private_code_text}];\n"
            + "const candidate = codes.map(value => String.fromCharCode(value)).join('');",
            ".js",
            "JavaScript unresolved map-join fail closed",
        ),
        (
            "const candidate = atob(" + json.dumps(spaced_private_base64) + ");",
            ".js",
            "JavaScript Base64 whitespace",
        ),
        (
            "const candidate = Buffer.from("
            + json.dumps(private_base64)
            + ", 'base64').toString();",
            ".cjs",
            "JavaScript explicit Base64 buffer",
        ),
        (
            "const candidate = Buffer.from("
            + json.dumps(private_hexadecimal)
            + ', "hex").toString();',
            ".ts",
            "JavaScript explicit hexadecimal buffer",
        ),
        (
            "const candidate = new TextDecoder().decode(new Uint8Array(["
            + private_code_text
            + "]));",
            ".ts",
            "JavaScript typed-array text decoder",
        ),
        (
            "const candidate = (new TextDecoder).decode(new Uint8Array(["
            + private_code_text
            + "]));",
            ".js",
            "JavaScript no-parentheses text decoder",
        ),
        (
            f"$candidate = [char[]]({private_code_text}) -join ''",
            ".ps1",
            "PowerShell character array",
        ),
        (
            "$candidate = "
            + " + ".join(f"[char]{value}" for value in private_codes),
            ".psm1",
            "PowerShell source-ordered character casts",
        ),
        (
            f"$codes = @({private_code_text}); "
            + "$candidate = $codes | ForEach-Object { [char]$_ }",
            ".ps1",
            "PowerShell unresolved pipeline fail closed",
        ),
        (
            f"$candidate = [Text.Encoding]::ASCII.GetString([byte[]]({private_code_text}))",
            ".ps1",
            "PowerShell ASCII byte decoding",
        ),
        (
            f"$candidate = [System.Text.Encoding]::UTF8.GetString([byte[]]({private_code_text}))",
            ".ps1",
            "PowerShell UTF-8 byte decoding",
        ),
        (
            "$candidate = [Convert]::FromBase64String("
            + json.dumps(spaced_private_base64)
            + ")",
            ".ps1",
            "PowerShell Base64 decoding",
        ),
    )
    for source, suffix, label in static_language_attacks:
        blocked, _ = static_language_policy_result(source, suffix)
        if not blocked:
            fail(errors, f"static-language privacy projection regression: {label}")

    altered_private = private_deep_url.replace(
        repository_name,
        "X" + repository_name[1:],
        1,
    )
    altered_codes = ", ".join(str(ord(character)) for character in altered_private)
    static_language_controls = (
        ("const ordinary = String.fromCharCode(65, 66, 67);", ".js", "ordinary JavaScript characters"),
        (
            f"const altered = String.fromCharCode({altered_codes});",
            ".ts",
            "altered JavaScript route",
        ),
        (
            f"// String.fromCharCode({private_code_text})",
            ".js",
            "JavaScript line comment",
        ),
        (
            "const documentation = "
            + json.dumps(f"String.fromCharCode({private_code_text})")
            + ";",
            ".js",
            "JavaScript documentation string",
        ),
        (
            "const documentation = "
            + template_delimiter
            + f"String.fromCharCode({private_code_text})"
            + template_delimiter
            + ";",
            ".js",
            "JavaScript static template documentation",
        ),
        (
            "const calculation = "
            + template_delimiter
            + "${8 / 2}"
            + template_delimiter
            + ";",
            ".js",
            "JavaScript template ordinary division",
        ),
        (
            r"const documentation = /String\.fromCharCode\(65,66,67\)/;",
            ".js",
            "JavaScript regex documentation",
        ),
        (
            "const ordinary = new TextDecoder().decode(new Uint8Array([65,66,67]));",
            ".js",
            "ordinary JavaScript typed-array decoder",
        ),
        (
            "const ordinary = new TextDecoder().decode(new Uint8ClampedArray(["
            + clamped_negative_code_text
            + "]));",
            ".js",
            "JavaScript negative clamped-array semantics",
        ),
        (
            "const ordinary = new TextDecoder().decode(new Uint8ClampedArray(["
            + clamped_positive_code_text
            + "]));",
            ".js",
            "JavaScript over-255 clamped-array semantics",
        ),
        (
            "const ordinary = textdecoder(runtimeBytes);",
            ".js",
            "JavaScript case-sensitive decoder identifier",
        ),
        (
            f"const bytes = new Uint8Array([{private_code_text}]);",
            ".js",
            "ordinary JavaScript typed array without decoder",
        ),
        (
            "// new TextDecoder().decode(new Uint8Array(["
            + private_code_text
            + "]))",
            ".js",
            "JavaScript typed-array decoder comment",
        ),
        (
            f"# [char[]]({private_code_text})",
            ".ps1",
            "PowerShell line comment",
        ),
        (
            "$documentation = " + json.dumps(f"[char[]]({private_code_text})"),
            ".ps1",
            "PowerShell documentation string",
        ),
        ("const ordinary = Buffer.from('hello');", ".js", "ordinary JavaScript buffer"),
    )
    for source, suffix, label in static_language_controls:
        blocked, projection_errors = static_language_policy_result(source, suffix)
        if blocked or projection_errors:
            fail(errors, f"static-language ordinary control regression: {label}")

    oversized_sequence = ",".join(
        "65" for _ in range(MAX_PYTHON_STATIC_SEQUENCE_ITEMS + 1)
    )
    precision_attack_codes = list(private_codes)
    precision_index = next(
        index for index, value in enumerate(precision_attack_codes)
        if value % 4 == 0
    )
    precision_attack_codes[precision_index] = (
        MAX_EXACT_JAVASCRIPT_INTEGER
        + precision_attack_codes[precision_index]
        + 2
    )
    precision_attack_source = "String.fromCharCode(" + ",".join(
        str(value) for value in precision_attack_codes
    ) + ");"
    static_language_fail_closed = (
        ("String.fromCodePoint(1114112);", ".js", "invalid JavaScript code point"),
        ("String.fromCharCode();", ".js", "empty JavaScript character call"),
        ("String.fromCharCode(runtimeValue);", ".js", "unresolved JavaScript character call"),
        (
            "new TextDecoder().decode(runtimeBytes);",
            ".js",
            "unresolved JavaScript text decoder",
        ),
        (
            "new TextDecoder('utf-16').decode(new Uint8Array([65,66]));",
            ".js",
            "unsupported JavaScript text-decoder encoding",
        ),
        (
            "new TextDecoder('ascii').decode(new Uint8Array([128]));",
            ".js",
            "unsupported WHATWG alias encoding",
        ),
        (
            precision_attack_source,
            ".js",
            "inexact JavaScript numeric literal",
        ),
        (
            f"String.fromCharCode({oversized_sequence});",
            ".js",
            "oversized JavaScript character call",
        ),
        ("$candidate = [char]$runtimeValue", ".ps1", "unresolved PowerShell character cast"),
        ("$candidate = [char[]]()", ".ps1", "empty PowerShell character array"),
    )
    for source, suffix, label in static_language_fail_closed:
        blocked, projection_errors = static_language_policy_result(source, suffix)
        if not blocked or not projection_errors:
            fail(errors, f"static-language fail-closed regression: {label}")

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
    if repository_name not in raw_fragment_projections:
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

    maximum_hexadecimal_input = bytes(
        MAX_PYTHON_STATIC_PROJECTION_CHARS // 2
    ).hex()
    oversized_hexadecimal_input = bytes(
        MAX_PYTHON_STATIC_PROJECTION_CHARS // 2 + 1
    ).hex()
    for source, expect_failure, label in (
        ('candidate = bytes.fromhex("zz").decode()', False, "invalid hexadecimal input"),
        (
            'candidate = bytes.fromhex("'
            + maximum_hexadecimal_input
            + '")',
            False,
            "maximum hexadecimal input",
        ),
        (
            'candidate = bytes.fromhex("'
            + oversized_hexadecimal_input
            + '")',
            True,
            "oversized hexadecimal input",
        ),
        (
            'candidate = b"x".decode("utf-8", encoding="utf-8")',
            True,
            "duplicate codec encoding option",
        ),
        (
            'candidate = b"x".decode("utf-8", "strict", errors="strict")',
            True,
            "duplicate codec errors option",
        ),
    ):
        codec_errors: list[str] = []
        python_literal_projections(source, Path("example.py"), codec_errors)
        if bool(codec_errors) is not expect_failure:
            fail(errors, f"Python bounded static-codec regression: {label}")

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
        normalized_text = normalize_privacy_text(text)
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
        elif relative.suffix.lower() in {
            ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts",
            ".ps1", ".psm1", ".psd1",
        }:
            language_projections = static_language_projections(text, relative, errors)
            if language_projections:
                projected_values = [text]
                projected_values.extend(
                    json.dumps(value) for value in language_projections
                )
                projected_source = "\n".join(projected_values)
                privacy_views.append((projected_source, True))
        for privacy_text, normalize_serialized in privacy_views:
            normalized_privacy_text = (
                normalize_privacy_text(privacy_text)
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
                scan_quoted_fragments=relative.suffix.lower() != ".py",
                quoted_language=quoted_fragment_language(relative),
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
