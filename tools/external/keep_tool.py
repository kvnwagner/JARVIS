"""
Tool: keep
Gestiona notas de Google Keep: crear, leer, buscar y agregar a listas.
Usa gkeepapi — sin API oficial, autenticación con cuenta Google.

Configuración en .env:
    GOOGLE_EMAIL=tu@gmail.com
    GOOGLE_APP_PASSWORD=xxxx xxxx xxxx xxxx  ← contraseña de aplicación, NO la de Gmail normal
    (Generar en: myaccount.google.com > Seguridad > Contraseñas de aplicaciones)

El token de sesión se guarda en .keep_cache para no pedir login cada vez.
"""
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from core.interfaces import Tool, ToolResult

load_dotenv()

logger = logging.getLogger("jarvis.keep")
CACHE_PATH = Path(".keep_cache")


def _get_keep():
    """
    Retorna una instancia autenticada de gkeepapi.Keep.
    Reutiliza el token del cache si existe, si no hace login completo.
    """
    try:
        import gkeepapi
    except ImportError:
        raise RuntimeError("gkeepapi no está instalado. Ejecuta: pip install gkeepapi")

    email    = os.getenv("GOOGLE_EMAIL", "").strip()
    password = os.getenv("GOOGLE_APP_PASSWORD", "").strip()

    if not email or not password:
        raise RuntimeError(
            "Faltan credenciales en el .env: GOOGLE_EMAIL y GOOGLE_APP_PASSWORD. "
            "Genera una contraseña de aplicación en myaccount.google.com > Seguridad > Contraseñas de aplicaciones."
        )

    keep = gkeepapi.Keep()

    # Intentar reanudar sesión con token cacheado
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            keep.resume(email, cache["token"], state=cache.get("state"))
            logger.debug("Google Keep: sesión reanudada desde cache")
            return keep
        except Exception as e:
            logger.warning("Cache de Keep inválido, reautenticando: %s", e)
            CACHE_PATH.unlink(missing_ok=True)

    # Login completo
    keep.login(email, password)

    # Guardar token para próximas sesiones
    try:
        cache = {"token": keep.getMasterToken(), "state": keep.dump()}
        CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    except Exception as e:
        logger.warning("No se pudo guardar el cache de Keep: %s", e)

    return keep


def _note_to_dict(note) -> dict:
    """Convierte un nodo de gkeepapi a dict serializable."""
    import gkeepapi
    result = {
        "id":    note.id,
        "title": note.title or "",
        "color": str(note.color).split(".")[-1].lower() if note.color else "white",
    }
    if isinstance(note, gkeepapi.node.List):
        items = [
            {"text": item.text, "checked": item.checked}
            for item in note.items
        ]
        result["type"]  = "list"
        result["items"] = items
    else:
        result["type"] = "note"
        result["text"] = note.text or ""
    return result


