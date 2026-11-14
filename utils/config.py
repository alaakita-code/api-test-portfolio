"""Project settings. Change values here, not inside the tests.

Usage:
    from utils.config import BASE_URL, TIMEOUT_SECONDS
"""

import os

# Base URL of the API under test. The service has no authentication,
# so no API key or account is needed.
# Set the API_BASE_URL environment variable to target another host
# without changing the code.
BASE_URL = os.environ.get("API_BASE_URL", "https://jsonplaceholder.typicode.com")

# Seconds to wait before a request is treated as failed.
# Basis: local runs measured about 1 second per test, so 10 seconds leaves
# roughly a tenfold margin. This is a stability limit, not a performance target.
TIMEOUT_SECONDS = 10
