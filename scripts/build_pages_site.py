#!/usr/bin/env python3
"""Build a static HTML projection of the public profile markdown.

This generator copies public-facing markdown and registry JSON into ./site.
It does not publish to Cloudflare, does not add runtime services, and does not
invent projects or metrics. Source-owned evidence remains the GitHub files.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PAGES_SRC = ROOT / "pages-src"
REGISTRY_PATH = ROOT / "registry" / "profile-repo-routing-registry.json"
DAD_URL = "https://github.com/lowelltwong-alt/Digital-Assett-Directory"
SOURCE_REPO = "https://github.com/lowelltwong-alt/lowelltwong-alt"

PAGES: list[dict[str, str]] = [
    {
        "source": "README.md",
        "output": "index.html",
        "nav": "Home",
        "title": "Lowell T. Wong",
        "wide": "false",
    },
    {
        "source": "AI_FRONT_DOOR.md",
        "output": "ai-front-door.html",
        "nav": "Front Door",
        "title": "AI Front Door",
        "wide": "false",
    },
    {
        "source": "PUBLIC_REPO_MAP.md",
        "output": "public-repo-map.html",
        "nav": "Repositories",
        "title": "Public repository map",
        "wide": "true",
    },
    {
        "source": "PORTABILITY_MAP.md",
        "output": "portability-map.html",
        "nav": "Portability",
        "title": "Portability map",
        "wide": "true",
    },
    {
        "source": "ai/BUILD_PHILOSOPHY.md",
        "output": "build-philosophy.html",
        "nav": "Philosophy",
        "title": "Build philosophy",
        "wide": "false",
    },
    {
        "source": "ai/AI_PORTFOLIO_TOC.md",
        "output": "portfolio-toc.html",
        "nav": "TOC",
        "title": "Portfolio TOC",
        "wide": "true",
    },
    {
        "source": "ai/SHANNON_INFORMATION_THEORY_FOR_AI_GOVERNANCE.md",
        "output": "shannon-note.html",
        "nav": "",
        "title": "Shannon note",
        "wide": "false",
    },
    {
        "source": "CLOUDFLARE_PAGES.md",
        "output": "cloudflare-pages.html",
        "nav": "",
        "title": "Cloudflare Pages notes",
        "wide": "false",
    },
]

REGISTRY_COPIES = [
    "registry/profile-repo-routing-registry.json",
    "registry/portfolio-capability-evidence.json",
    "registry/portable-workflow-patterns.json",
]

COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
FRONT_MATTER_RE = re.compile(r"^---\n.*?\n---\n", re.S)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
FENCE_RE = re.compile(r"^```(\w*)\s*$")
HR_RE = re.compile(r"^(-{3,}|\*{3,}|_{3,})\s*$")
TABLE_SEP_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
ORDERED_RE = re.compile(r"^(\s*)(\d+)\.\s+(.*)$")
UNORDERED_RE = re.compile(r"^(\s*)[-*+]\s+(.*)$")
BLOCKQUOTE_RE = re.compile(r"^>\s?(.*)$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)")
SLUG_RE = re.compile(r"[^a-z0-9]+")

GITHUB_MD = "https://github.com/lowelltwong-alt/lowelltwong-alt/blob/main/"


def output_for_source(source: str) -> str | None:
    for page in PAGES:
        if page["source"] == source:
            return page["output"]
    return None


def rewrite_href(target: str) -> str:
    href, fragment = (target.split("#", 1) + [""])[:2]
    suffix = f"#{fragment}" if fragment else ""
    stripped = href.strip()
    if not stripped or stripped.startswith(("http://", "https://", "mailto:", "/")):
        return target
    normalized = stripped[2:] if stripped.startswith("./") else stripped
    mapped = output_for_source(normalized)
    if mapped:
        return mapped + suffix
    if normalized in REGISTRY_COPIES:
        return normalized + suffix
    return GITHUB_MD + normalized + suffix


def slugify(text: str) -> str:
    plain = re.sub(r"<[^>]+>", "", text).lower()
    return SLUG_RE.sub("-", plain).strip("-")


def inline(text: str) -> str:
    placeholders: list[str] = []

    def hold(value: str) -> str:
        placeholders.append(value)
        return f"\x00PH{len(placeholders) - 1}\x00"

    def codes(match: re.Match[str]) -> str:
        return hold(f"<code>{html.escape(match.group(1))}</code>")

    work = CODE_RE.sub(codes, text)

    def links(match: re.Match[str]) -> str:
        label = inline(match.group(1))
        href = html.escape(rewrite_href(match.group(2)), quote=True)
        return hold(f'<a href="{href}">{label}</a>')

    work = LINK_RE.sub(links, work)
    work = html.escape(work)
    work = BOLD_RE.sub(r"<strong>\1</strong>", work)
    work = ITALIC_RE.sub(r"<em>\1</em>", work)
    for index, value in reversed(list(enumerate(placeholders))):
        work = work.replace(f"\x00PH{index}\x00", value)
    return work


def split_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    cells: list[str] = []
    current: list[str] = []
    in_code = False
    for char in line:
        if char == "`":
            in_code = not in_code
            current.append(char)
        elif char == "|" and not in_code:
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return cells


def close_list(parts: list[str], stack: list[str]) -> None:
    while stack:
        parts.append(f"</{stack.pop()}>")


def convert_markdown(markdown: str) -> str:
    text = COMMENT_RE.sub("", markdown)
    text = FRONT_MATTER_RE.sub("", text)
    lines = text.replace("\r\n", "\n").split("\n")
    parts: list[str] = []
    index = 0
    list_stack: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            parts.append("<p>" + inline(" ".join(paragraph).strip()) + "</p>")
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        fence = FENCE_RE.match(line)
        if fence:
            flush_paragraph()
            close_list(parts, list_stack)
            language = fence.group(1)
            collected: list[str] = []
            index += 1
            while index < len(lines) and not FENCE_RE.match(lines[index]):
                collected.append(lines[index])
                index += 1
            class_attr = f' class="language-{html.escape(language)}"' if language else ""
            parts.append(
                f"<pre><code{class_attr}>{html.escape(chr(10).join(collected))}</code></pre>"
            )
            index += 1
            continue

        if index + 1 < len(lines) and line.strip().startswith("|") and TABLE_SEP_RE.match(lines[index + 1]):
            flush_paragraph()
            close_list(parts, list_stack)
            headers = split_row(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(split_row(lines[index]))
                index += 1
            head = "".join(f"<th>{inline(cell)}</th>" for cell in headers)
            body = []
            for row in rows:
                padded = row + [""] * (len(headers) - len(row))
                body.append("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in padded[: len(headers)]) + "</tr>")
            parts.append(
                '<div class="table-wrap"><table><thead><tr>'
                + head
                + "</tr></thead><tbody>"
                + "".join(body)
                + "</tbody></table></div>"
            )
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            close_list(parts, list_stack)
            level = len(heading.group(1))
            title_html = inline(heading.group(2).strip())
            slug = slugify(heading.group(2))
            parts.append(f'<h{level} id="{slug}">{title_html}</h{level}>')
            index += 1
            continue

        if HR_RE.match(line.strip()) and not line.strip().startswith("|"):
            flush_paragraph()
            close_list(parts, list_stack)
            parts.append("<hr>")
            index += 1
            continue

        quote = BLOCKQUOTE_RE.match(line)
        if quote:
            flush_paragraph()
            close_list(parts, list_stack)
            quoted: list[str] = []
            while index < len(lines):
                match = BLOCKQUOTE_RE.match(lines[index])
                if not match:
                    break
                quoted.append(match.group(1))
                index += 1
            parts.append("<blockquote><p>" + inline(" ".join(quoted)) + "</p></blockquote>")
            continue

        ordered = ORDERED_RE.match(line)
        unordered = UNORDERED_RE.match(line)
        marker = ordered or unordered
        if marker:
            flush_paragraph()
            kind = "ol" if ordered else "ul"
            indent = len(marker.group(1).replace("\t", "    "))
            if not list_stack:
                parts.append(f"<{kind}>")
                list_stack.append(kind)
            elif kind != list_stack[-1] and indent == 0:
                close_list(parts, list_stack)
                parts.append(f"<{kind}>")
                list_stack.append(kind)
            elif indent >= 2 and (not list_stack or kind != list_stack[-1] or len(list_stack) == 1):
                parts.append(f"<{kind}>")
                list_stack.append(kind)
            item = marker.group(3) if ordered else marker.group(2)
            parts.append(f"<li>{inline(item)}")
            index += 1
            if index < len(lines) and not (ORDERED_RE.match(lines[index]) or UNORDERED_RE.match(lines[index]) or not lines[index].strip()):
                # Keep simple items closed; continuation lines join as text.
                pass
            parts[-1] += "</li>"
            continue

        if not line.strip():
            flush_paragraph()
            close_list(parts, list_stack)
            index += 1
            continue

        if list_stack:
            close_list(parts, list_stack)
        paragraph.append(line.strip())
        index += 1

    flush_paragraph()
    close_list(parts, list_stack)
    return "\n".join(parts)


def nav_html(current: str) -> str:
    links = []
    for page in PAGES:
        label = page["nav"]
        if not label:
            continue
        href = page["output"]
        current_attr = ' aria-current="page"' if href == current else ""
        links.append(f'<a href="{href}"{current_attr}>{html.escape(label)}</a>')
    return "\n        ".join(links)


def page_shell(title: str, current: str, body: str, wide: bool) -> str:
    prose_class = "prose prose--wide" if wide else "prose"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)} · Lowell T. Wong</title>
  <meta name="description" content="Public AI-systems architecture portfolio for Lowell T. Wong. Static projection of the GitHub profile repository.">
  <link rel="icon" href="favicon.svg" type="image/svg+xml">
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <a class="skip-link" href="#content">Skip to content</a>
  <header class="masthead">
    <div class="masthead-inner">
      <a class="identity" href="index.html">
        <span class="identity-name">Lowell T. Wong</span>
        <span class="identity-tag">Public AI-systems architecture portfolio</span>
      </a>
      <nav class="nav" aria-label="Primary">
        {nav_html(current)}
      </nav>
    </div>
  </header>
  <div class="banner">
    <p>Static HTML projection of the public profile repository. Source-owned evidence stays on GitHub. This page is not a runtime and does not assert a live Cloudflare publication.</p>
  </div>
  <main id="content">
    <article class="wrap {prose_class}">
{body}
    </article>
  </main>
  <footer class="site-footer">
    <div class="site-footer-inner">
      <p>Source: <a href="{SOURCE_REPO}">{SOURCE_REPO}</a></p>
      <p>Machine-readable routes: <a href="registry/profile-repo-routing-registry.json">routing registry</a> · <a href="registry/portfolio-capability-evidence.json">capability evidence</a></p>
      <p>Private by request: <a href="{DAD_URL}">DAD</a>. No other private work is named here.</p>
      <p>Also in this projection: <a href="shannon-note.html">Shannon concept note</a> · <a href="cloudflare-pages.html">Cloudflare Pages notes</a></p>
    </div>
  </footer>
</body>
</html>
"""


