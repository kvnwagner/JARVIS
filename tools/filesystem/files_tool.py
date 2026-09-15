"""
Tool: files
Busca, lista y lee archivos y carpetas personales del usuario.

Por seguridad SIEMPRE restringe:
  - Búsqueda y listado a carpetas personales típicas (Escritorio, Documentos,
    Descargas, Imágenes, incluyendo variantes de OneDrive).
  - Lectura a archivos de texto pequeños (<200 KB) dentro de esas mismas carpetas.
No puede leer archivos del sistema, ejecutables ni nada fuera de esas rutas.
"""

import os
from pathlib import Path
from core.interfaces import Tool, ToolResult

HOME = Path.home()

SEARCH_ROOTS = [
    HOME / "Desktop",
    HOME / "Documents",
    HOME / "Downloads",
    HOME / "Pictures",
    HOME / "OneDrive" / "Desktop",
    HOME / "OneDrive" / "Documents",
]

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".log", ".py", ".js", ".ts",
    ".html", ".css", ".yaml", ".yml", ".xml", ".ini", ".cfg",
}

MAX_READ_BYTES = 200_000
MAX_PREVIEW_CHARS = 3000
MAX_RESULTS = 20
MAX_WALK_DEPTH = 3


def _existing_roots() -> list[Path]:
    return [r for r in SEARCH_ROOTS if r.exists()]


def _is_within_allowed(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        return False
    return any(
        str(resolved).lower().startswith(str(root.resolve()).lower())
        for root in _existing_roots()
    )


class FilesTool(Tool):
    name = "files"
    description = (
        "Busca, lista o lee archivos y carpetas personales del usuario "
        "(Escritorio, Documentos, Descargas, Imágenes). "
        "Usa action=search para encontrar un archivo por nombre, "
        "action=list para ver el contenido de una carpeta, "
        "action=read para leer el contenido de un documento de texto. "
        "Úsalo cuando el usuario pida buscar un archivo, ver qué hay en una "
        "carpeta, o leer el contenido de un documento."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "list", "read"],
                "description": (
                    "'search' = buscar archivo por nombre (requiere 'query'), "
                    "'list' = listar contenido de una carpeta (opcional 'path', "
                    "por defecto el Escritorio), "
                    "'read' = leer un archivo de texto (requiere 'path')"
                )
            },
            "query": {
                "type": "string",
                "description": "Nombre o parte del nombre del archivo a buscar"
            },
            "path": {
                "type": "string",
                "description": (
                    "Ruta de la carpeta a listar o del archivo a leer, relativa "
                    "a la carpeta personal del usuario. Ej: 'Documents/notas.txt'"
                )
            }
        },
        "required": ["action"]
    }

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip().lower()

        if action == "search":
            return self._search(params.get("query", "").strip())
        if action == "list":
            return self._list(params.get("path", "").strip())
        if action == "read":
            return self._read(params.get("path", "").strip())

        return ToolResult.fail(f"Acción desconocida: '{action}'. Usa search, list o read.")

    def _resolve_target(self, raw_path: str) -> Path | None:
        if not raw_path:
            return None
        p = Path(raw_path)
        if not p.is_absolute():
            p = HOME / raw_path
        return p

    def _search(self, query: str) -> ToolResult:
        if not query:
            return ToolResult.fail("Debes indicar qué archivo buscar.")

        query_lower = query.lower()
        matches: list[Path] = []

        for root in _existing_roots():
            try:
                for dirpath, dirnames, filenames in os.walk(root):
                    depth = len(Path(dirpath).relative_to(root).parts)
                    if depth >= MAX_WALK_DEPTH:
                        dirnames[:] = []
                    for fname in filenames:
                        if query_lower in fname.lower():
                            matches.append(Path(dirpath) / fname)
                            if len(matches) >= MAX_RESULTS:
                                break
                    if len(matches) >= MAX_RESULTS:
                        break
            except Exception:
                continue
            if len(matches) >= MAX_RESULTS:
                break

        if not matches:
            return ToolResult.fail(f"No se encontraron archivos que coincidan con '{query}'.")

        lines = [f"🔍 Archivos encontrados para '{query}':\n"]
        for m in matches:
            try:
                size_kb = m.stat().st_size // 1024
                lines.append(f"  {m} ({size_kb} KB)")
            except Exception:
                lines.append(f"  {m}")

        return ToolResult.ok("\n".join(lines))

    def _list(self, raw_path: str) -> ToolResult:
        target = self._resolve_target(raw_path) if raw_path else (HOME / "Desktop")
        if target is None:
            return ToolResult.fail("Ruta inválida.")
        if not target.exists():
            return ToolResult.fail(f"La carpeta '{target}' no existe.")
        if not target.is_dir():
            return ToolResult.fail(f"'{target}' no es una carpeta.")
        if not _is_within_allowed(target):
            return ToolResult.fail(
                "Solo puedo listar carpetas personales (Escritorio, Documentos, "
                "Descargas, Imágenes)."
            )

        try:
            entries = sorted(target.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        except Exception as e:
            return ToolResult.fail(f"Error al listar '{target}': {e}")

        if not entries:
            return ToolResult.ok(f"La carpeta '{target.name}' está vacía.")

        lines = [f"📁 Contenido de '{target}':\n"]
        for e in entries[:50]:
            icon = "📁" if e.is_dir() else "📄"
            lines.append(f"  {icon} {e.name}")

        return ToolResult.ok("\n".join(lines))

    def _read(self, raw_path: str) -> ToolResult:
        if not raw_path:
            return ToolResult.fail("Debes indicar la ruta del archivo a leer.")

        target = self._resolve_target(raw_path)
        if target is None or not target.exists():
            return ToolResult.fail(f"No se encontró el archivo '{raw_path}'.")
        if not target.is_file():
            return ToolResult.fail(f"'{raw_path}' no es un archivo.")
        if not _is_within_allowed(target):
            return ToolResult.fail(
                "Solo puedo leer archivos dentro de carpetas personales "
                "(Escritorio, Documentos, Descargas, Imágenes)."
            )
        if target.suffix.lower() not in TEXT_EXTENSIONS:
            return ToolResult.fail(
                f"Solo puedo leer archivos de texto ({', '.join(sorted(TEXT_EXTENSIONS))})."
            )

        try:
            size = target.stat().st_size
            if size > MAX_READ_BYTES:
                return ToolResult.fail(
                    f"El archivo es demasiado grande ({size // 1024} KB). "
                    f"Límite: {MAX_READ_BYTES // 1024} KB."
                )

            content = target.read_text(encoding="utf-8", errors="replace")
            preview = content[:MAX_PREVIEW_CHARS]
            if len(content) > MAX_PREVIEW_CHARS:
                preview += "\n... (truncado)"

            return ToolResult.ok(f"📄 {target.name}\n\n{preview}")
        except Exception as e:
            return ToolResult.fail(f"Error al leer '{target}': {e}")