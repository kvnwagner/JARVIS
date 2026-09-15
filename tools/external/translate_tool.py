"""
Tool: translate
Traduce texto entre idiomas usando la API gratuita de MyMemory (sin API key).
"""
import requests
from core.interfaces import Tool, ToolResult

LANG_ALIASES: dict[str, str] = {
    "español": "es", "espanol": "es", "castellano": "es", "spanish": "es", "es": "es",
    "inglés": "en", "ingles": "en", "english": "en", "en": "en",
    "francés": "fr", "frances": "fr", "french": "fr", "fr": "fr",
    "portugués": "pt", "portugues": "pt", "portuguese": "pt", "pt": "pt",
    "alemán": "de", "aleman": "de", "german": "de", "de": "de",
    "italiano": "it", "italian": "it", "it": "it",
    "japonés": "ja", "japones": "ja", "japanese": "ja", "ja": "ja",
    "chino": "zh", "chinese": "zh", "zh": "zh",
    "coreano": "ko", "korean": "ko", "ko": "ko",
    "ruso": "ru", "russian": "ru", "ru": "ru",
}


class TranslateTool(Tool):
    name = "translate"
    description = (
        "Traduce texto entre idiomas. Usa esto cuando el usuario pida traducir "
        "una palabra, frase o texto a otro idioma. "
        "Ejemplos: 'traduce hola al inglés', 'cómo se dice gracias en francés', "
        "'traduce esto al español: thank you'."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "Texto a traducir"
            },
            "target": {
                "type": "string",
                "description": "Idioma destino. Ej: español, inglés, francés, alemán, italiano, portugués"
            },
            "source": {
                "type": "string",
                "description": "Idioma de origen (opcional). Si no se indica, se asume inglés como origen.",
                "default": "auto"
            }
        },
        "required": ["text", "target"]
    }

    def execute(self, params: dict) -> ToolResult:
        text = params.get("text", "").strip()
        target_raw = params.get("target", "").strip().lower()
        source_raw = params.get("source", "auto").strip().lower()

        if not text:
            return ToolResult.fail("Debes indicar el texto a traducir.")
        if not target_raw:
            return ToolResult.fail("Debes indicar el idioma destino.")

        target = LANG_ALIASES.get(target_raw, target_raw)
        source = LANG_ALIASES.get(source_raw, "en") if source_raw in ("auto", "") else LANG_ALIASES.get(source_raw, source_raw)

        langpair = f"{source}|{target}"

        try:
            response = requests.get(
                "https://api.mymemory.translated.net/get",
                params={"q": text, "langpair": langpair},
                timeout=10,
            )
            if response.status_code != 200:
                return ToolResult.fail(f"Error al traducir (código {response.status_code}).")

            data = response.json()
            translated = data.get("responseData", {}).get("translatedText", "")

            if not translated:
                return ToolResult.fail("No se pudo obtener la traducción.")

            return ToolResult.ok(f"🌐 «{text}» → «{translated}» ({source}→{target})")

        except requests.Timeout:
            return ToolResult.fail("La traducción tardó demasiado. Intenta de nuevo.")
        except Exception as e:
            return ToolResult.fail(f"Error inesperado al traducir: {e}")