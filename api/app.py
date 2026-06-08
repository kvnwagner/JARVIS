from __future__ import annotations

import json
import os
import sys
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.assistant_runtime import runtime


app = FastAPI(
    title="JARVIS API",
    description="API REST + WebSocket para el asistente Jarvis",
    version="0.8.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    source: str = "text"


class ChatResponse(BaseModel):
    response: str
    tool_used: Optional[str] = None
    success: bool = True
    error: Optional[str] = None


class ExecuteRequest(BaseModel):
    tool: str
    params: dict = {}


class ExecuteResponse(BaseModel):
    tool: str
    success: bool
    output: str
    error: Optional[str] = None


class VoiceConfigRequest(BaseModel):
    wake_word_enabled: Optional[bool] = None
    wake_word: Optional[str] = None


@app.on_event("startup")
def startup() -> None:
    if os.getenv("JARVIS_AUTO_LISTEN", "1").lower() in {"1", "true", "yes", "on", "si"}:
        runtime.start_listening()


@app.get("/health")
def health() -> dict:
    return runtime.health()


@app.get("/state")
def state() -> dict:
    return runtime.state.to_dict()


@app.get("/tools")
def get_tools() -> dict:
    return {
        "tools": [
            {"name": tool.name, "description": tool.description}
            for tool in runtime.registry.get_all()
        ]
    }


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    result = runtime.chat(req.message, input_source=req.source)
    if not result.get("success", False) and result.get("error"):
        return ChatResponse(
            response=result.get("response", ""),
            success=False,
            error=result.get("error"),
        )
    return ChatResponse(
        response=result.get("response", ""),
        tool_used=result.get("tool_used"),
        success=result.get("success", True),
        error=result.get("error"),
    )


@app.post("/chat/stream")
def chat_stream(req: ChatRequest) -> StreamingResponse:
    def event_source():
        for event in runtime.stream_response(req.message, input_source=req.source):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")


@app.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest) -> ExecuteResponse:
    tool = runtime.registry.get(req.tool)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{req.tool}' no encontrada.")

    result = runtime.registry.execute(req.tool, req.params)
    return ExecuteResponse(
        tool=req.tool,
        success=result.success,
        output=result.output,
        error=result.error,
    )


@app.get("/memory")
def get_memory(n: int = 20) -> dict:
    recent = runtime.memory.get_recent_facts(n=n)
    conversation = runtime.memory.get_conversation_context(n=n)
    return {
        "conversation": conversation,
        "facts": [
            {
                "id": entry.id,
                "content": entry.content,
                "source": entry.source,
                "timestamp": entry.timestamp.isoformat(),
                "tags": entry.tags,
            }
            for entry in recent
        ],
        "stats": runtime.memory.stats(),
    }


@app.post("/assistant/start")
def start_assistant() -> dict:
    return runtime.start_listening()


@app.post("/assistant/stop")
def stop_assistant() -> dict:
    return runtime.stop_listening()


@app.post("/assistant/voice")
def configure_voice(req: VoiceConfigRequest) -> dict:
    return runtime.configure_voice(
        wake_word_enabled=req.wake_word_enabled,
        wake_word=req.wake_word,
    )


@app.websocket("/ws")
async def websocket(websocket: WebSocket) -> None:
    await websocket.accept()
    stream = runtime.stream.subscribe()
    await websocket.send_json({"type": "state", "payload": runtime.state.to_dict()})

    async def receive_commands() -> None:
        while True:
            data = await websocket.receive_json()
            command = data.get("type")
            payload = data.get("payload", {})
            if command == "chat":
                result = runtime.chat(payload.get("message", ""), input_source=payload.get("source", "text"))
                await websocket.send_json({"type": "chat.result", "payload": result})
            elif command == "start_listening":
                await websocket.send_json({"type": "state", "payload": runtime.start_listening()})
            elif command == "stop_listening":
                await websocket.send_json({"type": "state", "payload": runtime.stop_listening()})
            elif command == "voice.config":
                await websocket.send_json({
                    "type": "state",
                    "payload": runtime.configure_voice(
                        wake_word_enabled=payload.get("wake_word_enabled"),
                        wake_word=payload.get("wake_word"),
                    ),
                })
            elif command == "ping":
                await websocket.send_json({"type": "pong", "payload": {}})

    receiver = None
    try:
        import asyncio

        receiver = asyncio.create_task(receive_commands())
        while True:
            event = await stream.get()
            await websocket.send_json(event)
    except WebSocketDisconnect:
        pass
    finally:
        if receiver:
            receiver.cancel()
        runtime.stream.unsubscribe(stream)
