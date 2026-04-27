"""Tests for valhopper_transactions retry logic."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.valhopper_transactions import _is_retryable


def test_is_retryable_rate_limit():
    assert _is_retryable("Rate limit exceeded")


def test_is_retryable_timeout():
    assert _is_retryable("Connection timeout")


def test_is_retryable_network():
    assert _is_retryable("Network error")


def test_is_retryable_429():
    assert _is_retryable("429 Too Many Requests")


def test_is_retryable_503():
    assert _is_retryable("503 Service Unavailable")


def test_is_retryable_busy():
    assert _is_retryable("Server is busy")


def test_is_retryable_pool():
    assert _is_retryable("Connection pool exhausted")


def test_not_retryable():
    assert not _is_retryable("Insufficient balance")


def test_not_retryable_permission():
    assert not _is_retryable("Permission denied")


def test_not_retryable_empty():
    assert not _is_retryable("")
