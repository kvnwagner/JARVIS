# ================================================================
# core/config.py
# Única fuente de configuración del proyecto
# Propietario: todos — carga de .env automática
# ================================================================

from functools import lru_cache
from pathlib import Path
import json
import os

from pydantic import BaseModel


class Settings(BaseModel):

    # ── LLM ─────────────────────────────────────────────────
    llm_provider:   str  = "gemini"     # "gemini" | "groq" | "cerebras" | "openai" | "ollama"
    gemini_api_key: str  = ""
    groq_api_key:   str  = ""
    cerebras_api_key: str = ""
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

    model_config = {"extra": "ignore"}


def _load_dotenv(path: Path = Path(".env")) -> dict[str, str]:
    """Carga pares CLAVE=valor de .env sin dependencia externa."""
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")

    return values


def _load_legacy_config(path: Path = Path("config.json")) -> dict[str, str]:
    """Compatibilidad temporal con el config.json usado antes de Fase 1."""
    if not path.exists():
        return {}

    data = json.loads(path.read_text(encoding="utf-8"))
    google_config = data.get("google", {}) if isinstance(data, dict) else {}
    return {
        "llm_provider": data.get("llm_provider", "gemini"),
        "gemini_api_key": google_config.get("api_key", ""),
        "db_path": data.get("db_path", "jarvis.db"),
        "log_file": str(Path(data.get("log_dir", "logs")) / "jarvis.log"),
    }


def _coerce_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    return value.lower() in {"1", "true", "yes", "on", "si", "sí"}


def _collect_settings_data() -> dict:
    dotenv = _load_dotenv()
    legacy = _load_legacy_config()

    env_map = {
        "LLM_PROVIDER": "llm_provider",
        "GEMINI_API_KEY": "gemini_api_key",
        "GROQ_API_KEY": "groq_api_key",
        "CEREBRAS_API_KEY": "cerebras_api_key",
        "OPENAI_API_KEY": "openai_api_key",
        "OLLAMA_BASE_URL": "ollama_base_url",
        "LLM_MODEL": "llm_model",
        "DB_PATH": "db_path",
        "DB_ECHO": "db_echo",
        "EVENT_BUS_BACKEND": "event_bus_backend",
        "REDIS_URL": "redis_url",
        "HA_URL": "ha_url",
        "HA_TOKEN": "ha_token",
        "API_HOST": "api_host",
        "API_PORT": "api_port",
        "DEBUG": "debug",
        "LOG_LEVEL": "log_level",
        "LOG_FILE": "log_file",
    }

    data = legacy.copy()
    for env_name, field_name in env_map.items():
        if env_name in dotenv:
            data[field_name] = dotenv[env_name]
        if env_name in os.environ:
            data[field_name] = os.environ[env_name]

    for bool_field in ("db_echo", "debug"):
        if bool_field in data:
            data[bool_field] = _coerce_bool(data[bool_field])

    if "api_port" in data:
        data["api_port"] = int(data["api_port"])

    return data


@lru_cache
def get_settings() -> Settings:
    """Singleton — siempre usar esto, nunca instanciar Settings directo."""
    return Settings(**_collect_settings_data())


# ── .env.example (copiar a .env y completar) ─────────────────
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=tu_clave_aqui
# DB_PATH=jarvis.db
# EVENT_BUS_BACKEND=memory
# REDIS_URL=redis://localhost:6379
# LOG_LEVEL=INFO
