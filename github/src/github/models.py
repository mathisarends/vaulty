from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel


class User(BaseModel):
    login: str


class PullRequestState(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class ReviewState(StrEnum):
    APPROVED = "APPROVED"
    CHANGES_REQUESTED = "CHANGES_REQUESTED"
    COMMENTED = "COMMENTED"
    DISMISSED = "DISMISSED"
    PENDING = "PENDING"


class PullRequest(BaseModel):
    """The subset of a PR's fields relevant to checking on its state."""

    number: int
    title: str
    state: PullRequestState
    html_url: str
    user: User
    merged: bool = False
    draft: bool = False
    created_at: datetime
    updated_at: datetime


class Review(BaseModel):
    """A submitted review (approve / request changes / comment)."""

    id: int
    user: User
    state: ReviewState
    body: str
    html_url: str
    submitted_at: datetime | None = None


class ReviewComment(BaseModel):
    """An inline comment left on a diff line as part of a review."""

    id: int
    user: User
    body: str
    path: str
    line: int | None = None
    html_url: str
    created_at: datetime


class IssueComment(BaseModel):
    """A top-level conversation comment on the PR (not tied to a diff line)."""

    id: int
    user: User
    body: str
    html_url: str
    created_at: datetime
