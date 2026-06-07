# ================================================================
# infrastructure/event_bus.py
# EventBus en memoria o Redis sin cambiar el resto del proyecto
# ================================================================

from collections import defaultdict
from datetime import datetime
import json
import logging
import threading
import uuid

try:
    import redis
except ImportError:  # pragma: no cover - se valida al instanciar RedisEventBus
    redis = None

from core.interfaces import Event, EventBus, EventHandler
from infrastructure.events import WILDCARD

logger = logging.getLogger("jarvis.event_bus")


class InMemoryEventBus(EventBus):
    """Bus sincrono en memoria."""

    def __init__(self):
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        self._handlers[event_name].append(handler)
        logger.debug("Subscribed %s -> %s", _handler_name(handler), event_name)

    def publish(self, event: Event) -> None:
        logger.debug("[BUS] %s -> %s", event.source, event.name)
        handlers = (
            self._handlers.get(event.name, [])
            + self._handlers.get(WILDCARD, [])
        )
        _dispatch(event, handlers)


class RedisEventBus(EventBus):
    """EventBus basado en Redis Pub/Sub con el mismo contrato local."""

    def __init__(self, url: str, channel_prefix: str = "jarvis:event:"):
        if redis is None:
            raise RuntimeError(
                "Falta la dependencia 'redis'. Instala requirements.txt de nuevo."
            )

        self._redis = redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        self._redis.ping()

        self._channel_prefix = channel_prefix
        self._instance_id = str(uuid.uuid4())
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._subscribed_channels: set[str] = set()
        self._subscribed_patterns: set[str] = set()
        self._lock = threading.RLock()
        self._pubsub = self._redis.pubsub(ignore_subscribe_messages=True)
        self._listener = threading.Thread(
            target=self._listen,
            name="jarvis-redis-event-bus",
            daemon=True,
        )
        self._listener.start()
        logger.info("RedisEventBus conectado a %s", url)

    def subscribe(self, event_name: str, handler: EventHandler) -> None:
        with self._lock:
            self._handlers[event_name].append(handler)

            if event_name == WILDCARD:
                pattern = f"{self._channel_prefix}*"
                if pattern not in self._subscribed_patterns:
                    self._pubsub.psubscribe(pattern)
                    self._subscribed_patterns.add(pattern)
            else:
                channel = self._channel_name(event_name)
                if channel not in self._subscribed_channels:
                    self._pubsub.subscribe(channel)
                    self._subscribed_channels.add(channel)

        logger.debug("Subscribed %s -> %s", _handler_name(handler), event_name)

    def publish(self, event: Event) -> None:
        logger.debug("[REDIS BUS] %s -> %s", event.source, event.name)
        self._dispatch_local(event)
        self._redis.publish(self._channel_name(event.name), self._serialize(event))

    def _listen(self) -> None:
        try:
            for message in self._pubsub.listen():
                if message.get("type") not in {"message", "pmessage"}:
                    continue

                envelope = self._deserialize(message.get("data"))
                if not envelope:
                    continue
                if envelope["publisher_id"] == self._instance_id:
                    continue

                self._dispatch_local(envelope["event"])
        except Exception as exc:
            logger.error("RedisEventBus dejo de escuchar eventos: %s", exc)

    def _dispatch_local(self, event: Event) -> None:
        with self._lock:
            handlers = list(self._handlers.get(event.name, []))
            handlers.extend(self._handlers.get(WILDCARD, []))

        _dispatch(event, handlers)

    def _channel_name(self, event_name: str) -> str:
        return f"{self._channel_prefix}{event_name}"

    def _serialize(self, event: Event) -> str:
        return json.dumps(
            {
                "publisher_id": self._instance_id,
                "event": {
                    "name": event.name,
                    "payload": event.payload,
                    "source": event.source,
                    "timestamp": event.timestamp.isoformat(),
                },
            },
            default=str,
            ensure_ascii=False,
        )

    def _deserialize(self, raw: str | bytes | None) -> dict | None:
        if raw is None:
            return None

        try:
            data = json.loads(raw)
            event_data = data["event"]
            return {
                "publisher_id": data.get("publisher_id"),
                "event": Event(
                    name=event_data["name"],
                    payload=event_data.get("payload", {}),
                    source=event_data.get("source", "redis"),
                    timestamp=datetime.fromisoformat(event_data["timestamp"]),
                ),
            }
        except Exception as exc:
            logger.error("Evento Redis invalido: %s", exc)
            return None


def _dispatch(event: Event, handlers: list[EventHandler]) -> None:
    for handler in handlers:
        try:
            handler(event)
        except Exception as exc:
            logger.error(
                "Handler %s fallo en evento %s: %s",
                _handler_name(handler),
                event.name,
                exc,
            )


def _handler_name(handler: EventHandler) -> str:
    return getattr(handler, "__qualname__", repr(handler))
