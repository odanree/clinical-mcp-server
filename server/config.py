"""Settings loaded from environment + .env."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # NCBI / PubMed E-utils
    ncbi_api_key: str = Field(default="", alias="NCBI_API_KEY")
    ncbi_tool_name: str = Field(default="clinical-mcp-server", alias="NCBI_TOOL_NAME")
    ncbi_email: str = Field(default="", alias="NCBI_EMAIL")

    # openFDA
    openfda_api_key: str = Field(default="", alias="OPENFDA_API_KEY")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


settings = Settings()
