from pathlib import Path

from nodriver import Config


def test_config_generates_browser_arguments():
    config = Config(
        headless=True,
        browser_executable_path=Path("/tmp/chromium"),
        browser_args=["--foo", "--bar"],
        sandbox=False,
    )

    args = config()

    assert config.browser_executable_path == Path("/tmp/chromium")
    assert config.headless is True
    assert config.sandbox is False
    assert config.uses_custom_data_dir is False
    assert "--foo" in args
    assert "--bar" in args
    assert "--headless=new" in args
    assert "--no-sandbox" in args


def test_config_creates_temp_profile_by_default(monkeypatch):
    monkeypatch.setattr(
        "nodriver.core.config.find_chrome_executable",
        lambda return_all=False: Path("/tmp/chromium"),
    )
    config = Config(headless=True)

    assert config.user_data_dir
    assert config.uses_custom_data_dir is False
