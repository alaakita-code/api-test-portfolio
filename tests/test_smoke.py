"""Smoke test: the smallest check that the setup works end to end.

A passing smoke test does not prove the API is correct. A failing one means
no other result in the suite can be trusted, so fix it first.

Usage (run only this test):
    .\\.venv\\Scripts\\python.exe -m pytest -m smoke
"""

import pytest

from utils.api_client import send_request


@pytest.mark.smoke
def test_get_post_with_valid_id_returns_200_and_same_id():
    """Smoke check (related to POS-02 in docs/test_plan.md).

    If it fails, check in this order:
      1. network or API down   -> environment problem
      2. wrong BASE_URL        -> configuration problem
      3. API changed its data  -> update docs/api_observed.md first
    """
    # Arrange
    post_id = 1

    # Act
    response = send_request("GET", f"/posts/{post_id}")

    # Assert
    assert response.status_code == 200
    assert response.json()["id"] == post_id