def write_favicon(destination: Path) -> None:
    destination.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="LW">
  <rect width="32" height="32" rx="4" fill="#7a2e3a"/>
  <text x="16" y="22" text-anchor="middle" fill="#f3eee4" font-size="13" font-family="Georgia, serif">LW</text>
</svg>
""",
        encoding="utf-8",
    )


def write_robots(destination: Path) -> None:
    destination.write_text("User-agent: *\nAllow: /\n", encoding="utf-8")


def write_404() -> str:
    body = """<div class="not-found">
<h1>Page not found</h1>
<p>This static projection only publishes selected public markdown from the profile repository.</p>
<p><a href="index.html">Return home</a> or open the <a href="public-repo-map.html">public repository map</a>.</p>
</div>
"""
    return page_shell("Not found", "", body, False)


def expected_names(registry: dict) -> list[str]:
    return [repo["name"] for repo in registry["repositories"]]


def check_site(registry: dict) -> None:
    errors: list[str] = []
    for page in PAGES:
        path = SITE / page["output"]
        if not path.is_file():
            errors.append(f"missing {page['output']}")
            continue
        text = path.read_text(encoding="utf-8")
        if "<article" not in text or "</html>" not in text:
            errors.append(f"{page['output']} is not a complete HTML document")
        if DAD_URL not in text and page["output"] != "404.html":
            # DAD belongs in the shared footer of every content page.
            if 'class="site-footer"' in text and DAD_URL not in text:
                errors.append(f"{page['output']} footer is missing the DAD URL")
    map_html = (SITE / "public-repo-map.html").read_text(encoding="utf-8")
    for name in expected_names(registry):
        if f"<code>{name}</code>" not in map_html:
            errors.append(f"public-repo-map.html missing visible repository name {name}")
    home = (SITE / "index.html").read_text(encoding="utf-8")
    for marker in ("Lowell T. Wong", "ai-front-door.html", "Deterministic validation"):
        if marker not in home:
            errors.append(f"index.html missing source marker: {marker}")
    for path in SITE.glob("*.html"):
        text = path.read_text(encoding="utf-8")
        if "\x00PH" in text or "@@PH" in text:
            errors.append(f"{path.name} still contains unresolved placeholders")
        for href in re.findall(r'href="([^"]+)"', text):
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            target = href.split("#", 1)[0]
            if target and not (SITE / target).exists():
                errors.append(f"{path.name} broken local href: {href}")
    for relative in REGISTRY_COPIES:
        if not (SITE / relative).is_file():
            errors.append(f"missing copied registry file {relative}")
    lowered_forbidden = ("career os", "dad journal")
    for path in SITE.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".html", ".css", ".json", ".txt", ".svg"}:
            continue
        lowered = path.read_text(encoding="utf-8", errors="ignore").lower()
        for token in lowered_forbidden:
            if token in lowered:
                errors.append(f"forbidden token {token!r} in {path.relative_to(SITE)}")
    if errors:
        raise SystemExit("PAGES SITE CHECK FAILED\n" + "\n".join(f"- {item}" for item in errors))


def build() -> None:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    shutil.copyfile(PAGES_SRC / "styles.css", SITE / "styles.css")
    shutil.copyfile(PAGES_SRC / "_headers", SITE / "_headers")
    write_favicon(SITE / "favicon.svg")
    write_robots(SITE / "robots.txt")
    (SITE / "404.html").write_text(write_404(), encoding="utf-8")
    for relative in REGISTRY_COPIES:
        destination = SITE / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, destination)
    for page in PAGES:
        source = ROOT / page["source"]
        body = convert_markdown(source.read_text(encoding="utf-8"))
        document = page_shell(page["title"], page["output"], body, page["wide"] == "true")
        (SITE / page["output"]).write_text(document, encoding="utf-8")
    check_site(registry)
    print(
        f"Built static projection in {SITE.relative_to(ROOT)}: "
        f"{len(PAGES)} markdown pages, {registry['public_inventory_count']} public repositories."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the public static HTML projection.")
    parser.parse_args()
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
