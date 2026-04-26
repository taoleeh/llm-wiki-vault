"""Unit tests for return computation status."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from valhopper.valhopper_cli import ReturnError, ReturnResult


def test_return_result_success():
    """Successful return has no error."""
    result = ReturnResult(value=1.5, error=ReturnError.NO_ERROR, message="")
    assert result.value == 1.5
    assert result.error == ReturnError.NO_ERROR
    assert not result.is_error


def test_return_result_not_in_metagraph():
    """Validator not in metagraph is an error condition."""
    result = ReturnResult(value=0.0, error=ReturnError.VALIDATOR_NOT_IN_METAGRAPH, message="Not found")
    assert result.value == 0.0
    assert result.error == ReturnError.VALIDATOR_NOT_IN_METAGRAPH
    assert result.is_error


def test_return_result_network_error():
    """Network error should log and return error status."""
    result = ReturnResult(value=0.0, error=ReturnError.NETWORK_ERROR, message="Connection timeout")
    assert result.value == 0.0
    assert result.error == ReturnError.NETWORK_ERROR
    assert result.is_error


def test_return_result_no_stake():
    """No stake is a known condition."""
    result = ReturnResult(value=0.0, error=ReturnError.NO_STAKE, message="Validator has no stake")
    assert result.error == ReturnError.NO_STAKE


def test_return_result_no_emission():
    """No emission is a known condition."""
    result = ReturnResult(value=0.0, error=ReturnError.NO_EMISSION, message="No emission")
    assert result.error == ReturnError.NO_EMISSION
