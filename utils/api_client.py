"""A thin wrapper around the requests library.

Every test calls the API through this module. It does three things:
1. adds the base URL, so tests only pass a path such as "/posts/1",
2. always sets a timeout, so a silent API cannot hang the suite,
3. logs each request and response, so a failed test shows what happened.

Usage:
    from utils.api_client import send_request

    response = send_request("GET", "/posts/1")
    response.status_code   # e.g. 200
    response.json()        # body parsed into a dict or list
    response.headers       # response headers
"""

import logging

import requests

from utils.config import BASE_URL, TIMEOUT_SECONDS

logger = logging.getLogger("api_client")


def send_request(method, path, json=None, timeout=TIMEOUT_SECONDS):
    """Send one HTTP request and return the requests.Response object.

    method:  "GET", "POST", "PUT", "PATCH" or "DELETE"
    path:    the part after the base URL, e.g. "/posts/1"
    json:    optional request body (a dict)
    timeout: seconds to wait; defaults to TIMEOUT_SECONDS in utils/config.py

    Raises requests.exceptions.Timeout if no response arrives in time.
    """
    url = BASE_URL + path
    logger.info("Request: %s %s body=%s", method, url, json)

    response = requests.request(method, url, json=json, timeout=timeout)

    # Log only the first 500 characters to keep long list responses readable.
    logger.info("Response: status=%s body=%s", response.status_code, response.text[:500])
    return response
