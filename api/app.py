# ================================================================
# api/app.py — Versión completa con WebSocket, TTS, Recordatorios,
# Mute/Stop de voz real, e historial paginado desde SQLite
# ================================================================

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys
import os
import asyncio
import json
import threading
import subprocess

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
    version="0.9.1"
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

# ─── Estado de voz (TTS) ───────────────────────────────────────
# _current_tts_proc: proceso de ffplay actualmente reproduciendo (o None)
# _tts_muted:        si está en True, Jarvis no reproduce nada nuevo
_tts_lock = threading.Lock()
_current_tts_proc: subprocess.Popen | None = None
_tts_muted: bool = False

# Prompt reducido a lo esencial — menos tokens por request, importante
# para no chocar con los límites de tokens/minuto de Groq.
SYSTEM_PROMPT = """
Eres Jarvis, asistente personal en español, claro y natural. Interpreta la
intención real del usuario aunque tenga errores ortográficos o jerga.

Herramientas: weather, news, email, spotify (action=play+query),
open_app (apps y sitios web: youtube/facebook/instagram/netflix/gmail/whatsapp),
search_web (site+query: buscar algo DENTRO de un sitio, ej: "busca X en youtube"),
screenshot, reminder (action=set/list/cancel), system, translate (text+target),
files (action=search/list/read, solo carpetas personales del usuario),
browser_history (historial de Chrome/Edge, opcional query),
code (action=list/read/search/write/edit/append/delete/run: leer, buscar,
crear, editar o borrar archivos de código del proyecto, o correr
tests/comandos permitidos como python/pytest/git/npm),
controlar_luz, controlar_clima, controlar_tv, abrir_app_tv, buscar_youtube_tv,
consultar_estado_hogar, ejecutar_escena.

Reglas: usa open_app para "abre X" (apps o webs, NUNCA para el TV). Usa
search_web cuando el usuario pida buscar algo específico dentro de un sitio
(ej: "busca en youtube intro de junior h" → search_web site=youtube
query="intro de junior h"; "busca audífonos en amazon" → search_web
site=amazon query="audífonos"). Usa controlar_tv para el televisor. Para
Spotify reproducir música usa la tool spotify con action=play, no search_web.
Usa 'code' cuando el usuario pida modificar, crear, revisar o corregir
código, buscar dónde está definida una función/clase, o correr tests. Para
action='edit', old_str debe ser el fragmento EXACTO de texto tal como está
en el archivo (incluyendo indentación) — si no estás seguro del texto
exacto, usa primero action='read' para verlo con números de línea antes de
editar. 'write' sobre un archivo existente y 'delete' requieren
confirm=true; si el usuario no lo ha confirmado explícitamente en su
mensaje, pídeselo antes de repetir la llamada con confirm=true. Para
conversación general sin acción concreta, responde solo con texto.

Cuando una herramienta devuelva mucha información (listas, historial,
noticias, archivos, código, etc.), muestra solo un resumen breve con lo más
relevante (3-5 puntos como máximo). Nunca vuelques toda la salida cruda.
Si hay más datos disponibles que no mostraste, termina preguntando si el
usuario quiere ver la información completa.
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

        if provider == "cerebras":
            # ── Cerebras con fallback automático a Groq ──────────────
            from llm import CerebrasProvider, GroqProvider

            cerebras_key = config.cerebras_api_key
            groq_key = config.groq_api_key or os.getenv("GROQ_API_KEY", "")

            llm = None
            if cerebras_key:
                try:
                    print("LLM: Intentando Cerebras...")
                    candidate = CerebrasProvider(api_key=cerebras_key)
                    test = candidate.chat([LLMMessage(role="user", content="hi")])
                    if test.error is None:
                        llm = candidate
                        print("LLM: ✓ Cerebras activo")
                    else:
                        print(f"LLM: ✗ Cerebras falló — {test.error}")
                except Exception as e:
                    print(f"LLM: ✗ Cerebras excepción — {e}")
            else:
                print("LLM: no hay CEREBRAS_API_KEY configurada")

            if llm is None and groq_key:
                print("LLM: ⚠ usando Groq como respaldo")
                llm = GroqProvider(api_key=groq_key, model="openai/gpt-oss-120b")

            if llm is None:
                print("LLM: ERROR — Cerebras falló y no hay GROQ_API_KEY de respaldo")

        elif provider == "groq":
            from llm import GroqProvider
            llm = GroqProvider(api_key=config.groq_api_key, model=config.llm_model or "openai/gpt-oss-120b")
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

class MuteRequest(BaseModel):
    muted: bool


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
                f"La herramienta '{tool_name}' devolvió este resultado:\n{tool_output}\n\n"
                f"Responde al usuario en español, breve y organizado: solo los puntos "
                f"clave (usa viñetas cortas si son varios ítems, no vuelques el resultado "
                f"completo). Si hay más información de la que mostraste (más noticias, "
                f"más archivos, más detalles, etc.), termina preguntando si quiere que se "
                f"la muestres completa. No uses herramientas."
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

    # Trim agresivo: system + últimos 6 mensajes.
    if len(messages_history) > 10:
        messages_history[:] = [messages_history[0]] + messages_history[-6:]

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
def get_memory(limit: int = 20, offset: int = 0):
    """
    Historial REAL y persistente (SQLite), paginado.
    offset=0 devuelve los mensajes más recientes; sube offset para pedir
    mensajes más antiguos ("cargar historial anterior" en el frontend).
    """
    return {
        "conversation": memory.get_conversation_page(limit=limit, offset=offset),
        "total": memory.get_conversation_total(),
        "limit": limit,
        "offset": offset,
        "facts": [
            {
                "id": e.id,
                "content": e.content,
                "source": e.source,
                "timestamp": e.timestamp.isoformat(),
                "tags": e.tags,
            }
            for e in memory.get_recent_facts(n=limit)
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
    in_path = shutil.which("ffplay")
    if in_path:
        return in_path
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
    global _current_tts_proc

    # Si está muteado, no reproducir nada
    if _tts_muted:
        return {"ok": False, "muted": True}

    async def _speak():
        global _current_tts_proc
        try:
            import edge_tts, tempfile
            clean_text = _clean_for_tts(req.text.strip())
            if not clean_text:
                return

            tts = edge_tts.Communicate(clean_text, "es-ES-AlvaroNeural", rate="+15%")
            tmp = tempfile.mktemp(suffix=".mp3")
            await tts.save(tmp)

            # Pudo mutearse mientras se generaba el audio — no reproducir
            if _tts_muted:
                return

            ffplay = _find_ffplay()
            if not ffplay:
                print("TTS error: ffplay no encontrado. Instala ffmpeg con: winget install Gyan.FFmpeg")
                return

            proc = subprocess.Popen(
                [ffplay, "-nodisp", "-autoexit", "-loglevel", "quiet", tmp],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            with _tts_lock:
                _current_tts_proc = proc

            # OJO: proc.wait() bloquea — nunca llamarlo directo dentro de un
            # async def, o congela TODO el event loop de FastAPI (mute, chat,
            # websocket, etc. quedan colgados hasta que el audio termine solo).
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, proc.wait)

            with _tts_lock:
                if _current_tts_proc is proc:
                    _current_tts_proc = None
        except Exception as e:
            print(f"TTS error: {e}")

    asyncio.create_task(_speak())
    return {"ok": True}


@app.post("/tts/stop")
def tts_stop():
    """Corta la reproducción de voz actual (silencio puntual, no bloquea futuras)."""
    global _current_tts_proc
    with _tts_lock:
        if _current_tts_proc and _current_tts_proc.poll() is None:
            _current_tts_proc.terminate()
        _current_tts_proc = None
    return {"ok": True}


@app.post("/tts/mute")
def tts_mute(req: MuteRequest):
    """
    Activa/desactiva el silencio de Jarvis.
    Al mutear, corta inmediatamente cualquier audio en reproducción y
    bloquea que se reproduzcan nuevos audios hasta que se desmute.
    """
    global _tts_muted, _current_tts_proc
    _tts_muted = req.muted

    if _tts_muted:
        with _tts_lock:
            if _current_tts_proc and _current_tts_proc.poll() is None:
                _current_tts_proc.terminate()
            _current_tts_proc = None

    return {"ok": True, "muted": _tts_muted}


@app.get("/tts/status")
def tts_status():
    """Estado actual de la voz — útil para sincronizar el botón del frontend."""
    with _tts_lock:
        speaking = _current_tts_proc is not None and _current_tts_proc.poll() is None
    return {
        "muted": _tts_muted,
        "speaking": speaking,
    }


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