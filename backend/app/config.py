from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Looks for .env in backend/ first, then the repo root.
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    database_url: str = "postgresql://postgres:postgres@localhost:5432/mlesprint"
    redis_url: str = "redis://localhost:6379/0"

    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    embed_batch_size: int = 64

    user_agent: str = "MLE-Sprint/0.1 (personal research aggregator; contact: you@example.com)"
    http_timeout: float = 20.0
    http_max_retries: int = 4
    host_min_interval: float = 1.0  # seconds between requests to the same host
    fetch_concurrency: int = 8

    reddit_client_id: str = ""
    reddit_client_secret: str = ""

    dedup_threshold: float = 0.92  # cosine similarity => "same story"
    dedup_window_days: int = 14  # only treat as duplicate if the canonical article is this recent
    max_item_age_days: int = 30
    default_max_items: int = 30

    # Circuit breaker: after N consecutive failures only retry the source once per `cooldown` hours.
    breaker_failures: int = 5
    breaker_cooldown_hours: int = 24

    sources_file: str = "sources/sources.yaml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
