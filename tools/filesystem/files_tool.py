"""
Tool: files
Busca, lista, lee (texto/Word/PDF), crea, escribe, mueve, elimina y abre
archivos y carpetas del usuario.

Alcance por defecto: Escritorio, Documentos, Descargas, Imágenes (y
variantes de OneDrive). Para ampliarlo sin tocar código, define la variable
de entorno JARVIS_EXTRA_FILE_ROOTS con rutas separadas por ';', ej:
    JARVIS_EXTRA_FILE_ROOTS=D:\Proyectos;E:\Backups

Carpetas críticas del sistema (Windows, Program Files, ProgramData) están
SIEMPRE bloqueadas, incluso si las agregas ahí — para que ampliar el acceso
a tus propias carpetas no abra la puerta a que Jarvis toque el sistema.

Las acciones destructivas ('delete' y 'move') exigen confirm=true en los
parámetros. Esto no es para desconfiar de ti — es para que una mala
interpretación del LLM ("borra esto" mal entendido) no ejecute un delete
sin que la intención haya quedado explícita en la misma llamada.
"""

import os
import shutil
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

_extra_env = os.environ.get("JARVIS_EXTRA_FILE_ROOTS", "")
EXTRA_ROOTS = [Path(p.strip()) for p in _extra_env.split(";") if p.strip()]

BLOCKED_ROOTS = [
    Path(os.environ.get("WINDIR", r"C:\Windows")),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    Path(os.environ.get("ProgramData", r"C:\ProgramData")),
]

TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".log", ".py", ".js", ".ts",
    ".html", ".css", ".yaml", ".yml", ".xml", ".ini", ".cfg",
}
DOCX_EXTENSIONS = {".docx"}
PDF_EXTENSIONS = {".pdf"}

MAX_READ_BYTES = 2_000_000     # 2 MB (antes 200 KB)
MAX_PREVIEW_CHARS = 6000       # límite de lo que se le manda al LLM, no del archivo
MAX_RESULTS = 20
MAX_WALK_DEPTH = 3


def _all_roots() -> list[Path]:
    return SEARCH_ROOTS + EXTRA_ROOTS


def _existing_roots() -> list[Path]:
    return [r for r in _all_roots() if r.exists()]


