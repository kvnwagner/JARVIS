"""
Tool: browser_history
Consulta el historial de navegación reciente de Chrome o Edge en Windows.

Cómo funciona: el archivo History de cada navegador es una base SQLite que
Chrome/Edge mantienen abierta mientras corren. Para no interferir (ni fallar
por el bloqueo del archivo), esta tool COPIA el archivo a una ruta temporal
antes de leerlo. Si el navegador tiene el archivo bloqueado de forma
exclusiva, la copia puede fallar — en ese caso, cerrar el navegador soluciona
el problema.

No se tocan pestañas abiertas (eso requeriría habilitar el protocolo de
depuración remota del navegador, que es un paso aparte y más invasivo).
"""

import os
import shutil
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from core.interfaces import Tool, ToolResult

LOCALAPPDATA = os.environ.get("LOCALAPPDATA", "")

BROWSER_PATHS: dict[str, Path] = {
    "chrome": Path(LOCALAPPDATA) / "Google" / "Chrome" / "User Data" / "Default" / "History",
    "edge":   Path(LOCALAPPDATA) / "Microsoft" / "Edge" / "User Data" / "Default" / "History",
}

# Chrome/Edge guardan las fechas como microsegundos desde 1601-01-01 (época de Windows)
CHROME_EPOCH = datetime(1601, 1, 1)


def _chrome_time_to_datetime(chrome_time: int) -> datetime | None:
    if not chrome_time:
        return None
    try:
        return CHROME_EPOCH + timedelta(microseconds=chrome_time)
    except OverflowError:
        return None


def _copy_history_db(source: Path, tag: str) -> Path | None:
    if not source.exists():
        return None
    tmp = Path(tempfile.gettempdir()) / f"jarvis_history_{tag}.db"
    try:
        shutil.copy2(source, tmp)
        return tmp
    except Exception:
        return None


class BrowserHistoryTool(Tool):
    name = "browser_history"
    description = (
        "Consulta el historial de navegación reciente de Chrome o Edge. "
        "Usa esto cuando el usuario pregunte qué páginas visitó, busque un "
        "sitio que vio antes, o pida su historial de navegación. "
        "Puede fallar si el navegador tiene el archivo de historial bloqueado; "
        "en ese caso sugiere cerrar el navegador e intentar de nuevo."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "browser": {
                "type": "string",
                "enum": ["chrome", "edge"],
                "description": "Navegador a consultar. Si se omite, revisa ambos.",
            },
            "query": {
                "type": "string",
                "description": "Palabra clave para filtrar por título o URL (opcional)"
            },
            "limit": {
                "type": "integer",
                "description": "Cuántos resultados devolver (por defecto 15)",
                "default": 15
            }
        },
        "required": []
    }

    def execute(self, params: dict) -> ToolResult:
        browser = params.get("browser", "").strip().lower()
        query = params.get("query", "").strip()
        limit = params.get("limit") or 15

        browsers_to_check = [browser] if browser in BROWSER_PATHS else list(BROWSER_PATHS.keys())

        all_results: list[dict] = []
        errors: list[str] = []

        for name in browsers_to_check:
            source = BROWSER_PATHS.get(name)
            if not source:
                continue

            tmp_db = _copy_history_db(source, name)
            if not tmp_db:
                errors.append(f"{name}: historial no encontrado o bloqueado")
                continue

            try:
                conn = sqlite3.connect(tmp_db)
                conn.row_factory = sqlite3.Row

                sql = "SELECT url, title, last_visit_time FROM urls"
                args: tuple = ()
                if query:
                    sql += " WHERE url LIKE ? OR title LIKE ?"
                    args = (f"%{query}%", f"%{query}%")
                sql += " ORDER BY last_visit_time DESC LIMIT ?"
                args = args + (limit,)

                rows = conn.execute(sql, args).fetchall()
                conn.close()

                for r in rows:
                    visited = _chrome_time_to_datetime(r["last_visit_time"])
                    all_results.append({
                        "browser": name,
                        "title": r["title"] or "(sin título)",
                        "url": r["url"],
                        "visited": visited.strftime("%Y-%m-%d %H:%M") if visited else "",
                        "sort_key": r["last_visit_time"] or 0,
                    })
            except Exception as e:
                errors.append(f"{name}: {e}")
            finally:
                try:
                    tmp_db.unlink(missing_ok=True)
                except Exception:
                    pass

        if not all_results:
            if errors:
                return ToolResult.fail(
                    "No se pudo leer el historial (" + "; ".join(errors) + "). "
                    "Si el navegador está abierto, ciérralo e intenta de nuevo."
                )
            return ToolResult.ok("No se encontraron resultados en el historial.")

        all_results.sort(key=lambda r: r["sort_key"], reverse=True)
        all_results = all_results[:limit]

        lines = ["🌐 Historial de navegación:\n"]
        for r in all_results:
            lines.append(f"  [{r['browser']}] {r['title']} — {r['url']} ({r['visited']})")

        return ToolResult.ok("\n".join(lines))