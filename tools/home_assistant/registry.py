"""
Tool Registry para Home Assistant Tools.
"""

from tools.home_assistant.ha_tools import (
    ControlarLuzTool,
    ControlarClimateTool,
    ConsultarEstadoTool,
    EjecutarEscenaTool,
    ControlarTVTool,
)

HA_TOOLS = [
    ControlarLuzTool(),
    ControlarClimateTool(),
    ConsultarEstadoTool(),
    EjecutarEscenaTool(),
    ControlarTVTool(),
]

HA_TOOLS_MAP = {tool.name: tool for tool in HA_TOOLS}


def get_tool(name: str):
    return HA_TOOLS_MAP.get(name)


def get_tool_schemas() -> list[dict]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters_schema,
        }
        for tool in HA_TOOLS
    ]