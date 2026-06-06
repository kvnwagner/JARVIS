# ================================================================
# memory/memory_manager.py
# Punto de acceso único a toda la memoria de Jarvis.
# Combina RAM (corto plazo) y SQLite (largo plazo).
# El agente solo habla con este manager, nunca con RAM o SQLite directamente.
# ================================================================

from datetime import datetime
from uuid import uuid4
from core.interfaces import MemoryEntry
from memory.ram_memory import RAMMemory
from memory.sqlite_memory import SQLiteMemory


class MemoryManager:
    """
    Orquesta los dos tipos de memoria:
    - RAM:    historial de la conversación actual (volátil)
    - SQLite: preferencias, notas y hechos persistentes
    """

    def __init__(self, db_path: str = "jarvis.db", ram_limit: int = 100):
        self.ram    = RAMMemory(max_entries=ram_limit)
        self.sqlite = SQLiteMemory(db_path=db_path)

    # ─── Guardar ──────────────────────────────────────────────

    def save_message(self, content: str, source: str) -> MemoryEntry:
        """
        Guarda un mensaje de la conversación en RAM.
        source: "user" | "assistant" | "tool"
        """
        entry = MemoryEntry(
            id=str(uuid4()),
            content=content,
            source=source,
            timestamp=datetime.utcnow(),
            tags=["conversacion"]
        )
        self.ram.save(entry)
        return entry

    def save_fact(self, content: str, tags: list[str] = []) -> MemoryEntry:
        """
        Guarda un hecho o dato importante en SQLite (persiste).
        Ejemplo: save_fact("El usuario trabaja de 8 a 5", ["horario"])
        """
        entry = MemoryEntry(
            id=str(uuid4()),
            content=content,
            source="system",
            timestamp=datetime.utcnow(),
            tags=["hecho"] + tags
        )
        self.sqlite.save(entry)
        return entry

    def save_preference(self, key: str, value: str) -> None:
        """
        Guarda una preferencia con clave fija (se puede actualizar).
        Ejemplo: save_preference("idioma", "español")
        """
        self.sqlite.save_preference(key, value)

    # ─── Recuperar ────────────────────────────────────────────

    def get_conversation_context(self, n: int = 20) -> list[dict]:
        """
        Retorna el historial reciente en formato para el LLM.
        [{"role": "user", "content": "..."}, ...]
        """
        return self.ram.to_llm_context(n)

    def get_preference(self, key: str) -> str | None:
        """Recupera una preferencia guardada."""
        return self.sqlite.get_preference(key)

    def search(self, query: str, limit: int = 5) -> list[MemoryEntry]:
        """
        Busca en ambas memorias y combina resultados.
        Primero SQLite (largo plazo), luego RAM (corto plazo).
        """
        long_term  = self.sqlite.search(query, limit=limit)
        short_term = self.ram.search(query, limit=limit)

        # Deduplicar por ID y ordenar por timestamp
        seen = set()
        combined = []
        for entry in long_term + short_term:
            if entry.id not in seen:
                seen.add(entry.id)
                combined.append(entry)

        combined.sort(key=lambda e: e.timestamp)
        return combined[-limit:]

    def get_recent_facts(self, n: int = 10) -> list[MemoryEntry]:
        """Retorna los hechos persistentes más recientes de SQLite."""
        return self.sqlite.get_recent(n)

    # ─── Info ─────────────────────────────────────────────────

    def stats(self) -> dict:
        """Retorna estadísticas de ambas memorias."""
        return {
            "ram_entries":    self.ram.count(),
            "sqlite_entries": self.sqlite.count(),
        }
