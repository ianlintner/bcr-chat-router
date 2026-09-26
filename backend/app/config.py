"""Configuration loaded from environment (.env optional)."""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    typesafe_api_key: str | None = field(default_factory=lambda: os.getenv("TYPESAFE_API_KEY") or None)
    typesafe_model: str = field(default_factory=lambda: os.getenv("TYPESAFE_MODEL", "jev-latest"))
    typesafe_base_url: str = field(
        default_factory=lambda: os.getenv("TYPESAFE_BASE_URL", "https://api.typesafe.ai/v1/systemone")
    )
    typesafe_timeout_seconds: float = field(
        default_factory=lambda: float(os.getenv("TYPESAFE_TIMEOUT_SECONDS", "4"))
    )
    min_confidence: float = field(default_factory=lambda: float(os.getenv("MIN_CONFIDENCE", "0.55")))

    @property
    def jev_enabled(self) -> bool:
        return bool(self.typesafe_api_key)


settings = Settings()
