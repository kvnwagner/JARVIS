#!/usr/bin/env python3
"""
main.py — Punto de entrada de Jarvis
Fase 1: LLM Provider + Tool Registry
"""

from core.container import Container
from core.interfaces import Event, LLMMessage, LLMResponse
from infrastructure import events
from llm import GeminiProvider
from tools import ToolRegistry

SYSTEM_PROMPT = """
Eres Jarvis, un asistente local. Responde en español, claro y breve.
Si hay herramientas disponibles y una herramienta es necesaria para cumplir
la petición, elige exactamente una herramienta. Si no hay una herramienta útil,
explica qué puedes hacer con el estado actual del proyecto.
""".strip()


def build_llm(container: Container) -> GeminiProvider | None:
    """Construye el proveedor LLM configurado."""
    config = container.config
    if config.llm_provider != "gemini":
        print(f"❌ ERROR: proveedor LLM no soportado aún: {config.llm_provider}")
        return None

    if not config.gemini_api_key:
        print("❌ ERROR: Falta GEMINI_API_KEY en el archivo .env")
        print("   Crea una clave en: https://aistudio.google.com/app/apikey")
        print("   Ejemplo .env: GEMINI_API_KEY=tu_clave_aqui")
        return None

    return GeminiProvider(api_key=config.gemini_api_key, model=config.llm_model)


def handle_llm_response(response: LLMResponse, registry: ToolRegistry) -> None:
    """Completa el flujo LLM → Tool Registry → Tool → EventBus."""
    if response.error:
        print(f"Jarvis: ❌ {response.error}")
        return

    if response.text:
        print(f"Jarvis: {response.text}")
        return

    if not response.tool_call:
        print("Jarvis: No recibí texto ni llamada a herramienta del LLM.")
        return

    tool_name = response.tool_call.get("tool", "")
    params = response.tool_call.get("params", {})
    print(f"🔧 Tool elegida: {tool_name}({params})")

    result = registry.execute(tool_name, params)
    if result.success:
        print(f"Jarvis: ✅ {result.output}")
    else:
        print(f"Jarvis: ❌ Tool falló: {result.error}")


def main() -> None:
    print("\n╔══════════════════════════════════════╗")
    print("║          JARVIS — Fase 1             ║")
    print("║   LLM Provider + Tool Registry       ║")
    print("╚══════════════════════════════════════╝\n")

    container = Container()
    bus = container.bus

    llm = build_llm(container)
    if llm is None:
        return

    print(f"✅ LLM: Gemini ({llm.model_name})")

    registry = ToolRegistry(bus)
    print("✅ Tool Registry inicializado")
    print(f"ℹ️ Tools registradas: {len(registry.get_all())}\n")

    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]

    while True:
        user_input = input("Tú: ").strip()
        if user_input.lower() in ["salir", "exit", "quit"]:
            break
        if not user_input:
            continue

        bus.publish(Event(name=events.USER_MESSAGE, payload={"text": user_input}, source="cli"))
        messages.append(LLMMessage(role="user", content=user_input))

        response = llm.chat(messages, tools=registry.get_all())

        if response.error:
            bus.publish(
                Event(
                    name=events.LLM_ERROR,
                    payload={"error": response.error},
                    source="llm.gemini",
                )
            )
        elif response.text:
            messages.append(LLMMessage(role="assistant", content=response.text))
            bus.publish(
                Event(
                    name=events.LLM_RESPONSE,
                    payload={"text": response.text},
                    source="llm.gemini",
                )
            )
        elif response.tool_call:
            bus.publish(
                Event(
                    name=events.LLM_TOOL_CALL,
                    payload=response.tool_call,
                    source="llm.gemini",
                )
            )

        handle_llm_response(response, registry)


if __name__ == "__main__":
    main()
