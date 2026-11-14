# API Test Portfolio

[![API tests](https://github.com/alaakita-code/api-test-portfolio/actions/workflows/tests.yml/badge.svg)](https://github.com/alaakita-code/api-test-portfolio/actions/workflows/tests.yml)

Automated API tests for the `/posts` resource of [JSONPlaceholder](https://jsonplaceholder.typicode.com), written with pytest and requests. Every expected value is traced to a recorded observation of the real API.

中文說明：[README.zh-TW.md](README.zh-TW.md)

## Purpose

This project demonstrates an evidence-based approach to designing and automating API tests:

- Test design precedes implementation. Each test maps to a case in the [test plan](docs/test_plan.md).
- Expected values are derived from evidence. They are taken from [recorded API responses](docs/api_observed.md), not from assumptions.
- Assertions cover more than the status code: fields, data types, content and headers are verified.
- Known limitations are documented, not hidden.

## Test Coverage

25 tests: 24 planned test cases and 1 smoke test.

| Group | Tests | What it checks |
|---|---|---|
| Positive | 9 | Valid requests return the expected status, fields, types and content |
| Boundary | 6 | Ids at the edges of the valid range (1-100) and just outside it |
| Negative | 5 | Unknown paths, filters with no match, empty request bodies, unknown ids |
| Error handling | 2 | A slow or silent API causes a clear failure instead of a hang |
| Repeat requests | 2 | Sending the same request again gives the same result |
| Smoke | 1 | The environment and connection work |

## Tech Stack

| Tool | Version | Role |
|---|---|---|
| Python | 3.11, 3.13 | Language |
| pytest | 9.1.1 | Test framework |
| requests | 2.34.2 | HTTP client |
| pytest-html | 4.2.0 | HTML report |
| GitHub Actions | - | Continuous integration |

## Project Structure

```text
api-test-portfolio/
├── .github/workflows/tests.yml   CI workflow
├── tests/
│   ├── conftest.py               Shared settings: report environment filter
│   ├── test_smoke.py             Smoke test
│   ├── test_posts_positive.py    POS-01 to POS-09
│   ├── test_posts_boundary.py    BND-01 to BND-06
│   ├── test_posts_negative.py    NEG-01 to NEG-05
│   ├── test_error_handling.py    ERR-01, ERR-02
│   └── test_repeat_requests.py   REP-01, REP-02
├── utils/
│   ├── api_client.py             Request wrapper: base URL, timeout, logging
│   └── config.py                 Settings
├── data/                         Test data
├── tools/explore_api.py          Observation tool: records real API responses
├── docs/
│   ├── test_plan.md              Scope, priorities, test cases and their basis
│   ├── api_observed.md           Initial recorded responses
│   ├── api_notes.md              Exploration summary and known limitations
│   ├── observations/             Timestamped observation records and index
│   └── USAGE.zh-TW.md            User manual (Traditional Chinese)
├── pytest.ini
└── requirements.txt
```

## Prerequisites

- Python 3.11 or later
- Network access to `https://jsonplaceholder.typicode.com`

No account, API key or database is required.

## Setup

Commands are shown for Windows PowerShell and are run from the project root.

```
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On macOS or Linux, use `.venv/bin/python` in place of `.\.venv\Scripts\python.exe`.

## Environment Variables

All variables are optional.

| Variable | Default | Purpose |
|---|---|---|
| `API_BASE_URL` | `https://jsonplaceholder.typicode.com` | Base URL of the API under test |
| `REPORT_FULL_ENVIRONMENT` | not set | Set to `1` to keep full machine details in a local report. Ignored on CI |

## How to Run

| Goal | Command |
|---|---|
| Run all tests | `.\.venv\Scripts\python.exe -m pytest` |
| Run the smoke test only | `.\.venv\Scripts\python.exe -m pytest -m smoke` |
| Run one file | `.\.venv\Scripts\python.exe -m pytest tests/test_posts_positive.py` |
| Record current API behavior | `.\.venv\Scripts\python.exe tools/explore_api.py` |

A successful run ends with a line like:

```
25 passed in 25.00s
```

## Reports

- **Local:** each run writes `reports/report.html`, a single file that opens offline.
- **CI:** the workflow runs on every push and pull request, and once a week. Each run publishes one report per Python version. Open a run on the [Actions page](https://github.com/alaakita-code/api-test-portfolio/actions) and download it from the **Artifacts** section.

The report keeps version information only. Details of the machine that ran the tests are filtered out by default.

## API Observation Records

`tools/explore_api.py` records the actual responses of the API and compares them with the previous run, so that a change in API behavior is detected rather than assumed.

Each run writes two records:

| Record | Location | Committed | Content |
|---|---|---|---|
| Public | `docs/observations/` | Yes | Status codes, body structure, selected headers |
| Full | `observations_local/` | No | All headers, full error messages, machine details |

The full record stays on the local machine for troubleshooting. Only the public record is published.

## Limitations

- JSONPlaceholder fakes all write operations. POST, PUT, PATCH and DELETE return a realistic response but save nothing, so read-after-write consistency cannot be tested.
- The API has no authentication and does not validate input. Permission tests and input validation tests are out of scope.
- For an id that does not exist, PUT returns 404 whereas DELETE returns 200. The tests record this behavior as observed (NEG-04, NEG-05).
- GET responses are served from a CDN cache. The repeat-request test for GET may verify the cache rather than the origin server.
- The suite depends on a third-party service. A failure caused by an outage is an environment problem, not a defect in the tests.
- Concurrency and load tests are not included.

A passing run indicates that the covered behavior matches the recorded expectations. It does not demonstrate that the API is free of defects.

## Documentation

- [Test plan](docs/test_plan.md)
- [User manual (Traditional Chinese)](docs/USAGE.zh-TW.md)
- [API exploration notes](docs/api_notes.md)
