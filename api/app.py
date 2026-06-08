"""FastAPI app para JARVIS.

Expone chat REST, chat por WebSocket con streaming simulado, memoria,
herramientas y estado del sistema.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.container import Container
from core.interfaces import Event, LLMMessage
from infrastructure import events
from llm import CerebrasProvider, GeminiProvider, GroqProvider
from memory.memory_manager import MemoryManager


app = FastAPI(
    title="JARVIS API",
    description="API REST y WebSocket para el asistente Jarvis",
    version="0.8.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

container = Container()
registry = container.tool_registry
bus = container.bus
memory = MemoryManager(db_path=container.config.db_path)
llm = None
messages: list[LLMMessage] = []

SYSTEM_PROMPT = """
Eres Jarvis, un asistente local. Responde en espanol, claro y breve.
Si hay herramientas disponibles y una herramienta es necesaria para cumplir
la peticion, elige exactamente una herramienta. Si no hay una herramienta util,
explica que puedes hacer con el estado actual del proyecto.
""".strip()


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str
    tool_used: Optional[str] = None
    success: bool = True


class ExecuteRequest(BaseModel):
    tool: str
    params: dict = {}


class ExecuteResponse(BaseModel):
    tool: str
    success: bool
    output: str
    error: Optional[str] = None


@app.on_event("startup")
def startup() -> None:
    global llm, messages
    llm = build_llm()
    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]


def build_llm():
    """Crea el provider configurado para la API."""
    config = container.config
    provider = config.llm_provider.lower().strip()

    if provider == "gemini" and config.gemini_api_key:
        return GeminiProvider(api_key=config.gemini_api_key, model=config.llm_model)
    if provider == "groq" and config.groq_api_key:
        return GroqProvider(api_key=config.groq_api_key, model=config.llm_model)
    if provider == "cerebras" and config.cerebras_api_key:
        return CerebrasProvider(api_key=config.cerebras_api_key)
    return None


def llm_name() -> str:
    if not llm:
        return "no configurado"
    return getattr(llm, "model_name", None) or getattr(llm, "model", "configurado")


def chunk_text(text: str, size: int = 18) -> list[str]:
    """Divide texto en fragmentos pequenos para la experiencia de streaming."""
    words = text.split(" ")
    chunks: list[str] = []
    current = ""
    for word in words:
        next_value = f"{current} {word}".strip()
        if len(next_value) > size and current:
            chunks.append(current + " ")
            current = word
        else:
            current = next_value
    if current:
        chunks.append(current)
    return chunks or [""]


def process_chat(message: str) -> ChatResponse:
    """Flujo unico de chat para REST y WebSocket."""
    clean_message = message.strip()
    if not clean_message:
        raise HTTPException(status_code=400, detail="Mensaje vacio.")
    if not llm:
        raise HTTPException(status_code=503, detail="LLM no configurado. Verifica tu .env")

    memory.save_message(clean_message, source="user")
    bus.publish(Event(
        name=events.USER_MESSAGE,
        payload={"text": clean_message},
        source="api",
    ))

    messages.append(LLMMessage(role="user", content=clean_message))
    response = llm.chat(messages, tools=registry.get_all())

    if response.error:
        raise HTTPException(status_code=500, detail=response.error)

    tool_used = None
    if response.tool_call:
        tool_name = response.tool_call.get("tool", "")
        params = response.tool_call.get("params", {})
        result = registry.execute(tool_name, params)
        tool_used = tool_name
        reply = result.output if result.success else f"Error: {result.error}"
        success = result.success
    else:
        reply = response.text or "Sin respuesta."
        success = True

    messages.append(LLMMessage(role="assistant", content=reply))
    memory.save_message(reply, source="assistant")

    if len(messages) > 17:
        del messages[1:-16]

    return ChatResponse(response=reply, tool_used=tool_used, success=success)


@app.get("/health")
def health():
    """Estado del sistema."""
    return {
        "status": "ok",
        "llm": llm_name(),
        "websocket": "/ws/chat",
        "tools": len(registry.get_all()),
        "memory": memory.stats(),
    }


@app.get("/tools")
def get_tools():
    """Lista todas las tools disponibles."""
    return {
        "tools": [
            {
                "name": t.name,
                "description": t.description,
            }
            for t in registry.get_all()
        ]
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """Envia un mensaje a Jarvis y recibe una respuesta."""
    return process_chat(req.message)


@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    """Chat por WebSocket con eventos de streaming para la interfaz."""
    await websocket.accept()
    await websocket.send_json({
        "type": "status",
        "status": "connected",
        "llm": llm_name(),
        "tools": len(registry.get_all()),
    })

    try:
        while True:
            data = await websocket.receive_json()
            message = str(data.get("message", "")).strip()
            if not message:
                await websocket.send_json({"type": "error", "message": "Mensaje vacio."})
                continue

            await websocket.send_json({"type": "typing", "active": True})
            try:
                result = await asyncio.to_thread(process_chat, message)
                for chunk in chunk_text(result.response):
                    await websocket.send_json({"type": "chunk", "content": chunk})
                    await asyncio.sleep(0.025)

                await websocket.send_json({
                    "type": "done",
                    "message": {
                        "role": "assistant",
                        "content": result.response,
                        "tool_used": result.tool_used,
                        "success": result.success,
                    },
                })
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
                await websocket.send_json({"type": "error", "message": detail})
            finally:
                await websocket.send_json({"type": "typing", "active": False})
    except WebSocketDisconnect:
        return


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
        error=result.error,
    )


@app.get("/memory")
def get_memory(n: int = 20):
    """Retorna las ultimas entradas de memoria."""
    recent = memory.get_recent_facts(n=n)
    conversation = memory.get_conversation_context(n=n)
    return {
        "conversation": conversation,
        "facts": [
            {
                "id": e.id,
                "content": e.content,
                "source": e.source,
                "timestamp": e.timestamp.isoformat(),
                "tags": e.tags,
            }
            for e in recent
        ],
        "stats": memory.stats(),
    }
