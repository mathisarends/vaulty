"""Fetch a PR's status, reviews, and comments once.

Requires GITHUB_TOKEN in the environment (or a .env file in the cwd).
"""

import asyncio

from github import GitHubClient, GitHubCredentials


async def main() -> None:
    credentials = GitHubCredentials()  # reads GITHUB_TOKEN

    async with GitHubClient(credentials, owner="mathisarends", repo="vault") as client:
        pr = await client.pulls.get(1)
        print(f"PR #{pr.number} ({pr.state}): {pr.title}")

        for review in await client.reviews.list(pr.number):
            print(f"- review by {review.user.login}: {review.state}")

        for comment in await client.issue_comments.list(pr.number):
            print(f"- comment by {comment.user.login}: {comment.body}")


if __name__ == "__main__":
    asyncio.run(main())
