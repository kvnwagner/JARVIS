"""
Tool: open_app
Abre una aplicación en Windows por nombre o un sitio web en el navegador.

Estrategia de resolución (en orden):
  1. Ruta conocida y fija (APP_ALIASES) — apps de escritorio comunes.
  2. Búsqueda dinámica de apps instaladas vía Windows Store/UWP
     (Get-StartApps) — detecta apps como TikTok, Netflix, Instagram, etc.
     sin necesidad de conocer su ruta de antemano.
  3. Alternativa web conocida (APP_WEB_FALLBACK) o URL directa —
     si la app no está instalada, se abre su versión en el navegador.
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

    # Sitios web (apps sin versión de escritorio típica, o que preferimos en navegador)
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
    "tiktok":             "https://www.tiktok.com",
}

# Alternativa web para apps que SÍ pueden estar instaladas como programa,
# pero si no lo están, abrimos esto en vez de fallar.
APP_WEB_FALLBACK: dict[str, str] = {
    "tiktok":    "https://www.tiktok.com",
    "discord":   "https://discord.com/app",
    "telegram":  "https://web.telegram.org",
    "spotify":   "https://open.spotify.com",
    "steam":     "https://store.steampowered.com/",
    "whatsapp":  "https://web.whatsapp.com",
}


def _find_uwp_app_id(name: str) -> str | None:
    """
    Busca, entre las apps instaladas de Windows (incluye apps de Store/UWP
    como TikTok, Instagram, Netflix, etc.), una cuyo nombre contenga 'name'.
    Retorna su AppID (usable con shell:AppsFolder\\<AppID>) o None si no
    se encontró o si algo falló (timeout, PowerShell no disponible, etc.).
    """
    try:
        safe_name = name.replace("'", "")
        ps_cmd = (
            "(Get-StartApps | Where-Object { $_.Name -like '*" + safe_name + "*' } "
            "| Select-Object -First 1 -ExpandProperty AppID)"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=8,
        )
        app_id = (result.stdout or "").strip()
        return app_id or None
    except Exception:
        return None


class OpenAppTool(Tool):
    name = "open_app"
    description = (
        "Abre una aplicación de Windows (incluso apps de Microsoft Store como TikTok) "
        "o un sitio web en el navegador. Si la aplicación no está instalada, abre "
        "automáticamente su versión web como alternativa. "
        "Usa esto cuando el usuario pida abrir, lanzar o iniciar cualquier programa, "
        "aplicación o sitio web como YouTube, Facebook, Instagram, Netflix, Gmail, "
        "Spotify, Chrome, VSCode, Discord, Steam, TikTok, etc."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": (
                    "Nombre de la aplicación o sitio web a abrir. "
                    "Ejemplos: spotify, chrome, youtube, facebook, instagram, netflix, gmail, discord, tiktok"
                )
            }
        },
        "required": ["app"]
    }

    def execute(self, params: dict) -> ToolResult:
        app_name = params.get("app", "").strip().lower()
        if not app_name:
            return ToolResult.fail("No se especificó ninguna aplicación.")

        executable = APP_ALIASES.get(app_name)

        # ── 1) Alias conocido que ES una URL directa ────────────────────────
        if executable and (executable.startswith("https://") or executable.startswith("http://")):
            try:
                webbrowser.open(executable)
                return ToolResult.ok(f"Abriendo {app_name} en el navegador.")
            except Exception as e:
                return ToolResult.fail(f"Error al abrir {app_name}: {e}")

        # ── 2) WhatsApp (UWP con AppID fijo conocido) ───────────────────────
        if app_name == "whatsapp":
            try:
                subprocess.Popen(
                    ["explorer.exe", "shell:AppsFolder\\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"]
                )
                return ToolResult.ok("WhatsApp abierto correctamente.")
            except Exception:
                pass  # si falla, seguimos con los siguientes niveles de fallback

        # ── 3) Shell apps genéricas ya resueltas en el alias ────────────────
        if executable and executable.startswith("shell:AppsFolder"):
            try:
                subprocess.Popen(
                    f'explorer.exe "{executable}"',
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS
                )
                return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
            except Exception:
                pass

        # ── 4) Discord: usa el updater con --processStart ───────────────────
        if app_name == "discord":
            discord_path = os.path.join(LOCALAPPDATA, r"Discord\Update.exe")
            if os.path.isfile(discord_path):
                try:
                    subprocess.Popen(
                        [discord_path, "--processStart", "Discord.exe"],
                        creationflags=subprocess.DETACHED_PROCESS
                    )
                    return ToolResult.ok("Discord abierto correctamente.")
                except Exception:
                    pass  # seguimos con los siguientes niveles

        # ── 5) Ruta local conocida (o en PATH) que SÍ existe ────────────────
        if executable and (os.path.isfile(executable) or shutil.which(executable)):
            try:
                subprocess.Popen(
                    executable,
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS
                )
                return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
            except Exception as e:
                return ToolResult.fail(f"Error al abrir '{app_name}': {e}")

        # ── 6) No estaba en la lista fija: buscar entre apps instaladas ─────
        #      (Store/UWP) por nombre — detecta TikTok, Instagram, Netflix, etc.
        #      sin necesidad de tener su ruta hardcodeada.
        uwp_id = _find_uwp_app_id(app_name)
        if uwp_id:
            try:
                subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{uwp_id}"])
                return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
            except Exception:
                pass  # si falla el lanzamiento, caemos al fallback web

        # ── 7) No está instalada: abrir su alternativa web si la conocemos ──
        web_url = APP_WEB_FALLBACK.get(app_name) or APP_ALIASES.get(app_name)
        if web_url and (web_url.startswith("http://") or web_url.startswith("https://")):
            try:
                webbrowser.open(web_url)
                return ToolResult.ok(
                    f"'{app_name}' no está instalada en el equipo — la abrí en el navegador."
                )
            except Exception as e:
                return ToolResult.fail(f"Error al abrir {app_name} en el navegador: {e}")

        # ── 8) Último intento: nombre tal cual, directamente en PATH ────────
        in_path = shutil.which(app_name)
        if in_path:
            try:
                subprocess.Popen(
                    in_path,
                    shell=True,
                    creationflags=subprocess.DETACHED_PROCESS
                )
                return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
            except Exception as e:
                return ToolResult.fail(f"Error al abrir '{app_name}': {e}")

        return ToolResult.fail(
            f"No se encontró '{app_name}' instalada en el sistema, "
            f"ni una alternativa web conocida para abrirla."
        )