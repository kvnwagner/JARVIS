"""
Tool: open_app
Abre una aplicación en Windows por nombre o un sitio web en el navegador.
Usa rutas dinámicas — funciona en cualquier computador sin modificar nada.
"""

import os
import subprocess
import shutil
import webbrowser
from core.interfaces import Tool, ToolResult

# Variables de entorno del sistema (dinámicas por usuario)
APPDATA      = os.environ.get("APPDATA", "")
LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")
PROGRAMFILES = os.environ.get("ProgramFiles", r"C:\Program Files")
PROGRAMFILESx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

# Mapa de nombres amigables → ejecutables o URLs
APP_ALIASES: dict[str, str] = {
    # Aplicaciones — rutas dinámicas
    "spotify":            os.path.join(APPDATA, r"Spotify\Spotify.exe"),
    "vscode":             os.path.join(LOCALAPPDATA, r"Programs\Microsoft VS Code\Code.exe"),
    "visual studio code": os.path.join(LOCALAPPDATA, r"Programs\Microsoft VS Code\Code.exe"),
    "chrome":             os.path.join(PROGRAMFILES, r"Google\Chrome\Application\chrome.exe"),
    "google chrome":      os.path.join(PROGRAMFILES, r"Google\Chrome\Application\chrome.exe"),
    "discord":            os.path.join(LOCALAPPDATA, r"Discord\Update.exe"),
    "telegram":           os.path.join(APPDATA, r"Telegram Desktop\Telegram.exe"),
    "steam":              os.path.join(PROGRAMFILES, r"Steam\steam.exe"),
    "whatsapp":           "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App",

    # Herramientas del sistema (en PATH, sin ruta absoluta)
    "notepad":            "notepad",
    "explorer":           "explorer",
    "calculadora":        "calc",
    "cmd":                "cmd",
    "powershell":         "powershell",
    "taskmgr":            "taskmgr",
    "paint":              "mspaint",

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
    "chatgpt":            "https://www.chatgpt.com",
    "claude":             "https://www.claude.ai",
}


class OpenAppTool(Tool):
    name = "open_app"
    description = (
        "Abre una aplicación de Windows o un sitio web en el navegador. "
        "Usa esto cuando el usuario pida abrir, lanzar o iniciar cualquier programa, "
        "aplicación o sitio web como YouTube, Facebook, Instagram, Netflix, Gmail, "
        "Spotify, Chrome, VSCode, Discord, Steam, etc."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": (
                    "Nombre de la aplicación o sitio web a abrir. "
                    "Ejemplos: spotify, chrome, youtube, facebook, instagram, netflix, gmail, discord"
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

        # ── URL → abrir en navegador ──────────────────────────────────────────
        if executable.startswith("https://") or executable.startswith("http://"):
            try:
                webbrowser.open(executable)
                return ToolResult.ok(f"Abriendo {app_name} en el navegador.")
            except Exception as e:
                return ToolResult.fail(f"Error al abrir {app_name}: {e}")

        # ── WhatsApp (UWP) ───────────────────────────────────────────────────
        if app_name == "whatsapp":
            try:
                subprocess.Popen(
                    ["explorer.exe", "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"]
                )
                return ToolResult.ok("WhatsApp abierto correctamente.")
            except Exception as e:
                return ToolResult.fail(f"Error al abrir WhatsApp: {e}")

        # ── Shell apps genéricas ─────────────────────────────────────────────
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

        # ── Discord: usa el updater con --processStart ───────────────────────
        if app_name == "discord":
            discord_path = os.path.join(LOCALAPPDATA, r"Discord\Update.exe")
            if os.path.isfile(discord_path):
                try:
                    subprocess.Popen(
                        [discord_path, "--processStart", "Discord.exe"],
                        creationflags=subprocess.DETACHED_PROCESS
                    )
                    return ToolResult.ok("Discord abierto correctamente.")
                except Exception as e:
                    return ToolResult.fail(f"Error al abrir Discord: {e}")

        # ── Verificar que el ejecutable existe (ruta absoluta o PATH) ────────
        if not os.path.isfile(executable) and not shutil.which(executable):
            # Último intento: buscar en PATH por si el usuario tiene la app instalada
            in_path = shutil.which(app_name)
            if in_path:
                executable = in_path
            else:
                return ToolResult.fail(
                    f"No se encontró '{app_name}' en el sistema. "
                    f"Verifica que esté instalada o agrégala al PATH."
                )

        # ── Lanzar ejecutable ────────────────────────────────────────────────
        try:
            subprocess.Popen(
                executable,
                shell=True,
                creationflags=subprocess.DETACHED_PROCESS
            )
            return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
        except Exception as e:
            return ToolResult.fail(f"Error al abrir '{app_name}': {e}")