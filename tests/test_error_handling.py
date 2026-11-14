"""Error-handling tests: checks on the test tooling itself, not on the API.

These tests make sure a slow or silent API produces a clear failure
instead of a suite that hangs.

Each test maps to one Test ID in docs/test_plan.md.

Usage (run only this file):
    .venv\\Scripts\\python -m pytest tests/test_error_handling.py
"""

import pytest
import requests

from utils.api_client import send_request
from utils.config import TIMEOUT_SECONDS


def test_request_with_extremely_short_timeout_raises_timeout_error():
    """ERR-01 (P1): a request that cannot finish in time raises Timeout.

    0.001 seconds is far too short to open a connection, so this always
    times out. That makes the result stable instead of flaky.
    """
    # pytest.raises passes only if the block raises the given exception.
    with pytest.raises(requests.exceptions.Timeout):
        send_request("GET", "/posts", timeout=0.001)


def test_normal_request_completes_within_configured_timeout():
    """ERR-02 (P2): a normal request finishes well inside the timeout.

    The limit is a generous safety margin, not a performance target.
    """
    # Act
    response = send_request("GET", "/posts/1")

    # Assert
    assert response.status_code == 200
    # response.elapsed is the response time measured by requests.
    assert response.elapsed.total_seconds() < TIMEOUT_SECONDS
