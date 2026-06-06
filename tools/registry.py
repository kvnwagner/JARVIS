"""Registro centralizado de herramientas."""

from typing import Dict, List, Optional

from core.interfaces import Event, EventBus, Tool, ToolResult
from infrastructure import events


class ToolRegistry:
    """Registro central de herramientas y unico punto de ejecucion."""

    def __init__(self, bus: EventBus, auto_subscribe: bool = True):
        self.bus = bus
        self._tools: Dict[str, Tool] = {}
        if auto_subscribe:
            self.bus.subscribe(events.LLM_TOOL_CALL, self.handle_llm_tool_call)

    def register(self, tool: Tool) -> None:
        """Registra una herramienta por nombre."""
        self._validate_tool(tool)
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[Tool]:
        """Obtiene una herramienta por nombre."""
        return self._tools.get(name)

    def get_all(self) -> List[Tool]:
        """Lista todas las herramientas registradas."""
        return list(self._tools.values())

    def handle_llm_tool_call(self, event: Event) -> None:
        """Ejecuta la herramienta decidida por el LLM a traves del EventBus."""
        tool_name = event.payload.get("tool", "")
        params = event.payload.get("params", event.payload.get("args", {}))
        self._execute(tool_name, params, requested_by=event.source)

    def execute(self, name: str, params: dict) -> ToolResult:
        """Valida, ejecuta y notifica el resultado de una herramienta."""
        return self._execute(name=name, params=params, requested_by=None)

    def _execute(
        self,
        name: str,
        params: dict,
        requested_by: Optional[str],
    ) -> ToolResult:
        if not name:
            result = ToolResult(
                success=False,
                output="",
                error="La decision del LLM no incluyo herramienta.",
            )
            self._publish_tool_event(events.TOOL_FAILED, "unknown", {}, result, requested_by)
            return result

        if not isinstance(params, dict):
            result = ToolResult(
                success=False,
                output="",
                error="Los parametros de la herramienta deben ser un diccionario.",
            )
            self._publish_tool_event(events.TOOL_FAILED, name, {}, result, requested_by)
            return result

        tool = self.get(name)
        if not tool:
            result = ToolResult(
                success=False,
                output="",
                error=f"Herramienta '{name}' no encontrada",
            )
            self._publish_tool_event(events.TOOL_FAILED, name, params, result, requested_by)
            return result

        self.bus.publish(
            Event(
                name=events.TOOL_STARTED,
                payload={
                    "tool": name,
                    "params": params,
                    "requested_by": requested_by,
                },
                source="tool_registry",
            )
        )

        try:
            result = tool.execute(params)
        except Exception as exc:
            result = ToolResult(success=False, output="", error=str(exc))

        event_name = events.TOOL_EXECUTED if result.success else events.TOOL_FAILED
        self._publish_tool_event(event_name, name, params, result, requested_by)
        return result

    def _validate_tool(self, tool: Tool) -> None:
        missing = [
            field
            for field in ("name", "description", "parameters_schema")
            if not getattr(tool, field, None)
        ]
        if missing:
            raise ValueError(f"Tool invalida. Faltan campos: {', '.join(missing)}")

        if not callable(getattr(tool, "execute", None)):
            raise ValueError("Tool invalida. Falta execute(params).")

        if not isinstance(tool.parameters_schema, dict):
            raise ValueError("Tool invalida. parameters_schema debe ser dict.")

    def _publish_tool_event(
        self,
        event_name: str,
        tool_name: str,
        params: dict,
        result: ToolResult,
        requested_by: Optional[str] = None,
    ) -> None:
        self.bus.publish(
            Event(
                name=event_name,
                payload={
                    "tool": tool_name,
                    "params": params,
                    "requested_by": requested_by,
                    "success": result.success,
                    "output": result.output,
                    "error": result.error,
                    "metadata": result.metadata,
                },
                source=tool_name,
            )
        )
