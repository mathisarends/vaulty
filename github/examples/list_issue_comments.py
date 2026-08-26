import asyncio

from github import GitHubClient, GitHubCredentials


async def main() -> None:
    credentials = GitHubCredentials()

    async with GitHubClient(credentials, owner="mathisarends", repo="vault") as client:
        for comment in await client.issue_comments.list(1):
            print(f"- comment by {comment.user.login}: {comment.body}")


if __name__ == "__main__":
    asyncio.run(main())
