from types import SimpleNamespace

import pytest

from nodriver.core.browser import Browser
from nodriver.core.config import Config


@pytest.mark.asyncio
async def test_wait_for_initial_targets_retries_until_page_exists(monkeypatch):
    browser = Browser(
        Config(
            headless=True,
            browser_executable_path="/tmp/chromium",
            sandbox=False,
        )
    )

    calls = 0

    async def fake_update_targets():
        nonlocal calls
        calls += 1
        if calls == 3:
            browser.targets.append(SimpleNamespace(type_="page"))

    monkeypatch.setattr(browser, "update_targets", fake_update_targets)

    await browser._wait_for_initial_targets(retries=5, delay=0)

    assert calls == 3
    assert browser.main_tab.type_ == "page"
