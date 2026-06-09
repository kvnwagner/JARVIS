# ================================================================
# core/container.py
# Contenedor de dependencias — único lugar donde se instancia todo
# ================================================================
import logging

from core.config import Settings, get_settings
from core.interfaces import EventBus
from infrastructure.event_bus import InMemoryEventBus, RedisEventBus
from infrastructure.logger import JarvisLogger, setup_logging
from infrastructure.reminder_scheduler import ReminderScheduler
from tools import ToolRegistry
from tools.windows import WINDOWS_TOOLS
from tools.external.weather import WeatherTool
from tools.external.news import NewsTool
from tools.external.email_tool import EmailTool
from tools.external.spotify_tool import SpotifyTool
from tools.external.reminder_tool import ReminderTool, init_reminders_table
from tools.external.system_tool import SystemTool
from tools.external.tasks_tool import TasksTool
from tools.windows.clipboard import set_llm as clipboard_set_llm
from tools.home_assistant.registry import HA_TOOLS


class Container:
    """Crea y conecta todos los componentes del sistema."""

    def __init__(self, settings: Settings | None = None):
        self.config = settings or get_settings()

        # 1. Logging primero
        setup_logging(log_level=self.config.log_level, log_file=self.config.log_file)

        # 2. EventBus
        self.bus: EventBus = self._build_event_bus()

        # 3. Logger
        self.logger = JarvisLogger(self.bus)

        # 4. Tool Registry
        self.tool_registry = ToolRegistry(self.bus)

        # 5. Registrar Windows Tools
        for tool in WINDOWS_TOOLS:
            self.tool_registry.register(tool)

        # 6. Registrar herramientas externas
        self.tool_registry.register(WeatherTool())
        self.tool_registry.register(NewsTool())
        self.tool_registry.register(EmailTool())
        self.tool_registry.register(SpotifyTool())
        self.tool_registry.register(ReminderTool())
        self.tool_registry.register(SystemTool())
        self.tool_registry.register(TasksTool())

        # 7. Registrar herramientas de Home Assistant
        for tool in HA_TOOLS:
            self.tool_registry.register(tool)

        # 8. Inicializar tabla de recordatorios en SQLite
        init_reminders_table()

        # 9. Scheduler — recibe bus para poder notificar al WebSocket
        self.reminder_scheduler = ReminderScheduler(bus=self.bus)

    def inject_llm(self, llm) -> None:
        """Inyecta el LLM en las tools que lo necesitan (ej: ClipboardTool)."""
        clipboard_set_llm(llm)

    def start_scheduler(self, voice=None) -> None:
        """
        Arranca el scheduler con acceso al VoiceManager.
        Llamar desde main.py después de construir el voice.
        """
        self.reminder_scheduler._voice = voice
        self.reminder_scheduler.start()

    def _build_event_bus(self) -> EventBus:
        backend = self.config.event_bus_backend.lower().strip()
        if backend == "memory":
            return InMemoryEventBus()
        if backend == "redis":
            try:
                return RedisEventBus(self.config.redis_url)
            except Exception as exc:
                logging.getLogger("jarvis.container").warning(
                    "Redis no esta disponible (%s). Usando EventBus en memoria.",
                    exc,
                )
                return InMemoryEventBus()
        raise ValueError(
            "EVENT_BUS_BACKEND debe ser 'memory' o 'redis'. "
            f"Valor recibido: {self.config.event_bus_backend!r}"
        )