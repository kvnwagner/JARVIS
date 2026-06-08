from __future__ import annotations

import asyncio
import os
import queue
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

from core.container import Container
from core.interfaces import Event, LLMMessage, LLMProvider
from infrastructure import events
from llm import CerebrasProvider, GeminiProvider, GroqProvider
from memory.memory_manager import MemoryManager

try:
    from voice import VoiceManager
except ImportError:  # pragma: no cover - voz opcional
    VoiceManager = None


SYSTEM_PROMPT = """
Eres Jarvis, un asistente personal local. Responde siempre en espanol, breve,
natural y util. Interpreta errores ortograficos y lenguaje informal. Usa una
herramienta solo cuando el usuario pida una accion concreta del computador,
Home Assistant, musica, clima, noticias, email o captura de pantalla.
""".strip()


TOOL_CONFIRMATIONS = {
    "open_app": lambda p: f"Listo, abriendo {p.get('app', 'la aplicacion')}",
    "close_app": lambda p: f"Cerrando {p.get('app', 'la aplicacion')}",
    "spotify": lambda p: (
        f"Reproduciendo {p.get('query', 'musica')} en Spotify"
        if p.get("action") == "play"
        else "Controlando Spotify"
    ),
    "weather": lambda p: f"Consultando el clima en {p.get('city', 'tu ciudad')}",
    "news": lambda p: f"Buscando noticias sobre {p.get('query', 'el tema')}",
    "email": lambda p: f"Enviando correo a {p.get('to', 'el destinatario')}",
    "screenshot": lambda p: "Tomando captura de pantalla",
    "volume_control": lambda p: "Ajustando el volumen",
    "controlar_luz": lambda p: (
        "Encendiendo la luz" if p.get("action") == "on" else "Apagando la luz"
    ),
    "controlar_tv": lambda p: "Controlando el televisor",
    "controlar_clima": lambda p: "Ajustando el clima",
    "ejecutar_escena": lambda p: "Activando la escena",
    "consultar_estado_hogar": lambda p: "Consultando el dispositivo",
}


@dataclass
class RuntimeState:
    status: str = "starting"
    listening: bool = False
    wake_word_enabled: bool = True
    wake_word: str = "jarvis"
    voice_engine: str = "unavailable"
    llm: str = "not configured"
    last_heard: str = ""
    last_response: str = ""
    last_error: str = ""
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        data = self.__dict__.copy()
        data["updated_at"] = datetime.utcnow().isoformat()
        return data


class EventStream:
    def __init__(self) -> None:
        self._subscribers: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue]] = set()
        self._lock = threading.RLock()

    def subscribe(self) -> asyncio.Queue:
        loop = asyncio.get_running_loop()
        stream: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subscribers.add((loop, stream))
        return stream

    def unsubscribe(self, stream: asyncio.Queue) -> None:
        with self._lock:
            self._subscribers = {
                item for item in self._subscribers if item[1] is not stream
            }

    def publish(self, event_type: str, payload: dict) -> None:
        envelope = {
            "type": event_type,
            "payload": payload,
            "ts": datetime.utcnow().isoformat(),
        }
        with self._lock:
            subscribers = list(self._subscribers)
        for loop, stream in subscribers:
            if loop.is_closed():
                continue
            loop.call_soon_threadsafe(self._put_event, stream, envelope)

    @staticmethod
    def _put_event(stream: asyncio.Queue, envelope: dict) -> None:
        try:
            stream.put_nowait(envelope)
        except asyncio.QueueFull:
            try:
                stream.get_nowait()
                stream.put_nowait(envelope)
            except Exception:
                pass


