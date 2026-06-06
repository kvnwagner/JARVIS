# ================================================================
# core/container.py
# Contenedor de dependencias — único lugar donde se instancia todo
# ================================================================

from core.config import Settings, get_settings
from core.interfaces import EventBus
from infrastructure.event_bus import InMemoryEventBus
from infrastructure.logger import JarvisLogger, setup_logging
from tools import ToolRegistry


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
