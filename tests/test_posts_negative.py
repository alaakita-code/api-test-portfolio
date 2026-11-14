"""Negative tests for /posts: requests that are wrong or match nothing.

Important: some results here show that this demo API is lenient. It accepts
an empty POST body and reports success when deleting a post that does not
exist. These tests record what the API really does. They do not claim that
a production API should behave this way.

Each test maps to one Test ID in docs/test_plan.md.
Expected values come from real responses recorded in docs/api_observed.md.

Usage (run only this file):
    .\\.venv\\Scripts\\python.exe -m pytest tests/test_posts_negative.py
"""

from utils.api_client import send_request


def test_get_unknown_path_returns_404_and_empty_object():
    """NEG-01 (P1): a path that does not exist is 'not found'."""
    # Act
    response = send_request("GET", "/not-a-real-path")

    # Assert
    assert response.status_code == 404
    assert response.json() == {}


def test_get_posts_filtered_by_unknown_user_id_returns_200_and_empty_list():
    """NEG-02 (P1): a filter that matches nothing is not an error.

    "No data found" and "bad request" are different outcomes.
    """
    # Act
    response = send_request("GET", "/posts?userId=999")

    # Assert
    assert response.status_code == 200
    assert response.json() == []


def test_create_post_with_empty_body_is_still_accepted_with_201():
    """NEG-03 (P2): known limitation - the API does not validate input.

    A production API should reject an empty post. This one creates it anyway.
    """
    # Act
    response = send_request("POST", "/posts", json={})

    # Assert
    assert response.status_code == 201
    assert response.json() == {"id": 101}


def test_replace_post_with_unknown_id_returns_404_and_empty_object():
    """NEG-04 (P2): updating a post that does not exist is 'not found'."""
    # Act
    response = send_request("PUT", "/posts/101", json={"title": "x"})

    # Assert
    assert response.status_code == 404
    assert response.json() == {}


def test_delete_post_with_unknown_id_still_returns_200_and_empty_object():
    """NEG-05 (P2): known inconsistency - DELETE succeeds for an unknown id.

    Compare with NEG-04: PUT on the same unknown id returns 404.
    """
    # Act
    response = send_request("DELETE", "/posts/101")

    # Assert
    assert response.status_code == 200
    assert response.json() == {}
