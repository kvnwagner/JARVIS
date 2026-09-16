"""
Tool: code
Permite a Jarvis leer, buscar, crear, editar (reemplazo de texto exacto) y
borrar archivos de código dentro de los proyectos de programación del
usuario, además de correr comandos permitidos (tests, scripts, git). El
objetivo es que Jarvis pueda ayudar a programar directamente desde el chat,
sin salir de la conversación.

Alcance: por defecto, la raíz del propio proyecto Jarvis (se detecta sola,
subiendo dos niveles desde este archivo) más cualquier carpeta declarada en
la variable de entorno JARVIS_CODE_ROOTS (rutas separadas por ';'), igual
que JARVIS_EXTRA_FILE_ROOTS en tools/filesystem/files_tool.py. Las carpetas
críticas del sistema (Windows, Program Files, ProgramData) están SIEMPRE
bloqueadas.

Ejemplo en .env:
    JARVIS_CODE_ROOTS=C:\\Users\\Wagne\\Downloads\\JARVIS;D:\\Proyectos\\texticode

Acciones destructivas:
- 'write' sobre un archivo que YA EXISTE requiere confirm=true. Si no se
  confirma, devuelve un diff de lo que habría cambiado.
- 'delete' siempre requiere confirm=true y solo borra archivos individuales
  (nunca carpetas completas).
- 'edit' exige que 'old_str' aparezca EXACTAMENTE una vez en el archivo —
  si no aparece o aparece varias veces, falla explicando por qué, en vez de
  adivinar y arriesgarse a romper el archivo.
- 'run' solo acepta comandos que empiecen con un binario de una lista
  blanca (python, pytest, pip, node, npm, npx, git).
"""

import difflib
import os
import subprocess
from pathlib import Path

from core.interfaces import Tool, ToolResult

# Raíz del proyecto Jarvis: .../tools/code/code_editor_tool.py -> subir 2 niveles
JARVIS_ROOT = Path(__file__).resolve().parents[2]

_extra_env = os.environ.get("JARVIS_CODE_ROOTS", "")
EXTRA_ROOTS = [Path(p.strip()) for p in _extra_env.split(";") if p.strip()]

CODE_ROOTS: list[Path] = [JARVIS_ROOT] + EXTRA_ROOTS

BLOCKED_ROOTS = [
    Path(os.environ.get("WINDIR", r"C:\Windows")),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    Path(os.environ.get("ProgramData", r"C:\ProgramData")),
]

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".html", ".css", ".scss",
    ".json", ".yaml", ".yml", ".md", ".txt", ".ini", ".cfg", ".toml", ".sql",
    ".sh", ".ps1", ".bat",
}

IGNORED_DIRS = {"__pycache__", "node_modules", ".git", "venv", ".venv", "dist", "build"}

MAX_READ_BYTES = 1_500_000
MAX_PREVIEW_CHARS = 8000
MAX_RESULTS = 30
MAX_LIST_RESULTS = 200
MAX_WALK_DEPTH = 6

# Comandos permitidos para action='run' — cualquier otro binario se rechaza.
ALLOWED_RUN_COMMANDS = {"python", "python3", "pytest", "pip", "node", "npm", "npx", "git"}
RUN_TIMEOUT_SECONDS = 120


def _existing_roots() -> list[Path]:
    return [r for r in CODE_ROOTS if r.exists()]


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


