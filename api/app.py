# ================================================================
# api/app.py
# Fase 4 — FastAPI
# Expone el agente Jarvis como una API REST.
# Endpoints:
#   POST /chat        — enviar mensaje y recibir respuesta
#   POST /execute     — ejecutar una tool directamente
#   GET  /memory      — consultar memoria reciente
#   GET  /tools       — listar tools disponibles
#   GET  /health      — estado del sistema
# ================================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.container import Container
from core.interfaces import LLMMessage, Event
from infrastructure import events
from llm import GeminiProvider
from memory.memory_manager import MemoryManager

# ─── App ─────────────────────────────────────────────────────

app = FastAPI(
    title="JARVIS API",
    description="API REST para el asistente Jarvis",
    version="0.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Estado global ────────────────────────────────────────────

container  = Container()
registry   = container.tool_registry
bus        = container.bus
memory     = MemoryManager(db_path="jarvis.db")
llm: Optional[GeminiProvider] = None
messages:  list[LLMMessage] = []

SYSTEM_PROMPT = """
Eres Jarvis, un asistente local. Responde en español, claro y breve.
Si hay herramientas disponibles y una herramienta es necesaria para cumplir
la petición, elige exactamente una herramienta. Si no hay una herramienta útil,
explica qué puedes hacer con el estado actual del proyecto.
""".strip()


@app.on_event("startup")
def startup():
    global llm, messages
    config = container.config
    if config.gemini_api_key:
        llm = GeminiProvider(api_key=config.gemini_api_key, model=config.llm_model)
    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]


# ─── Schemas ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response:  str
    tool_used: Optional[str] = None
    success:   bool = True

class ExecuteRequest(BaseModel):
    tool:   str
    params: dict = {}

class ExecuteResponse(BaseModel):
    tool:    str
    success: bool
    output:  str
    error:   Optional[str] = None


# ─── Endpoints ───────────────────────────────────────────────

@app.get("/health")
def health():
    """Estado del sistema."""
    return {
        "status":  "ok",
        "llm":     llm.model_name if llm else "no configurado",
        "tools":   len(registry.get_all()),
        "memory":  memory.stats(),
    }


@app.get("/tools")
def get_tools():
    """Lista todas las tools disponibles."""
    return {
        "tools": [
            {
                "name":        t.name,
                "description": t.description,
            }
            for t in registry.get_all()
        ]
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Envía un mensaje a Jarvis y recibe una respuesta."""
    if not llm:
        raise HTTPException(status_code=503, detail="LLM no configurado. Verifica GEMINI_API_KEY en .env")

    # Guardar en memoria RAM
    memory.save_message(req.message, source="user")

    # Publicar evento
    bus.publish(Event(
        name=events.USER_MESSAGE,
        payload={"text": req.message},
        source="api"
    ))

    # Agregar al historial
    messages.append(LLMMessage(role="user", content=req.message))

    # Llamar al LLM
    response = llm.chat(messages, tools=registry.get_all())

    tool_used = None

    if response.error:
        raise HTTPException(status_code=500, detail=response.error)

    if response.tool_call:
        tool_name = response.tool_call.get("tool", "")
        params    = response.tool_call.get("params", {})
        result    = registry.execute(tool_name, params)
        tool_used = tool_name

        reply = result.output if result.success else f"Error: {result.error}"
        messages.append(LLMMessage(role="assistant", content=reply))
        memory.save_message(reply, source="assistant")

        return ChatResponse(
            response=reply,
            tool_used=tool_used,
            success=result.success
        )

    reply = response.text or "Sin respuesta."
    messages.append(LLMMessage(role="assistant", content=reply))
    memory.save_message(reply, source="assistant")

    return ChatResponse(response=reply, tool_used=None, success=True)


@app.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest):
    """Ejecuta una tool directamente sin pasar por el LLM."""
    tool = registry.get(req.tool)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{req.tool}' no encontrada.")

    result = registry.execute(req.tool, req.params)
    return ExecuteResponse(
        tool=req.tool,
        success=result.success,
        output=result.output,
        error=result.error
    )


@app.get("/memory")
def get_memory(n: int = 20):
    """Retorna las últimas n entradas de memoria."""
    recent = memory.get_recent_facts(n=n)
    conversation = memory.get_conversation_context(n=n)
    return {
        "conversation": conversation,
        "facts":        [
            {
                "id":        e.id,
                "content":   e.content,
                "source":    e.source,
                "timestamp": e.timestamp.isoformat(),
                "tags":      e.tags,
            }
            for e in recent
        ],
        "stats": memory.stats()
    }
