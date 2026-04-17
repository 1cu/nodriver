from __future__ import annotations

import asyncio

import pytest

from nodriver import cdp


pytestmark = [pytest.mark.integration, pytest.mark.asyncio(loop_scope="module")]


async def test_browser_starts_headless(browser):
    assert browser.connection is not None, "browser connection was not established"
    assert browser.main_tab is not None, "browser.main_tab was not available"
    assert browser.tabs, f"browser.tabs was empty: {browser.targets!r}"


async def test_can_navigate_data_url_and_read_content(browser):
    tab = browser.main_tab
    await tab.get("data:text/html,<html><body><h1>data url</h1></body></html>")

    content = await tab.get_content()

    assert "data url" in content.lower(), f"unexpected content: {content!r}"


async def test_can_open_and_close_tab(browser):
    tab = browser.main_tab
    new_tab = await tab.get(
        "data:text/html,<html><body><p>new tab</p></body></html>",
        new_tab=True,
    )

    await browser.update_targets()
    assert len(browser.tabs) >= 2

    await new_tab.close()
    for _ in range(50):
        await browser.update_targets()
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
        await tab.get(test_site)
        await tab.sleep(0.5)

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
