# ================================================================
# infrastructure/reminder_scheduler.py
# Hilo daemon que revisa recordatorios cada 30 segundos y avisa
# por consola, voz (TTS) y EventBus (→ WebSocket frontend).
# ================================================================

import logging
import threading
from datetime import datetime
from typing import Optional

from tools.external.reminder_tool import get_pending_reminders, mark_fired

logger = logging.getLogger("jarvis.reminders")


class ReminderScheduler:
    """
    Corre en un hilo daemon. Cada 30 segundos revisa los recordatorios
    pendientes en SQLite y dispara los que coincidan con la hora actual.

    Uso:
        scheduler = ReminderScheduler(voice=voice_manager, bus=event_bus)
        scheduler.start()
    """

    def __init__(self, voice=None, bus=None):
        self._voice = voice
        self._bus = bus
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Arranca el hilo background. Llamar UNA sola vez al iniciar Jarvis."""
        if self._thread and self._thread.is_alive():
            logger.warning("ReminderScheduler ya está corriendo.")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop,
            name="jarvis-reminder-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info("ReminderScheduler activo — revisando cada 30 segundos")

    def stop(self) -> None:
        """Detiene el scheduler limpiamente."""
        self._stop_event.set()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._check()
            except Exception as exc:
                logger.error("Error en ReminderScheduler: %s", exc)
            self._stop_event.wait(timeout=30)

    def _check(self) -> None:
        """Revisa recordatorios pendientes y dispara los que toca."""
        now = datetime.now().strftime("%H:%M")
        pending = get_pending_reminders()

        for reminder in pending:
            if reminder["time"] == now:
                self._fire(reminder)

    def _fire(self, reminder: dict) -> None:
        """Dispara un recordatorio: consola + voz + EventBus."""
        message = reminder["message"]
        reminder_id = reminder["id"]

        # Marcar como disparado ANTES de notificar para evitar repetición
        mark_fired(reminder_id)

        alert = f"🔔 RECORDATORIO: {message}"
        print(f"\nJarvis: {alert}\n")
        logger.info("Recordatorio disparado: %s", message)

        # Notificar al EventBus para que llegue al WebSocket
        if self._bus:
            try:
                from core.interfaces import Event
                self._bus.publish(Event(
                    name="reminder.fired",
                    payload={
                        "message": message,
                        "id": reminder_id,
                        "alert": alert,
                    },
                    source="reminder_scheduler",
                ))
            except Exception as exc:
                logger.error("Error publicando evento reminder.fired: %s", exc)

        # Notificar por voz si está disponible
        if self._voice and self._voice.tts_available:
            self._voice.speak_async(f"Recordatorio: {message}")