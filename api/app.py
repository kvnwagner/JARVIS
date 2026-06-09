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
from voice import VoiceManager

# 25002500 Instancia global de voz 250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500250025002500
_voice: VoiceManager | None = None


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

# ── Clientes WebSocket activos ────────────────────────────────────
active_websockets: list[WebSocket] = []


SYSTEM_PROMPT = """
Eres Jarvis, un asistente personal inteligente. Respondes en español, de forma clara, natural y amigable.

INTERPRETACIÓN DE MENSAJES:
- Interpreta SIEMPRE la intención real del usuario, aunque haya errores ortográficos, abreviaciones o lenguaje informal.
- Ejemplos: "apga el tele" = apagar TV, "ke clima ay en bogota" = clima Bogotá, "pone regueton" = reproducir reggaetón, "manda correo a juan" = enviar email a juan.
- Si el mensaje es ambiguo, elige la interpretación más lógica y actúa.
- Si el usuario dice solo el nombre de una aplicación (ej: "Spotify", "Chrome", "Discord"), interpreta que quiere ABRIRLA y usa open_app.

HERRAMIENTAS DISPONIBLES:
- clima / weather: para preguntas sobre el tiempo, temperatura, lluvia de cualquier ciudad.
- noticias / news: para pedir noticias, novedades o qué pasó sobre algún tema o lugar.
- email: para enviar correos electrónicos a alguien.
- spotify: para reproducir, poner o escuchar música en el computador. Parámetros: action=play y query=nombre de canción o artista. NUNCA uses action=search para reproducir.
- open_app: para abrir aplicaciones del computador que NO sean el televisor.
- screenshot: para tomar capturas de pantalla.
- reminder: para crear, listar o cancelar recordatorios a una hora exacta del día.
- system: para consultar el estado del computador. Usa query=all para resumen completo, o query=cpu/ram/disk/ip/processes para algo específico.
- keep: para gestionar notas de Google Keep.
  · create_note → crear nota de texto (title + text)
  · create_list → crear lista de verificación (title + items como array)
  · list_notes → ver las últimas notas
  · search → buscar notas por palabra clave (query)
  · read → leer una nota específica por título (query)
  Ejemplos: "crea una nota en Keep con el título Compras", "qué tengo en mis notas de Keep", "busca en Keep mis notas de trabajo", "crea una lista del mercado con leche, pan y huevos". Usa query=all para resumen completo, o query=cpu/ram/disk/ip/processes para algo específico. Ejemplos: "cómo está el sistema", "cuánta RAM tengo libre", "cuál es mi IP", "qué procesos están usando más CPU".
  Usa action=set con message y time en formato HH:MM (24h).
  Convierte lenguaje natural: "a las 8pm" → time="20:00", "a las 3 de la tarde" → time="15:00", "a las 8am" → time="08:00".
  Ejemplos:
    "recuérdame tomar la medicina a las 8pm" → action=set, message="tomar la medicina", time="20:00"
    "qué recordatorios tengo" → action=list
    "cancela el recordatorio abc123" → action=cancel, id="abc123"

REGLAS IMPORTANTES:
- Usa una herramienta SOLO si el usuario pide una acción concreta.
- Para preguntas generales, matemáticas, curiosidades, conversación o información: responde con texto directamente, SIN herramientas.
- Para Spotify: "pon", "reproduce", "escucha", "pone", "dale play", "quero escuchar" → SIEMPRE usa la tool spotify con action=play y query=nombre de la canción.
- Si el usuario dice solo "Spotify" sin más contexto → usa open_app con app=spotify.
- Para correos: usa EXACTAMENTE el destinatario que menciona el usuario.

HERRAMIENTAS DEL HOGAR (Home Assistant):
- Luces → controlar_luz: entity_id, action (on/off), brightness opcional.
- Clima/aire → controlar_clima: entity_id, temperature, mode opcional.
- Consultar dispositivo → consultar_estado_hogar: entity_id.
- Escenas → ejecutar_escena: entity_id.
- Televisor/TV → controlar_tv: SIEMPRE usa esta para encender/apagar/volumen, NUNCA open_app.
  - "apaga el tv / tele / televisor" → controlar_tv action=turn_off
  - "enciende el tv / tele / televisor" → controlar_tv action=turn_on
  - "sube el volumen / más volumen" → controlar_tv action=volume_up
  - "baja el volumen / menos volumen" → controlar_tv action=volume_down
  - "silencia / mutea el tv" → controlar_tv action=mute
  - "pausa el tv" → controlar_tv action=pause
  - "play el tv / reanuda" → controlar_tv action=play
- Abrir app en TV → abrir_app_tv: cuando el usuario pida abrir Netflix, YouTube, Spotify, etc. en el TV.
  - "abre Netflix en el tv" → abrir_app_tv app=netflix
  - "abre YouTube en el tv" → abrir_app_tv app=youtube
- Buscar en YouTube en TV → buscar_youtube_tv: cuando el usuario pida poner algo específico en YouTube en el TV.
  - "pon música de Bad Bunny en el tv" → buscar_youtube_tv query="música de Bad Bunny"
  - "pon videos de risa en el tv" → buscar_youtube_tv query="videos de risa"
  - "pon reggaetón en el tv" → buscar_youtube_tv query="reggaetón"

TONO:
- Responde siempre en español.
- Sé conciso pero amigable, como un asistente real.
- No expliques qué herramienta usaste a menos que el usuario lo pregunte.
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


def _broadcast_reminder(event: Event) -> None:
    """
    Recibe el evento reminder.fired del EventBus y lo reenvía
    a todos los clientes WebSocket conectados.
    Corre en el hilo del scheduler, usa asyncio.run_coroutine_threadsafe.
    """
    payload = event.payload
    message_text = f"🔔 Recordatorio: {payload.get('message', '')}"

    async def _send_all():
        dead = []
        for ws in active_websockets:
            try:
                await ws.send_json({
                    "type": "done",
                    "message": {
                        "role": "assistant",
                        "content": message_text,
                        "tool_used": "reminder",
                        "tool_success": True,
                        "tool_output": message_text,
                    },
                })
            except Exception:
                dead.append(ws)
        for ws in dead:
            active_websockets.remove(ws)

    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.run_coroutine_threadsafe(_send_all(), loop)


# Suscribir al EventBus para capturar recordatorios disparados
bus.subscribe("reminder.fired", _broadcast_reminder)


@app.on_event("startup")
def startup() -> None:
    global llm, messages, _voice
    llm = build_llm()
    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]
    container.inject_llm(llm)
    container.reminder_scheduler.start()
    try:
        _voice = VoiceManager(tts_enabled=True, stt_enabled=False)
    except Exception as e:
        import logging
        logging.getLogger("jarvis.api").warning("TTS no disponible: %s", e)


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


@app.get("/reminders/alerts")
def reminders_alerts():
    import sqlite3
    from pathlib import Path
    try:
        conn = sqlite3.connect(Path("jarvis.db"))
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM reminders WHERE status = 'fired' ORDER BY time").fetchall()
        alerts = [dict(r) for r in rows]
        if alerts:
            ids = [a["id"] for a in alerts]
            conn.execute(f"UPDATE reminders SET status = 'notified' WHERE id IN ({','.join('?'*len(ids))})", ids)
            conn.commit()
        conn.close()
    except Exception:
        alerts = []
    return {"alerts": [{"message": a["message"], "id": a["id"], "time": a["time"]} for a in alerts]}


class TTSRequest(BaseModel):
    text: str


@app.post("/tts/speak")
async def tts_speak(req: TTSRequest):
    """Reproduce texto con el TTS del backend (edge-tts)."""
    if not _voice or not _voice.tts_available:
        raise HTTPException(status_code=503, detail="TTS no disponible.")
    if not req.text or not req.text.strip():
        return {"ok": False}
    await asyncio.to_thread(_voice.speak, req.text.strip())
    return {"ok": True}


@app.post("/tts/stop")
def tts_stop():
    """Detiene la reproduccion de voz actual."""
    if _voice:
        _voice.stop_speaking()
    return {"ok": True}


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
    active_websockets.append(websocket)   # ← registrar cliente

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
                        "tool_success": result.success,
                        "tool_output": result.response if result.tool_used else None,
                    },
                })
            except HTTPException as exc:
                detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
                await websocket.send_json({"type": "error", "message": detail})
            finally:
                await websocket.send_json({"type": "typing", "active": False})
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)   # ← limpiar al desconectar


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


@app.get("/tools/status")
def tools_status():
    """Estado y lista de todas las tools registradas."""
    return {
        "tools": [{"name": t.name, "description": t.description} for t in registry.get_all()],
        "count": len(registry.get_all()),
    }


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