"""
Tool: recientes
Consulta los documentos y archivos abiertos más recientemente en Windows
(carpeta shell:Recent — accesos directos .lnk que Windows crea automáticamente
cada vez que abres un archivo desde el Explorador o una aplicación).
"""

import os
from pathlib import Path
from datetime import datetime
from core.interfaces import Tool, ToolResult

RECENT_DIR = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Recent"


def _resolve_shortcut_target(lnk_path: Path) -> str | None:
    """Resuelve el destino real de un .lnk usando pywin32 (si está disponible)."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(str(lnk_path))
        return shortcut.Targetpath or None
    except Exception:
        return None


class RecentFilesTool(Tool):
    name = "recientes"
    description = (
        "Consulta los archivos y documentos abiertos más recientemente en "
        "Windows (Word, Excel, PDFs, carpetas, etc., sin importar la app). "
        "Úsalo cuando el usuario pregunte qué documento abrió último, qué "
        "archivos ha usado recientemente, o pida reabrir algo reciente."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Cuántos archivos recientes devolver (por defecto 15)",
                "default": 15
            },
            "query": {
                "type": "string",
                "description": "Palabra clave opcional para filtrar por nombre"
            }
        },
        "required": []
    }

    def execute(self, params: dict) -> ToolResult:
        limit = params.get("limit") or 15
        query = params.get("query", "").strip().lower()

        if not RECENT_DIR.exists():
            return ToolResult.fail("No se encontró la carpeta de recientes de Windows.")

        try:
            entries = [p for p in RECENT_DIR.iterdir() if p.suffix.lower() == ".lnk"]
        except Exception as e:
            return ToolResult.fail(f"Error al leer recientes: {e}")

        if query:
            entries = [e for e in entries if query in e.stem.lower()]

        entries.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        entries = entries[:limit]

        if not entries:
            return ToolResult.ok("No se encontraron archivos recientes que coincidan.")

        lines = [f"🕘 Archivos recientes ({len(entries)}):\n"]
        for e in entries:
            mtime = datetime.fromtimestamp(e.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            target = _resolve_shortcut_target(e)
            display = target if target else e.stem
            lines.append(f"  {e.stem} — {display}  ({mtime})")

        return ToolResult.ok("\n".join(lines))