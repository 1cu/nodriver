from __future__ import annotations

import asyncio
import time
from typing import cast

import pytest

from nodriver import Tab, cdp


pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]


def _target_summary(browser) -> str:
    return f"targets={len(getattr(browser, 'targets', []) or [])}"


async def _await_logged(label: str, awaitable, browser, tab=None):
    started_at = time.monotonic()
    tab_info = ""
    if tab is not None:
        tab_info = (
            f" tab={getattr(tab, 'id', None)!r}"
            f" url={getattr(tab, 'url', None)!r}"
            f" closed={getattr(tab, 'closed', None)!r}"
        )
    print(
        f"[integration-op] START {label}{tab_info} targets={_target_summary(browser)}",
        flush=True,
    )
    result = await awaitable
    elapsed = time.monotonic() - started_at
    extra = ""
    if label.endswith("get_content") and isinstance(result, str):
        extra = f" content_len={len(result)}"
    print(
        f"[integration-op] END {label}{tab_info} elapsed={elapsed:.2f}s"
        f" targets={_target_summary(browser)}{extra}",
        flush=True,
    )
    return result


def _log_checkpoint(label: str, browser, tab=None):
    tab_info = ""
    if tab is not None:
        tab_info = (
            f" tab={getattr(tab, 'id', None)!r}"
            f" url={getattr(tab, 'url', None)!r}"
            f" closed={getattr(tab, 'closed', None)!r}"
        )
    print(
        f"[integration-op] CHECKPOINT {label}{tab_info} {_target_summary(browser)}",
        flush=True,
    )


async def test_browser_starts_headless(browser):
    assert browser.connection is not None, "browser connection was not established"
    assert browser.main_tab is not None, "browser.main_tab was not available"
    assert browser.tabs, f"browser.tabs was empty: {browser.targets!r}"


async def test_can_navigate_data_url_and_read_content(browser):
    _log_checkpoint("before browser.main_tab", browser)
    tab = browser.main_tab
    _log_checkpoint("after browser.main_tab", browser, tab)
    await asyncio.wait_for(
        _await_logged(
            "tab.get(data-url)",
            tab.get("data:text/html,<html><body><h1>data url</h1></body></html>"),
            browser,
            tab,
        ),
        timeout=10,
    )

    content = await _await_logged("tab.get_content", tab.get_content(), browser, tab)

    assert "data url" in content.lower(), f"unexpected content: {content!r}"


async def test_can_open_and_close_tab(browser):
    _log_checkpoint("before browser.main_tab", browser)
    tab = browser.main_tab
    _log_checkpoint("after browser.main_tab", browser, tab)
    new_tab = cast(
        Tab,
        await _await_logged(
            "tab.get(new_tab)",
            tab.get(
                "data:text/html,<html><body><p>new tab</p></body></html>", new_tab=True
            ),
            browser,
            tab,
        ),
    )

    await _await_logged("browser.update_targets#1", browser.update_targets(), browser)
    assert len(browser.tabs) >= 2

    await _await_logged("new_tab.close", new_tab.close(), browser, new_tab)
    for _ in range(50):
        await _await_logged(
            "browser.update_targets#poll", browser.update_targets(), browser
        )
        if len(browser.tabs) == 1:
            break
        await asyncio.sleep(0.1)

    assert len(browser.tabs) == 1, f"tabs after close: {browser.tabs!r}"


async def test_event_handler_registration_smoke(browser, test_site):
    events: list[str] = []

    def on_request(event):
        events.append(event.request.url)

    tab = browser.main_tab
    tab.add_handler(cdp.network.RequestWillBeSent, on_request)
    try:
        await _await_logged("tab.get(test_site)", tab.get(test_site), browser, tab)
        await _await_logged("tab.sleep(0.5)", tab.sleep(0.5), browser, tab)

        assert events, "no network events were captured"
        assert any(url.startswith(test_site) for url in events), (
            f"unexpected events: {events!r}"
        )
    finally:
        tab.remove_handler(cdp.network.RequestWillBeSent, on_request)


async def test_browser_stop_after_disconnect(isolated_browser):
    proc = isolated_browser._process

    await isolated_browser.connection.disconnect()
    isolated_browser.stop()
    await asyncio.wait_for(proc.wait(), timeout=10)

    assert proc.returncode is not None, "browser process still running after stop()"
