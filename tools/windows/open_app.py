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
    "spotify": "spotify",

    "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",

    "vscode": r"C:\Users\qandr\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio code": r"C:\Users\qandr\AppData\Local\Programs\Microsoft VS Code\Code.exe",

    "whatsapp": "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",

    "discord": "discord",
    "telegram": "telegram",
    "steam": "steam",

    "notepad": "notepad",
    "explorer": "explorer",
    "calculadora": "calc",
}



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

        if app_name == "whatsapp":
            subprocess.Popen(
                ["explorer.exe", "shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"]
            )
            return ToolResult.ok("WhatsApp abierto correctamente.")


        # Verificar si el ejecutable existe en PATH
        if not shutil.which(executable):
            return ToolResult.fail(
                f"No se encontró '{executable}' en el sistema. "
                f"Verifica que la aplicación esté instalada y en el PATH."
            )

        try:
            # creationflags=0x00000008 → DETACHED_PROCESS (no bloquea)
            if executable.startswith("shell:AppsFolder"):
                subprocess.Popen(
                    f'explorer.exe "{executable}"',
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS
                )
            else:
                subprocess.Popen(
                    executable,
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS
                )
            return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
        except Exception as e:
            return ToolResult.fail(f"Error al abrir '{app_name}': {e}")