class CodeEditorTool(Tool):
    name = "code"
    description = (
        "Lee, busca, crea, edita y borra archivos de código dentro de los "
        "proyectos de programación del usuario (por defecto, el propio "
        "proyecto Jarvis y cualquier carpeta agregada en JARVIS_CODE_ROOTS), "
        "y puede correr tests o comandos permitidos. Úsalo cuando el usuario "
        "pida modificar un archivo de código, agregar o corregir una "
        "función, refactorizar, crear un archivo nuevo, buscar dónde está "
        "definida una función/clase/variable, o correr tests/scripts del "
        "proyecto. 'edit' reemplaza un fragmento EXACTO de texto por otro "
        "(como buscar y reemplazar); el fragmento debe aparecer una sola "
        "vez en el archivo. 'write' sobre un archivo que ya existe, y "
        "'delete', requieren confirm=true."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "read", "search", "write", "edit", "append", "delete", "run"],
                "description": (
                    "'list' = listar archivos de código en una carpeta (opcional 'path'), "
                    "'read' = leer un archivo con números de línea (requiere 'path'), "
                    "'search' = buscar texto dentro de los archivos del proyecto (requiere 'query', opcional 'path'), "
                    "'write' = crear o sobrescribir un archivo completo (requiere 'path' y 'content'), "
                    "'edit' = reemplazar un fragmento exacto de texto por otro (requiere 'path', 'old_str', 'new_str'), "
                    "'append' = agregar contenido al final del archivo (requiere 'path' y 'content'), "
                    "'delete' = eliminar un archivo (requiere 'path' y confirm=true), "
                    "'run' = ejecutar un comando permitido dentro del proyecto (requiere 'command')"
                )
            },
            "path": {
                "type": "string",
                "description": "Ruta del archivo o carpeta (relativa a la raíz del proyecto, o absoluta)"
            },
            "query": {"type": "string", "description": "Texto a buscar (action='search')"},
            "content": {
                "type": "string",
                "description": "Contenido completo del archivo (action='write') o texto a agregar (action='append')"
            },
            "old_str": {
                "type": "string",
                "description": "Fragmento exacto de texto a reemplazar (action='edit'). Debe aparecer una sola vez en el archivo."
            },
            "new_str": {
                "type": "string",
                "description": "Texto de reemplazo (action='edit'). Puede ir vacío para borrar el fragmento."
            },
            "command": {
                "type": "string",
                "description": "Comando a ejecutar (action='run'), ej: 'pytest tests/', 'python demo_memory.py', 'git status'"
            },
            "confirm": {
                "type": "boolean",
                "description": "Debe ser true para sobrescribir un archivo existente o para eliminarlo",
                "default": False
            },
        },
        "required": ["action"]
    }

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip().lower()

        if action == "list":
            return self._list(params.get("path", "").strip())
        if action == "read":
            return self._read(params.get("path", "").strip())
        if action == "search":
            return self._search(params.get("query", "").strip(), params.get("path", "").strip())
        if action == "write":
            return self._write(params)
        if action == "edit":
            return self._edit(params)
        if action == "append":
            return self._append(params)
        if action == "delete":
            return self._delete(params)
        if action == "run":
            return self._run(params)

        return ToolResult.fail(
            f"Acción desconocida: '{action}'. Opciones: list, read, search, write, edit, append, delete, run."
        )

    # ── Resolución de rutas ──────────────────────────────────

    def _resolve(self, raw_path: str) -> Path | None:
        if not raw_path:
            return None
        p = Path(raw_path)
        if p.is_absolute():
            return p
        # Relativa: probar contra cada raíz de proyecto conocida
        for root in _existing_roots():
            candidate = root / raw_path
            if candidate.exists():
                return candidate
        # Si no existe en ninguna raíz todavía (ej. archivo nuevo a crear),
        # se asume relativa a la primera raíz (el propio proyecto Jarvis).
        return CODE_ROOTS[0] / raw_path

    # ── list / search ────────────────────────────────────────

    def _list(self, raw_path: str) -> ToolResult:
        target = self._resolve(raw_path) if raw_path else CODE_ROOTS[0]
        if target is None or not target.exists():
            return ToolResult.fail(f"La carpeta '{raw_path or target}' no existe.")
        if not target.is_dir():
            return ToolResult.fail(f"'{target}' no es una carpeta.")
        if not _is_within_allowed(target):
            return ToolResult.fail("Esa carpeta está fuera del alcance permitido.")

        matches: list[Path] = []
        try:
            for dirpath, dirnames, filenames in os.walk(target):
                dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
                depth = len(Path(dirpath).relative_to(target).parts)
                if depth >= MAX_WALK_DEPTH:
                    dirnames[:] = []
                for fname in filenames:
                    if Path(fname).suffix.lower() in CODE_EXTENSIONS:
                        matches.append(Path(dirpath) / fname)
                        if len(matches) >= MAX_LIST_RESULTS:
                            break
                if len(matches) >= MAX_LIST_RESULTS:
                    break
        except Exception as e:
            return ToolResult.fail(f"Error al listar '{target}': {e}")

        if not matches:
            return ToolResult.ok(f"No se encontraron archivos de código en '{target}'.")

        lines = [f"📁 Archivos de código en '{target}' ({len(matches)}):\n"]
        for m in matches:
            rel = m.relative_to(target)
            lines.append(f"  {rel}")

        return ToolResult.ok("\n".join(lines))

    def _search(self, query: str, raw_path: str) -> ToolResult:
        if not query:
            return ToolResult.fail("Debes indicar qué texto buscar.")

        root = self._resolve(raw_path) if raw_path else CODE_ROOTS[0]
        if root is None or not root.exists():
            return ToolResult.fail(f"La carpeta '{raw_path or root}' no existe.")
        if not _is_within_allowed(root):
            return ToolResult.fail("Esa carpeta está fuera del alcance permitido.")

        query_lower = query.lower()
        results: list[str] = []

        try:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRS]
                for fname in filenames:
                    if Path(fname).suffix.lower() not in CODE_EXTENSIONS:
                        continue
                    fpath = Path(dirpath) / fname
                    try:
                        text = fpath.read_text(encoding="utf-8", errors="ignore")
                    except Exception:
                        continue
                    for i, line in enumerate(text.splitlines(), start=1):
                        if query_lower in line.lower():
                            rel = fpath.relative_to(root)
                            results.append(f"{rel}:{i}: {line.strip()}")
                            if len(results) >= MAX_RESULTS:
                                break
                    if len(results) >= MAX_RESULTS:
                        break
                if len(results) >= MAX_RESULTS:
                    break
        except Exception as e:
            return ToolResult.fail(f"Error al buscar: {e}")

        if not results:
            return ToolResult.ok(f"No se encontraron coincidencias para '{query}'.")

        suffix = "+" if len(results) >= MAX_RESULTS else ""
        header = f"🔍 Coincidencias para '{query}' ({len(results)}{suffix}):\n"
        return ToolResult.ok(header + "\n".join(results))

    # ── read ─────────────────────────────────────────────────

    def _read(self, raw_path: str) -> ToolResult:
        if not raw_path:
            return ToolResult.fail("Debes indicar la ruta del archivo a leer.")

        target = self._resolve(raw_path)
        if target is None or not target.exists():
            return ToolResult.fail(f"No se encontró el archivo '{raw_path}'.")
        if not target.is_file():
            return ToolResult.fail(f"'{raw_path}' no es un archivo.")
        if not _is_within_allowed(target):
            return ToolResult.fail("Esa ruta está fuera del alcance permitido.")

        try:
            size = target.stat().st_size
            if size > MAX_READ_BYTES:
                return ToolResult.fail(
                    f"El archivo es demasiado grande ({size // 1024} KB). "
                    f"Límite: {MAX_READ_BYTES // 1024} KB."
                )
            content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult.fail(f"Error al leer '{target}': {e}")

        numbered = "\n".join(
            f"{i + 1:>5}\t{line}" for i, line in enumerate(content.splitlines())
        )
        preview = numbered[:MAX_PREVIEW_CHARS]
        if len(numbered) > MAX_PREVIEW_CHARS:
            preview += "\n... (truncado)"

        return ToolResult.ok(f"📄 {target}\n\n{preview}")

    # ── write / edit / append / delete ──────────────────────

    def _write(self, params: dict) -> ToolResult:
        raw_path = params.get("path", "").strip()
        content = params.get("content", "")
        confirm = bool(params.get("confirm", False))

        if not raw_path:
            return ToolResult.fail("Debes indicar la ruta del archivo a escribir.")

        target = self._resolve(raw_path)
        check_target = target if target.exists() else target.parent
        if not _is_within_allowed(check_target):
            return ToolResult.fail("Esa ruta está fuera del alcance permitido.")

        if target.exists() and not confirm:
            try:
                old = target.read_text(encoding="utf-8", errors="replace")
            except Exception:
                old = ""
            diff = "\n".join(difflib.unified_diff(
                old.splitlines(), content.splitlines(),
                fromfile=str(target), tofile=str(target), lineterm=""
            ))
            preview = diff[:MAX_PREVIEW_CHARS] or "(sin diferencias detectadas)"
            return ToolResult.fail(
                "El archivo ya existe. Vuelve a pedirlo con confirm=true para "
                f"sobrescribirlo. Vista previa del cambio:\n{preview}"
            )

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            verbo = "sobrescrito" if confirm else "creado"
            return ToolResult.ok(f"✅ Archivo {verbo}: '{target}'.")
        except Exception as e:
            return ToolResult.fail(f"Error al escribir '{target}': {e}")

    def _edit(self, params: dict) -> ToolResult:
        raw_path = params.get("path", "").strip()
        old_str = params.get("old_str", "")
        new_str = params.get("new_str", "")

        if not raw_path:
            return ToolResult.fail("Debes indicar la ruta del archivo a editar.")
        if not old_str:
            return ToolResult.fail("Debes indicar 'old_str': el fragmento exacto a reemplazar.")

        target = self._resolve(raw_path)
        if target is None or not target.exists():
            return ToolResult.fail(f"No se encontró el archivo '{raw_path}'.")
        if not _is_within_allowed(target):
            return ToolResult.fail("Esa ruta está fuera del alcance permitido.")

        try:
            content = target.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return ToolResult.fail(f"Error al leer '{target}': {e}")

        count = content.count(old_str)
        if count == 0:
            return ToolResult.fail(
                "El fragmento indicado no aparece en el archivo. Revisa espacios, "
                "saltos de línea o indentación exactos."
            )
        if count > 1:
            return ToolResult.fail(
                f"El fragmento aparece {count} veces en el archivo. Agrega más "
                "contexto a 'old_str' para que sea único."
            )

        new_content = content.replace(old_str, new_str, 1)

        try:
            target.write_text(new_content, encoding="utf-8")
        except Exception as e:
            return ToolResult.fail(f"Error al escribir '{target}': {e}")

        diff = "\n".join(difflib.unified_diff(
            content.splitlines(), new_content.splitlines(),
            fromfile=str(target), tofile=str(target), lineterm=""
        ))
        preview = diff[:MAX_PREVIEW_CHARS] or "(sin diferencias detectadas)"
        return ToolResult.ok(f"✅ Editado '{target}':\n{preview}")

    def _append(self, params: dict) -> ToolResult:
        raw_path = params.get("path", "").strip()
        content = params.get("content", "")

        if not raw_path:
            return ToolResult.fail("Debes indicar la ruta del archivo.")
        if not content:
            return ToolResult.fail("Debes indicar 'content' con el texto a agregar.")

        target = self._resolve(raw_path)
        check_target = target if target.exists() else target.parent
        if not _is_within_allowed(check_target):
            return ToolResult.fail("Esa ruta está fuera del alcance permitido.")

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(target, "a", encoding="utf-8") as f:
                if target.exists() and target.stat().st_size > 0:
                    f.write("\n")
                f.write(content)
            return ToolResult.ok(f"✅ Contenido agregado a '{target}'.")
        except Exception as e:
            return ToolResult.fail(f"Error al escribir '{target}': {e}")

    def _delete(self, params: dict) -> ToolResult:
        raw_path = params.get("path", "").strip()
        if not params.get("confirm"):
            return ToolResult.fail(
                "Para eliminar un archivo, vuelve a pedirlo confirmando la acción (confirm=true)."
            )

        target = self._resolve(raw_path)
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

    # ── run (tests, scripts, git) ────────────────────────────

    def _run(self, params: dict) -> ToolResult:
        command = params.get("command", "").strip()
        raw_path = params.get("path", "").strip()

        if not command:
            return ToolResult.fail("Debes indicar el comando a ejecutar.")

        first_word = command.split()[0].lower()
        if first_word not in ALLOWED_RUN_COMMANDS:
            return ToolResult.fail(
                f"Comando no permitido: '{first_word}'. Permitidos: "
                f"{', '.join(sorted(ALLOWED_RUN_COMMANDS))}."
            )

        cwd = self._resolve(raw_path) if raw_path else CODE_ROOTS[0]
        if cwd is None or not cwd.exists() or not _is_within_allowed(cwd):
            cwd = CODE_ROOTS[0]

        try:
            result = subprocess.run(
                command,
                cwd=str(cwd),
                shell=True,
                capture_output=True,
                text=True,
                timeout=RUN_TIMEOUT_SECONDS,
            )
            output = (result.stdout or "") + (result.stderr or "")
            output = output[:MAX_PREVIEW_CHARS] or "(sin salida)"
            status = "✅" if result.returncode == 0 else f"⚠️ (código {result.returncode})"
            return ToolResult.ok(f"{status} `{command}` en '{cwd}':\n{output}")
        except subprocess.TimeoutExpired:
            return ToolResult.fail(f"El comando '{command}' tardó demasiado (>{RUN_TIMEOUT_SECONDS}s).")
        except Exception as e:
            return ToolResult.fail(f"Error al ejecutar '{command}': {e}")