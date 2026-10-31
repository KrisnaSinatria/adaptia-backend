from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    groq_api_key: str = ""
    jwt_secret: str = ""

    llm_model: str = ""
    llm_mode: Literal["live", "scripted"] = "live"
    llm_timeout_seconds: float = 6.0
    # Hanya untuk model penalaran (mis. openai/gpt-oss-*); kosongkan untuk model lain.
    llm_reasoning_effort: Literal["", "low", "medium", "high"] = "low"

    allowed_origins: str = "http://localhost:5173"
    rate_limit_enabled: bool = True

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def llm_live(self) -> bool:
        return self.llm_mode == "live" and bool(self.groq_api_key) and bool(self.llm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
