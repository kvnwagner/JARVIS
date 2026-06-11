# ================================================================
# api/app.py — Versión completa con WebSocket, TTS y Recordatorios
# ================================================================

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys
import os
import asyncio
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.container import Container
from core.interfaces import LLMMessage, Event
from infrastructure import events
from memory.memory_manager import MemoryManager
from tools.external.reminder_tool import init_reminders_table, get_pending_reminders

# ─── App ─────────────────────────────────────────────────────

app = FastAPI(
    title="JARVIS API",
    description="API REST para el asistente Jarvis",
    version="0.8.0"
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
llm        = None
messages_history: list[LLMMessage] = []

# Lista de alertas pendientes para el frontend
_pending_alerts: list[dict] = []

SYSTEM_PROMPT = """
Eres Jarvis, un asistente personal inteligente. Respondes en español, de forma clara, natural y amigable.

INTERPRETACIÓN DE MENSAJES:
- Interpreta SIEMPRE la intención real del usuario, aunque haya errores ortográficos o lenguaje informal.
- Si el mensaje es ambiguo, elige la interpretación más lógica y actúa.
- SIEMPRE usa herramientas cuando el usuario pida abrir algo, reproducir música, consultar clima, etc.

HERRAMIENTAS DISPONIBLES:
- weather: clima de cualquier ciudad
- news: noticias recientes
- email: enviar correos
- spotify: reproducir música (action=play, query=canción o artista)
- open_app: abrir aplicaciones Windows Y sitios web. Usar para:
  * Aplicaciones: spotify, chrome, discord, vscode, notepad, calculadora
  * Sitios web: youtube → app=youtube, facebook → app=facebook, instagram → app=instagram, netflix → app=netflix, gmail → app=gmail, whatsapp → app=whatsapp
- screenshot: captura de pantalla
- reminder: crear recordatorios (action=set, message=..., time=HH:MM)
- system: estado del sistema (CPU, RAM, disco, IP)
- controlar_luz: encender/apagar luces del hogar
- controlar_clima: controlar aire acondicionado
- controlar_tv: controlar televisor (encender, apagar, volumen, pausa)
- abrir_app_tv: abrir apps en el TV (netflix, youtube, spotify)
- buscar_youtube_tv: reproducir algo en YouTube en el TV
- consultar_estado_hogar: consultar estado de dispositivos del hogar
- ejecutar_escena: activar escenas del hogar

REGLAS IMPORTANTES:
- SIEMPRE usa open_app cuando el usuario diga "abre", "abre YouTube", "abre Facebook", "abre Instagram", etc.
- Para Spotify en el PC: usa spotify con action=play y query=nombre.
- Para TV: usa controlar_tv, NUNCA open_app.
- Para sitios web en el PC: usa open_app con el nombre del sitio como app.
- Para conversación general sin acción concreta: responde con texto directamente.
- NUNCA respondas solo con texto cuando el usuario pide abrir algo.
""".strip()


@app.on_event("startup")
def startup():
    global llm, messages_history

    # Inicializar tabla de recordatorios
    init_reminders_table()

    # Inicializar LLM
    from core.config import get_settings
    config = get_settings()

    try:
        provider = config.llm_provider.lower().strip()
        if provider == "groq":
            from llm import GroqProvider
            llm = GroqProvider(api_key=config.groq_api_key, model=config.llm_model or "llama-3.3-70b-versatile")
        elif provider == "cerebras":
            from llm import CerebrasProvider
            llm = CerebrasProvider(api_key=config.cerebras_api_key)
        elif provider == "gemini":
            from llm import GeminiProvider
            llm = GeminiProvider(api_key=config.gemini_api_key, model=config.llm_model or "gemini-1.5-flash")
    except Exception as e:
        print(f"LLM no configurado: {e}")
        llm = None

    messages_history = [LLMMessage(role="system", content=SYSTEM_PROMPT)]

    # Scheduler de recordatorios
    try:
        from infrastructure.reminder_scheduler import ReminderScheduler
        scheduler = ReminderScheduler(bus=bus)
        scheduler.start()

        def on_reminder_fired(event: Event):
            _pending_alerts.append({
                "id": event.payload.get("id"),
                "message": event.payload.get("message"),
            })
        bus.subscribe("reminder.fired", on_reminder_fired)
    except Exception as e:
        print(f"Scheduler no iniciado: {e}")


# ─── Schemas ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response:   str
    tool_used:  Optional[str] = None
    success:    bool = True

class ExecuteRequest(BaseModel):
    tool:   str
    params: dict = {}

class ExecuteResponse(BaseModel):
    tool:    str
    success: bool
    output:  str
    error:   Optional[str] = None

class TTSRequest(BaseModel):
    text: str


# ─── Helper LLM ──────────────────────────────────────────────

def _run_llm(user_message: str):
    """Ejecuta el LLM y devuelve (reply_text, tool_used, tool_success, tool_output)."""
    if not llm:
        return "LLM no configurado. Agrega tu API key en el archivo .env", None, None, None

    memory.save_message(user_message, source="user")
    bus.publish(Event(name=events.USER_MESSAGE, payload={"text": user_message}, source="api"))
    messages_history.append(LLMMessage(role="user", content=user_message))

    response = llm.chat(messages_history, tools=registry.get_all())

    if response.error:
        return f"Error del LLM: {response.error}", None, None, None

    tool_used = None
    tool_success = None
    tool_output = None

    if response.tool_call:
        tool_name = response.tool_call.get("tool", "")
        params    = response.tool_call.get("params", {})
        result    = registry.execute(tool_name, params)
        tool_used    = tool_name
        tool_success = result.success
        tool_output  = result.output if result.success else result.error

        # Segunda llamada al LLM para respuesta natural
        interp = [
            LLMMessage(role="system", content=SYSTEM_PROMPT),
            LLMMessage(role="user", content=user_message),
            LLMMessage(role="user", content=(
                f"La herramienta '{tool_name}' devolvió: {tool_output}. "
                f"Responde al usuario en español natural y breve. No uses herramientas."
            )),
        ]
        final = llm.chat(interp, tools=None)
        reply = final.text or tool_output
    elif response.text:
        reply = response.text
    else:
        reply = "No obtuve respuesta del LLM."

    messages_history.append(LLMMessage(role="assistant", content=reply))
    memory.save_message(reply, source="assistant")
    bus.publish(Event(name=events.LLM_RESPONSE, payload={"text": reply}, source="api"))

    # Limpiar historial si crece demasiado
    if len(messages_history) > 20:
        messages_history[:] = [messages_history[0]] + messages_history[-10:]

    return reply, tool_used, tool_success, tool_output


# ─── Endpoints REST ──────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "ok",
        "llm":    llm.model_name if llm and hasattr(llm, "model_name") else (llm.model if llm and hasattr(llm, "model") else "no configurado"),
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


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    reply, tool_used, tool_success, tool_output = _run_llm(req.message)
    return ChatResponse(
        response=reply,
        tool_used=tool_used,
        success=tool_success if tool_success is not None else True,
    )


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
        error=result.error,
    )


