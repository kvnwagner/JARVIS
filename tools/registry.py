"""Registro centralizado de herramientas."""

from typing import Dict, List, Optional

from core.interfaces import Event, EventBus, Tool, ToolResult
from infrastructure import events


class ToolRegistry:
    """Registro central de todas las herramientas y punto único de ejecución."""

    def __init__(self, bus: EventBus):
        self.bus = bus
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Registra una herramienta por nombre."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Obtiene una herramienta por nombre."""
        return self._tools.get(name)

    def get_all(self) -> List[Tool]:
        """Lista todas las herramientas registradas."""
        return list(self._tools.values())

    def execute(self, name: str, params: dict) -> ToolResult:
        """Valida, ejecuta y notifica el resultado de una herramienta."""
        tool = self.get(name)
        if not tool:
            result = ToolResult(
                success=False,
                output="",
                error=f"Herramienta '{name}' no encontrada",
            )
            self._publish_tool_event(events.TOOL_FAILED, name, params, result)
            return result

        self.bus.publish(
            Event(
                name=events.TOOL_STARTED,
                payload={"tool": name, "params": params},
                source="tool_registry",
            )
        )

        try:
            result = tool.execute(params)
        except Exception as exc:
            result = ToolResult(success=False, output="", error=str(exc))

        event_name = events.TOOL_EXECUTED if result.success else events.TOOL_FAILED
        self._publish_tool_event(event_name, name, params, result)
        return result

    def _publish_tool_event(
        self,
        event_name: str,
        tool_name: str,
        params: dict,
        result: ToolResult,
    ) -> None:
        self.bus.publish(
            Event(
                name=event_name,
                payload={
                    "tool": tool_name,
                    "params": params,
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "metadata": result.metadata,
                },
                source="tool_registry",
            )
        )
