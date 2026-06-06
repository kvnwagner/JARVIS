"""
Tool: open_app
Abre una aplicación en Windows por nombre.
Soporta nombres comunes (spotify, chrome, vscode) y rutas absolutas.
"""

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


class OpenAppTool(Tool):
    name = "open_app"
    description = (
        "Abre una aplicación de Windows. "
        "Usa esto cuando el usuario pida abrir, lanzar o iniciar cualquier programa o aplicación."
    )
    parameters = {
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

        # Verificar si el ejecutable existe en PATH
        if not shutil.which(executable):
            return ToolResult.fail(
                f"No se encontró '{executable}' en el sistema. "
                f"Verifica que la aplicación esté instalada y en el PATH."
            )

        try:
            # creationflags=0x00000008 → DETACHED_PROCESS (no bloquea)
            subprocess.Popen(
                [executable],
                creationflags=subprocess.DETACHED_PROCESS,
                close_fds=True
            )
            return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
        except Exception as e:
            return ToolResult.fail(f"Error al abrir '{app_name}': {e}")
