"""
GitHub API transport layer.

Uses only Python's standard library.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error

from config import (
    API_URL,
    GITHUB_TOKEN,
    REQUEST_TIMEOUT,
    VERSION,
)

if not GITHUB_TOKEN:
    raise RuntimeError(
        "GITHUB_TOKEN environment variable is not set."
    )


HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "User-Agent": f"github_to_gptingester/{VERSION}",
}


class GitHubAPIError(RuntimeError):
    pass


def request(endpoint: str):

    req = urllib.request.Request(
        API_URL + endpoint,
        headers=HEADERS,
        method="GET",
    )

    try:

        with urllib.request.urlopen(
            req,
            timeout=REQUEST_TIMEOUT,
        ) as response:

            return json.loads(
                response.read().decode("utf-8")
            )

    except urllib.error.HTTPError as e:

        body = e.read().decode(
            "utf-8",
            errors="replace",
        )

        raise GitHubAPIError(
            f"HTTP {e.code}: {body}"
        ) from e

    except urllib.error.URLError as e:

        raise GitHubAPIError(
            f"Network error: {e.reason}"
        ) from e


def get(endpoint: str):

    return request(endpoint)


if __name__ == "__main__":

    me = get("/user")

    print(
        f"Authenticated as: "
        f"{me['login']}"
    )
