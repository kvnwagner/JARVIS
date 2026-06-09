# ================================================================
# api/app.py - Fase 4 – FastAPI con CerebrasProvider
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
from llm.cerebras_provider import CerebrasProvider
from memory.memory_manager import MemoryManager

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

container = Container()
registry  = container.tool_registry
bus       = container.bus
memory    = MemoryManager(db_path="jarvis.db")
llm: Optional[CerebrasProvider] = None
messages: list[LLMMessage] = []

SYSTEM_PROMPT = """
Eres Jarvis, un asistente local. Responde en español, claro y breve.
Si hay herramientas disponibles y una herramienta es necesaria para cumplir
la petición, elige exactamente una herramienta. Si no hay una herramienta útil,
explica qué puedes hacer con el estado actual del proyecto.
""".strip()


@app.on_event("startup")
def startup():
    global llm, messages
    api_key = os.getenv("CEREBRAS_API_KEY", "")
    if api_key:
        llm = CerebrasProvider(api_key=api_key)
    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm":    llm.model if llm else "no configurado",
        "tools":  len(registry.get_all()),
        "memory": memory.stats(),
    }


@app.get("/tools")
def get_tools():
    return {
        "tools": [
            {"name": t.name, "description": t.description}
            for t in registry.get_all()
        ]
    }


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



import webbrowser as _wb
import urllib.parse as _up
import os as _os

_SITES = {
    "abre youtube":      "https://youtube.com",
    "abre facebook":     "https://facebook.com",
    "abre gmail":        "https://mail.google.com",
    "abre instagram":    "https://instagram.com",
    "abre disney":       "https://www.disneyplus.com",
    "abre disney plus":  "https://www.disneyplus.com",
    "abre disney+":      "https://www.disneyplus.com",
    "abre netflix":      "https://www.netflix.com",
    "abre prime":        "https://www.primevideo.com",
    "abre prime video":  "https://www.primevideo.com",
    "abre twitch":       "https://www.twitch.tv",
    "abre twitter":      "https://twitter.com",
    "abre x":            "https://twitter.com",
    "abre whatsapp":     "https://web.whatsapp.com",
    "abre reddit":       "https://www.reddit.com",
    "abre linkedin":     "https://www.linkedin.com",
    "abre tiktok":       "https://www.tiktok.com",
}

def _shortcut(msg: str):
    low = msg.strip().lower()
    # Ignorar prefijos comunes
    for prefix in ["jarvis ", "hey jarvis ", "oye jarvis "]:
        if low.startswith(prefix):
            low = low[len(prefix):]
            break
    if low in _SITES:
        _wb.open(_SITES[low])
        return f"Abriendo {_SITES[low]}"
    if low.startswith("busca ") or low.startswith("buscar "):
        q = msg[7:].strip() if low.startswith("buscar ") else msg[6:].strip()
        _wb.open("https://www.google.com/search?q=" + _up.quote(q))
        return f"Buscando {q} en Google"
    if low.startswith("youtube "):
        q = msg[8:].strip()
        _wb.open("https://www.youtube.com/results?search_query=" + _up.quote(q))
        return f"Buscando {q} en YouTube"
    if low == "abre documentos":
        _os.startfile(r"C:\Users\qandr\Documents"); return "Abriendo Documentos"
    if low == "abre descargas":
        _os.startfile(r"C:\Users\qandr\Downloads"); return "Abriendo Descargas"
    if low == "abre escritorio":
        _os.startfile(r"C:\Users\qandr\Desktop"); return "Abriendo Escritorio"
    return None

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if not llm:
        raise HTTPException(status_code=503, detail="LLM no configurado. Verifica CEREBRAS_API_KEY en .env")

    _sc = _shortcut(req.message)
    if _sc:
        return ChatResponse(response=_sc, tool_used=None, success=True)
    memory.save_message(req.message, source="user")
    bus.publish(Event(
        name=events.USER_MESSAGE,
        payload={"text": req.message},
        source="api"
    ))

    messages.append(LLMMessage(role="user", content=req.message))
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

        return ChatResponse(response=reply, tool_used=tool_used, success=result.success)

    reply = response.text or "Sin respuesta."
    messages.append(LLMMessage(role="assistant", content=reply))
    memory.save_message(reply, source="assistant")

    return ChatResponse(response=reply, tool_used=None, success=True)



_tts_instance = None

def _get_tts():
    global _tts_instance
    if _tts_instance is None:
        from voice.tts import JarvisTTS
        _tts_instance = JarvisTTS()
    return _tts_instance

@app.post("/tts/speak")
def tts_speak(req: dict):
    try:
        text = req.get("text", "")
        if text:
            _get_tts().speak_async(text)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@app.post("/tts/stop")
def tts_stop():
    try:
        _get_tts().stop()
    except Exception:
        pass
    return {"ok": True}

@app.post("/execute", response_model=ExecuteResponse)
def execute(req: ExecuteRequest):
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
    recent = memory.get_recent_facts(n=n)
    conversation = memory.get_conversation_context(n=n)
    return {
        "conversation": conversation,
        "facts": [
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
