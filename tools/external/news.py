"""
Tool: news
Consulta noticias recientes por tema o país usando NewsAPI.
"""
import os
import requests
from dotenv import load_dotenv
from core.interfaces import Tool, ToolResult

load_dotenv()


class NewsTool(Tool):
    name = "news"
    description = (
        "Busca noticias recientes sobre un tema o país. Usa esto cuando el usuario "
        "pregunte qué pasó hoy, últimas noticias, novedades sobre algún tema o país."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Tema a buscar, por ejemplo: Colombia, tecnología, fútbol, política"
            },
            "language": {
                "type": "string",
                "description": "Idioma de las noticias: 'es' para español, 'en' para inglés",
                "default": "es"
            }
        },
        "required": ["query"]
    }

    def execute(self, params: dict) -> ToolResult:
        query    = params.get("query", "").strip()
        language = params.get("language", "es")

        if not query:
            return ToolResult.fail("Debes indicar un tema para buscar noticias.")

        api_key = os.getenv("NEWS_API_KEY", "")
        if not api_key:
            return ToolResult.fail("No se encontró la API key de NewsAPI en el .env.")

        try:
            url = "https://newsapi.org/v2/everything"
            response = requests.get(url, params={
                "q": query,
                "language": language,
                "sortBy": "publishedAt",
                "pageSize": 5,
                "apiKey": api_key
            }, timeout=10)

            if response.status_code != 200:
                return ToolResult.fail(f"Error al consultar noticias (código {response.status_code}).")

            data = response.json()
            articles = data.get("articles", [])

            if not articles:
                return ToolResult.fail(f"No se encontraron noticias sobre '{query}'.")

            lines = [f"📰 Últimas noticias sobre '{query}':\n"]
            for i, article in enumerate(articles[:5], 1):
                title  = article.get("title", "Sin título")
                source = article.get("source", {}).get("name", "Fuente desconocida")
                lines.append(f"{i}. [{source}] {title}")

            return ToolResult.ok("\n".join(lines))

        except requests.Timeout:
            return ToolResult.fail("La consulta de noticias tardó demasiado. Intenta de nuevo.")
        except Exception as e:
            return ToolResult.fail(f"Error inesperado: {e}")