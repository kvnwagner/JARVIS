"""
Tool: close_app
Cierra una aplicación en Windows usando taskkill.
Termina todos los procesos que coincidan con el nombre.
"""

import subprocess
import shutil
from core.interfaces import Tool, ToolResult

# Mapa de nombres amigables → nombre del proceso (.exe)
PROCESS_ALIASES: dict[str, str] = {
    "spotify":        "Spotify.exe",
    "chrome":         "chrome.exe",
    "google chrome":  "chrome.exe",
    "firefox":        "firefox.exe",
    "vscode":         "Code.exe",
    "visual studio code": "Code.exe",
    "notepad":        "notepad.exe",
    "bloc de notas":  "notepad.exe",
    "explorer":       "explorer.exe",
    "explorador":     "explorer.exe",
    "calculadora":    "Calculator.exe",
    "calculator":     "Calculator.exe",
    "paint":          "mspaint.exe",
    "discord":        "Discord.exe",
    "slack":          "slack.exe",
    "zoom":           "Zoom.exe",
    "obs":            "obs64.exe",
    "vlc":            "vlc.exe",
    "word":           "WINWORD.EXE",
    "excel":          "EXCEL.EXE",
    "powerpoint":     "POWERPNT.EXE",
}


class CloseAppTool(Tool):
    name = "close_app"
    description = (
        "Cierra una aplicación de Windows que esté corriendo. "
        "Usa esto cuando el usuario pida cerrar, terminar o matar un programa."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": "Nombre de la aplicación a cerrar (ej: spotify, chrome)"
            },
            "force": {
                "type": "boolean",
                "description": "Si es true, fuerza el cierre sin esperar que la app responda. Default: false.",
                "default": False
            }
        },
        "required": ["app"]
    }

    def execute(self, params: dict) -> ToolResult:
        app_name = params.get("app", "").strip().lower()
        force = params.get("force", False)

        if not app_name:
            return ToolResult.fail("No se especificó ninguna aplicación.")

        process_name = PROCESS_ALIASES.get(app_name, app_name)

        # Asegurar que tiene extensión .exe
        if not process_name.lower().endswith(".exe"):
            process_name += ".exe"

        cmd = ["taskkill", "/IM", process_name]
        if force:
            cmd.append("/F")  # /F = force kill

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                return ToolResult.ok(f"'{app_name}' cerrada correctamente.")

            # Código 128 = proceso no encontrado
            if result.returncode == 128:
                return ToolResult.fail(
                    f"'{app_name}' no estaba corriendo."
                )

            return ToolResult.fail(
                f"Error al cerrar '{app_name}': {result.stderr.strip()}"
            )

        except FileNotFoundError:
            return ToolResult.fail("taskkill no está disponible. ¿Estás en Windows?")
        except Exception as e:
            return ToolResult.fail(f"Error inesperado: {e}")