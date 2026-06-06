# ================================================================
# infrastructure/logger.py
# Logging centralizado — escucha TODOS los eventos del sistema
# Propietario: Persona 4
# ================================================================

import logging
import json
from pathlib import Path

from core.interfaces import Event, EventBus
from infrastructure.events import WILDCARD, SYSTEM_ERROR


def setup_logging(log_level: str = "INFO", log_file: str = "logs/jarvis.log") -> None:
    """Configura el sistema de logging. Llamar UNA vez al arrancar."""
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(name)-22s | %(levelname)-7s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )


class JarvisLogger:
    """
    Se suscribe al EventBus con WILDCARD y registra todo lo que ocurre.

    Formato de cada línea en jarvis.log:
      2026-06-05 10:23:01 | jarvis.events | INFO |
        user.message | source=cli | {"text": "abre spotify"}
    """

    def __init__(self, bus: EventBus):
        self._log = logging.getLogger("jarvis.events")
        bus.subscribe(WILDCARD, self._handle)
        self._log.info("JarvisLogger activo — escuchando todos los eventos")

    def _handle(self, event: Event) -> None:
        level = logging.ERROR if event.name == SYSTEM_ERROR else logging.INFO

        try:
            payload_str = json.dumps(event.payload, default=str, ensure_ascii=False)
        except Exception:
            payload_str = str(event.payload)

        self._log.log(
            level,
            "%-30s | source=%-20s | %s",
            event.name,
            event.source,
            payload_str,
        )