"""
Tool: clipboard
Lee o escribe texto en el portapapeles de Windows.
Usa win32clipboard para mayor compatibilidad con procesos en background.
Requiere: pip install pywin32

Acciones inteligentes (summarize, translate, fix, explain):
Leen el portapapeles, pasan el texto al LLM con un prompt específico
y devuelven el resultado listo para pegar.
El LLM se inyecta desde container.py via set_llm().
"""

import win32clipboard
import win32con
from core.interfaces import Tool, ToolResult

# LLM inyectado desde container — None hasta que se llame set_llm()
_llm = None


def set_llm(llm) -> None:
    """Llamar desde container.py después de construir el provider."""
    global _llm
    _llm = llm


def _read_clipboard() -> str:
    win32clipboard.OpenClipboard()
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
            return win32clipboard.GetClipboardData(win32con.CF_UNICODETEXT)
        return ""
    finally:
        win32clipboard.CloseClipboard()


def _write_clipboard(text: str) -> None:
    win32clipboard.OpenClipboard()
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32con.CF_UNICODETEXT, text)
    finally:
        win32clipboard.CloseClipboard()


def _ask_llm(system_prompt: str, user_text: str) -> str:
    """Llama al LLM con un prompt de sistema y el texto del usuario."""
    if not _llm:
        raise RuntimeError("LLM no disponible para acciones inteligentes del portapapeles.")
    from core.interfaces import LLMMessage
    messages = [
        LLMMessage(role="system", content=system_prompt),
        LLMMessage(role="user", content=user_text),
    ]
    response = _llm.chat(messages)
    if response.error:
        raise RuntimeError(response.error)
    return (response.text or "").strip()


class ClipboardTool(Tool):
    name = "clipboard"
    description = (
        "Lee, escribe o procesa inteligentemente el texto del portapapeles de Windows. "
        "Acciones básicas: 'get' para leer, 'set' para escribir, 'clear' para vaciar. "
        "Acciones inteligentes sobre el texto copiado: "
        "'summarize' para resumir, "
        "'translate' para traducir al español o inglés, "
        "'fix' para corregir ortografía y gramática, "
        "'explain' para obtener una explicación clara del contenido. "
        "Ejemplos: 'corrige lo que tengo copiado', 'resúmeme esto que copié', "
        "'explícame el texto del portapapeles', 'traduce lo que copié al inglés'."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["get", "set", "clear", "summarize", "translate", "fix", "explain"],
                "description": (
                    "'get' = leer portapapeles, "
                    "'set' = escribir texto (requiere 'text'), "
                    "'clear' = vaciar portapapeles, "
                    "'summarize' = resumir el texto copiado, "
                    "'translate' = traducir el texto copiado (usa 'target_lang' para el idioma destino), "
                    "'fix' = corregir ortografía y gramática del texto copiado, "
                    "'explain' = explicar el contenido del portapapeles de forma clara"
                )
            },
            "text": {
                "type": "string",
                "description": "Texto a escribir en el portapapeles (solo para action='set')"
            },
            "target_lang": {
                "type": "string",
                "description": "Idioma destino para traducir. Ejemplos: 'inglés', 'español', 'francés'. Por defecto: inglés."
            }
        },
        "required": ["action"]
    }

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip().lower()

        if action == "get":
            return self._get()

        if action == "set":
            return self._set(params)

        if action == "clear":
            return self._clear()

        if action == "summarize":
            return self._smart_action(
                system_prompt=(
                    "Eres un asistente que resume textos de forma concisa y clara. "
                    "Resume el siguiente texto en español, manteniendo los puntos más importantes. "
                    "Responde SOLO con el resumen, sin preámbulos ni explicaciones."
                ),
                label="Resumen",
            )

        if action == "translate":
            target = params.get("target_lang", "inglés").strip()
            return self._smart_action(
                system_prompt=(
                    f"Eres un traductor experto. Traduce el siguiente texto al {target}. "
                    "Responde SOLO con la traducción, sin preámbulos ni notas."
                ),
                label=f"Traducción al {target}",
            )

        if action == "fix":
            return self._smart_action(
                system_prompt=(
                    "Eres un corrector de estilo. Corrige la ortografía, gramática y puntuación "
                    "del siguiente texto sin cambiar su significado ni su tono. "
                    "Responde SOLO con el texto corregido, sin explicaciones ni marcas de cambio."
                ),
                label="Texto corregido",
            )

        if action == "explain":
            return self._smart_action(
                system_prompt=(
                    "Eres un experto que explica conceptos de forma clara y accesible. "
                    "Explica el siguiente texto o concepto en español de manera simple, "
                    "como si se lo explicaras a alguien inteligente pero sin conocimientos previos. "
                    "Sé directo y concreto."
                ),
                label="Explicación",
            )

        return ToolResult.fail(
            f"Acción desconocida: '{action}'. "
            "Opciones: get, set, clear, summarize, translate, fix, explain."
        )

    # ── Acciones básicas ─────────────────────────────────────────

    def _get(self) -> ToolResult:
        try:
            content = _read_clipboard()
            if not content:
                return ToolResult.ok("El portapapeles está vacío.")
            preview = content[:500] + ("..." if len(content) > 500 else "")
            return ToolResult.ok(f"Portapapeles ({len(content)} caracteres):\n{preview}")
        except Exception as e:
            return ToolResult.fail(f"Error al leer el portapapeles: {e}")

    def _set(self, params: dict) -> ToolResult:
        text = params.get("text", "")
        if not text:
            return ToolResult.fail("Para action='set' debes proporcionar 'text'.")
        try:
            _write_clipboard(text)
            return ToolResult.ok(f"Texto copiado al portapapeles ({len(text)} caracteres).")
        except Exception as e:
            return ToolResult.fail(f"Error al escribir en el portapapeles: {e}")

    def _clear(self) -> ToolResult:
        try:
            _write_clipboard("")
            return ToolResult.ok("Portapapeles vaciado.")
        except Exception as e:
            return ToolResult.fail(f"Error al vaciar el portapapeles: {e}")

    # ── Acciones inteligentes ────────────────────────────────────

    def _smart_action(self, system_prompt: str, label: str) -> ToolResult:
        """Lee el portapapeles, lo procesa con el LLM y devuelve el resultado."""
        try:
            content = _read_clipboard()
        except Exception as e:
            return ToolResult.fail(f"Error al leer el portapapeles: {e}")

        if not content or not content.strip():
            return ToolResult.fail("El portapapeles está vacío. Copia un texto primero.")

        # Limitar a 4000 caracteres para no saturar el contexto del LLM
        text_to_process = content[:4000]
        if len(content) > 4000:
            text_to_process += "\n[Texto recortado — solo se procesaron los primeros 4000 caracteres]"

        try:
            result = _ask_llm(system_prompt, text_to_process)
        except RuntimeError as e:
            return ToolResult.fail(str(e))
        except Exception as e:
            return ToolResult.fail(f"Error al procesar con el LLM: {e}")

        if not result:
            return ToolResult.fail("El LLM no devolvió resultado.")

        return ToolResult.ok(f"{label}:\n\n{result}")