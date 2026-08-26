import asyncio

from github import GitHubClient, GitHubCredentials


async def main() -> None:
    credentials = GitHubCredentials()

    async with GitHubClient(credentials, owner="mathisarends", repo="vault") as client:
        pr = await client.get_pull_request(1)
        print(f"PR #{pr.number} ({pr.state}): {pr.title}")


if __name__ == "__main__":
    asyncio.run(main())
