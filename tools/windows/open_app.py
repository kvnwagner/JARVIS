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
    "chrome": [
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ],
    "msedge": [
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
    ],
    "firefox": [
        os.path.expandvars(r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe"),
    ],
    "spotify": [
        os.path.expandvars(r"%APPDATA%\Spotify\Spotify.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Spotify\Spotify.exe"),
    ],
    "discord": [
        os.path.expandvars(r"%LOCALAPPDATA%\Discord\Update.exe"),
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


# Navegadores que soportan abrir URLs directamente como argumento
BROWSER_EXECUTABLES = {"chrome", "firefox", "msedge"}


class OpenAppTool(Tool):
    name = "open_app"
    description = (
        "Abre una aplicación de Windows. "
        "Si el usuario pide abrir un sitio web o una URL en el navegador, "
        "usa el parámetro 'url' para que abra directamente en ese sitio. "
        "Usa esto cuando el usuario pida abrir, lanzar o iniciar cualquier programa, "
        "aplicación o página web."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "app": {
                "type": "string",
                "description": (
                    "Nombre de la aplicación a abrir (ej: spotify, chrome, vscode). "
                    "Para abrir un sitio web usa 'chrome' o 'firefox' junto con 'url'."
                )
            },
            "url": {
                "type": "string",
                "description": (
                    "URL a abrir en el navegador. Solo aplica cuando app es un navegador. "
                    "Ej: 'https://www.disneyplus.com'. Si el usuario dice 'abre Disney en Chrome' "
                    "debes poner 'https://www.disneyplus.com' aquí."
                )
            }
        },
        "required": ["app"]
    }

    def execute(self, params: dict) -> ToolResult:
        app_name = params.get("app", "").strip().lower()
        url = params.get("url", "").strip()

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
            # Si es un navegador y hay URL, abrirla directamente
            if executable in BROWSER_EXECUTABLES and url:
                # Asegurar que la URL tenga esquema
                if not url.startswith(("http://", "https://")):
                    url = "https://" + url
                subprocess.Popen(
                    [resolved, url],
                    creationflags=subprocess.DETACHED_PROCESS,
                    close_fds=True,
                )
                return ToolResult.ok(f"Chrome abriendo '{url}'.")

            subprocess.Popen(
                [resolved],
                creationflags=subprocess.DETACHED_PROCESS,
                close_fds=True,
            )
            return ToolResult.ok(f"Aplicación '{app_name}' abierta correctamente.")
        except Exception as e:
            return ToolResult.fail(f"Error al abrir '{app_name}': {e}")