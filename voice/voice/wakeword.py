"""
voice/wakeword.py
Detección de "Hey Jarvis" 100% local (sin nube) usando openWakeWord.

Corre en un hilo daemon escuchando el micrófono en streaming permanente,
con costo de CPU bajo — a diferencia de mandar audio continuo a Google STT.

Doble uso:
  1. Jarvis "dormido" -> detecta "Hey Jarvis" -> dispara on_wake() para
     empezar a escuchar el comando real.
  2. Jarvis hablando (TTS activo) -> detecta "Hey Jarvis" otra vez ->
     se interpreta como orden de INTERRUMPIR, dispara on_interrupt()
     en vez de on_wake(). Así "para" se resuelve diciendo el wake word
     de nuevo mientras habla, sin necesitar un modelo de voz separado
     para la palabra "para" ni STT en la nube corriendo todo el tiempo.
"""

import logging
import threading
import time
from typing import Callable, Optional

logger = logging.getLogger("jarvis.wakeword")


class WakeWordDetector:
    def __init__(
        self,
        on_wake: Callable[[], None],
        threshold: float = 0.5,
        sample_rate: int = 16000,
        chunk_size: int = 1280,  # ~80ms a 16kHz, tamaño esperado por openWakeWord
        model_name: str = "hey_jarvis_v0.1",
        is_speaking: Optional[Callable[[], bool]] = None,
        on_interrupt: Optional[Callable[[], None]] = None,
        cooldown: float = 1.5,
    ):
        try:
            import openwakeword
            from openwakeword.model import Model
        except ImportError as exc:
            raise ImportError(
                "Falta openwakeword. Instala con: pip install openwakeword"
            ) from exc

        try:
            import sounddevice as sd
        except ImportError as exc:
            raise ImportError(
                "Falta sounddevice. Instala requirements.txt de nuevo."
            ) from exc

        self._sd = sd
        self._threshold = threshold
        self._sample_rate = sample_rate
        self._chunk_size = chunk_size
        self._on_wake = on_wake
        self._is_speaking = is_speaking or (lambda: False)
        self._on_interrupt = on_interrupt
        self._cooldown = cooldown
        self._last_trigger = 0.0

        # Descarga el modelo preentrenado la primera vez (requiere internet
        # solo esa vez; después queda cacheado localmente).
        try:
            openwakeword.utils.download_models([model_name])
        except Exception as exc:
            logger.warning("No se pudieron verificar/descargar modelos: %s", exc)

        self._model = Model(wakeword_models=[model_name], inference_framework="onnx")
        self._model_key = model_name

        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        logger.info("WakeWordDetector listo - modelo: %s", model_name)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="jarvis-wakeword")
        self._thread.start()
        logger.info("WakeWordDetector escuchando en segundo plano")

    def stop(self) -> None:
        self._stop_event.set()

    def _loop(self) -> None:
        try:
            with self._sd.InputStream(
                samplerate=self._sample_rate,
                channels=1,
                dtype="int16",
                blocksize=self._chunk_size,
            ) as stream:
                while not self._stop_event.is_set():
                    audio_chunk, _ = stream.read(self._chunk_size)
                    audio_flat = audio_chunk.reshape(-1)

                    prediction = self._model.predict(audio_flat)
                    score = prediction.get(self._model_key, 0.0)

                    if score >= self._threshold:
                        self._handle_trigger()
        except Exception as exc:
            logger.error("WakeWordDetector se detuvo por error: %s", exc)

    def _handle_trigger(self) -> None:
        now = time.time()
        if now - self._last_trigger < self._cooldown:
            return  # evita disparos repetidos por la misma frase
        self._last_trigger = now

        if self._is_speaking():
            logger.info("Wake word detectada MIENTRAS Jarvis hablaba -> interrumpir")
            if self._on_interrupt:
                self._on_interrupt()
        else:
            logger.info("Wake word detectada -> despertar")
            self._on_wake()

    @property
    def available(self) -> bool:
        return self._thread is not None and self._thread.is_alive()