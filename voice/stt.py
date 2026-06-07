import logging
import os
import tempfile
import threading
import wave
from typing import Callable, Optional

logger = logging.getLogger("jarvis.stt")


class JarvisSTT:
    """Speech-to-text con microfono local y Google Speech Recognition."""

    def __init__(
        self,
        language: str = "es-CO",
        duration: int = 5,
        sample_rate: int = 16000,
    ):
        try:
            import sounddevice as sd
            import speech_recognition as sr
        except ImportError as exc:
            raise ImportError(
                "Faltan dependencias de voz. Instala requirements.txt de nuevo."
            ) from exc

        self._sd = sd
        self._sr = sr
        self._recognizer = sr.Recognizer()
        self._language = language
        self._duration = duration
        self._sample_rate = sample_rate
        self._stop_event = threading.Event()
        self._listening_thread: Optional[threading.Thread] = None
        logger.info("JarvisSTT iniciado - idioma: %s", language)

    def listen(self) -> Optional[str]:
        try:
            print("  Grabando...", end="", flush=True)
            audio_data = self._sd.rec(
                int(self._duration * self._sample_rate),
                samplerate=self._sample_rate,
                channels=1,
                dtype="int16",
            )
            self._sd.wait()
            print(" listo.")

            tmp_path = self._write_temp_wav(audio_data)
            try:
                with self._sr.AudioFile(tmp_path) as source:
                    audio = self._recognizer.record(source)
            finally:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

            text = self._recognizer.recognize_google(audio, language=self._language)
            logger.info("STT reconocio: %r", text)
            return text.strip()

        except self._sr.UnknownValueError:
            print("  No se entendio. Intenta de nuevo.")
            return None
        except self._sr.RequestError as exc:
            logger.error("Error en Google STT: %s", exc)
            print("  Error de conexion con Google STT.")
            return None
        except Exception as exc:
            logger.error("Error en STT: %s", exc)
            return None

    def start_listening(self, callback: Callable[[str], None]) -> None:
        if self._listening_thread and self._listening_thread.is_alive():
            return
        self._stop_event.clear()
        self._listening_thread = threading.Thread(
            target=self._listen_loop,
            args=(callback,),
            daemon=True,
        )
        self._listening_thread.start()

    def stop_listening(self) -> None:
        self._stop_event.set()

    def _listen_loop(self, callback: Callable[[str], None]) -> None:
        while not self._stop_event.is_set():
            text = self.listen()
            if text:
                try:
                    callback(text)
                except Exception as exc:
                    logger.error("Error en callback STT: %s", exc)

    def _write_temp_wav(self, audio_data) -> str:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as file:
            tmp_path = file.name

        with wave.open(tmp_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(self._sample_rate)
            wav_file.writeframes(audio_data.tobytes())

        return tmp_path

    @property
    def available(self) -> bool:
        try:
            devices = self._sd.query_devices()
            return any(device["max_input_channels"] > 0 for device in devices)
        except Exception:
            return False
