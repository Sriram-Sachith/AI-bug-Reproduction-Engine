"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field(default="claude-sonnet-4-5", validation_alias="ANTHROPIC_MODEL")
    data_dir: Path = Field(
        default=PROJECT_ROOT / "data",
        validation_alias=AliasChoices("BUGREPRO_DATA_DIR", "data_dir"),
    )
    allowed_root: Path = Field(
        default=PROJECT_ROOT / "examples",
        validation_alias=AliasChoices("BUGREPRO_ALLOWED_ROOT", "allowed_root"),
    )
    use_docker: bool = Field(
        default=True,
        validation_alias=AliasChoices("BUGREPRO_USE_DOCKER", "use_docker"),
    )
    timeout_seconds: int = Field(
        default=30,
        validation_alias=AliasChoices("BUGREPRO_TIMEOUT_SECONDS", "timeout_seconds"),
    )
    repeat: int = Field(default=3, validation_alias=AliasChoices("BUGREPRO_REPEAT", "repeat"))
    docker_image: str = Field(
        default="bugrepro-runner:latest",
        validation_alias=AliasChoices("BUGREPRO_DOCKER_IMAGE", "docker_image"),
    )
    memory: str = Field(default="256m", validation_alias=AliasChoices("BUGREPRO_MEMORY", "memory"))
    cpus: str = Field(default="0.5", validation_alias=AliasChoices("BUGREPRO_CPUS", "cpus"))
    pids: int = Field(default=64, validation_alias=AliasChoices("BUGREPRO_PIDS", "pids"))

    def resolved_data_dir(self) -> Path:
        path = self.data_dir
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    def resolved_allowed_root(self) -> Path:
        path = self.allowed_root
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        return path.resolve()


def get_settings() -> Settings:
    return Settings()