class ContinuousVoiceService:
    """Background voice loop with optional Porcupine/Vosk engines."""

    def __init__(
        self,
        on_text: Callable[[str, str], None],
        emit: Callable[[str, dict], None],
        language: str = "es-CO",
        wake_word: str = "jarvis",
    ) -> None:
        self.on_text = on_text
        self.emit = emit
        self.language = language
        self.wake_word = wake_word.lower().strip() or "jarvis"
        self.enabled = False
        self.wake_word_enabled = True
        self.engine = "unavailable"
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._voice = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            self.enabled = True
            return
        self.enabled = True
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="jarvis-continuous-voice",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self.enabled = False
        self._stop.set()
        if self._voice:
            try:
                self._voice.stop_listening()
            except Exception:
                pass

    def configure(self, wake_word_enabled: Optional[bool] = None, wake_word: Optional[str] = None) -> None:
        if wake_word_enabled is not None:
            self.wake_word_enabled = wake_word_enabled
        if wake_word:
            self.wake_word = wake_word.lower().strip()

    def _loop(self) -> None:
        if self._try_porcupine_loop():
            return
        if self._try_vosk_loop():
            return
        self._fallback_stt_loop()

    def _try_porcupine_loop(self) -> bool:
        access_key = os.getenv("PICOVOICE_ACCESS_KEY", "").strip()
        if not access_key:
            return False
        try:
            import pvporcupine
            import sounddevice as sd
        except ImportError:
            return False

        porcupine = None
        try:
            keyword_paths = [
                item.strip()
                for item in os.getenv("PORCUPINE_KEYWORD_PATHS", "").split(";")
                if item.strip()
            ]
            if keyword_paths:
                porcupine = pvporcupine.create(
                    access_key=access_key,
                    keyword_paths=keyword_paths,
                )
            else:
                porcupine = pvporcupine.create(
                    access_key=access_key,
                    keywords=[self.wake_word],
                )

            self.engine = "porcupine"
            self.emit("voice.engine", {"engine": self.engine})
            if VoiceManager is not None and self._voice is None:
                self._voice = VoiceManager(tts_enabled=True, stt_enabled=True, language=self.language)
            wake_queue: queue.Queue[bool] = queue.Queue()

            def callback(indata, frames, time_info, status) -> None:
                if status:
                    self.emit("voice.status", {"status": str(status)})
                pcm = memoryview(indata).cast("h")
                if porcupine and porcupine.process(pcm) >= 0:
                    wake_queue.put(True)

            with sd.RawInputStream(
                samplerate=porcupine.sample_rate,
                blocksize=porcupine.frame_length,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                while not self._stop.is_set():
                    try:
                        wake_queue.get(timeout=0.1)
                    except queue.Empty:
                        continue
                    self.emit("voice.wake", {"wake_word": self.wake_word, "source": "porcupine"})
                    if self._voice:
                        command = self._voice.listen()
                        if command:
                            self.on_text(command, "porcupine")
                    time.sleep(0.1)
            return True
        except Exception as exc:
            self.emit("voice.error", {"error": f"Porcupine no pudo iniciar: {exc}"})
            return False
        finally:
            if porcupine:
                porcupine.delete()

    def _try_vosk_loop(self) -> bool:
        model_path = os.getenv("VOSK_MODEL_PATH", "").strip()
        if not model_path:
            return False
        try:
            import json
            import sounddevice as sd
            import vosk
        except ImportError:
            return False

        try:
            model = vosk.Model(model_path)
            recognizer = vosk.KaldiRecognizer(model, 16000)
            audio_queue: queue.Queue[bytes] = queue.Queue()
            self.engine = "vosk"
            self.emit("voice.engine", {"engine": self.engine, "model": model_path})

            def callback(indata, frames, time_info, status) -> None:
                if status:
                    self.emit("voice.status", {"status": str(status)})
                audio_queue.put(bytes(indata))

            with sd.RawInputStream(
                samplerate=16000,
                blocksize=8000,
                dtype="int16",
                channels=1,
                callback=callback,
            ):
                while not self._stop.is_set():
                    if not self.enabled:
                        time.sleep(0.2)
                        continue
                    chunk = audio_queue.get(timeout=0.5)
                    if recognizer.AcceptWaveform(chunk):
                        result = json.loads(recognizer.Result())
                        text = (result.get("text") or "").strip()
                        self._handle_text(text, "vosk")
            return True
        except Exception as exc:
            self.emit("voice.error", {"error": f"Vosk no pudo iniciar: {exc}"})
            return False

    def _fallback_stt_loop(self) -> None:
        if VoiceManager is None:
            self.engine = "unavailable"
            self.emit("voice.error", {"error": "VoiceManager no esta disponible"})
            return

        try:
            self._voice = VoiceManager(
                tts_enabled=True,
                stt_enabled=True,
                language=self.language,
            )
            self.engine = "speech_recognition"
            self.emit("voice.engine", {"engine": self.engine})
        except Exception as exc:
            self.engine = "unavailable"
            self.emit("voice.error", {"error": f"No se pudo iniciar voz: {exc}"})
            return

        while not self._stop.is_set():
            if not self.enabled:
                time.sleep(0.2)
                continue
            text = self._voice.listen()
            self._handle_text(text or "", "speech_recognition")

    def _handle_text(self, text: str, source: str) -> None:
        text = text.strip()
        if not text:
            return

        self.emit("voice.heard", {"text": text, "source": source})
        lowered = text.lower()
        if self.wake_word_enabled:
            if self.wake_word not in lowered:
                self.emit("voice.ignored", {"text": text, "reason": "wake_word"})
                return
            command = lowered.split(self.wake_word, 1)[1].strip(" ,.:;-")
            if not command:
                self.emit("voice.wake", {"wake_word": self.wake_word})
                return
            text = command

        self.on_text(text, source)

    def speak_async(self, text: str) -> None:
        if self._voice and getattr(self._voice, "tts_available", False):
            self._voice.speak_async(text)


class JarvisRuntime:
    def __init__(self) -> None:
        self.container = Container()
        self.registry = self.container.tool_registry
        self.bus = self.container.bus
        self.memory = MemoryManager(db_path=self.container.config.db_path)
        self.stream = EventStream()
        self.state = RuntimeState()
        self.messages: list[LLMMessage] = [LLMMessage(role="system", content=SYSTEM_PROMPT)]
        self._lock = threading.RLock()
        self.llm = self._build_llm()
        self.voice = ContinuousVoiceService(
            on_text=lambda text, source: self.chat(text, input_source="voice"),
            emit=self.emit,
        )
        self.bus.subscribe(events.WILDCARD, self._forward_bus_event)
        self._sync_state("ready")

    def _build_llm(self) -> Optional[LLMProvider]:
        config = self.container.config
        provider = config.llm_provider.lower().strip()
        if provider == "gemini" and config.gemini_api_key:
            return GeminiProvider(api_key=config.gemini_api_key, model=config.llm_model)
        if provider == "groq" and config.groq_api_key:
            return GroqProvider(api_key=config.groq_api_key, model=config.llm_model)
        if provider == "cerebras" and config.cerebras_api_key:
            return CerebrasProvider(api_key=config.cerebras_api_key)
        return None

    def _sync_state(self, status: Optional[str] = None) -> None:
        if status:
            self.state.status = status
        self.state.listening = self.voice.enabled
        self.state.wake_word_enabled = self.voice.wake_word_enabled
        self.state.wake_word = self.voice.wake_word
        self.state.voice_engine = self.voice.engine
        self.state.llm = getattr(self.llm, "model_name", "not configured") if self.llm else "not configured"
        self.stream.publish("state", self.state.to_dict())

    def _forward_bus_event(self, event: Event) -> None:
        self.stream.publish(
            "bus.event",
            {
                "name": event.name,
                "payload": event.payload,
                "source": event.source,
                "timestamp": event.timestamp.isoformat(),
            },
        )

    def emit(self, event_type: str, payload: dict) -> None:
        if event_type == "voice.engine":
            self.state.voice_engine = payload.get("engine", self.state.voice_engine)
        if event_type == "voice.heard":
            self.state.last_heard = payload.get("text", "")
        if event_type.endswith(".error"):
            self.state.last_error = payload.get("error", "")
        self.stream.publish(event_type, payload)
        self._sync_state()

    def start_listening(self) -> dict:
        self.voice.start()
        self._sync_state("listening")
        return self.state.to_dict()

    def stop_listening(self) -> dict:
        self.voice.stop()
        self._sync_state("idle")
        return self.state.to_dict()

    def configure_voice(self, wake_word_enabled: Optional[bool] = None, wake_word: Optional[str] = None) -> dict:
        self.voice.configure(wake_word_enabled=wake_word_enabled, wake_word=wake_word)
        self._sync_state()
        return self.state.to_dict()

    def chat(self, message: str, input_source: str = "text") -> dict:
        message = message.strip()
        if not message:
            return {"response": "", "success": False, "error": "Mensaje vacio"}

        if not self.llm:
            error = "LLM no configurado. Revisa LLM_PROVIDER y la API key en .env."
            self.state.last_error = error
            self.emit("assistant.error", {"error": error})
            return {"response": error, "success": False, "error": error}

        with self._lock:
            self._sync_state("thinking")
            event_name = events.USER_VOICE_INPUT if input_source == "voice" else events.USER_MESSAGE
            self.bus.publish(Event(name=event_name, payload={"text": message}, source=input_source))
            self.memory.save_message(message, source="user")
            self.messages.append(LLMMessage(role="user", content=message))
            self.emit("chat.user", {"text": message, "source": input_source})

            response = self.llm.chat(self.messages, tools=self.registry.get_all())
            if response.error:
                self.bus.publish(Event(name=events.LLM_ERROR, payload={"error": response.error}, source="llm"))
                self.state.last_error = response.error
                self._sync_state("error")
                return {"response": response.error, "success": False, "error": response.error}

            tool_used = None
            if response.tool_call:
                tool_name = response.tool_call.get("tool", "")
                params = response.tool_call.get("params", {})
                tool_used = tool_name
                confirmation = self._confirmation(tool_name, params)
                self.emit("assistant.partial", {"text": confirmation})
                self.voice.speak_async(confirmation)
                self.bus.publish(Event(name=events.LLM_TOOL_CALL, payload=response.tool_call, source="llm"))
                result = self.registry.execute(tool_name, params)
                answer = result.output if result.success else f"Error: {result.error}"
                success = result.success
            else:
                answer = response.text or "Sin respuesta."
                success = True

            self.messages.append(LLMMessage(role="assistant", content=answer))
            self.memory.save_message(answer, source="assistant")
            self.bus.publish(Event(name=events.LLM_RESPONSE, payload={"text": answer}, source="llm"))
            self.voice.speak_async(answer)

            if len(self.messages) > 9:
                self.messages = [self.messages[0]] + self.messages[-8:]

            self.state.last_response = answer
            self._sync_state("listening" if self.voice.enabled else "ready")
            self.emit("chat.assistant", {"text": answer, "tool_used": tool_used, "success": success})
            return {"response": answer, "tool_used": tool_used, "success": success}

    def stream_response(self, message: str, input_source: str = "text") -> list[dict]:
        result = self.chat(message, input_source=input_source)
        text = result.get("response", "")
        chunks = [{"type": "start", "payload": {"source": "assistant"}}]
        for word in text.split():
            chunks.append({"type": "token", "payload": {"text": word + " "}})
        chunks.append({"type": "done", "payload": result})
        return chunks

    def health(self) -> dict:
        return {
            "status": self.state.status,
            "llm": self.state.llm,
            "tools": len(self.registry.get_all()),
            "memory": self.memory.stats(),
            "voice": {
                "enabled": self.voice.enabled,
                "engine": self.voice.engine,
                "wake_word_enabled": self.voice.wake_word_enabled,
                "wake_word": self.voice.wake_word,
            },
        }

    @staticmethod
    def _confirmation(tool_name: str, params: dict) -> str:
        confirmation = TOOL_CONFIRMATIONS.get(tool_name)
        return confirmation(params) if confirmation else f"Ejecutando {tool_name}"


runtime = JarvisRuntime()