def _is_blocked(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except Exception:
        return True
    return any(
        str(resolved).lower().startswith(str(b.resolve()).lower())
        for b in BLOCKED_ROOTS if b.exists()
    )


def _is_within_allowed(path: Path) -> bool:
    if _is_blocked(path):
        return False
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
        "Gestiona archivos y carpetas del usuario: buscar, listar, leer "
        "(texto, Word .docx y PDF), crear/escribir texto, mover/renombrar, "
        "eliminar y abrir con la app predeterminada de Windows. Opera dentro "
        "de las carpetas personales del usuario salvo que se hayan agregado "
        "rutas extra. 'delete' y 'move' requieren confirm=true."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "list", "read", "write", "delete", "move", "open"],
                "description": (
                    "'search' = buscar por nombre (requiere 'query'), "
                    "'list' = listar carpeta (opcional 'path'), "
                    "'read' = leer texto/Word/PDF (requiere 'path'), "
                    "'write' = crear o sobrescribir texto (requiere 'path' y 'content'), "
                    "'delete' = eliminar archivo (requiere 'path' y confirm=true), "
                    "'move' = mover/renombrar (requiere 'path', 'destination' y confirm=true), "
                    "'open' = abrir con la app predeterminada (requiere 'path')"
                )
            },
            "query": {"type": "string", "description": "Texto a buscar (action=search)"},
            "path": {"type": "string", "description": "Ruta del archivo o carpeta"},
            "destination": {"type": "string", "description": "Ruta destino (action=move)"},
            "content": {"type": "string", "description": "Contenido a escribir (action=write)"},
            "append": {
                "type": "boolean",
                "description": "Si es true, agrega al final en vez de sobrescribir (action=write)",
                "default": False
            },
            "confirm": {
                "type": "boolean",
                "description": "Debe ser true para ejecutar delete o move",
                "default": False
            },
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
        if action == "write":
            return self._write(params)
        if action == "delete":
            return self._delete(params)
        if action == "move":
            return self._move(params)
        if action == "open":
            return self._open(params.get("path", "").strip())

        return ToolResult.fail(f"Acción desconocida: '{action}'.")

    def _resolve_target(self, raw_path: str) -> Path | None:
        if not raw_path:
            return None
        p = Path(raw_path)
        if not p.is_absolute():
            p = HOME / raw_path
        return p

    # ── search / list ────────────────────────────────────────

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
            return ToolResult.fail("Esa carpeta está fuera del alcance permitido.")

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

    # ── read (texto / docx / pdf) ───────────────────────────

    def _read(self, raw_path: str) -> ToolResult:
        if not raw_path:
            return ToolResult.fail("Debes indicar la ruta del archivo a leer.")

        target = self._resolve_target(raw_path)
        if target is None or not target.exists():
            return ToolResult.fail(f"No se encontró el archivo '{raw_path}'.")
        if not target.is_file():
            return ToolResult.fail(f"'{raw_path}' no es un archivo.")
        if not _is_within_allowed(target):
            return ToolResult.fail("Esa ruta está fuera del alcance permitido.")

        suffix = target.suffix.lower()
        try:
            size = target.stat().st_size
            if size > MAX_READ_BYTES:
                return ToolResult.fail(
                    f"El archivo es demasiado grande ({size // 1024} KB). "
                    f"Límite: {MAX_READ_BYTES // 1024} KB."
                )

            if suffix in TEXT_EXTENSIONS:
                content = target.read_text(encoding="utf-8", errors="replace")
            elif suffix in DOCX_EXTENSIONS:
                content = self._extract_docx(target)
            elif suffix in PDF_EXTENSIONS:
                content = self._extract_pdf(target)
            else:
                return ToolResult.fail(
                    f"No sé leer archivos '{suffix}'. Soportados: texto plano, .docx, .pdf."
                )

            preview = content[:MAX_PREVIEW_CHARS]
            if len(content) > MAX_PREVIEW_CHARS:
                preview += "\n... (truncado)"

            return ToolResult.ok(f"📄 {target.name}\n\n{preview}")
        except ImportError as e:
            return ToolResult.fail(str(e))
        except Exception as e:
            return ToolResult.fail(f"Error al leer '{target}': {e}")

    def _extract_docx(self, path: Path) -> str:
        try:
            import docx
        except ImportError:
            raise ImportError("Falta python-docx. Ejecuta: pip install python-docx")
        document = docx.Document(str(path))
        return "\n".join(p.text for p in document.paragraphs)

    def _extract_pdf(self, path: Path) -> str:
        try:
            from pypdf import PdfReader
        except ImportError:
            raise ImportError("Falta pypdf. Ejecuta: pip install pypdf")
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    # ── write / delete / move / open ────────────────────────

    def _write(self, params: dict) -> ToolResult:
        raw_path = params.get("path", "").strip()
        content = params.get("content", "")
        append = bool(params.get("append", False))

        if not raw_path:
            return ToolResult.fail("Debes indicar la ruta del archivo a escribir.")

        target = self._resolve_target(raw_path)
        if target.suffix.lower() not in TEXT_EXTENSIONS:
            return ToolResult.fail("Solo puedo crear/escribir archivos de texto plano.")
        if not _is_within_allowed(target if target.exists() else target.parent):
            return ToolResult.fail("Esa ruta está fuera del alcance permitido.")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            mode = "a" if append else "w"
            with open(target, mode, encoding="utf-8") as f:
                f.write(content)
            verbo = "agregado a" if append else "escrito en"
            return ToolResult.ok(f"✅ Contenido {verbo} '{target}'.")
        except Exception as e:
            return ToolResult.fail(f"Error al escribir '{target}': {e}")

    def _delete(self, params: dict) -> ToolResult:
        raw_path = params.get("path", "").strip()
        if not params.get("confirm"):
            return ToolResult.fail("Para eliminar un archivo, vuelve a pedirlo confirmando la acción.")

        target = self._resolve_target(raw_path)
        if target is None or not target.exists():
            return ToolResult.fail(f"No se encontró '{raw_path}'.")
        if not _is_within_allowed(target):
            return ToolResult.fail("Esa ruta está fuera del alcance permitido.")
        if target.is_dir():
            return ToolResult.fail("Por seguridad no elimino carpetas completas, solo archivos individuales.")

        try:
            target.unlink()
            return ToolResult.ok(f"🗑️ Archivo eliminado: '{target}'.")
        except Exception as e:
            return ToolResult.fail(f"Error al eliminar '{target}': {e}")

    def _move(self, params: dict) -> ToolResult:
        raw_path = params.get("path", "").strip()
        raw_dest = params.get("destination", "").strip()
        if not params.get("confirm"):
            return ToolResult.fail("Para mover o renombrar, vuelve a pedirlo confirmando la acción.")

        source = self._resolve_target(raw_path)
        dest = self._resolve_target(raw_dest)
        if not source or not source.exists():
            return ToolResult.fail(f"No se encontró '{raw_path}'.")
        if dest is None:
            return ToolResult.fail("Debes indicar el destino.")
        if not _is_within_allowed(source) or not _is_within_allowed(dest.parent):
            return ToolResult.fail("Origen o destino están fuera del alcance permitido.")

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(dest))
            return ToolResult.ok(f"📦 Movido: '{source}' → '{dest}'.")
        except Exception as e:
            return ToolResult.fail(f"Error al mover '{source}': {e}")

    def _open(self, raw_path: str) -> ToolResult:
        if not raw_path:
            return ToolResult.fail("Debes indicar qué archivo abrir.")

        target = self._resolve_target(raw_path)
        if not target or not target.exists():
            return ToolResult.fail(f"No se encontró '{raw_path}'.")
        if not _is_within_allowed(target):
            return ToolResult.fail("Esa ruta está fuera del alcance permitido.")

        try:
            os.startfile(str(target))
            return ToolResult.ok(f"Abriendo '{target.name}' con la aplicación predeterminada.")
        except Exception as e:
            return ToolResult.fail(f"Error al abrir '{target}': {e}")