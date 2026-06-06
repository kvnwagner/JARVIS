# ================================================================
# infrastructure/events.py
# Catálogo oficial de eventos del sistema
# REGLA: siempre usar estas constantes — nunca strings sueltos
# Propietario: todos — coordinar antes de añadir eventos nuevos
# ================================================================


# ─── Wildcard ────────────────────────────────────────────────
WILDCARD = "*"          # handlers que escuchan TODOS los eventos


# ─── Usuario ─────────────────────────────────────────────────
USER_MESSAGE     = "user.message"     # usuario envía texto
USER_VOICE_INPUT = "user.voice_input" # usuario habla (fase 8)


# ─── LLM ─────────────────────────────────────────────────────
LLM_RESPONSE     = "llm.response"     # LLM devolvió texto
LLM_TOOL_CALL    = "llm.tool_call"    # LLM eligió una herramienta
LLM_ERROR        = "llm.error"        # LLM falló o timeout


# ─── Tools ───────────────────────────────────────────────────
TOOL_STARTED     = "tool.started"     # tool comenzó a ejecutar
TOOL_EXECUTED    = "tool.executed"    # tool completó con éxito
TOOL_FAILED      = "tool.failed"      # tool lanzó error


# ─── Windows (fase 3) ────────────────────────────────────────
APP_OPENED       = "windows.app_opened"
APP_CLOSED       = "windows.app_closed"
VOLUME_CHANGED   = "windows.volume_changed"


# ─── Memory (fase 4) ─────────────────────────────────────────
MEMORY_SAVED     = "memory.saved"
MEMORY_RETRIEVED = "memory.retrieved"


# ─── Home Assistant (fase 6) ─────────────────────────────────
DEVICE_CHANGED   = "ha.device_changed"
SCENE_ACTIVATED  = "ha.scene_activated"


# ─── Sistema ─────────────────────────────────────────────────
SYSTEM_ERROR     = "system.error"
SYSTEM_READY     = "system.ready"


# ─── Uso correcto ─────────────────────────────────────────────
#
#   from infrastructure.events import TOOL_EXECUTED
#
#   bus.publish(Event(
#       name    = TOOL_EXECUTED,       ← constante
#       payload = result.__dict__,
#       source  = tool.name
#   ))
#
#   bus.subscribe(TOOL_EXECUTED, my_handler)
#
# NUNCA:
#   bus.subscribe("TOOL_EXECUTED", ...)   ← string suelto, error silencioso