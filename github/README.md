# github

Minimal async GitHub REST client for reading pull request state: PR status,
reviews, inline review comments, and issue (conversation) comments. Built on
`httpx` and `pydantic`, with no dependency on the rest of the workspace so
both `vaulty` (agent tool) and `daemon` (polling) can depend on it.
