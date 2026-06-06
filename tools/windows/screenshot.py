"""
Tool: screenshot
Toma una captura de pantalla en Windows y la guarda en disco.
Requiere: pip install pillow
"""

import os
from datetime import datetime
from pathlib import Path
from core.interfaces import Tool, ToolResult

# Carpeta donde se guardan las capturas
SCREENSHOTS_DIR = Path("screenshots")


class ScreenshotTool(Tool):
    name = "screenshot"
    description = (
        "Toma una captura de pantalla de la pantalla actual de Windows. "
        "Guarda la imagen en la carpeta screenshots/. "
        "Úsalo cuando el usuario pida capturar, fotografiar o guardar lo que hay en pantalla."
    )
    parameters = {
        "type": "object",
        "properties": {
            "filename": {
                "type": "string",
                "description": (
                    "Nombre opcional del archivo sin extensión. "
                    "Si no se especifica, se usa la fecha y hora actual."
                )
            },
            "region": {
                "type": "object",
                "description": "Región específica a capturar (opcional). Omitir para pantalla completa.",
                "properties": {
                    "x": {"type": "integer", "description": "Coordenada X izquierda"},
                    "y": {"type": "integer", "description": "Coordenada Y superior"},
                    "width": {"type": "integer", "description": "Ancho en píxeles"},
                    "height": {"type": "integer", "description": "Alto en píxeles"}
                },
                "required": ["x", "y", "width", "height"]
            }
        }
    }

    def execute(self, params: dict) -> ToolResult:
        try:
            from PIL import ImageGrab
        except ImportError:
            return ToolResult.fail(
                "Pillow no está instalado. Ejecuta: pip install pillow"
            )

        # Preparar nombre de archivo
        filename = params.get("filename", "").strip()
        if not filename:
            filename = datetime.now().strftime("screenshot_%Y%m%d_%H%M%S")

        # Asegurar que la carpeta existe
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        filepath = SCREENSHOTS_DIR / f"{filename}.png"

        # Capturar región o pantalla completa
        region_params = params.get("region")
        try:
            if region_params:
                x = region_params["x"]
                y = region_params["y"]
                w = region_params["width"]
                h = region_params["height"]
                bbox = (x, y, x + w, y + h)
                img = ImageGrab.grab(bbox=bbox)
                area_desc = f"región ({x},{y}) {w}×{h}px"
            else:
                img = ImageGrab.grab()
                area_desc = "pantalla completa"

            img.save(str(filepath), "PNG")

            size_kb = filepath.stat().st_size // 1024
            return ToolResult.ok(
                f"Captura guardada: {filepath.resolve()} "
                f"({area_desc}, {img.width}×{img.height}px, {size_kb}KB)"
            )

        except Exception as e:
            return ToolResult.fail(f"Error al tomar la captura: {e}")
