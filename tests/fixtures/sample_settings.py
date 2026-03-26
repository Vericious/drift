"""Sample Pydantic settings/models for testing the PydanticExtractor."""
from pydantic import BaseSettings, BaseModel, Field


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""

    debug: bool = Field(False, description="Enable debug mode.")
    port: int = Field(8000, description="Port to listen on.", env="PORT")
    host: str = Field("localhost", description="Host to bind to.", env="HOST")
    database_url: str = Field(..., description="Database connection URL.", env="DATABASE_URL")
    log_level: str = Field("info", alias="level", description="Logging level.")


class UserModel(BaseModel):
    """Sample user model."""

    name: str = Field(..., description="User's full name.")
    count: int = Field(0, description="Number of times accessed.")
    tags: list[str] = Field(default_factory=list, description="User tags.")
