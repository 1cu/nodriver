from __future__ import annotations

import http.server
import os
import shutil
import socketserver
import asyncio
import subprocess
import sys
import threading
from pathlib import Path
from typing import Iterator

import pytest
import pytest_asyncio

from nodriver import start


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
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            for path in (
                Path(local_app_data) / "Chromium" / "Application" / "chrome.exe",
                Path(local_app_data)
                / "Google"
                / "Chrome"
                / "Application"
                / "chrome.exe",
                Path(local_app_data)
                / "Microsoft"
                / "Edge"
                / "Application"
                / "msedge.exe",
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


@pytest.fixture(scope="session")
def browser_executable() -> Path:
    return resolve_browser_executable()


@pytest_asyncio.fixture
async def browser(browser_executable: Path):
    instance = await start(
        headless=True,
        browser_executable_path=str(browser_executable),
        sandbox=False,
    )
    for _ in range(20):
        await instance.update_targets()
        if instance.targets:
            break
        await asyncio.sleep(0.25)
    try:
        yield instance
    finally:
        proc = getattr(instance, "_process", None)
        instance.stop()
        if proc is not None:
            try:
                await asyncio.wait_for(proc.wait(), timeout=10)
            except asyncio.TimeoutError:
                proc.kill()
                await asyncio.wait_for(proc.wait(), timeout=10)


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
