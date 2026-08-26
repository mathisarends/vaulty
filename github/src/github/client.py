from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel

from github.models import IssueComment, PullRequest, Review, ReviewComment

_API_BASE_URL = "https://api.github.com"
_API_VERSION = "2022-11-28"


class GitHubClient:
    """Minimal async client for reading pull request state.

    Only covers what's needed to poll a PR: its status, its reviews, and its
    comments (inline review comments and general conversation comments).
    """

    def __init__(
        self,
        token: str,
        owner: str,
        repo: str,
        *,
        base_url: str = _API_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._owner = owner
        self._repo = repo
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": _API_VERSION,
            },
            timeout=timeout,
        )

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

    async def get_pull_request(self, number: int) -> PullRequest:
        response = await self._client.get(
            f"/repos/{self._owner}/{self._repo}/pulls/{number}"
        )
        response.raise_for_status()
        return PullRequest.model_validate(response.json())

    async def list_reviews(self, number: int) -> list[Review]:
        return await self._paginate(
            f"/repos/{self._owner}/{self._repo}/pulls/{number}/reviews", Review
        )

    async def list_review_comments(self, number: int) -> list[ReviewComment]:
        return await self._paginate(
            f"/repos/{self._owner}/{self._repo}/pulls/{number}/comments",
            ReviewComment,
        )

    async def list_issue_comments(self, number: int) -> list[IssueComment]:
        return await self._paginate(
            f"/repos/{self._owner}/{self._repo}/issues/{number}/comments",
            IssueComment,
        )

    async def _paginate[T: BaseModel](self, path: str, model: type[T]) -> list[T]:
        items: list[T] = []
        url: str | None = path
        params: dict[str, object] | None = {"per_page": 100}

        while url:
            response = await self._client.get(url, params=params)
            response.raise_for_status()
            items.extend(model.model_validate(item) for item in response.json())
            url = response.links.get("next", {}).get("url")
            params = None  # the "next" link already carries the query string

        return items
