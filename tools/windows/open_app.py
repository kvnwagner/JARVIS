"""
Tool: open_app
Abre una aplicación en Windows por nombre.
Soporta nombres comunes (spotify, chrome, vscode) y rutas absolutas.
"""

import os
import subprocess
import shutil
from core.interfaces import Tool, ToolResult

# Mapa de nombres amigables → ejecutables reales
APP_ALIASES: dict[str, str] = {
    "spotify":        "spotify",
    "chrome":         "chrome",
    "google chrome":  "chrome",
    "firefox":        "firefox",
    "vscode":         "code",
    "visual studio code": "code",
    "notepad":        "notepad",
    "bloc de notas":  "notepad",
    "explorer":       "explorer",
    "explorador":     "explorer",
    "calculadora":    "calc",
    "calculator":     "calc",
    "paint":          "mspaint",
    "cmd":            "cmd",
    "powershell":     "powershell",
    "task manager":   "taskmgr",
    "administrador de tareas": "taskmgr",
    "discord":        "discord",
    "slack":          "slack",
    "zoom":           "zoom",
    "obs":            "obs64",
    "vlc":            "vlc",
    "word":           "winword",
    "excel":          "excel",
    "powerpoint":     "powerpnt",
}

# Rutas comunes para apps que no suelen estar en PATH
APP_FALLBACK_PATHS: dict[str, list[str]] = {
    "spotify": [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Spotify\Spotify.exe"),
    ],
    "discord": [
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\app-*\Discord.exe"),
    ],
    "zoom": [
        os.path.expandvars(r"%APPDATA%\Zoom\bin\Zoom.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Zoom\bin\Zoom.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Zoom\bin\Zoom.exe"),
    ],
}


def _resolve_executable(executable: str) -> str | None:
    """
    Intenta encontrar el ejecutable en PATH primero,
    luego en rutas de fallback conocidas.
    Retorna la ruta final o None si no se encuentra.
    """
    # 1. Buscar en PATH
    if shutil.which(executable):
        return executable

    # 2. Buscar en rutas de fallback
    for path in APP_FALLBACK_PATHS.get(executable, []):
        if os.path.exists(path):
            return path

    return None


class OpenAppTool(Tool):
    name = "open_app"
    description = (
        "Abre una aplicación de Windows. "
        "Usa esto cuando el usuario pida abrir, lanzar o iniciar cualquier programa o aplicación."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": "Nombre de la aplicación a abrir (ej: spotify, chrome, vscode)"
            }
        },
        "required": ["app"]
    }

    def execute(self, params: dict) -> ToolResult:
        app_name = params.get("app", "").strip().lower()
        if not app_name:
            return ToolResult.fail("No se especificó ninguna aplicación.")

        # Resolver alias
        executable = APP_ALIASES.get(app_name, app_name)

        # Resolver ruta final
        resolved = _resolve_executable(executable)
        if not resolved:
            return ToolResult.fail(
                f"No se encontró '{app_name}' en el sistema. "
                f"Verifica que la aplicación esté instalada."
            )

        try:
            subprocess.Popen(
                [resolved],
                creationflags=subprocess.DETACHED_PROCESS,
                close_fds=True
            )
            return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
        except Exception as e:
            return ToolResult.fail(f"Error al abrir '{app_name}': {e}")