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


def test_request_with_extremely_short_read_timeout_raises_timeout_error():
    """ERR-01 (P1): a response that does not arrive in time raises Timeout.

    The timeout is given as (connect, read). The connection is opened with
    the normal limit, then the response must arrive within 0.0001 seconds,
    which no remote server can meet, so the request always times out.

    Why a read timeout and not a short connect timeout: with a very short
    connect timeout the client tries each address of the host in turn and
    reports the error of the last attempt. On a machine without an IPv6
    route that last error is "Network is unreachable" (a ConnectionError),
    not a timeout, so the result depended on the network of the machine.
    A read timeout is applied after the connection exists and behaves the
    same everywhere.
    """
    # pytest.raises passes only if the block raises the given exception.
    with pytest.raises(requests.exceptions.Timeout):
        send_request("GET", "/posts", timeout=(TIMEOUT_SECONDS, 0.0001))


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
