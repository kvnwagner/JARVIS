# ================================================================
# core/container.py
# Contenedor de dependencias — único lugar donde se instancia todo
# ================================================================

from pathlib import Path
from infrastructure.event_bus import InMemoryEventBus
from infrastructure.logger import JarvisLogger, setup_logging
from core.interfaces import EventBus


class Container:
    """
    Crea y conecta todos los componentes del sistema.
    """

    def __init__(self, log_level: str = "INFO", log_file: str = "logs/jarvis.log"):

        # 0. Cargar configuración
        self.config = self._cargar_config()

        # 1. Logging primero
        setup_logging(log_level=log_level, log_file=log_file)

        # 2. EventBus
        self.bus: EventBus = InMemoryEventBus()

        # 3. Logger
        self.logger = JarvisLogger(self.bus)

    def _cargar_config(self) -> dict:
        """Carga configuración desde config.json."""
        import json
        from pathlib import Path
        
        config_path = Path("config.json")
        
        if config_path.exists():
            with open(config_path, encoding="utf-8") as f:
                return json.load(f)
        
        return {
            "llm_provider": "gemini",
            "google": {
                "api_key": "TU_API_KEY"
            },
            "log_dir": "logs",
            "db_path": "jarvis.db"
        }