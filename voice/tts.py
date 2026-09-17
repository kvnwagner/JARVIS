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
        self._control_path: str | None = None

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

    @property
    def is_speaking(self) -> bool:
        return self._playback_proc is not None and self._playback_proc.poll() is None

    def speak(self, text: str) -> None:
        if not self._enabled or not text or not text.strip():
            return

        with self._lock:
            try:
                import edge_tts

                mp3_path = os.path.join(tempfile.gettempdir(), "jarvis_tts.mp3")
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

                self._paused = False
                self._pause_event.set()
                self._play_mp3(mp3_path)
            except Exception as exc:
                logger.error("Error en TTS: %s", exc)

    def speak_async(self, text: str) -> None:
        thread = threading.Thread(target=self.speak, args=(text,), daemon=True)
        thread.start()

    def _write_control(self, cmd: str) -> None:
        if not self._control_path:
            return
        try:
            with open(self._control_path, "w", encoding="utf-8") as f:
                f.write(cmd)
        except Exception as exc:
            logger.error("Error escribiendo control TTS: %s", exc)

    def pause(self) -> None:
        """Pausa la reproducción actual (real: llama $player.Pause() vía archivo de control)."""
        if not self._paused and self.is_speaking:
            self._paused = True
            self._pause_event.clear()
            self._write_control("PAUSE")
            logger.info("TTS pausado")

    def resume(self) -> None:
        """Reanuda la reproducción pausada."""
        if self._paused:
            self._paused = False
            self._pause_event.set()
            self._write_control("PLAY")
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
        self._write_control("STOP")
        if self._playback_proc and self._playback_proc.poll() is None:
            self._playback_proc.terminate()

    def toggle(self) -> bool:
        self._enabled = not self._enabled
        return self._enabled

    def _play_mp3(self, mp3_path: str) -> None:
        control_path = os.path.join(tempfile.gettempdir(), "jarvis_tts_control.txt")
        with open(control_path, "w", encoding="utf-8") as f:
            f.write("PLAY")
        self._control_path = control_path

        ps_script = f"""
Add-Type -AssemblyName PresentationCore
$player = New-Object System.Windows.Media.MediaPlayer
$player.Open([System.Uri]::new('{mp3_path}'))
$controlPath = '{control_path}'
$player.Play()
$isPaused = $false
$waited = 0
while ($player.NaturalDuration.HasTimeSpan -eq $false -and $waited -lt 10) {{
    Start-Sleep -Milliseconds 100
    $waited++
}}
$dur = 1
if ($player.NaturalDuration.HasTimeSpan) {{
    $dur = $player.NaturalDuration.TimeSpan.TotalSeconds
}}
while ($true) {{
    Start-Sleep -Milliseconds 150
    $cmd = "PLAY"
    try {{ $cmd = (Get-Content -Path $controlPath -ErrorAction Stop -Raw).Trim() }} catch {{}}

    if ($cmd -eq "STOP") {{
        $player.Stop()
        break
    }}
    elseif ($cmd -eq "PAUSE" -and -not $isPaused) {{
        $player.Pause()
        $isPaused = $true
    }}
    elseif ($cmd -eq "PLAY" -and $isPaused) {{
        $player.Play()
        $isPaused = $false
    }}

    if (-not $isPaused -and $player.Position.TotalSeconds -ge ($dur - 0.15)) {{
        break
    }}
}}
$player.Close()
"""
        self._playback_proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._playback_proc.wait()
        self._playback_proc = None