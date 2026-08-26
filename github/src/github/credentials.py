from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class GitHubCredentials(BaseSettings):
    """Reads `GH_TOKEN` from the environment (or a `.env` file)."""

    model_config = SettingsConfigDict(env_prefix="GH_", env_file=".env", extra="ignore")

    token: SecretStr
