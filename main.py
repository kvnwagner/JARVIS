# ================================================================
# main.py — Punto de entrada de Jarvis
# Fase 0.75: arranca el sistema y verifica que el bus
# y el logger están conectados y funcionando.
# ================================================================

import logging
from core.container import Container
from core.interfaces import Event
from infrastructure import events

log = logging.getLogger("jarvis.main")


def main():
    print("\n╔══════════════════════════════════════╗")
    print("║         JARVIS — Fase 0.75           ║")
    print("║   EventBus + Logging operativos      ║")
    print("╚══════════════════════════════════════╝\n")

    # Arrancar el sistema completo
    container = Container(log_level="INFO", log_file="logs/jarvis.log")
    bus = container.bus

    log.info("Sistema iniciado correctamente")

    # ── Demostración: simular un flujo real de eventos ──────────
    # Esto no es código de producción — es para verificar
    # que bus + logger funcionan antes de pasar a Fase 1.

    # Simula lo que hará Memory en Fase 4
    memoria_simulada = []
    bus.subscribe(events.TOOL_EXECUTED, lambda e: memoria_simulada.append(e))
    bus.subscribe(events.USER_MESSAGE,  lambda e: memoria_simulada.append(e))

    print("── Simulando flujo de eventos ──────────────────────────\n")

    bus.publish(Event(
        name=events.SYSTEM_READY,
        payload={"version": "0.75", "phase": "EventBus + Logging"},
        source="main"
    ))

    bus.publish(Event(
        name=events.USER_MESSAGE,
        payload={"text": "Jarvis, abre Spotify"},
        source="cli"
    ))

    bus.publish(Event(
        name=events.LLM_TOOL_CALL,
        payload={"tool": "open_app", "params": {"app": "spotify"}},
        source="gemini"
    ))

    bus.publish(Event(
        name=events.TOOL_EXECUTED,
        payload={"success": True, "output": "Spotify abierto", "tool": "open_app"},
        source="open_app"
    ))

    bus.publish(Event(
        name=events.MEMORY_SAVED,
        payload={"entry": "Usuario pidió abrir Spotify"},
        source="memory"
    ))

    # ── Resultado ───────────────────────────────────────────────
    print(f"\n── Resultado ───────────────────────────────────────────\n")
    print(f"  Módulos que recibieron eventos : memoria simulada")
    print(f"  Eventos capturados             : {len(memoria_simulada)}")
    for e in memoria_simulada:
        print(f"    • {e.name}")

    print("\n  Log guardado en : logs/jarvis.log")
    print("\n✓ Fase 0.75 operativa — listo para Fase 1\n")


if __name__ == "__main__":
    main()