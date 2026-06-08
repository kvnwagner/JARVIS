import asyncio
import logging
import os
import subprocess
import tempfile
import threading

logger = logging.getLogger("jarvis.tts")


class JarvisTTS:
    def __init__(
        self,
        voice: str = "es-ES-AlvaroNeural",
        rate: int = 175,
        volume: float = 0.95,
    ):
        self._voice = voice
        self._enabled = True
        self._lock = threading.Lock()
        self._rate = rate
        self._volume = volume

        # Control de pausa
        self._paused = False
        self._pause_event = threading.Event()
        self._pause_event.set()  # inicia sin pausa
        self._playback_proc: subprocess.Popen | None = None

        try:
            import edge_tts  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "Falta edge-tts. Instala requirements.txt de nuevo."
            ) from exc

        logger.info("JarvisTTS listo - voz: %s", voice)

    @property
    def available(self) -> bool:
        try:
            import edge_tts  # noqa: F401
            return True
        except ImportError:
            return False

    def speak(self, text: str) -> None:
        if not self._enabled or not text or not text.strip():
            return

        with self._lock:
            try:
                import edge_tts

                mp3_path = os.path.join(tempfile.gettempdir(), "jarvis_tts.mp3")

                # Velocidad original + 25% → rate="+25%"
                rate_str = "+25%"

                async def generate_audio() -> None:
                    communicate = edge_tts.Communicate(
                        text.strip(),
                        self._voice,
                        rate=rate_str,
                    )
                    await communicate.save(mp3_path)

                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(generate_audio())
                finally:
                    loop.close()

                self._play_mp3(mp3_path)
            except Exception as exc:
                logger.error("Error en TTS: %s", exc)

    def speak_async(self, text: str) -> None:
        thread = threading.Thread(target=self.speak, args=(text,), daemon=True)
        thread.start()

    def pause(self) -> None:
        """Pausa la reproducción actual."""
        if not self._paused:
            self._paused = True
            self._pause_event.clear()
            if self._playback_proc and self._playback_proc.poll() is None:
                # Suspende el proceso de PowerShell en Windows
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     f"Suspend-Process -Id {self._playback_proc.pid} -ErrorAction SilentlyContinue"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
            logger.info("TTS pausado")

    def resume(self) -> None:
        """Reanuda la reproducción pausada."""
        if self._paused:
            self._paused = False
            self._pause_event.set()
            if self._playback_proc and self._playback_proc.poll() is None:
                subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                     f"Resume-Process -Id {self._playback_proc.pid} -ErrorAction SilentlyContinue"],
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
            logger.info("TTS reanudado")

    def toggle_pause(self) -> bool:
        """Alterna entre pausa y reproducción. Retorna True si quedó pausado."""
        if self._paused:
            self.resume()
        else:
            self.pause()
        return self._paused

    def stop(self) -> None:
        """Detiene la reproducción completamente."""
        self._paused = False
        self._pause_event.set()
        if self._playback_proc and self._playback_proc.poll() is None:
            self._playback_proc.terminate()

    def toggle(self) -> bool:
        self._enabled = not self._enabled
        return self._enabled

    def _play_mp3(self, mp3_path: str) -> None:
        ps_script = f"""
Add-Type -AssemblyName PresentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$player.Open([System.Uri]::new('{mp3_path}'))
$player.Play()
Start-Sleep -Milliseconds 500
$dur = 0
$waited = 0
while ($player.NaturalDuration.HasTimeSpan -eq $false -and $waited -lt 10) {{
    Start-Sleep -Milliseconds 100
    $waited++
}}
if ($player.NaturalDuration.HasTimeSpan) {{
    $dur = $player.NaturalDuration.TimeSpan.TotalSeconds
}}
Start-Sleep -Seconds ([Math]::Max($dur, 1) + 0.3)
$player.Close()
"""
        self._playback_proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._playback_proc.wait()
        self._playback_proc = None