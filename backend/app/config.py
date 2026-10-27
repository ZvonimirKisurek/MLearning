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

    # --- LLM / curriculum engine ---
    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-5-5"
    llm_effort: str = "medium"  # low|medium|high|xhigh|max: how hard the model thinks before answering
    llm_max_tokens: int = 16000  # thinking tokens count against this too
    llm_max_repairs: int = 2  # re-prompts after a validation failure before giving up
    llm_sdk_retries: int = 5  # SDK-level exponential backoff on 429/5xx/connection errors
    prompt_article_count: int = 50  # articles injected into the prompt
    candidate_window_days: int = 7
    max_per_source: int = 6  # diversity cap so one firehose (arXiv) can't fill the prompt
    min_candidates: int = 10
    # --- AI summaries (cheap, high-volume => small model) ---
    summary_model: str = "claude-haiku-5-5"
    summary_effort: str = "low"
    summary_batch_size: int = 10
    summary_max_per_run: int = 60

    # --- API ---
    api_token: str = ""  # if set, every /api request needs "Authorization: Bearer <token>"
    cors_origins: str = "http://localhost:3000"  # comma-separated
    db_pool_size: int = 10
    match_strong: float = 0.40  # cosine(article, skill) thresholds for the UI badge; calibrate with `cli feed-stats`
    match_moderate: float = 0.28

    timezone: str = "UTC"  # IANA name; drives "today", the Sunday-night/morning schedules


    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
