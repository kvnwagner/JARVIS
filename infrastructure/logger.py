# ================================================================
# infrastructure/logger.py
# Observabilidad centralizada — escucha todos los eventos
# Propietario: Persona 4 (Integraciones / Logging)
# ================================================================

import logging
import json
from pathlib import Path
from core.interfaces import Event, EventBus
from infrastructure.events import WILDCARD, SYSTEM_ERROR
from core.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    Path(settings.log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level   = settings.log_level,
        format  = "%(asctime)s | %(name)-20s | %(levelname)-7s | %(message)s",
        handlers = [
            logging.StreamHandler(),
            logging.FileHandler(settings.log_file, encoding="utf-8")
        ]
    )


class JarvisLogger:
    """Se registra al EventBus y loguea todo lo que pasa."""

    def __init__(self, bus: EventBus):
        self._log = logging.getLogger("jarvis.events")
        bus.subscribe(WILDCARD, self._handle)

    def _handle(self, event: Event) -> None:
        level = logging.ERROR if event.name == SYSTEM_ERROR else logging.INFO

        self._log.log(level, "%s | source=%-20s | %s", (
            event.name,
            event.source,
            json.dumps(event.payload, default=str, ensure_ascii=False)
        ))


# ── Ejemplo de log que verías en jarvis.log ───────────────────
#
# 2026-06-05 10:23:01 | jarvis.events       | INFO    |
#   user.message | source=cli              | {"text": "abre spotify"}
#
# 2026-06-05 10:23:01 | jarvis.events       | INFO    |
#   llm.tool_call | source=gemini          | {"tool": "open_app", "params": {"app": "spotify"}}
#
# 2026-06-05 10:23:02 | jarvis.events       | INFO    |
#   tool.executed | source=open_app        | {"success": true, "output": "Spotify abierto"}
#
# Cuando algo falla ves la cadena completa:
# ¿Qué dijo el usuario? ¿Qué eligió el LLM? ¿Qué ejecutó? ¿Qué devolvió?