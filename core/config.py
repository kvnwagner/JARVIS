# ================================================================
# core/config.py
# Única fuente de configuración del proyecto
# Propietario: todos — carga de .env automática
# ================================================================

from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache


class Settings(BaseSettings):

    # ── LLM ─────────────────────────────────────────────────
    llm_provider:   str  = "gemini"     # "gemini" | "openai" | "ollama"
    gemini_api_key: str  = ""
    openai_api_key: str  = ""
    ollama_base_url:str  = "http://localhost:11434"
    llm_model:      str  = "gemini-1.5-flash"

    # ── Base de datos ────────────────────────────────────────
    db_path:        str  = "jarvis.db"
    db_echo:        bool = False        # True para debug SQL

    # ── EventBus ─────────────────────────────────────────────
    event_bus_backend: str = "memory"   # "memory" | "redis"
    redis_url:         str = "redis://localhost:6379"

    # ── Home Assistant (fase 6) ──────────────────────────────
    ha_url:         str  = ""
    ha_token:       str  = ""

    # ── API (fase 5) ─────────────────────────────────────────
    api_host:       str  = "0.0.0.0"
    api_port:       int  = 8000
    debug:          bool = False

    # ── Logging ──────────────────────────────────────────────
    log_level:      str  = "INFO"
    log_file:       str  = "logs/jarvis.log"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Singleton — siempre usar esto, nunca instanciar Settings directo."""
    return Settings()


# ── .env.example (copiar a .env y completar) ─────────────────
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=tu_clave_aqui
# DB_PATH=jarvis.db
# EVENT_BUS_BACKEND=memory
# LOG_LEVEL=INFO
