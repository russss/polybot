import configparser
from unittest.mock import MagicMock

from polybot.service import Bluesky


def test_interactive_no(monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _: "n")
    config = configparser.ConfigParser()
    service = Bluesky(config, False, True)
    service.post('Status')


def test_interactive_yes(monkeypatch):
    monkeypatch.setattr('builtins.input', lambda _: "y")
    config = configparser.ConfigParser()
    service = Bluesky(config, False, True)
    # Better way of mocking?
    service.connected = True
    service.bluesky = MagicMock()
    m = MagicMock()
    m.cid = 'CID'
    m.uri = 'URI'
    service.bluesky.send_post.return_value = m
    service.post('Status')
