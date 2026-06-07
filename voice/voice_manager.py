import logging
from typing import Callable, Optional

from voice.stt import JarvisSTT
from voice.tts import JarvisTTS

logger = logging.getLogger("jarvis.voice")


class VoiceManager:
    def __init__(
        self,
        tts_enabled: bool = True,
        stt_enabled: bool = True,
        prefer_edge_tts: bool = True,
        language: str = "es-CO",
        tts_rate: int = 175,
        tts_volume: float = 0.95,
    ):
        self._tts: Optional[JarvisTTS] = None
        self._stt: Optional[JarvisSTT] = None

        if tts_enabled:
            try:
                self._tts = JarvisTTS(rate=tts_rate, volume=tts_volume)
            except Exception as exc:
                logger.warning("No se pudo iniciar TTS: %s", exc)

        if stt_enabled:
            try:
                self._stt = JarvisSTT(language=language)
            except Exception as exc:
                logger.warning("No se pudo iniciar STT: %s", exc)

        logger.info(
            "VoiceManager listo - TTS=%s | STT=%s",
            "ok" if self.tts_available else "no disponible",
            "ok" if self.stt_available else "no disponible",
        )

    def speak(self, text: str) -> None:
        if self._tts and self._tts.available:
            self._tts.speak(text)

    def speak_async(self, text: str) -> None:
        if self._tts and self._tts.available:
            self._tts.speak_async(text)

    def stop_speaking(self) -> None:
        if self._tts:
            self._tts.stop()

    def toggle_voice(self) -> bool:
        if self._tts:
            return self._tts.toggle()
        return False

    def listen(self) -> Optional[str]:
        if not self._stt:
            return None
        return self._stt.listen()

    def start_listening(self, callback: Callable[[str], None]) -> None:
        if self._stt:
            self._stt.start_listening(callback)

    def stop_listening(self) -> None:
        if self._stt:
            self._stt.stop_listening()

    @property
    def tts_available(self) -> bool:
        return bool(self._tts and self._tts.available)

    @property
    def stt_available(self) -> bool:
        return bool(self._stt and self._stt.available)
