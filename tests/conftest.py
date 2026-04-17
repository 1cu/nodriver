from __future__ import annotations

import http.server
import os
import shutil
import socketserver
import asyncio
import time
import subprocess
import sys
import threading
from pathlib import Path
from typing import Iterator

import pytest
import pytest_asyncio

from nodriver.core.browser import Browser
from nodriver.core.config import Config


class _ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class _SiteHandler(http.server.BaseHTTPRequestHandler):
    pages = {
        "/": """
            <!doctype html>
            <html>
              <head><title>nodriver test</title></head>
              <body>
                <h1 id="headline">nodriver test page</h1>
                <div id="status">ready</div>
              </body>
            </html>
        """,
        "/next": """
            <!doctype html>
            <html>
              <body><p id="page">second page</p></body>
            </html>
        """,
    }

    def do_GET(self):
        body = self.pages.get(self.path)
        if body is None:
            self.send_error(404)
            return

        payload = "\n".join(line.strip() for line in body.splitlines() if line.strip())
        encoded = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        return


def _candidate_browser_paths() -> Iterator[Path]:
    env = os.environ.get("NODRIVER_BROWSER_EXECUTABLE")
    if env:
        yield Path(env)

    for name in (
        "chromium",
        "chromium-browser",
        "google-chrome",
        "google-chrome-stable",
        "chrome",
        "msedge",
    ):
        found = shutil.which(name)
        if found:
            yield Path(found)

    if sys.platform == "darwin":
        for path in (
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        ):
            yield path

    if sys.platform.startswith("win"):
        for path in (
            Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
            Path(r"C:\Program Files\Chromium\Application\chrome.exe"),
            Path(r"C:\Program Files (x86)\Chromium\Application\chrome.exe"),
            Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
            Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
        ):
            yield path


def resolve_browser_executable() -> Path:
    for candidate in _candidate_browser_paths():
        if candidate.exists():
            return candidate

    msg = (
        "Could not locate a Chromium/Chrome executable. Set NODRIVER_BROWSER_EXECUTABLE to "
        "the browser path."
    )
    if os.environ.get("CI"):
        raise RuntimeError(msg)
    pytest.skip(msg)
    raise RuntimeError(msg)


def _browser_startup_timeout_seconds() -> float:
    raw = os.environ.get("NODRIVER_BROWSER_STARTUP_TIMEOUT", "60")
    try:
        return float(raw)
    except ValueError:
        return 60.0


def _tail(text: str | bytes | None, limit: int = 4000) -> str:
    if text is None:
        return ""
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return text[-limit:]


def _target_summary(instance: Browser) -> str:
    targets = getattr(instance, "targets", []) or []
    if not targets:
        return "none"

    items = []
    for target in targets[:5]:
        raw_target = getattr(target, "target", None)
        if raw_target is None:
            items.append(repr(target))
            continue

        target_id = getattr(raw_target, "target_id", "?")
        target_type = getattr(raw_target, "type", "?")
        target_url = getattr(raw_target, "url", "")
        items.append(f"{target_id}:{target_type}:{target_url}")

    if len(targets) > 5:
        items.append(f"...(+{len(targets) - 5} more)")
    return "; ".join(items)


async def _process_output_tail(proc: asyncio.subprocess.Process) -> tuple[str, str]:
    try:
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
        return _tail(stdout), _tail(stderr)
    except Exception as exc:  # noqa: BLE001
        return "", f"<failed to collect browser output: {exc!r}>"


async def _browser_failure_details(
    instance: Browser,
    browser_executable: Path,
    elapsed: float,
    reason: Exception,
) -> str:
    proc = getattr(instance, "_process", None)
    pid = getattr(proc, "pid", None) if proc else None
    returncode = getattr(proc, "returncode", None) if proc else None
    stdout_tail = ""
    stderr_tail = ""

    if proc is not None:
        stdout_tail, stderr_tail = await _process_output_tail(proc)

    return (
        "browser startup failed\n"
        f"  executable: {browser_executable}\n"
        f"  timeout_s: {_browser_startup_timeout_seconds()}\n"
        f"  elapsed_s: {elapsed:.2f}\n"
        f"  pid: {pid}\n"
        f"  returncode: {returncode}\n"
        f"  targets: {_target_summary(instance)}\n"
        f"  reason: {reason!r}\n"
        f"  stdout_tail: {stdout_tail or '<empty>'}\n"
        f"  stderr_tail: {stderr_tail or '<empty>'}"
    )


@pytest.fixture(scope="session")
def browser_executable() -> Path:
    return resolve_browser_executable()


async def _start_browser(browser_executable: Path):
    config = Config(
        headless=True,
        browser_executable_path=str(browser_executable),
        sandbox=False,
    )
    instance = Browser(config)
    started_at = time.monotonic()
    try:
        await asyncio.wait_for(
            instance.start(), timeout=_browser_startup_timeout_seconds()
        )
    except Exception as exc:  # noqa: BLE001
        elapsed = time.monotonic() - started_at
        details = await _browser_failure_details(
            instance,
            browser_executable,
            elapsed,
            exc,
        )
        await _stop_browser(instance)
        raise RuntimeError(details) from exc

    return instance


async def _stop_browser(instance):
    proc = getattr(instance, "_process", None)
    instance.stop()
    if proc is not None:
        try:
            await asyncio.wait_for(proc.wait(), timeout=10)
        except asyncio.TimeoutError:
            proc.kill()
            await asyncio.wait_for(proc.wait(), timeout=10)


@pytest.fixture(autouse=True)
def integration_test_diagnostics(request):
    if not request.node.get_closest_marker("integration"):
        yield
        return

    started_at = time.monotonic()
    browser_executable = request.getfixturevalue("browser_executable")
    requested_fixtures = [
        name for name in ("browser", "isolated_browser") if name in request.fixturenames
    ]
    print(
        f"[integration] START {request.node.nodeid} "
        f"fixtures={requested_fixtures} "
        f"browser_executable={browser_executable}",
        flush=True,
    )
    try:
        yield
    finally:
        elapsed = time.monotonic() - started_at
        print(
            f"[integration] END {request.node.nodeid} elapsed={elapsed:.2f}s",
            flush=True,
        )


@pytest_asyncio.fixture(scope="module", loop_scope="module")
async def browser(browser_executable: Path):
    instance = await _start_browser(browser_executable)
    try:
        yield instance
    finally:
        await _stop_browser(instance)


@pytest_asyncio.fixture(scope="function", loop_scope="module")
async def isolated_browser(browser_executable: Path):
    instance = await _start_browser(browser_executable)
    try:
        yield instance
    finally:
        await _stop_browser(instance)


@pytest.fixture(scope="session")
def test_site() -> Iterator[str]:
    server = _ThreadingHTTPServer(("127.0.0.1", 0), _SiteHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host = server.server_address[0]
        port = server.server_address[1]
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
