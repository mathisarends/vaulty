import asyncio

from github import GitHubClient, GitHubCredentials


async def main() -> None:
    credentials = GitHubCredentials()

    async with GitHubClient(credentials, owner="mathisarends", repo="vault") as client:
        for review in await client.reviews.list(1):
            print(f"- review by {review.user.login}: {review.state}")


if __name__ == "__main__":
    asyncio.run(main())
