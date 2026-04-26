"""Tests for BittensorClient — delegate indexing and cache."""
import time
from unittest.mock import MagicMock
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.client import BittensorClient


def _make_mock_delegate(hotkey="hk1", take=0.18, registrations=None, validator_permits=None, nominators=None):
    d = MagicMock()
    d.hotkey_ss58 = hotkey
    d.take = take
    d.registrations = registrations or [1]
    d.validator_permits = validator_permits or [1]
    d.nominators = nominators or ["nom1"]
    return d


def test_cache_is_valid_with_none():
    mock_sub = MagicMock()
    client = BittensorClient(subtensor=mock_sub)
    assert not client._cache_is_valid(None)


def test_cache_is_valid_with_fresh_data():
    mock_sub = MagicMock()
    client = BittensorClient(subtensor=mock_sub)
    fresh = ("data", time.time())
    assert client._cache_is_valid(fresh)


def test_cache_is_valid_with_stale_data():
    mock_sub = MagicMock()
    client = BittensorClient(subtensor=mock_sub)
    stale = ("data", time.time() - 400)
    assert not client._cache_is_valid(stale)


def test_refresh_caches_clears_all():
    mock_sub = MagicMock()
    client = BittensorClient(subtensor=mock_sub)
    client._delegates_cache = ([], {}, time.time())
    client._delegates_by_hotkey = {"hk1": MagicMock()}
    client._metagraph_cache = {1: ({}, time.time())}
    client._current_block = (1000, time.time())
    client._tempo_cache = {1: (360, time.time())}

    client.refresh_caches()

    assert client._delegates_cache is None
    assert client._delegates_by_hotkey == {}
    assert client._metagraph_cache == {}
    assert client._current_block is None
    assert client._tempo_cache == {}


def test_delegate_indexing():
    mock_sub = MagicMock()
    d1 = _make_mock_delegate(hotkey="hk_alpha")
    d2 = _make_mock_delegate(hotkey="hk_beta")
    mock_sub.get_delegates.return_value = [d1, d2]

    client = BittensorClient(subtensor=mock_sub)
    delegates = client.get_delegates()

    assert len(delegates) == 2
    assert client._get_delegate_by_hotkey("hk_alpha") is d1
    assert client._get_delegate_by_hotkey("hk_beta") is d2
    assert client._get_delegate_by_hotkey("nonexistent") is None


def test_get_take_from_index():
    mock_sub = MagicMock()
    d1 = _make_mock_delegate(hotkey="hk1", take=0.10)
    mock_sub.get_delegates.return_value = [d1]

    client = BittensorClient(subtensor=mock_sub)
    assert client._get_take("hk1") == 0.10
    assert client._get_take("unknown") == 0.18


def test_di_subtensor():
    mock_sub = MagicMock()
    client = BittensorClient(subtensor=mock_sub)
    assert client.subtensor is mock_sub
