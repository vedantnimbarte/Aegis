"""Derive an OpenAPI description of an API from its source.

APIs are where the breaches are, and the usual blocker to testing one is
banal: nobody has an up-to-date spec, so the scanner has no routes to
exercise and falls back to crawling a single-page app that renders nothing
useful. Aegis already clones the repository at scan time — the routes are
right there in the code.

This is a *reader*, not a compiler. It matches the route-declaration idioms of
the frameworks people actually ship, records where each route was found, and
stops. It will miss routes built by metaprogramming, and it says so rather
than pretending to completeness: ``sources`` names which frameworks were
recognised so a user can tell "no API here" from "we could not read yours".

Pure and dependency-free (paths in, plain dicts out) so it can be unit-tested
without a checkout, matching ``strix_report`` and ``scan_progress``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")

# Directories that never contain first-party routes and are enormous. Skipping
# them is the difference between a scan that reads a repo and one that reads a
# dependency tree.
SKIP_DIRS = frozenset(
    {
        ".git", "node_modules", "vendor", "dist", "build", "target", ".venv",
        "venv", "__pycache__", ".next", ".nuxt", "coverage", "site-packages",
        ".tox", ".mypy_cache", ".pytest_cache", "migrations", "bower_components",
    }
)

_EXTENSIONS = frozenset(
    {".py", ".js", ".ts", ".jsx", ".tsx", ".rb", ".go", ".java", ".kt", ".php", ".cs"}
)


@dataclass(frozen=True)
class Route:
    """One discovered endpoint."""

    method: str
    path: str
    source: str
    framework: str


def _methods_group() -> str:
    return "|".join(HTTP_METHODS)


# Each pattern must yield a `method` and a `path` group. Written against the
# declaration forms these frameworks document, and tolerant of surrounding
# whitespace because formatters differ.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # FastAPI / Flask / Starlette: @app.get("/x"), @router.post("/x")
    (
        "python-decorator",
        re.compile(
            rf"@\w+\.(?P<method>{_methods_group()})\s*\(\s*[\"'](?P<path>/[^\"']*)[\"']",
            re.IGNORECASE,
        ),
    ),
    # Flask: @app.route("/x", methods=["POST"]) — method captured separately.
    (
        "flask-route",
        re.compile(
            r"@\w+\.route\s*\(\s*[\"'](?P<path>/[^\"']*)[\"']"
            r"(?P<rest>[^)]*)\)",
            re.IGNORECASE,
        ),
    ),
    # Express / Koa / Fastify: app.get('/x', ...), router.post("/x", ...)
    (
        "express",
        re.compile(
            rf"\b\w+\.(?P<method>{_methods_group()})\s*\(\s*[\"'`](?P<path>/[^\"'`]*)[\"'`]",
            re.IGNORECASE,
        ),
    ),
    # NestJS: @Get('x'), @Post()
    (
        "nestjs",
        re.compile(
            r"@(?P<method>Get|Post|Put|Patch|Delete|Head|Options)\s*\(\s*"
            r"[\"'](?P<path>[^\"']*)[\"']\s*\)"
        ),
    ),
    # Spring: @GetMapping("/x"), @RequestMapping(value = "/x")
    (
        "spring",
        re.compile(
            r"@(?P<method>Get|Post|Put|Patch|Delete)Mapping\s*\(\s*"
            r"(?:value\s*=\s*)?[\"'](?P<path>/[^\"']*)[\"']"
        ),
    ),
    # Go: r.GET("/x", handler), mux.HandleFunc("/x", handler)
    (
        "go",
        re.compile(
            rf"\.(?P<method>{_methods_group()})\s*\(\s*[\"`](?P<path>/[^\"`]*)[\"`]",
            re.IGNORECASE,
        ),
    ),
    # Rails routes.rb: get '/x' => 'c#a', post 'x', to: 'c#a'
    (
        "rails",
        re.compile(
            rf"^\s*(?P<method>{_methods_group()})\s+[\"'](?P<path>/?[^\"']+)[\"']",
            re.IGNORECASE | re.MULTILINE,
        ),
    ),
    # Laravel: Route::get('/x', ...)
    (
        "laravel",
        re.compile(
            rf"Route::(?P<method>{_methods_group()})\s*\(\s*[\"'](?P<path>/?[^\"']*)[\"']",
            re.IGNORECASE,
        ),
    ),
)

# Django's urls.py declares no method, so routes land as GET with a note.
_DJANGO = re.compile(r"\b(?:path|re_path)\s*\(\s*[\"'](?P<path>[^\"']*)[\"']")
_FLASK_METHODS = re.compile(r"methods\s*=\s*\[([^\]]*)\]", re.IGNORECASE)

# Framework-specific path-parameter syntaxes, normalized to OpenAPI's {name}.
_PARAM_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"<(?:[a-zA-Z_]+:)?([a-zA-Z_][\w]*)>"), r"{\1}"),   # Flask/Django
    (re.compile(r":([a-zA-Z_][\w]*)"), r"{\1}"),                     # Express/Rails
    (re.compile(r"\(\?P<([a-zA-Z_][\w]*)>[^)]*\)"), r"{\1}"),        # Django re_path
)


def normalize_path(raw: str) -> str:
    """Rewrite a framework's path syntax into an OpenAPI path."""
    path = raw.strip()
    if not path.startswith("/"):
        path = "/" + path
    for pattern, replacement in _PARAM_REWRITES:
        path = pattern.sub(replacement, path)
    # Drop regex anchors that leak in from Django's re_path.
    path = path.replace("^", "").replace("$", "")
    # Collapse duplicate slashes without touching the leading one.
    while "//" in path:
        path = path.replace("//", "/")
    return path or "/"


