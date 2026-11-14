"""Positive tests for /posts: valid requests should succeed.

Each test maps to one Test ID in docs/test_plan.md.
Expected values come from real responses recorded in docs/api_observed.md.

Note: this API fakes all writes (POST, PUT, PATCH, DELETE). It returns a
realistic response but saves nothing, so every test here is independent
and can run alone or in any order.

Usage (run only this file):
    .venv\\Scripts\\python -m pytest tests/test_posts_positive.py
"""

import json
from pathlib import Path

from utils.api_client import send_request

# Resolve data/ from this file's location so the tests work from any
# working directory.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_test_data(file_name):
    """Read one JSON file from the data/ folder.

    Test data lives in files so it can change without touching test code.
    """
    with open(DATA_DIR / file_name, encoding="utf-8") as handle:
        return json.load(handle)


def test_get_all_posts_returns_200_and_100_items():
    """POS-01 (P0): the full list contains exactly 100 posts."""
    # Act
    response = send_request("GET", "/posts")

    # Assert
    assert response.status_code == 200
    assert len(response.json()) == 100


def test_get_post_with_valid_id_returns_expected_fields_and_types():
    """POS-02 (P0): one post has exactly four fields with the right types.

    A 200 response with the wrong structure is a common defect, so the
    status code alone is not enough.
    """
    # Act
    response = send_request("GET", "/posts/1")

    # Assert
    assert response.status_code == 200
    post = response.json()
    assert post["id"] == 1
    # Exact match: no missing fields and no unexpected ones.
    assert set(post.keys()) == {"userId", "id", "title", "body"}
    # "type(x) is int" rejects booleans, which isinstance(x, int) would accept.
    assert type(post["userId"]) is int
    assert type(post["id"]) is int
    assert type(post["title"]) is str
    assert type(post["body"]) is str


def test_get_posts_filtered_by_user_id_returns_only_that_users_posts():
    """POS-03 (P1): filtering by userId=1 returns 10 posts, all from user 1."""
    # Act
    response = send_request("GET", "/posts?userId=1")

    # Assert
    assert response.status_code == 200
    posts = response.json()
    assert len(posts) == 10
    assert all(post["userId"] == 1 for post in posts)


def test_get_comments_of_post_returns_only_comments_of_that_post():
    """POS-04 (P1): every comment under /posts/1/comments belongs to post 1."""
    # Act
    response = send_request("GET", "/posts/1/comments")

    # Assert
    assert response.status_code == 200
    comments = response.json()
    # Guard: all() is True for an empty list, so make sure there is data first.
    assert len(comments) > 0
    assert all(comment["postId"] == 1 for comment in comments)


def test_create_post_returns_201_with_sent_fields_and_new_id():
    """POS-05 (P0): creating a post echoes the sent fields and adds id 101."""
    # Arrange
    new_post = load_test_data("new_post.json")

    # Act
    response = send_request("POST", "/posts", json=new_post)

    # Assert
    assert response.status_code == 201
    created = response.json()
    assert created["id"] == 101
    assert created["title"] == new_post["title"]
    assert created["body"] == new_post["body"]
    assert created["userId"] == new_post["userId"]


def test_replace_post_returns_200_and_the_sent_content():
    """POS-06 (P1): a full update (PUT) returns exactly what was sent."""
    # Arrange
    updated_post = load_test_data("updated_post.json")

    # Act
    response = send_request("PUT", "/posts/1", json=updated_post)

    # Assert
    assert response.status_code == 200
    assert response.json() == updated_post


def test_patch_post_title_changes_title_and_keeps_other_fields():
    """POS-07 (P1): a partial update (PATCH) changes only the title."""
    # Arrange: read the current post to learn which values must stay the same.
    # This avoids hard-coding the long original text in the test.
    original = send_request("GET", "/posts/1").json()

    # Act
    response = send_request("PATCH", "/posts/1", json={"title": "patched"})

    # Assert
    assert response.status_code == 200
    patched = response.json()
    assert patched["title"] == "patched"
    assert patched["userId"] == original["userId"]
    assert patched["id"] == original["id"]
    assert patched["body"] == original["body"]


def test_delete_post_returns_200_and_empty_object():
    """POS-08 (P1): deleting a post returns an empty JSON object."""
    # Act
    response = send_request("DELETE", "/posts/1")

    # Assert
    assert response.status_code == 200
    assert response.json() == {}


def test_get_post_response_content_type_is_json_utf8():
    """POS-09 (P2): the response declares JSON with UTF-8 encoding."""
    # Act
    response = send_request("GET", "/posts/1")

    # Assert
    assert response.headers["Content-Type"] == "application/json; charset=utf-8"
