"""Unit tests for cache functionality."""
import time
from unittest.mock import MagicMock, patch
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from valhopper.valhopper_cli import BittensorClient, ReturnError, ReturnResult


def test_cache_is_valid_with_none():
    """Cache with None data is invalid."""
    client = BittensorClient('finney')
    assert not client._cache_is_valid(None)


def test_cache_is_valid_with_fresh_data():
    """Cache with data from 1 second ago is valid."""
    client = BittensorClient('finney')
    fresh = ("data", time.time())
    assert client._cache_is_valid(fresh)


def test_cache_is_valid_with_stale_data():
    """Cache older than TTL is invalid."""
    client = BittensorClient('finney')
    stale = ("data", time.time() - 400)  # Older than 300s TTL
    assert not client._cache_is_valid(stale)


def test_refresh_caches_clears_all():
    """refresh_caches clears all cache storage."""
    client = BittensorClient('finney')
    # Populate caches
    client._delegates_cache = ([], time.time())
    client._metagraph_cache = {1: ({}, time.time())}
    client._current_block = (1000, time.time())
    client._tempo_cache = {1: (360, time.time())}

    client.refresh_caches()

    assert client._delegates_cache is None
    assert client._metagraph_cache == {}
    assert client._current_block is None
    assert client._tempo_cache == {}
