"""Shared pytest settings. pytest loads this file automatically.

Purpose: control which environment details appear in the HTML report.

By default pytest-html writes details of the machine that ran the tests
(operating system build, environment variables such as JAVA_HOME) into the
"Environment" table. A report is a file that gets attached to tickets, sent
to colleagues or uploaded by CI, so the safe default is to keep version
information only.

When the full environment is needed to investigate a local problem, turn it
on for one run with the REPORT_FULL_ENVIRONMENT switch (see Usage). The
report is then marked "local use only". The switch is ignored on CI, so a
published report can never carry the full details.

Usage:
    Default (filtered report):
        .venv\\Scripts\\python -m pytest

    Full environment for one run (PowerShell):
        $env:REPORT_FULL_ENVIRONMENT = "1"
        .venv\\Scripts\\python -m pytest
        Remove-Item Env:REPORT_FULL_ENVIRONMENT

    To always show another row, add its name to the allow-list below.
"""

import os

import pytest

# pytest-metadata is installed as a dependency of pytest-html and collects
# the data shown in the report's "Environment" table.
try:
    from pytest_metadata.plugin import metadata_key
except ImportError:
    metadata_key = None

# Allow-list: only these rows appear in the "Environment" table by default.
# An allow-list (rather than a block-list) also filters out any new rows
# that a future plugin version might add.
ALLOWED_REPORT_ENVIRONMENT_ROWS = {"Python", "Packages", "Plugins"}

# Set this environment variable to "1" to keep the full table for one run.
FULL_ENVIRONMENT_SWITCH = "REPORT_FULL_ENVIRONMENT"

# Row added to a full report so it cannot be mistaken for a shareable one.
FULL_REPORT_NOTICE_ROW = "Report scope"
FULL_REPORT_NOTICE_TEXT = "Full environment details - local use only, do not share"


def full_environment_requested():
    """Return True if this run should keep the full environment table.

    GitHub Actions sets GITHUB_ACTIONS=true. The switch is ignored there so
    that a report published by CI is always filtered.
    """
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return False
    return os.environ.get(FULL_ENVIRONMENT_SWITCH) == "1"


def filter_report_environment(metadata, keep_full):
    """Apply the report policy to the metadata dict, in place."""
    if keep_full:
        metadata[FULL_REPORT_NOTICE_ROW] = FULL_REPORT_NOTICE_TEXT
        return
    for row_name in list(metadata.keys()):
        if row_name not in ALLOWED_REPORT_ENVIRONMENT_ROWS:
            del metadata[row_name]


# tryfirst=True runs this hook before pytest-html writes the report.
@pytest.hookimpl(tryfirst=True)
def pytest_sessionfinish(session, exitstatus):
    """Filter the report's environment table before the report is written."""
    if metadata_key is None:
        return
    metadata = session.config.stash.get(metadata_key, None)
    if metadata is None:
        return
    filter_report_environment(metadata, keep_full=full_environment_requested())
