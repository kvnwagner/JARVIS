"""
Tool: tasks
Gestiona tareas de Google Tasks: crear, leer, completar y listar.
Usa la API oficial de Google Tasks con OAuth2.

Configuración:
    - credentials.json en la raíz del proyecto (descargado de Google Cloud Console)
    - token_tasks.json se genera automáticamente con auth_tasks.py (una sola vez)
"""
import logging
import os
from pathlib import Path

from core.interfaces import Tool, ToolResult

logger = logging.getLogger("jarvis.tasks")

CREDENTIALS_PATH = Path("credentials.json")
TOKEN_PATH        = Path("token_tasks.json")
SCOPES            = ["https://www.googleapis.com/auth/tasks"]


def _get_service():
    """Retorna un cliente autenticado de Google Tasks API."""
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "Faltan dependencias. Ejecuta: pip install google-auth-oauthlib google-api-python-client"
        )

    if not TOKEN_PATH.exists():
        raise RuntimeError(
            "No hay token de autenticación. Ejecuta auth_tasks.py una vez para autorizar el acceso."
        )

    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    # Refrescar token si expiró
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")

    return build("tasks", "v1", credentials=creds, cache_discovery=False)


def _get_default_tasklist(service) -> str:
    """Retorna el ID de la lista de tareas principal (@default)."""
    return "@default"


class TasksTool(Tool):
    name = "tasks"
    description = (
        "Gestiona tareas de Google Tasks. "
        "Crea tareas, lista tareas pendientes, marca tareas como completadas y busca por título. "
        "Úsalo cuando el usuario pida crear una tarea, ver sus pendientes, "
        "marcar algo como hecho, o gestionar su lista de tareas de Google."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "complete", "delete", "search"],
                "description": (
                    "'create' = crear tarea nueva (requiere title, opcional notes y due), "
                    "'list' = ver tareas pendientes, "
                    "'complete' = marcar tarea como completada (requiere query con el título), "
                    "'delete' = eliminar una tarea (requiere query con el título), "
                    "'search' = buscar tarea por título (requiere query)"
                )
            },
            "title": {
                "type": "string",
                "description": "Título de la tarea a crear"
            },
            "notes": {
                "type": "string",
                "description": "Notas o descripción adicional de la tarea (opcional)"
            },
            "due": {
                "type": "string",
                "description": "Fecha límite en formato YYYY-MM-DD (opcional), ej: '2025-12-31'"
            },
            "query": {
                "type": "string",
                "description": "Título o palabra clave para buscar, completar o eliminar una tarea"
            }
        },
        "required": ["action"]
    }

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip().lower()

        try:
            service = _get_service()
        except RuntimeError as e:
            return ToolResult.fail(str(e))
        except Exception as e:
            return ToolResult.fail(f"Error al conectar con Google Tasks: {e}")

        if action == "create":
            return self._create(service, params)
        if action == "list":
            return self._list(service)
        if action == "complete":
            return self._complete(service, params)
        if action == "delete":
            return self._delete(service, params)
        if action == "search":
            return self._search(service, params)

        return ToolResult.fail(
            f"Acción desconocida: '{action}'. Opciones: create, list, complete, delete, search."
        )

    # ── Acciones ─────────────────────────────────────────────────

    def _create(self, service, params: dict) -> ToolResult:
        title = params.get("title", "").strip()
        notes = params.get("notes", "").strip()
        due   = params.get("due", "").strip()

        if not title:
            return ToolResult.fail("Debes indicar el título de la tarea.")

        body = {"title": title}
        if notes:
            body["notes"] = notes
        if due:
            body["due"] = f"{due}T00:00:00.000Z"

        try:
            task = service.tasks().insert(tasklist="@default", body=body).execute()
            due_str = f"\n  Fecha:   {due}" if due else ""
            notes_str = f"\n  Notas:   {notes}" if notes else ""
            return ToolResult.ok(
                f"Tarea creada en Google Tasks ✓\n"
                f"  Título:  {task.get('title', title)}"
                f"{due_str}{notes_str}"
            )
        except Exception as e:
            return ToolResult.fail(f"Error al crear tarea: {e}")

    def _list(self, service) -> ToolResult:
        try:
            result = service.tasks().list(
                tasklist="@default",
                showCompleted=False,
                maxResults=15
            ).execute()
            tasks = result.get("items", [])

            if not tasks:
                return ToolResult.ok("No tienes tareas pendientes en Google Tasks.")

            lines = [f"📋 Tareas pendientes ({len(tasks)}):\n"]
            for t in tasks:
                due = t.get("due", "")
                due_str = f" — vence {due[:10]}" if due else ""
                notes = t.get("notes", "")
                notes_str = f"\n     📝 {notes[:60]}" if notes else ""
                lines.append(f"  ☐ {t.get('title', '(sin título)')}{due_str}{notes_str}")

            return ToolResult.ok("\n".join(lines))
        except Exception as e:
            return ToolResult.fail(f"Error al listar tareas: {e}")

    def _find_task(self, service, query: str):
        """Busca una tarea por título (coincidencia parcial). Retorna (task, error_msg)."""
        try:
            result = service.tasks().list(
                tasklist="@default",
                showCompleted=False,
                maxResults=100
            ).execute()
            tasks = result.get("items", [])
            query_lower = query.lower()
            matches = [t for t in tasks if query_lower in t.get("title", "").lower()]
            if not matches:
                return None, f"No se encontró ninguna tarea con '{query}'."
            return matches[0], None
        except Exception as e:
            return None, f"Error al buscar tarea: {e}"

    def _complete(self, service, params: dict) -> ToolResult:
        query = params.get("query", "").strip()
        if not query:
            return ToolResult.fail("Indica el título de la tarea a completar.")

        task, error = self._find_task(service, query)
        if error:
            return ToolResult.fail(error)

        try:
            task["status"] = "completed"
            service.tasks().update(
                tasklist="@default",
                task=task["id"],
                body=task
            ).execute()
            return ToolResult.ok(f"Tarea completada ✓\n  '{task.get('title')}'")
        except Exception as e:
            return ToolResult.fail(f"Error al completar tarea: {e}")

    def _delete(self, service, params: dict) -> ToolResult:
        query = params.get("query", "").strip()
        if not query:
            return ToolResult.fail("Indica el título de la tarea a eliminar.")

        task, error = self._find_task(service, query)
        if error:
            return ToolResult.fail(error)

        try:
            service.tasks().delete(
                tasklist="@default",
                task=task["id"]
            ).execute()
            return ToolResult.ok(f"Tarea eliminada ✓\n  '{task.get('title')}'")
        except Exception as e:
            return ToolResult.fail(f"Error al eliminar tarea: {e}")

    def _search(self, service, params: dict) -> ToolResult:
        query = params.get("query", "").strip()
        if not query:
            return ToolResult.fail("Indica qué buscar.")

        try:
            result = service.tasks().list(
                tasklist="@default",
                showCompleted=False,
                maxResults=100
            ).execute()
            tasks = result.get("items", [])
            query_lower = query.lower()
            matches = [t for t in tasks if query_lower in t.get("title", "").lower()]

            if not matches:
                return ToolResult.ok(f"No se encontraron tareas con '{query}'.")

            lines = [f"🔍 Tareas que coinciden con '{query}':\n"]
            for t in matches[:5]:
                due = t.get("due", "")
                due_str = f" — vence {due[:10]}" if due else ""
                lines.append(f"  ☐ {t.get('title', '(sin título)')}{due_str}")

            return ToolResult.ok("\n".join(lines))
        except Exception as e:
            return ToolResult.fail(f"Error al buscar: {e}")