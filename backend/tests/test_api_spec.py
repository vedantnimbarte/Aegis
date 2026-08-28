"""Deriving an OpenAPI description from source."""
from __future__ import annotations

from pathlib import Path

from app.services import api_spec


def test_fastapi_decorators() -> None:
    routes = api_spec.extract_routes(
        '@router.get("/users")\n'
        '@router.post("/users/{user_id}/invoices")\n',
        "app/api.py",
    )
    assert ("GET", "/users") in [(r.method, r.path) for r in routes]
    assert ("POST", "/users/{user_id}/invoices") in [(r.method, r.path) for r in routes]


def test_flask_route_with_methods() -> None:
    routes = api_spec.extract_routes(
        "@app.route('/login', methods=['GET', 'POST'])", "app.py"
    )
    assert {r.method for r in routes} == {"GET", "POST"}


def test_express_paths_and_params() -> None:
    routes = api_spec.extract_routes(
        "router.get('/orders/:orderId', handler)", "routes.js"
    )
    assert routes[0].path == "/orders/{orderId}"


def test_spring_and_nest_annotations() -> None:
    spring = api_spec.extract_routes('@GetMapping("/health")', "Ctrl.java")
    assert spring[0].method == "GET"
    nest = api_spec.extract_routes("@Post('users')", "users.controller.ts")
    assert (nest[0].method, nest[0].path) == ("POST", "/users")


def test_django_urls_are_recognized_only_in_urls_py() -> None:
    source = "path('accounts/<int:pk>/', view)"
    # The trailing slash is kept: with APPEND_SLASH that *is* the real URL,
    # and requesting it without one gets a redirect rather than the endpoint.
    assert api_spec.extract_routes(source, "app/urls.py")[0].path == "/accounts/{pk}/"
    assert api_spec.extract_routes(source, "app/views.py") == []


def test_static_assets_and_config_keys_are_not_routes() -> None:
    """Every regex over source code collects false positives; these are the
    ones that would otherwise be reported as API surface."""
    assert api_spec.extract_routes("app.get('config.key')", "a.js") == []
    assert api_spec.extract_routes("app.get('/static/main.js')", "a.js") == []


def test_duplicate_declarations_collapse() -> None:
    routes = api_spec.extract_routes(
        '@app.get("/users")\n@app.get("/users")\n', "a.py"
    )
    assert len(routes) == 1


def test_derive_spec_over_a_tree(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "api.py").write_text(
        '@router.get("/users")\n@router.delete("/users/{user_id}")\n', encoding="utf-8"
    )
    # Vendored code must not be mistaken for the application's own surface.
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "lib.js").write_text(
        "app.get('/should-not-appear')", encoding="utf-8"
    )

    document = api_spec.derive_spec(tmp_path, title="Acme", server_url="https://acme.test")
    assert set(document["paths"]) == {"/users", "/users/{user_id}"}
    assert document["servers"][0]["url"] == "https://acme.test"
    assert document["paths"]["/users/{user_id}"]["delete"]["parameters"][0]["name"] == "user_id"
    assert "/should-not-appear" not in document["paths"]


def test_derive_spec_returns_none_when_there_is_nothing(tmp_path: Path) -> None:
    """An empty spec would tell the engine to test nothing while looking like
    it had a plan."""
    (tmp_path / "readme.md").write_text("no code here", encoding="utf-8")
    assert api_spec.derive_spec(tmp_path) is None


def test_summarize_is_honest_about_nothing_found() -> None:
    assert "No API routes" in api_spec.summarize(None)
