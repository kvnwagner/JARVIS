# ================================================================
# infrastructure/event_bus.py
# EventBus en memoria — migrable a Redis sin cambiar el resto
# Propietario: Persona 1 (Core)
# ================================================================

from collections import defaultdict
from typing import Optional
import logging

from core.interfaces import EventBus, Event, EventHandler
from infrastructure.events import WILDCARD

logger = logging.getLogger("jarvis.event_bus")


class InMemoryEventBus(EventBus):
    """Bus síncrono en memoria. Fase 1–4."""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)
        logger.debug(f"Subscribed {handler.__qualname__} → {event_name}")

    def publish(self, event: Event) -> None:
        logger.debug(f"[BUS] {event.source} → {event.name}")

        handlers = (
            self._handlers.get(event.name, []) +
            self._handlers.get(WILDCARD, [])
        )

        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Handler {handler.__qualname__} falló "
                    f"en evento {event.name}: {e}"
                )
                # Un handler que falla no para los demás


# ── Preparado para Redis (misma interfaz) ──────────────────────
#
# class RedisEventBus(EventBus):
#     def __init__(self, url: str):
#         self._redis = redis.from_url(url)
#
#     def publish(self, event: Event) -> None:
#         self._redis.publish(event.name, json.dumps({
#             "payload": event.payload,
#             "source":  event.source,
#             "ts":      event.timestamp.isoformat()
#         }))
#
#     def subscribe(self, event_name: str, handler: ...) -> None:
#         ...  # pubsub.subscribe en thread separado
#
# Para migrar: cambiar solo en main.py o en el contenedor DI:
#   bus = RedisEventBus(settings.redis_url)
#
# Nada más cambia.