class KeepTool(Tool):
    name = "keep"
    description = (
        "Gestiona notas de Google Keep. "
        "Crea notas de texto o listas de verificación, lee notas existentes y busca por título o contenido. "
        "Úsalo cuando el usuario pida crear una nota, guardar algo en Keep, leer sus notas o hacer una lista."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create_note", "create_list", "list_notes", "search", "read"],
                "description": (
                    "'create_note' = crear nota de texto (requiere title y text), "
                    "'create_list' = crear lista de verificación (requiere title e items), "
                    "'list_notes' = ver las últimas notas, "
                    "'search' = buscar notas por palabra clave (requiere query), "
                    "'read' = leer el contenido de una nota específica (requiere query con el título)"
                )
            },
            "title": {
                "type": "string",
                "description": "Título de la nota a crear"
            },
            "text": {
                "type": "string",
                "description": "Contenido de la nota de texto"
            },
            "items": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Lista de elementos para una lista de verificación. Ej: ['leche', 'pan', 'huevos']"
            },
            "query": {
                "type": "string",
                "description": "Término de búsqueda o título de la nota a leer"
            }
        },
        "required": ["action"]
    }

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip().lower()

        try:
            keep = _get_keep()
        except RuntimeError as e:
            return ToolResult.fail(str(e))
        except Exception as e:
            return ToolResult.fail(f"Error al conectar con Google Keep: {e}")

        if action == "create_note":
            return self._create_note(keep, params)
        if action == "create_list":
            return self._create_list(keep, params)
        if action == "list_notes":
            return self._list_notes(keep)
        if action == "search":
            return self._search(keep, params)
        if action == "read":
            return self._read(keep, params)

        return ToolResult.fail(
            f"Acción desconocida: '{action}'. "
            "Opciones: create_note, create_list, list_notes, search, read."
        )

    # ── Acciones ─────────────────────────────────────────────────

    def _create_note(self, keep, params: dict) -> ToolResult:
        title = params.get("title", "").strip()
        text  = params.get("text", "").strip()

        if not title and not text:
            return ToolResult.fail("Debes indicar al menos un título o texto para la nota.")

        note = keep.createNote(title, text)
        keep.sync()

        return ToolResult.ok(
            f"Nota creada en Google Keep ✓\n"
            f"  Título: {title or '(sin título)'}\n"
            f"  Texto:  {text[:100] + '...' if len(text) > 100 else text}"
        )

    def _create_list(self, keep, params: dict) -> ToolResult:
        title = params.get("title", "").strip()
        items = params.get("items", [])

        if not title:
            return ToolResult.fail("Debes indicar un título para la lista.")
        if not items:
            return ToolResult.fail("Debes indicar los elementos de la lista (parámetro 'items').")

        # gkeepapi espera lista de tuplas (texto, checked)
        gnote = keep.createList(title, [(item, False) for item in items])
        keep.sync()

        items_str = "\n".join(f"  ☐ {item}" for item in items)
        return ToolResult.ok(
            f"Lista creada en Google Keep ✓\n"
            f"  Título: {title}\n"
            f"{items_str}"
        )

    def _list_notes(self, keep) -> ToolResult:
        keep.sync()
        notes = list(keep.all())

        if not notes:
            return ToolResult.ok("No tienes notas en Google Keep.")

        # Mostrar las últimas 8
        recent = notes[:8]
        lines  = [f"📝 Notas en Google Keep ({len(notes)} total):\n"]
        for n in recent:
            d = _note_to_dict(n)
            if d["type"] == "list":
                count  = len(d["items"])
                done   = sum(1 for i in d["items"] if i["checked"])
                lines.append(f"  [{d['type']}] {d['title'] or '(sin título)'} — {done}/{count} completados")
            else:
                preview = d["text"][:60] + "..." if len(d["text"]) > 60 else d["text"]
                lines.append(f"  [nota] {d['title'] or '(sin título)'} — {preview}")

        return ToolResult.ok("\n".join(lines))

    def _search(self, keep, params: dict) -> ToolResult:
        query = params.get("query", "").strip()
        if not query:
            return ToolResult.fail("Debes indicar qué buscar.")

        keep.sync()
        query_lower = query.lower()
        results = []

        for note in keep.all():
            d = _note_to_dict(note)
            title_match = query_lower in d["title"].lower()
            if d["type"] == "list":
                content_match = any(query_lower in i["text"].lower() for i in d["items"])
            else:
                content_match = query_lower in d["text"].lower()

            if title_match or content_match:
                results.append(d)

        if not results:
            return ToolResult.ok(f"No se encontraron notas con '{query}'.")

        lines = [f"🔍 Notas que coinciden con '{query}':\n"]
        for d in results[:5]:
            if d["type"] == "list":
                items_preview = ", ".join(i["text"] for i in d["items"][:3])
                if len(d["items"]) > 3:
                    items_preview += f" (+{len(d['items'])-3} más)"
                lines.append(f"  [lista] {d['title']} → {items_preview}")
            else:
                preview = d["text"][:80] + "..." if len(d["text"]) > 80 else d["text"]
                lines.append(f"  [nota]  {d['title']} → {preview}")

        return ToolResult.ok("\n".join(lines))

    def _read(self, keep, params: dict) -> ToolResult:
        query = params.get("query", "").strip()
        if not query:
            return ToolResult.fail("Indica el título de la nota que quieres leer.")

        keep.sync()
        query_lower = query.lower()
        match = None

        for note in keep.all():
            if query_lower in note.title.lower():
                match = note
                break

        if not match:
            return ToolResult.ok(f"No se encontró ninguna nota con el título '{query}'.")

        d = _note_to_dict(match)
        if d["type"] == "list":
            lines = [f"📋 {d['title']}\n"]
            for item in d["items"]:
                check = "☑" if item["checked"] else "☐"
                lines.append(f"  {check} {item['text']}")
            return ToolResult.ok("\n".join(lines))
        else:
            return ToolResult.ok(f"📄 {d['title']}\n\n{d['text']}")