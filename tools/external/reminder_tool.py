"""
Tool: reminder
Gestiona recordatorios con hora exacta del día.
Persiste en SQLite y avisa por voz + consola cuando llega la hora.
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from core.interfaces import Tool, ToolResult


DB_PATH = Path("jarvis.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_reminders_table() -> None:
    """Crea la tabla de recordatorios si no existe. Llamar al arrancar."""
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id       TEXT PRIMARY KEY,
                message  TEXT NOT NULL,
                time     TEXT NOT NULL,
                status   TEXT NOT NULL DEFAULT 'pending',
                created  TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_status
            ON reminders (status)
        """)
        conn.commit()


def get_pending_reminders() -> list[dict]:
    """Retorna todos los recordatorios pendientes. Usado por el scheduler."""
    try:
        with _connect() as conn:
            rows = conn.execute(
                "SELECT * FROM reminders WHERE status = 'pending' ORDER BY time"
            ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def mark_fired(reminder_id: str) -> None:
    """Marca un recordatorio como disparado."""
    with _connect() as conn:
        conn.execute(
            "UPDATE reminders SET status = 'fired' WHERE id = ?",
            (reminder_id,)
        )
        conn.commit()


class ReminderTool(Tool):
    name = "reminder"
    description = (
        "Gestiona recordatorios a una hora exacta del día. "
        "Usa action=set para crear un recordatorio indicando la hora (formato HH:MM, ej: 08:00, 20:30). "
        "Usa action=list para ver los recordatorios pendientes. "
        "Usa action=cancel para cancelar un recordatorio por su ID. "
        "Ejemplos: 'recuérdame tomar la medicina a las 8pm', "
        "'recuérdame la reunión a las 14:30', 'qué recordatorios tengo'."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["set", "list", "cancel"],
                "description": (
                    "'set' = crear recordatorio (requiere message y time), "
                    "'list' = ver pendientes, "
                    "'cancel' = cancelar por ID"
                )
            },
            "message": {
                "type": "string",
                "description": "Qué debe recordar Jarvis. Ej: 'tomar la medicina', 'reunión con el equipo'"
            },
            "time": {
                "type": "string",
                "description": (
                    "Hora exacta en formato HH:MM (24h). "
                    "Ej: '08:00', '14:30', '20:00'. "
                    "Convierte 8pm → 20:00, 8am → 08:00."
                )
            },
            "id": {
                "type": "string",
                "description": "ID del recordatorio a cancelar (obtenido con action=list)"
            }
        },
        "required": ["action"]
    }

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip().lower()

        if action == "set":
            return self._set(params)
        if action == "list":
            return self._list()
        if action == "cancel":
            return self._cancel(params)

        return ToolResult.fail(f"Acción desconocida: '{action}'. Usa set, list o cancel.")

    def _set(self, params: dict) -> ToolResult:
        message = params.get("message", "").strip()
        time_str = params.get("time", "").strip()

        if not message:
            return ToolResult.fail("Debes indicar qué recordar (parámetro 'message').")
        if not time_str:
            return ToolResult.fail("Debes indicar la hora (parámetro 'time', formato HH:MM).")

        # Normalizar formato de hora
        try:
            parsed = datetime.strptime(time_str, "%H:%M")
            time_normalized = parsed.strftime("%H:%M")
        except ValueError:
            return ToolResult.fail(
                f"Formato de hora inválido: '{time_str}'. Usa HH:MM, por ejemplo 08:00 o 20:30."
            )

        reminder_id = str(uuid4())[:8]

        try:
            with _connect() as conn:
                conn.execute(
                    """
                    INSERT INTO reminders (id, message, time, status, created)
                    VALUES (?, ?, ?, 'pending', ?)
                    """,
                    (reminder_id, message, time_normalized, datetime.now().isoformat())
                )
                conn.commit()
        except Exception as e:
            return ToolResult.fail(f"Error al guardar el recordatorio: {e}")

        return ToolResult.ok(
            f"Recordatorio guardado ✓\n"
            f"  Hora:    {time_normalized}\n"
            f"  Mensaje: {message}\n"
            f"  ID:      {reminder_id}"
        )

    def _list(self) -> ToolResult:
        pending = get_pending_reminders()

        if not pending:
            return ToolResult.ok("No tienes recordatorios pendientes.")

        lines = [f"Recordatorios pendientes ({len(pending)}):\n"]
        for r in pending:
            lines.append(f"  [{r['time']}] {r['message']}  (ID: {r['id']})")

        return ToolResult.ok("\n".join(lines))

    def _cancel(self, params: dict) -> ToolResult:
        reminder_id = params.get("id", "").strip()

        if not reminder_id:
            return ToolResult.fail("Debes indicar el ID del recordatorio a cancelar.")

        try:
            with _connect() as conn:
                cursor = conn.execute(
                    "UPDATE reminders SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
                    (reminder_id,)
                )
                conn.commit()

            if cursor.rowcount == 0:
                return ToolResult.fail(
                    f"No se encontró un recordatorio pendiente con ID '{reminder_id}'."
                )
        except Exception as e:
            return ToolResult.fail(f"Error al cancelar: {e}")

        return ToolResult.ok(f"Recordatorio '{reminder_id}' cancelado.")