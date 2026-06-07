# ================================================================
# core/container.py
# Contenedor de dependencias — único lugar donde se instancia todo
# ================================================================

from core.config import Settings, get_settings
from core.interfaces import EventBus
from infrastructure.event_bus import InMemoryEventBus
from infrastructure.logger import JarvisLogger, setup_logging
from tools import ToolRegistry
from tools.windows import WINDOWS_TOOLS
from tools.external.weather import WeatherTool
from tools.external.news import NewsTool
from tools.external.email_tool import EmailTool
from tools.external.spotify_tool import SpotifyTool
from tools.home_assistant.registry import HA_TOOLS  # ← nuevo


class Container:
    """Crea y conecta todos los componentes del sistema."""

    def __init__(self, settings: Settings | None = None):
        # 0. Cargar configuración desde la fuente oficial (core/config.py)
        self.config = settings or get_settings()

        # 1. Logging primero
        setup_logging(log_level=self.config.log_level, log_file=self.config.log_file)

        # 2. EventBus
        self.bus: EventBus = InMemoryEventBus()

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
        # 6. Registrar Home Assistant Tools  ← nuevo
        for tool in HA_TOOLS:
            self.tool_registry.register(tool)
