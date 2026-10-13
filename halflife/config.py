"""Runtime settings, all from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    nebius_api_key: str = os.getenv("NEBIUS_API_KEY", "")
    nebius_base_url: str = os.getenv(
        "NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1/"
    )
    nemotron_model: str = os.getenv("NEMOTRON_MODEL", "nvidia/Nemotron-3-Nano-30B-A3B")

    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    search_depth: str = os.getenv("TAVILY_SEARCH_DEPTH", "basic")
    max_results: int = int(os.getenv("TAVILY_MAX_RESULTS", "5"))

    concurrency: int = int(os.getenv("HALFLIFE_CONCURRENCY", "32"))
    max_claims: int = int(os.getenv("HALFLIFE_MAX_CLAIMS", "200"))
    cache_dir: str = os.getenv("HALFLIFE_CACHE_DIR", ".halflife-cache")

    def require_keys(self) -> None:
        missing = [
            name
            for name, value in (
                ("NEBIUS_API_KEY", self.nebius_api_key),
                ("TAVILY_API_KEY", self.tavily_api_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                f"Missing {', '.join(missing)}. Copy .env.example to .env and fill it in, "
                "or run with --replay to use a recorded run."
            )


settings = Settings()
