# ================================================================
# core/interfaces.py
# CONTRATO DEL EQUIPO — no modificar sin aprobación unánime
# Propietario: todos / Revisor: líder técnico
# ================================================================

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional
from datetime import datetime


# ─── Tool ────────────────────────────────────────────────────

@dataclass
class ToolResult:
    success: bool
    output:  str
    error:   Optional[str] = None
    metadata: dict = field(default_factory=dict)


class Tool(ABC):
    name:              str
    description:       str
    parameters_schema: dict        # JSON Schema

    @abstractmethod
    def execute(self, params: dict) -> ToolResult:
        """Ejecuta la herramienta. Nunca lanza excepción — siempre
        devuelve ToolResult con success=False en caso de error."""
        ...


# ─── LLM ─────────────────────────────────────────────────────

@dataclass
class LLMMessage:
    role:    str           # "user" | "assistant" | "system"
    content: str

@dataclass
class LLMResponse:
    text:      Optional[str]
    tool_call: Optional[dict] = None  # {"tool": str, "params": dict}
    raw:       Any = None             # respuesta original del proveedor
    error:     Optional[str] = None

class LLMProvider(ABC):

    @abstractmethod
    def chat(self,
             messages: list[LLMMessage],
             tools:    Optional[list[Tool]] = None
             ) -> LLMResponse:
        """Única forma de hablar con el LLM en todo el proyecto."""
        ...


# ─── Memory ──────────────────────────────────────────────────

@dataclass
class MemoryEntry:
    id:         str
    content:    str
    source:     str           # "user" | "tool" | "system"
    timestamp:  datetime = field(default_factory=datetime.utcnow)
    tags:       list[str] = field(default_factory=list)

class MemoryProvider(ABC):

    @abstractmethod
    def save(self, entry: MemoryEntry) -> None: ...

    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[MemoryEntry]: ...

    @abstractmethod
    def get_recent(self, n: int = 20) -> list[MemoryEntry]: ...


# ─── EventBus ────────────────────────────────────────────────

@dataclass
class Event:
    name:      str
    payload:   dict
    source:    str
    timestamp: datetime = field(default_factory=datetime.utcnow)

EventHandler = Callable[[Event], None]

class EventBus(ABC):

    @abstractmethod
    def publish(self, event: Event) -> None: ...

    @abstractmethod
    def subscribe(self, event_name: str, handler: EventHandler) -> None: ...
