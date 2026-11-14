"""Repeat-request tests: sending the same request again gives the same result.

In real systems, double clicks and network retries cause duplicate requests,
so repeated calls must not produce inconsistent results.

Each test maps to one Test ID in docs/test_plan.md.
Expected values come from real responses recorded in docs/api_observed.md.

Known limitation: GET responses are served from a CDN cache, so the GET
test below may be checking the cache rather than the origin server.

Usage (run only this file):
    .venv\\Scripts\\python -m pytest tests/test_repeat_requests.py
"""

from utils.api_client import send_request


def test_same_get_request_sent_three_times_returns_identical_results():
    """REP-01 (P1): three identical GET requests give identical responses."""
    # Act
    responses = [send_request("GET", "/posts/1") for _ in range(3)]

    # Assert: every response is 200 and matches the first body.
    first_body = responses[0].json()
    for response in responses:
        assert response.status_code == 200
        assert response.json() == first_body


def test_same_delete_request_sent_twice_returns_same_result_both_times():
    """REP-02 (P2): deleting the same post twice succeeds both times.

    The API does not really delete data, so the second call is not a 404.
    """
    # Act
    first = send_request("DELETE", "/posts/1")
    second = send_request("DELETE", "/posts/1")

    # Assert
    assert first.status_code == 200
    assert first.json() == {}
    assert second.status_code == 200
    assert second.json() == {}
