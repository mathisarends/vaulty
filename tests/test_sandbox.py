from vaulty.config import SandboxSettings
from vaulty.sandbox import build_sandbox


def test_sandbox_inherits_github_token_when_present(tmp_path, monkeypatch):
    monkeypatch.setenv("GH_TOKEN", "test-token")

    sandbox = build_sandbox(tmp_path, SandboxSettings())

    assert sandbox._inherit_environment == ("GH_TOKEN",)


def test_sandbox_does_not_require_github_token(tmp_path, monkeypatch):
    monkeypatch.delenv("GH_TOKEN", raising=False)

    sandbox = build_sandbox(tmp_path, SandboxSettings())

    assert sandbox._inherit_environment == ()
