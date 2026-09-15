# ================================================================
# memory/sqlite_memory.py
# Memoria de largo plazo — persiste entre sesiones usando SQLite.
# Guarda preferencias, notas, hechos sobre el usuario, comandos frecuentes
# y el historial real de conversación (tabla conversation_log).
# No requiere instalación extra (sqlite3 viene con Python).
# ================================================================

import sqlite3
import json
from datetime import datetime
from uuid import uuid4
from pathlib import Path
from core.interfaces import MemoryProvider, MemoryEntry


class SQLiteMemory(MemoryProvider):
    """
    Memoria persistente para información que Jarvis debe recordar
    entre sesiones: preferencias, notas, recordatorios, hechos del usuario
    y el historial completo de la conversación.
    """

    def __init__(self, db_path: str = "jarvis.db"):
        self._db_path = Path(db_path)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row  # acceso por nombre de columna
        return conn

    def _init_db(self) -> None:
        """Crea las tablas si no existen."""
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id          TEXT PRIMARY KEY,
                    content     TEXT NOT NULL,
                    source      TEXT NOT NULL,
                    timestamp   TEXT NOT NULL,
                    tags        TEXT NOT NULL DEFAULT '[]'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_timestamp
                ON memories (timestamp DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_source
                ON memories (source)
            """)

            # ── Historial real de conversación (persiste entre reinicios) ──
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_log (
                    id        TEXT PRIMARY KEY,
                    role      TEXT NOT NULL,
                    content   TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_timestamp
                ON conversation_log (timestamp DESC)
            """)
            conn.commit()

    # ─── MemoryProvider interface ─────────────────────────────

    def save(self, entry: MemoryEntry) -> None:
        """Guarda una entrada en SQLite."""
        if not entry.id:
            entry.id = str(uuid4())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO memories (id, content, source, timestamp, tags)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entry.id,
                    entry.content,
                    entry.source,
                    entry.timestamp.isoformat(),
                    json.dumps(entry.tags),
                )
            )
            conn.commit()

    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]:
        """Búsqueda por palabras clave en el contenido (LIKE)."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memories
                WHERE content LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (f"%{query}%", limit)
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_recent(self, n: int = 20) -> list[MemoryEntry]:
        """Retorna las n entradas más recientes."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY timestamp DESC LIMIT ?",
                (n,)
            ).fetchall()
        # Invertir para orden cronológico
        return [self._row_to_entry(r) for r in reversed(rows)]

    # ─── Conversación (real, persistente) ─────────────────────

    def save_conversation_message(self, role: str, content: str) -> None:
        """Guarda un mensaje del chat en SQLite (no se pierde al reiniciar)."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO conversation_log (id, role, content, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (str(uuid4()), role, content, datetime.utcnow().isoformat())
            )
            conn.commit()

    def get_conversation_page(self, limit: int = 20, offset: int = 0) -> list[dict]:
        """
        Retorna una página del historial de conversación.
        offset=0 → los más recientes. Resultado en orden cronológico ascendente.
        """
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT role, content, timestamp FROM conversation_log
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            ).fetchall()
        return [
            {"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]}
            for r in reversed(rows)
        ]

    def count_conversation(self) -> int:
        """Total de mensajes guardados en el historial persistente."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as total FROM conversation_log"
            ).fetchone()
        return row["total"]

    # ─── Métodos extra (no en la interfaz base) ───────────────

    def save_preference(self, key: str, value: str) -> None:
        """
        Guarda una preferencia del usuario como memoria etiquetada.
        Ejemplo: save_preference("horario_trabajo", "8am a 5pm")
        """
        entry = MemoryEntry(
            id=f"pref_{key}",   # ID fijo para poder actualizar
            content=f"{key}: {value}",
            source="system",
            tags=["preferencia", key]
        )
        self.save(entry)

    def get_preference(self, key: str) -> str | None:
        """Recupera una preferencia por clave."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT content FROM memories WHERE id = ?",
                (f"pref_{key}",)
            ).fetchone()
        if row:
            # content es "key: value", extraer solo el valor
            return row["content"].split(": ", 1)[-1]
        return None

    def search_by_tag(self, tag: str, limit: int = 10) -> list[MemoryEntry]:
        """Busca entradas que tengan un tag específico."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM memories
                WHERE tags LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (f'%"{tag}"%', limit)
            ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def delete(self, entry_id: str) -> bool:
        """Elimina una entrada por ID. Retorna True si existía."""
        with self._connect() as conn:
            cursor = conn.execute(
                "DELETE FROM memories WHERE id = ?", (entry_id,)
            )
            conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        """Retorna el total de entradas en la base de datos."""
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) as total FROM memories").fetchone()
        return row["total"]

    def clear_all(self) -> None:
        """Elimina TODAS las memorias. Usar con cuidado."""
        with self._connect() as conn:
            conn.execute("DELETE FROM memories")
            conn.commit()

    # ─── Helper ───────────────────────────────────────────────

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            source=row["source"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            tags=json.loads(row["tags"]),
        )