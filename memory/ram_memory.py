# ================================================================
# memory/ram_memory.py
# Memoria de corto plazo — vive solo mientras Jarvis está corriendo.
# Guarda el historial de la conversación actual en RAM.
# Se borra automáticamente al cerrar el proceso.
# ================================================================

from datetime import datetime
from uuid import uuid4
from core.interfaces import MemoryProvider, MemoryEntry


class RAMMemory(MemoryProvider):
    """
    Memoria volátil para el contexto de la conversación actual.
    Rápida, sin dependencias, se reinicia con cada sesión.
    """

    def __init__(self, max_entries: int = 100):
        self._entries: list[MemoryEntry] = []
        self._max_entries = max_entries

    def save(self, entry: MemoryEntry) -> None:
        """Guarda una entrada. Si supera el límite, elimina la más antigua."""
        if not entry.id:
            entry.id = str(uuid4())
        self._entries.append(entry)
        if len(self._entries) > self._max_entries:
            self._entries.pop(0)

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Búsqueda simple por palabras clave en el contenido."""
        query_lower = query.lower()
        results = [
            e for e in self._entries
            if query_lower in e.content.lower()
        ]
        return results[-limit:]

    def get_recent(self, n: int = 20) -> list[MemoryEntry]:
        """Retorna las n entradas más recientes."""
        return self._entries[-n:]

    def clear(self) -> None:
        """Vacía toda la memoria RAM."""
        self._entries.clear()

    def count(self) -> int:
        """Retorna cuántas entradas hay en memoria."""
        return len(self._entries)

    def to_llm_context(self, n: int = 20) -> list[dict]:
        """
        Convierte las últimas n entradas al formato que espera el LLM.
        Retorna lista de {"role": ..., "content": ...}
        """
        recent = self.get_recent(n)
        context = []
        for entry in recent:
            role = "user" if entry.source == "user" else "assistant"
            context.append({"role": role, "content": entry.content})
        return context
