import httpx
import pytest

from github import GitHubClient, GitHubCredentials


def _client(handler: httpx.MockTransport) -> GitHubClient:
    credentials = GitHubCredentials(token="fake-token")
    return GitHubClient(
        credentials, owner="mathisarends", repo="vault", transport=handler
    )


async def test_get_pull_request_parses_status():
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/repos/mathisarends/vault/pulls/1"
        return httpx.Response(
            200,
            json={
                "number": 1,
                "title": "Tend the vault",
                "state": "open",
                "html_url": "https://github.com/mathisarends/vault/pull/1",
                "user": {"login": "vaulty-bot"},
                "merged": False,
                "draft": False,
                "created_at": "2026-08-25T04:00:00Z",
                "updated_at": "2026-08-26T09:00:00Z",
            },
        )

    async with _client(httpx.MockTransport(handle)) as client:
        pr = await client.pulls.get(1)

    assert pr.number == 1
    assert pr.state == "open"
    assert pr.user.login == "vaulty-bot"


async def test_list_reviews_follows_pagination():
    pages = {
        "/repos/mathisarends/vault/pulls/1/reviews": [
            {
                "id": 1,
                "user": {"login": "mathisarends"},
                "state": "COMMENTED",
                "body": "looks good so far",
                "html_url": "https://github.com/mathisarends/vault/pull/1#pullrequestreview-1",
                "submitted_at": "2026-08-26T08:00:00Z",
            }
        ],
        "/page/2": [
            {
                "id": 2,
                "user": {"login": "mathisarends"},
                "state": "APPROVED",
                "body": "",
                "html_url": "https://github.com/mathisarends/vault/pull/1#pullrequestreview-2",
                "submitted_at": "2026-08-26T09:00:00Z",
            }
        ],
    }

    def handle(request: httpx.Request) -> httpx.Response:
        body = pages[request.url.path]
        headers = {}
        if request.url.path == "/repos/mathisarends/vault/pulls/1/reviews":
            headers["Link"] = '<https://api.github.com/page/2>; rel="next"'
        return httpx.Response(200, json=body, headers=headers)

    async with _client(httpx.MockTransport(handle)) as client:
        reviews = await client.reviews.list(1)

    assert [review.id for review in reviews] == [1, 2]
    assert reviews[1].state == "APPROVED"


@pytest.mark.parametrize(
    ("namespace_name", "path"),
    [
        ("review_comments", "/repos/mathisarends/vault/pulls/1/comments"),
        ("issue_comments", "/repos/mathisarends/vault/issues/1/comments"),
    ],
)
async def test_comment_listings_hit_expected_endpoint(namespace_name, path):
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.url.path == path
        return httpx.Response(200, json=[])

    async with _client(httpx.MockTransport(handle)) as client:
        result = await getattr(client, namespace_name).list(1)

    assert result == []
