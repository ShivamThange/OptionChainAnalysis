"""Central configuration loaded from environment / .env (pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # provider selection
    data_provider: str = "auto"  # kite | nse | auto

    # kite connect
    kite_api_key: str = ""
    kite_api_secret: str = ""
    kite_user_id: str = ""
    kite_password: str = ""
    kite_totp_secret: str = ""
    kite_token_cache: str = ".kite_token.json"

    # underlyings
    underlyings: list[str] = Field(default_factory=lambda: ["NIFTY", "BANKNIFTY"])
    strike_window: int = 20

    # analytics
    risk_free_rate: float = 0.065
    dividend_yield: float = 0.012
    iv_buy_sell_threshold: float = 20.0
    recompute_debounce_ms: int = 750

    # snapshots (seconds)
    snapshot_fast_sec: int = 180
    snapshot_med_sec: int = 300
    snapshot_slow_sec: int = 900

    # storage
    db_path: str = "data/optionchain.db"

    # server
    host: str = "127.0.0.1"
    port: int = 8000
    frontend_origin: str = "http://localhost:5173"

    @field_validator("underlyings", mode="before")
    @classmethod
    def _split_underlyings(cls, v):
        if isinstance(v, str):
            return [s.strip().upper() for s in v.split(",") if s.strip()]
        return v

    # --- derived helpers -----------------------------------------------------
    @property
    def kite_enabled(self) -> bool:
        """Kite is usable only when both key and secret are present.

        This is the single gate that keeps Kite dormant until the user buys
        Connect credentials — there is deliberately no auth bypass path.
        """
        return bool(self.kite_api_key and self.kite_api_secret)

    @property
    def effective_provider(self) -> str:
        if self.data_provider == "auto":
            return "kite" if self.kite_enabled else "nse"
        return self.data_provider

    @property
    def db_file(self) -> Path:
        p = Path(self.db_path)
        if not p.is_absolute():
            p = BACKEND_DIR / p
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def token_cache_file(self) -> Path:
        p = Path(self.kite_token_cache)
        if not p.is_absolute():
            p = BACKEND_DIR / p
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
