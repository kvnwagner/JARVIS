"""
Tool: search_web
Busca algo específico DENTRO de un sitio o app web (YouTube, Google,
Amazon, Mercado Libre, etc.) y abre los resultados en el navegador.

Diferencia con open_app: open_app solo ABRE el sitio (ej: "abre youtube").
search_web BUSCA algo dentro del sitio (ej: "busca en youtube intro de junior h").
"""
import urllib.parse
import webbrowser
from core.interfaces import Tool, ToolResult

# Patrones de búsqueda por sitio. {q} se reemplaza por el texto codificado.
SEARCH_PATTERNS: dict[str, str] = {
    "youtube":         "https://www.youtube.com/results?search_query={q}",
    "google":          "https://www.google.com/search?q={q}",
    "google imagenes": "https://www.google.com/search?tbm=isch&q={q}",
    "imagenes":        "https://www.google.com/search?tbm=isch&q={q}",
    "google maps":     "https://www.google.com/maps/search/{q}",
    "maps":            "https://www.google.com/maps/search/{q}",
    "wikipedia":       "https://es.wikipedia.org/w/index.php?search={q}",
    "amazon":          "https://www.amazon.com/s?k={q}",
    "mercado libre":   "https://listado.mercadolibre.com.co/{q}",
    "mercadolibre":    "https://listado.mercadolibre.com.co/{q}",
    "netflix":         "https://www.netflix.com/search?q={q}",
    "twitter":         "https://twitter.com/search?q={q}",
    "x":               "https://twitter.com/search?q={q}",
    "instagram":       "https://www.instagram.com/explore/tags/{q_notag}",
    "github":          "https://github.com/search?q={q}",
    "reddit":          "https://www.reddit.com/search/?q={q}",
    "twitch":          "https://www.twitch.tv/search?term={q}",
    "spotify":         "https://open.spotify.com/search/{q_path}",
    "play store":      "https://play.google.com/store/search?q={q}",
    "app store":       "https://apps.apple.com/search?term={q}",
}

# Alias para que el LLM no tenga que acertar el nombre exacto del sitio
SITE_ALIASES: dict[str, str] = {
    "yt": "youtube",
    "gmaps": "google maps",
    "wiki": "wikipedia",
    "ig": "instagram",
    "gh": "github",
}


class SearchWebTool(Tool):
    name = "search_web"
    description = (
        "Busca algo específico DENTRO de un sitio o plataforma web "
        "(YouTube, Google, Amazon, Mercado Libre, Netflix, Wikipedia, "
        "GitHub, Twitter/X, Reddit, Twitch, Spotify, Play Store, App Store, "
        "Google Maps, imágenes). "
        "Úsalo cuando el usuario pida 'busca X en Y', 'busca X en youtube', "
        "'encuentra X en amazon', etc. NO uses esto para solo abrir un sitio "
        "sin buscar nada (para eso usa open_app). "
        "Si el usuario no especifica sitio (ej: solo 'busca X'), usa site='google'."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "site": {
                "type": "string",
                "description": (
                    "Sitio donde buscar. Ej: youtube, google, amazon, "
                    "mercado libre, netflix, wikipedia, github, twitter, "
                    "reddit, twitch, spotify, maps, imagenes, play store, "
                    "app store. Si no se indica, usa 'google'."
                )
            },
            "query": {
                "type": "string",
                "description": "Qué buscar. Ej: 'intro de junior h', 'audífonos bluetooth'"
            }
        },
        "required": ["query"]
    }

    def execute(self, params: dict) -> ToolResult:
        query = params.get("query", "").strip()
        site_raw = params.get("site", "google").strip().lower()

        if not query:
            return ToolResult.fail("Debes indicar qué quieres buscar.")

        site = SITE_ALIASES.get(site_raw, site_raw)
        pattern = SEARCH_PATTERNS.get(site)

        if not pattern:
            # Sitio desconocido → fallback: búsqueda en Google
            pattern = SEARCH_PATTERNS["google"]
            query = f"{query} {site_raw}" if site_raw != "google" else query
            site = "google"

        q_encoded = urllib.parse.quote_plus(query)
        q_path = urllib.parse.quote(query)                     # rutas tipo /search/{q}
        q_notag = urllib.parse.quote(query.replace(" ", ""))   # hashtags

        url = pattern.format(q=q_encoded, q_path=q_path, q_notag=q_notag)

        try:
            webbrowser.open(url)
            return ToolResult.ok(f"Buscando '{query}' en {site}.")
        except Exception as e:
            return ToolResult.fail(f"Error al buscar en {site}: {e}")