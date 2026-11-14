"""Boundary tests for /posts: ids at and just outside the valid range.

Defects cluster at the edges of a range. The API holds posts with ids
1 to 100, so these tests cover both edges (1, 100), the values just
outside them (0, 101), and two malformed ids (negative, non-numeric).

Each test maps to one Test ID in docs/test_plan.md.
Expected values come from real responses recorded in docs/api_observed.md.

Usage (run only this file):
    .venv\\Scripts\\python -m pytest tests/test_posts_boundary.py
"""

import pytest

from utils.api_client import send_request


def test_get_post_with_lowest_valid_id_returns_200_and_that_post():
    """BND-01 (P1): id 1 is the first valid post."""
    # Act
    response = send_request("GET", "/posts/1")

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == 1


def test_get_post_with_highest_valid_id_returns_200_and_that_post():
    """BND-02 (P1): id 100 is the last valid post."""
    # Act
    response = send_request("GET", "/posts/100")

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == 100


# The four ids below share one expected result, so one test function runs
# four times. Each pytest.param is a separate test case in the report, and
# its id maps back to a Test ID in the test plan.
@pytest.mark.parametrize(
    "invalid_id",
    [
        pytest.param("0", id="BND-03-below-lowest-id"),
        pytest.param("101", id="BND-04-above-highest-id"),
        pytest.param("-1", id="BND-05-negative-id"),
        pytest.param("abc", id="BND-06-non-numeric-id"),
    ],
)
def test_get_post_with_id_outside_valid_range_returns_404_and_empty_object(invalid_id):
    """BND-03 to BND-06: an id outside 1-100 is 'not found', with an empty body."""
    # Act
    response = send_request("GET", f"/posts/{invalid_id}")

    # Assert
    assert response.status_code == 404
    assert response.json() == {}
