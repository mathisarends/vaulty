from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel

from github.models import IssueComment, PullRequest, Review, ReviewComment

if TYPE_CHECKING:
    from github.client import GitHubClient


class _Namespace:
    def __init__(self, client: "GitHubClient") -> None:
        self._parent = client

    @property
    def _client(self) -> httpx.AsyncClient:
        return self._parent._client

    @property
    def _owner(self) -> str:
        return self._parent._owner

    @property
    def _repo(self) -> str:
        return self._parent._repo

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


class PullRequests(_Namespace):
    async def get(self, number: int) -> PullRequest:
        response = await self._client.get(
            f"/repos/{self._owner}/{self._repo}/pulls/{number}"
        )
        response.raise_for_status()
        return PullRequest.model_validate(response.json())


class Reviews(_Namespace):
    async def list(self, number: int) -> list[Review]:
        return await self._paginate(
            f"/repos/{self._owner}/{self._repo}/pulls/{number}/reviews", Review
        )


class ReviewComments(_Namespace):
    async def list(self, number: int) -> list[ReviewComment]:
        return await self._paginate(
            f"/repos/{self._owner}/{self._repo}/pulls/{number}/comments",
            ReviewComment,
        )


class IssueComments(_Namespace):
    async def list(self, number: int) -> list[IssueComment]:
        return await self._paginate(
            f"/repos/{self._owner}/{self._repo}/issues/{number}/comments",
            IssueComment,
        )
