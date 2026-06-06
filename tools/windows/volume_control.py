"""
Tool: volume_control
Controla el volumen del sistema en Windows usando pycaw.
Requiere: pip install pycaw comtypes
"""

from core.interfaces import Tool, ToolResult


def _get_vol():
    """Retorna el objeto EndpointVolume de pycaw (API >= 20231023)."""
    from pycaw.pycaw import AudioUtilities
    device = AudioUtilities.GetSpeakers()
    return device.EndpointVolume


class VolumeControlTool(Tool):
    name = "volume_control"
    description = (
        "Controla el volumen del sistema Windows. "
        "Puede subir, bajar, silenciar o establecer un nivel exacto. "
        "Úsalo cuando el usuario pida cambiar el volumen, silenciar o aumentar el sonido."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["set", "up", "down", "mute", "unmute", "get"],
                "description": (
                    "'set' = nivel exacto (requiere 'level'), "
                    "'up' = subir (requiere 'step'), "
                    "'down' = bajar (requiere 'step'), "
                    "'mute' = silenciar, "
                    "'unmute' = quitar silencio, "
                    "'get' = consultar nivel actual"
                )
            },
            "level": {
                "type": "integer",
                "minimum": 0,
                "maximum": 100,
                "description": "Nivel de volumen del 0 al 100 (solo para action='set')"
            },
            "step": {
                "type": "integer",
                "minimum": 1,
                "maximum": 50,
                "default": 10,
                "description": "Cuánto subir o bajar el volumen (solo para action='up'/'down')"
            }
        },
        "required": ["action"]
    }

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip().lower()
        level  = params.get("level", None)
        step   = params.get("step", 10)

        try:
            vol = _get_vol()

            if action == "get":
                current = round(vol.GetMasterVolumeLevelScalar() * 100)
                return ToolResult.ok(f"Volumen actual: {current}%")

            if action == "set":
                if level is None:
                    return ToolResult.fail("Para action='set' debes proporcionar 'level' (0-100).")
                level = max(0, min(100, level))
                vol.SetMasterVolumeLevelScalar(level / 100.0, None)
                return ToolResult.ok(f"Volumen establecido a {level}%.")

            if action in ("up", "down"):
                current = round(vol.GetMasterVolumeLevelScalar() * 100)
                new_level = current + step if action == "up" else current - step
                new_level = max(0, min(100, new_level))
                vol.SetMasterVolumeLevelScalar(new_level / 100.0, None)
                direction = "subido" if action == "up" else "bajado"
                return ToolResult.ok(f"Volumen {direction} a {new_level}% (era {current}%).")

            if action == "mute":
                vol.SetMute(1, None)
                return ToolResult.ok("Sistema silenciado.")

            if action == "unmute":
                vol.SetMute(0, None)
                return ToolResult.ok("Silencio desactivado.")

            return ToolResult.fail(
                f"Acción desconocida: '{action}'. Opciones: set, up, down, mute, unmute, get."
            )

        except ImportError:
            return ToolResult.fail("pycaw no está instalado. Ejecuta: pip install pycaw comtypes")
        except Exception as e:
            return ToolResult.fail(f"Error al controlar el volumen: {e}")