"""Registro centralizado de herramientas."""
from typing import Dict, List, Optional
from core.interfaces import Tool, ToolResult, EventBus

class ToolRegistry:
    """Registro central de todas las herramientas."""
    
    def __init__(self, bus: EventBus):
        self.bus = bus
        self._tools: Dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> None:
        """Registra una herramienta."""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[Tool]:
        """Obtiene una herramienta por nombre."""
        return self._tools.get(name)
    
    def get_all(self) -> List[Tool]:
        """Lista todas las herramientas."""
        return list(self._tools.values())
    
    def execute(self, name: str, params: dict) -> ToolResult:
        """Ejecuta una herramienta."""
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Herramienta '{name}' no encontrada"
            )
        
        try:
            return tool.execute(params)
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=str(e)
            )