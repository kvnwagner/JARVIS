"""
Home Assistant Tools
Controla dispositivos del hogar a través de la API de Home Assistant.
"""

import asyncio
from core.interfaces import Tool, ToolResult
from tools.home_assistant.ha_client import HomeAssistantClient

ha = HomeAssistantClient()


class ControlarLuzTool(Tool):
    name = "controlar_luz"
    description = (
        "Enciende o apaga una luz del hogar. "
        "Usa esto cuando el usuario pida encender, apagar o controlar una luz."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "entity_id": {
                "type": "string",
                "description": "ID de la luz en Home Assistant. Ej: 'light.salon', 'light.cocina'"
            },
            "action": {
                "type": "string",
                "description": "Acción a ejecutar: 'on' para encender, 'off' para apagar"
            },
            "brightness": {
                "type": "integer",
                "description": "Brillo de 0 a 255 (opcional, solo cuando action es 'on')"
            }
        },
        "required": ["entity_id", "action"]
    }

    def execute(self, params: dict) -> ToolResult:
        entity_id = params.get("entity_id", "").strip()
        action = params.get("action", "").strip()
        brightness = params.get("brightness", None)
        if not entity_id:
            return ToolResult.fail("No se especificó el entity_id de la luz.")
        if action not in ("on", "off"):
            return ToolResult.fail("La acción debe ser 'on' o 'off'.")
        try:
            service = "turn_on" if action == "on" else "turn_off"
            data = {"entity_id": entity_id}
            if brightness is not None and action == "on":
                data["brightness"] = brightness
            asyncio.run(ha.call_service("light", service, data))
            return ToolResult.ok(f"Luz '{entity_id}' → {action}")
        except Exception as e:
            return ToolResult.fail(f"Error al controlar luz: {e}")


class ControlarClimateTool(Tool):
    name = "controlar_clima"
    description = (
        "Controla el aire acondicionado o calefacción del hogar. "
        "Usa esto cuando el usuario pida cambiar la temperatura o el modo del clima."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "entity_id": {
                "type": "string",
                "description": "ID del clima. Ej: 'climate.sala'"
            },
            "temperature": {
                "type": "number",
                "description": "Temperatura deseada en grados. Ej: 22.0"
            },
            "mode": {
                "type": "string",
                "description": "Modo del clima: 'heat' para calentar, 'cool' para enfriar, 'off' para apagar"
            }
        },
        "required": ["entity_id"]
    }

    def execute(self, params: dict) -> ToolResult:
        entity_id = params.get("entity_id", "").strip()
        temperature = params.get("temperature", None)
        mode = params.get("mode", None)
        if not entity_id:
            return ToolResult.fail("No se especificó el entity_id del clima.")
        try:
            if mode:
                asyncio.run(ha.call_service("climate", "set_hvac_mode",
                            {"entity_id": entity_id, "hvac_mode": mode}))
            if temperature:
                asyncio.run(ha.call_service("climate", "set_temperature",
                            {"entity_id": entity_id, "temperature": temperature}))
            return ToolResult.ok(f"Clima '{entity_id}' actualizado correctamente.")
        except Exception as e:
            return ToolResult.fail(f"Error al controlar clima: {e}")


class ConsultarEstadoTool(Tool):
    name = "consultar_estado_hogar"
    description = (
        "Consulta el estado actual de cualquier dispositivo del hogar. "
        "Usa esto cuando el usuario pregunte por el estado de una luz, sensor, TV, etc."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "entity_id": {
                "type": "string",
                "description": "ID del dispositivo. Ej: 'light.salon', 'media_player.smart_tv'"
            }
        },
        "required": ["entity_id"]
    }

    def execute(self, params: dict) -> ToolResult:
        entity_id = params.get("entity_id", "").strip()
        if not entity_id:
            return ToolResult.fail("No se especificó el entity_id.")
        try:
            state = asyncio.run(ha.get_state(entity_id))
            return ToolResult.ok(
                f"{entity_id}: {state['state']} | "
                f"atributos: {state.get('attributes', {})}"
            )
        except Exception as e:
            return ToolResult.fail(f"Error al consultar estado: {e}")


class EjecutarEscenaTool(Tool):
    name = "ejecutar_escena"
    description = (
        "Activa una escena preconfigurada en el hogar. "
        "Usa esto cuando el usuario pida activar un modo como 'modo cine', 'buenas noches', etc."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "entity_id": {
                "type": "string",
                "description": "ID de la escena. Ej: 'scene.modo_cine'"
            }
        },
        "required": ["entity_id"]
    }

    def execute(self, params: dict) -> ToolResult:
        entity_id = params.get("entity_id", "").strip()
        if not entity_id:
            return ToolResult.fail("No se especificó el entity_id de la escena.")
        try:
            asyncio.run(ha.call_service("scene", "turn_on", {"entity_id": entity_id}))
            return ToolResult.ok(f"Escena '{entity_id}' activada correctamente.")
        except Exception as e:
            return ToolResult.fail(f"Error al ejecutar escena: {e}")


class ControlarTVTool(Tool):
    name = "controlar_tv"
    description = (
        "Controla el televisor Smart TV TCL. "
        "Usa esto cuando el usuario pida encender, apagar, subir volumen, "
        "bajar volumen, silenciar, pausar o reproducir el televisor."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "description": (
                    "Acción a ejecutar en el TV. Valores posibles: "
                    "'turn_on' encender, 'turn_off' apagar, "
                    "'volume_up' subir volumen, 'volume_down' bajar volumen, "
                    "'mute' silenciar, 'pause' pausar, 'play' reproducir"
                )
            }
        },
        "required": ["action"]
    }

    def execute(self, params: dict) -> ToolResult:
        action = params.get("action", "").strip()
        entity_id = "media_player.smart_tv"
        if not action:
            return ToolResult.fail("No se especificó ninguna acción.")
        try:
            if action in ("turn_on", "turn_off"):
                asyncio.run(ha.call_service("media_player", action, {"entity_id": entity_id}))
            elif action == "volume_up":
                asyncio.run(ha.call_service("media_player", "volume_up", {"entity_id": entity_id}))
            elif action == "volume_down":
                asyncio.run(ha.call_service("media_player", "volume_down", {"entity_id": entity_id}))
            elif action == "mute":
                asyncio.run(ha.call_service("media_player", "volume_mute",
                            {"entity_id": entity_id, "is_volume_muted": True}))
            elif action == "pause":
                asyncio.run(ha.call_service("media_player", "media_pause", {"entity_id": entity_id}))
            elif action == "play":
                asyncio.run(ha.call_service("media_player", "media_play", {"entity_id": entity_id}))
            return ToolResult.ok(f"TV → {action} ejecutado correctamente.")
        except Exception as e:
            return ToolResult.fail(f"Error al controlar el TV: {e}")