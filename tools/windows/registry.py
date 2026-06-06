"""
Tool Registry para Windows Tools.
Importa todas las herramientas disponibles y las expone como una lista
que el agente puede consumir directamente.

Uso:
    from tools.windows.registry import WINDOWS_TOOLS

    for tool in WINDOWS_TOOLS:
        agent.register_tool(tool)
"""

from tools.windows.open_app import OpenAppTool
from tools.windows.close_app import CloseAppTool
from tools.windows.volume_control import VolumeControlTool
from tools.windows.screenshot import ScreenshotTool
from tools.windows.clipboard import ClipboardTool

# Lista única que el agente consume
WINDOWS_TOOLS = [
    OpenAppTool(),
    CloseAppTool(),
    VolumeControlTool(),
    ScreenshotTool(),
    ClipboardTool(),
]

# Mapa por nombre para lookup rápido
WINDOWS_TOOLS_MAP = {tool.name: tool for tool in WINDOWS_TOOLS}


def get_tool(name: str):
    """Retorna un tool por nombre, o None si no existe."""
    return WINDOWS_TOOLS_MAP.get(name)


def get_tool_schemas() -> list[dict]:
    """
    Retorna los schemas de todas las tools en formato
    compatible con function calling de Gemini/OpenAI.
    """
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        for tool in WINDOWS_TOOLS
    ]
