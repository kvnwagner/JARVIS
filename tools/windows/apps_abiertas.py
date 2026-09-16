"""
Tool: apps_abiertas
Lista las ventanas visibles actualmente abiertas en Windows y cuál
es la ventana activa (foco). Usa pywin32 (win32gui / win32process).
"""

import win32gui
import win32process
import psutil
from core.interfaces import Tool, ToolResult


def _list_visible_windows() -> list[dict]:
    windows = []

    def _enum_handler(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd):
            return
        title = win32gui.GetWindowText(hwnd)
        if not title.strip():
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process_name = psutil.Process(pid).name()
        except Exception:
            process_name = "desconocido"

        windows.append({
            "hwnd": hwnd,
            "title": title,
            "process": process_name,
        })

    win32gui.EnumWindows(_enum_handler, None)
    return windows


class OpenWindowsTool(Tool):
    name = "apps_abiertas"
    description = (
        "Lista las ventanas y aplicaciones actualmente abiertas en Windows, "
        "y cuál es la ventana activa en este momento. "
        "Úsalo cuando el usuario pregunte qué tiene abierto, qué aplicaciones "
        "están corriendo con ventana visible, o cuál es la ventana activa ahora."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "solo_activa": {
                "type": "boolean",
                "description": "Si es true, solo devuelve la ventana activa (en foco) en vez de la lista completa.",
                "default": False
            }
        },
        "required": []
    }

    def execute(self, params: dict) -> ToolResult:
        solo_activa = params.get("solo_activa", False)

        try:
            if solo_activa:
                hwnd = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(hwnd)
                if not title:
                    return ToolResult.ok("No se pudo determinar la ventana activa.")
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    process_name = psutil.Process(pid).name()
                except Exception:
                    process_name = "desconocido"
                return ToolResult.ok(f"🪟 Ventana activa: '{title}' ({process_name})")

            windows = _list_visible_windows()
            if not windows:
                return ToolResult.ok("No se detectaron ventanas abiertas.")

            active_hwnd = win32gui.GetForegroundWindow()

            lines = [f"🪟 Ventanas abiertas ({len(windows)}):\n"]
            for w in windows:
                marker = " ⭐ (activa)" if w["hwnd"] == active_hwnd else ""
                lines.append(f"  [{w['process']}] {w['title']}{marker}")

            return ToolResult.ok("\n".join(lines))

        except Exception as e:
            return ToolResult.fail(f"Error al consultar ventanas abiertas: {e}")