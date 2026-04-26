"""Tests for ReturnResult — now in valhopper.models."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from valhopper.models import ReturnError, ReturnResult


def test_return_result_success():
    result = ReturnResult(value=1.5, error=ReturnError.NO_ERROR, message="")
    assert result.value == 1.5
    assert result.error == ReturnError.NO_ERROR
    assert not result.is_error


def test_return_result_not_in_metagraph():
    result = ReturnResult(
        value=0.0, error=ReturnError.VALIDATOR_NOT_IN_METAGRAPH, message="Not found"
    )
    assert result.value == 0.0
    assert result.error == ReturnError.VALIDATOR_NOT_IN_METAGRAPH
    assert result.is_error


def test_return_result_network_error():
    result = ReturnResult(
        value=0.0, error=ReturnError.NETWORK_ERROR, message="Connection timeout"
    )
    assert result.is_error


def test_return_result_no_stake():
    result = ReturnResult(value=0.0, error=ReturnError.NO_STAKE, message="Validator has no stake")
    assert result.error == ReturnError.NO_STAKE


def test_return_result_no_emission():
    result = ReturnResult(value=0.0, error=ReturnError.NO_EMISSION, message="No emission")
    assert result.error == ReturnError.NO_EMISSION