def _looks_like_route(path: str) -> bool:
    """Filter the false positives every regex over source code collects.

    ``app.get('config.key')`` and a fetch to ``https://…`` both match a naive
    pattern; neither is a route this service serves.
    """
    if not path.startswith("/"):
        return False
    if path.startswith("//"):
        return False
    if any(ch in path for ch in (" ", "<", ">", "\\")):
        return False
    # A file extension means a static asset, not an API route.
    tail = path.rsplit("/", 1)[-1]
    if "." in tail and not tail.endswith("}"):
        return False
    return True


def extract_routes(text: str, source: str) -> list[Route]:
    """Every route declaration recognisable in one file's contents."""
    routes: list[Route] = []
    seen: set[tuple[str, str]] = set()

    def add(method: str, raw_path: str, framework: str) -> None:
        path = normalize_path(raw_path)
        if not _looks_like_route(path):
            return
        key = (method.upper(), path)
        if key in seen:
            return
        seen.add(key)
        routes.append(Route(method.upper(), path, source, framework))

    for framework, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            groups = match.groupdict()
            if framework == "flask-route":
                methods = _FLASK_METHODS.search(groups.get("rest") or "")
                names = (
                    re.findall(r"[\"'](\w+)[\"']", methods.group(1))
                    if methods
                    else ["GET"]
                )
                for name in names:
                    if name.lower() in HTTP_METHODS:
                        add(name, groups["path"], framework)
                continue
            add(groups["method"], groups["path"], framework)

    if source.endswith("urls.py"):
        for match in _DJANGO.finditer(text):
            add("GET", match.group("path"), "django")

    return routes


def _iter_source_files(
    root: Path, max_files: int, max_bytes: int
) -> Iterable[tuple[Path, str]]:
    """Walk the checkout, skipping vendored trees and files too big to be code."""
    count = 0
    for path in sorted(root.rglob("*")):
        if count >= max_files:
            return
        if not path.is_file() or path.suffix not in _EXTENSIONS:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            if path.stat().st_size > max_bytes:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        count += 1
        yield path, text


def derive_spec(
    root: Path,
    *,
    title: str = "Discovered API",
    server_url: Optional[str] = None,
    max_files: int = 2000,
    max_file_bytes: int = 512_000,
) -> Optional[dict]:
    """Build an OpenAPI 3.1 document from the routes found under ``root``.

    Returns None when nothing was found — an empty spec would tell the engine
    to test nothing while looking like it had a plan.
    """
    routes: list[Route] = []
    for path, text in _iter_source_files(root, max_files, max_file_bytes):
        try:
            relative = str(path.relative_to(root))
        except ValueError:  # pragma: no cover - rglob paths are always under root
            relative = str(path)
        routes.extend(extract_routes(text, relative))

    if not routes:
        return None
    return build_document(routes, title=title, server_url=server_url)


def build_document(
    routes: list[Route], *, title: str, server_url: Optional[str] = None
) -> dict:
    """Render discovered routes as an OpenAPI document."""
    paths: dict[str, dict] = {}
    frameworks: set[str] = set()

    for route in sorted(routes, key=lambda r: (r.path, r.method)):
        frameworks.add(route.framework)
        operations = paths.setdefault(route.path, {})
        if route.method.lower() in operations:
            continue
        operation: dict = {
            "summary": f"{route.method} {route.path}",
            "description": (
                "Discovered by Aegis from source. Parameters and schemas are "
                "not inferred — treat the shape as unverified."
            ),
            "responses": {"default": {"description": "Not described"}},
            "x-aegis-source": route.source,
            "x-aegis-framework": route.framework,
        }
        parameters = [
            {
                "name": name,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
            for name in re.findall(r"\{([^}]+)\}", route.path)
        ]
        if parameters:
            operation["parameters"] = parameters
        operations[route.method.lower()] = operation

    document: dict = {
        "openapi": "3.1.0",
        "info": {
            "title": title,
            "version": "0.0.0-derived",
            "description": (
                "Derived from source by Aegis. Routes declared dynamically or "
                "through metaprogramming are not represented."
            ),
        },
        "paths": paths,
        "x-aegis-derived": True,
        "x-aegis-frameworks": sorted(frameworks),
        "x-aegis-route-count": len(routes),
    }
    if server_url:
        document["servers"] = [{"url": server_url}]
    return document


def summarize(document: Optional[dict]) -> str:
    """One line describing what was derived, for logs and the UI."""
    if not document:
        return "No API routes found in source"
    count = len(document.get("paths") or {})
    frameworks = ", ".join(document.get("x-aegis-frameworks") or []) or "unknown"
    return f"{count} path(s) derived from {frameworks}"
