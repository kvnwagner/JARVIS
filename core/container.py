# ================================================================
# core/container.py
# Contenedor de dependencias — único lugar donde se instancia todo
#
# REGLA: nadie fuera de container.py hace InMemoryEventBus()
# directamente. Así migrar a Redis = cambiar UNA línea aquí.
# ================================================================

from infrastructure.event_bus import InMemoryEventBus
from infrastructure.logger import JarvisLogger, setup_logging
from core.interfaces import EventBus


class Container:
    """
    Crea y conecta todos los componentes del sistema.

    Fase 0.75 : bus + logger
    Fase 1    : + llm
    Fase 2    : + tool registry
    Fase 4    : + memory
    """

    def __init__(self, log_level: str = "INFO", log_file: str = "logs/jarvis.log"):

        # 1. Logging primero — para que todo lo que sigue quede registrado
        setup_logging(log_level=log_level, log_file=log_file)

        # 2. EventBus — columna vertebral del sistema
        #    Para migrar a Redis solo cambiar estas dos líneas:
        #      from infrastructure.redis_event_bus import RedisEventBus
        #      self.bus: EventBus = RedisEventBus(url=settings.redis_url)
        self.bus: EventBus = InMemoryEventBus()

        # 3. Logger — se suscribe al bus con WILDCARD, registra todo
        self.logger = JarvisLogger(self.bus)

        # Fases siguientes (descomentar cuando llegue cada fase):
        # self.llm      = GeminiProvider(...)            # Fase 1
        # self.registry = ToolRegistry(self.bus)         # Fase 2
        # self.memory   = SQLiteMemory(self.bus)         # Fase 4
        # self.agent    = Agent(self.llm, self.registry,
        #                       self.memory, self.bus)   # Fase 1