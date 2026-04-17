from nodriver import Browser, Config, Element, Tab, start


def test_public_api_exports():
    assert Browser.__name__ == "Browser"
    assert Tab.__name__ == "Tab"
    assert Config.__name__ == "Config"
    assert Element.__name__ == "Element"
    assert callable(start)
