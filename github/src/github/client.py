from types import TracebackType
from typing import Self

import httpx

from github.credentials import GitHubCredentials
from github.namespaces import IssueComments, PullRequests, ReviewComments, Reviews

_API_BASE_URL = "https://api.github.com"
_API_VERSION = "2022-11-28"


class GitHubClient:
    """Minimal async client for reading pull request state.

    Only covers what's needed to poll a PR: its status, its reviews, and its
    comments (inline review comments and general conversation comments).
    """

    def __init__(
        self,
        credentials: GitHubCredentials,
        owner: str,
        repo: str,
        *,
        base_url: str = _API_BASE_URL,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._token = credentials.token
        self._owner = owner
        self._repo = repo
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {self._token.get_secret_value()}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            timeout=timeout,
            transport=transport,
        )

        self.pulls = PullRequests(self)
        self.reviews = Reviews(self)
        self.review_comments = ReviewComments(self)
        self.issue_comments = IssueComments(self)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()
