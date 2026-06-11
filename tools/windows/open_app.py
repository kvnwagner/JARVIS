"""
Tool: open_app
Abre una aplicación en Windows por nombre o un sitio web en el navegador.
"""

import os
import subprocess
import shutil
import webbrowser
from core.interfaces import Tool, ToolResult

# Mapa de nombres amigables → ejecutables o URLs
APP_ALIASES: dict[str, str] = {
    # Aplicaciones
    "spotify":            r"C:\Users\Wagne\AppData\Roaming\Spotify\Spotify.exe",
    "chrome":             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "google chrome":      r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "vscode":             r"C:\Users\Wagne\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio code": r"C:\Users\Wagne\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "whatsapp":           "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",
    "discord":            "discord",
    "telegram":           "telegram",
    "steam":              "steam",
    "notepad":            "notepad",
    "explorer":           "explorer",
    "calculadora":        "calc",

    # Sitios web
    "youtube":            "https://www.youtube.com",
    "facebook":           "https://www.facebook.com",
    "instagram":          "https://www.instagram.com",
    "gmail":              "https://mail.google.com",
    "netflix":            "https://www.netflix.com",
    "twitter":            "https://www.twitter.com",
    "x":                  "https://www.x.com",
    "twitch":             "https://www.twitch.tv",
    "reddit":             "https://www.reddit.com",
    "prime video":        "https://www.primevideo.com",
    "disney":             "https://www.disneyplus.com",
    "disney+":            "https://www.disneyplus.com",
    "google":             "https://www.google.com",
    "github":             "https://www.github.com",
    "linkedin":           "https://www.linkedin.com",
}


class OpenAppTool(Tool):
    name = "open_app"
    description = (
        "Abre una aplicación de Windows o un sitio web en el navegador. "
        "Usa esto cuando el usuario pida abrir, lanzar o iniciar cualquier programa, "
        "aplicación o sitio web como YouTube, Facebook, Instagram, Netflix, Gmail, etc."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": (
                    "Nombre de la aplicación o sitio web a abrir. "
                    "Ejemplos: spotify, chrome, youtube, facebook, instagram, netflix, gmail"
                )
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

        # Si es una URL, abrir en el navegador
        if executable.startswith("https://") or executable.startswith("http://"):
            try:
                webbrowser.open(executable)
                return ToolResult.ok(f"Abriendo {app_name} en el navegador.")
            except Exception as e:
                return ToolResult.fail(f"Error al abrir {app_name}: {e}")

        # WhatsApp app de escritorio
        if app_name == "whatsapp":
            try:
                subprocess.Popen(
                    ["explorer.exe", "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"]
                )
                return ToolResult.ok("WhatsApp abierto correctamente.")
            except Exception as e:
                return ToolResult.fail(f"Error al abrir WhatsApp: {e}")

        # Shell apps
        if executable.startswith("shell:AppsFolder"):
            try:
                subprocess.Popen(
                    f'explorer.exe "{executable}"',
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS
                )
                return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
            except Exception as e:
                return ToolResult.fail(f"Error al abrir '{app_name}': {e}")

        # Verificar si el ejecutable existe en PATH o es ruta absoluta
        if not os.path.isfile(executable) and not shutil.which(executable):
            return ToolResult.fail(
                f"No se encontró '{app_name}' en el sistema. "
                f"Verifica que esté instalada y en el PATH."
            )

        try:
            subprocess.Popen(
                executable,
                shell=True,
                creationflags=subprocess.DETACHED_PROCESS
            )
            return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
        except Exception as e:
            return ToolResult.fail(f"Error al abrir '{app_name}': {e}")