@app.get("/memory")
def get_memory(n: int = 20):
    return {
        "conversation": memory.get_conversation_context(n=n),
        "facts": [
            {
                "id": e.id,
                "content": e.content,
                "source": e.source,
                "timestamp": e.timestamp.isoformat(),
                "tags": e.tags,
            }
            for e in memory.get_recent_facts(n=n)
        ],
        "stats": memory.stats(),
    }


@app.get("/reminders/alerts")
def get_reminder_alerts():
    """Retorna alertas de recordatorios disparados y las limpia."""
    alerts = list(_pending_alerts)
    _pending_alerts.clear()
    return {"alerts": alerts}


def _clean_for_tts(text: str) -> str:
    """Elimina emojis y caracteres especiales que no deben leerse en voz."""
    import re
    text = re.sub(r'[\U0001F000-\U0010FFFF]', '', text)
    text = re.sub(r'[\u2000-\u2BFF]', '', text)
    text = re.sub(r'[\u2600-\u27FF]', '', text)
    text = re.sub(r'[#*_`~|<>{}\[\]\\]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _find_ffplay() -> str | None:
    """Busca ffplay en PATH o en la ruta típica de WinGet, sin importar el usuario."""
    import shutil, glob
    # 1. Intentar desde PATH (si el sistema lo tiene registrado)
    in_path = shutil.which("ffplay")
    if in_path:
        return in_path
    # 2. Buscar en la carpeta de WinGet del usuario actual
    local = os.environ.get("LOCALAPPDATA", "")
    pattern = os.path.join(
        local,
        "Microsoft", "WinGet", "Packages",
        "Gyan.FFmpeg_*", "ffmpeg-*", "bin", "ffplay.exe"
    )
    matches = glob.glob(pattern)
    if matches:
        return matches[0]
    return None


@app.post("/tts/speak")
async def tts_speak(req: TTSRequest):
    """Sintetiza voz con edge-tts y reproduce con ffplay (ruta dinámica)."""
    async def _speak():
        try:
            import edge_tts, tempfile
            clean_text = _clean_for_tts(req.text.strip())
            if not clean_text:
                return

            tts = edge_tts.Communicate(clean_text, "es-ES-AlvaroNeural", rate="+15%")
            tmp = tempfile.mktemp(suffix=".mp3")
            await tts.save(tmp)

            ffplay = _find_ffplay()
            if not ffplay:
                print("TTS error: ffplay no encontrado. Instala ffmpeg con: winget install Gyan.FFmpeg")
                return

            import subprocess
            subprocess.Popen(
                [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", tmp],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            print(f"TTS error: {e}")

    asyncio.create_task(_speak())
    return {"ok": True}


@app.post("/tts/stop")
def tts_stop():
    return {"ok": True}


# ─── WebSocket ───────────────────────────────────────────────

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    await websocket.send_json({
        "type": "status",
        "status": "ok",
        "llm": llm.model_name if llm and hasattr(llm, "model_name") else (llm.model if llm and hasattr(llm, "model") else "no configurado"),
        "tools": len(registry.get_all()),
    })

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)
            user_message = payload.get("message", "").strip()

            if not user_message:
                continue

            await websocket.send_json({"type": "typing", "active": True})

            loop = asyncio.get_event_loop()
            reply, tool_used, tool_success, tool_output = await loop.run_in_executor(
                None, _run_llm, user_message
            )

            await websocket.send_json({"type": "typing", "active": False})

            await websocket.send_json({
                "type": "done",
                "message": {
                    "content":      reply,
                    "tool_used":    tool_used,
                    "tool_success": tool_success,
                    "tool_output":  tool_output,
                },
            })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass