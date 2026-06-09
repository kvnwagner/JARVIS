"""
Tool: clipboard
Lee o escribe texto en el portapapeles de Windows.
Usa win32clipboard para mayor compatibilidad con procesos en background.
Requiere: pip install pywin32
"""

import win32clipboard
import win32con
from core.interfaces import Tool, ToolResult


def _read_clipboard() -> str:
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return ""
    finally:
        win32clipboard.CloseClipboard()


def _write_clipboard(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


class ClipboardTool(Tool):
    name = "clipboard"
    description = (
        "Lee o escribe texto en el portapapeles de Windows. "
        "Usa 'get' para leer lo que hay copiado, 'set' para escribir texto nuevo. "
        "Úsalo cuando el usuario pida copiar algo, pegar, o leer el portapapeles."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get", "set", "clear"],
                "description": (
                    "'get' = leer portapapeles, "
                    "'set' = escribir texto (requiere 'text'), "
                    "'clear' = vaciar portapapeles"
                )
            },
            "text": {
                "type": "string",
                "description": "Texto a escribir en el portapapeles (solo para action='set')"
            }
        },
        "required": ["action"]
    }

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip().lower()

        if action == "get":
            try:
                content = _read_clipboard()
                if not content:
                    return ToolResult.ok("El portapapeles está vacío.")
                preview = content[:500] + ("..." if len(content) > 500 else "")
                return ToolResult.ok(f"Portapapeles ({len(content)} caracteres):\n{preview}")
            except Exception as e:
                return ToolResult.fail(f"Error al leer el portapapeles: {e}")

        if action == "set":
            text = params.get("text", "")
            if not text:
                return ToolResult.fail("Para action='set' debes proporcionar 'text'.")
            try:
                _write_clipboard(text)
                return ToolResult.ok(f"Texto copiado al portapapeles ({len(text)} caracteres).")
            except Exception as e:
                return ToolResult.fail(f"Error al escribir en el portapapeles: {e}")

        if action == "clear":
            try:
                _write_clipboard("")
                return ToolResult.ok("Portapapeles vaciado.")
            except Exception as e:
                return ToolResult.fail(f"Error al vaciar el portapapeles: {e}")

        return ToolResult.fail(f"Acción desconocida: '{action}'. Opciones: get, set, clear.")