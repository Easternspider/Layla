"""Surface crawl stays on the target and separates the three roles."""
import contextlib
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

from app.services import surface


def test_crawl_rejects_another_host():
    command = surface.crawl_command("app.example", "https://app.example/start", "sessions/user.jar", "user")
    assert "https://app.example/start" in command
    assert "sessions/user.jar" in command
    try:
        surface.crawl_command("app.example", "https://evil.example/", "", "anon")
    except ValueError as exc:
        assert "цели" in str(exc)
    else:
        raise AssertionError("foreign url was accepted")
    try:
        surface.compare_command("app.example", ["//evil.example"], "", "")
    except ValueError:
        return
    raise AssertionError("scheme-relative path was accepted")


def test_verdicts_distinguish_auth_and_the_other_user():
    assert surface.verdict("/account", 401, 200, None) == "auth-only"
    assert surface.verdict("/orders/15", 401, 200, 200) == "idor-candidate"
    assert surface.verdict("/orders/15", 401, 200, 403) == "separated"
    assert surface.verdict("/health", 200, 200, 200) == "same"
    assert surface.verdict("/health", 0, None, None) == "blocked"
    rows = surface.absorb([
        {"path": "/orders/15", "anon": 401, "user": 200, "other": 200},
        {"path": "/api/me", "status": None, "role": "user", "from": "js"},
    ])
    by_path = {row["path"]: row for row in rows}
    assert by_path["/orders/15"]["verdict"] == "idor-candidate"
    assert by_path["/api/me"]["from"] == "js"


def test_actions_exist():
    from app.services.pentest_workers import Action
    assert Action.model_validate({"action": "save_role", "query": "user", "path": "user.jar"}).query == "user"
    assert Action.model_validate({"action": "map_surface"}).action == "map_surface"
    assert Action.model_validate({"action": "compare_roles"}).action == "compare_roles"


def test_remote_crawler_reads_links_and_js_routes():
    pages = {
        "/": ("text/html", '<a href="/account">A</a><script src="/app.js"></script>'),
        "/account": ("text/html", "<form action='/profile'></form>"),
        "/app.js": ("text/javascript", 'fetch("/api/orders")'),
        "/profile": ("text/html", "ok"),
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            kind, body = pages.get(self.path.split("?")[0], ("text/plain", ""))
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    try:
        source = surface.crawl_command("127.0.0.1", f"http://127.0.0.1:{port}/", "", "anon")
        body = source.split("<< 'PY'\n", 1)[1].rsplit("\nPY", 1)[0]
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            exec(body, {})
        found = surface.parse_report(buffer.getvalue())
    finally:
        server.shutdown()
    paths = {row["path"] for row in found}
    assert "/account" in paths
    assert "/profile" in paths
    assert "/api/orders" in paths
