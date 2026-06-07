"""
Tool: spotify
Controla Spotify: reproducir canciones, pausar, siguiente, anterior,
ver canción actual y buscar artistas o playlists.
"""
import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
from core.interfaces import Tool, ToolResult

load_dotenv()

SCOPE = "user-modify-playback-state user-read-playback-state user-read-currently-playing"


def _get_spotify() -> spotipy.Spotify | None:
    client_id     = os.getenv("SPOTIFY_CLIENT_ID", "")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET", "")
    redirect_uri  = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

    if not client_id or not client_secret:
        return None

    auth = SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scope=SCOPE,
        open_browser=True,
        cache_path=".spotify_cache"
    )
    return spotipy.Spotify(auth_manager=auth)


def _get_active_device(sp: spotipy.Spotify) -> str | None:
    """Retorna el device_id activo, o el primero disponible."""
    try:
        devices = sp.devices().get("devices", [])
        if not devices:
            return None
        for d in devices:
            if d.get("is_active"):
                return d["id"]
        return devices[0]["id"]
    except Exception:
        return None


class SpotifyTool(Tool):
    name = "spotify"
    description = (
        "Controla Spotify. Usa action=play para reproducir música. "
        "Usa action=pause para pausar. Usa action=next para siguiente. "
        "Usa action=previous para anterior. Usa action=current para ver qué suena. "
        "Usa action=search solo para buscar sin reproducir."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["play", "pause", "next", "previous", "current", "search"]
            },
            "query": {
                "type": "string",
                "description": "Nombre de canción o artista"
            }
        },
        "required": ["action"]
    }

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip()
        query  = params.get("query", "").strip()

        sp = _get_spotify()
        if sp is None:
            return ToolResult.fail("No se encontraron las credenciales de Spotify en el .env.")

        try:
            if action == "play":
                device_id = _get_active_device(sp)
                if not device_id:
                    return ToolResult.fail("No hay un dispositivo Spotify activo. Abre Spotify en tu PC o celular primero.")

                if query:
                    results = sp.search(q=query, type="track", limit=1)
                    tracks  = results.get("tracks", {}).get("items", [])
                    if not tracks:
                        return ToolResult.fail(f"No se encontró '{query}' en Spotify.")
                    track = tracks[0]
                    sp.start_playback(device_id=device_id, uris=[track["uri"]])
                    artist = track["artists"][0]["name"]
                    name   = track["name"]
                    return ToolResult.ok(f"Reproduciendo: {name} — {artist}")
                else:
                    sp.start_playback(device_id=device_id)
                    return ToolResult.ok("Reproducción iniciada.")

            elif action == "pause":
                sp.pause_playback()
                return ToolResult.ok("Spotify pausado.")

            elif action == "next":
                sp.next_track()
                return ToolResult.ok("Siguiente canción.")

            elif action == "previous":
                sp.previous_track()
                return ToolResult.ok("Canción anterior.")

            elif action == "current":
                current = sp.current_playback()
                if not current or not current.get("item"):
                    return ToolResult.ok("No hay ninguna canción reproduciéndose ahora.")
                track  = current["item"]
                name   = track["name"]
                artist = track["artists"][0]["name"]
                status = "▶️ Reproduciendo" if current["is_playing"] else "⏸️ Pausado"
                return ToolResult.ok(f"{status}: {name} — {artist}")

            elif action == "search":
                if not query:
                    return ToolResult.fail("Debes indicar qué buscar.")
                results = sp.search(q=query, type="track", limit=5)
                tracks  = results.get("tracks", {}).get("items", [])
                if not tracks:
                    return ToolResult.fail(f"No se encontraron resultados para '{query}'.")
                lines = [f"🎵 Resultados para '{query}':\n"]
                for i, t in enumerate(tracks, 1):
                    artist = t["artists"][0]["name"]
                    lines.append(f"{i}. {t['name']} — {artist}")
                return ToolResult.ok("\n".join(lines))

            else:
                return ToolResult.fail(f"Acción '{action}' no reconocida.")

        except spotipy.exceptions.SpotifyException as e:
            if "No active device" in str(e) or "404" in str(e):
                return ToolResult.fail("No hay un dispositivo Spotify activo. Abre Spotify en tu PC o celular primero.")
            return ToolResult.fail(f"Error de Spotify: {e}")
        except Exception as e:
            return ToolResult.fail(f"Error inesperado: {e}")