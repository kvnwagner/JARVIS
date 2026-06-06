#!/usr/bin/env python3
"""
main.py - Punto de entrada de Jarvis
Fase 1: LLM Provider + Tool Registry
"""

from core.container import Container
from core.interfaces import Event, EventBus, LLMMessage, LLMResponse
from infrastructure import events
from llm import GeminiProvider
from tools import ToolRegistry

SYSTEM_PROMPT = """
Eres Jarvis, un asistente local. Responde en espanol, claro y breve.
Si hay herramientas disponibles y una herramienta es necesaria para cumplir
la peticion, elige exactamente una herramienta. Si no hay una herramienta util,
explica que puedes hacer con el estado actual del proyecto.
""".strip()


def build_llm(container: Container) -> GeminiProvider | None:
    """Construye el proveedor LLM configurado."""
    config = container.config
    if config.llm_provider != "gemini":
        print(f"ERROR: proveedor LLM no soportado aun: {config.llm_provider}")
        return None

    if not config.gemini_api_key:
        print("ERROR: Falta GEMINI_API_KEY en el archivo .env")
        print("Crea una clave en: https://aistudio.google.com/app/apikey")
        print("Ejemplo .env: GEMINI_API_KEY=tu_clave_aqui")
        return None

    return GeminiProvider(api_key=config.gemini_api_key, model=config.llm_model)


def attach_cli_tool_output(bus: EventBus) -> None:
    """Muestra en CLI el resultado publicado por ToolRegistry."""

    def print_tool_success(event: Event) -> None:
        print(f"Jarvis: OK {event.payload.get('output', '')}")

    def print_tool_failure(event: Event) -> None:
        print(f"Jarvis: Tool fallo: {event.payload.get('error', 'error desconocido')}")

    bus.subscribe(events.TOOL_EXECUTED, print_tool_success)
    bus.subscribe(events.TOOL_FAILED, print_tool_failure)


def publish_llm_result(response: LLMResponse, bus: EventBus) -> None:
    """Publica la respuesta del LLM sin ejecutar herramientas directamente."""
    if response.error:
        bus.publish(
            Event(
                name=events.LLM_ERROR,
                payload={"error": response.error},
                source="llm.gemini",
            )
        )
        print(f"Jarvis: {response.error}")
        return

    if response.text:
        bus.publish(
            Event(
                name=events.LLM_RESPONSE,
                payload={"text": response.text},
                source="llm.gemini",
            )
        )
        print(f"Jarvis: {response.text}")
        return

    if response.tool_call:
        tool_name = response.tool_call.get("tool", "")
        params = response.tool_call.get("params", {})
        print(f"Tool elegida: {tool_name}({params})")
        bus.publish(
            Event(
                name=events.LLM_TOOL_CALL,
                payload=response.tool_call,
                source="llm.gemini",
            )
        )
        return

    print("Jarvis: No recibi texto ni llamada a herramienta del LLM.")


def main() -> None:
    print("\nJARVIS - Fase 1")
    print("LLM Provider + Tool Registry\n")

    container = Container()
    bus = container.bus
    registry: ToolRegistry = container.tool_registry
    attach_cli_tool_output(bus)

    llm = build_llm(container)
    if llm is None:
        return

    print(f"LLM: Gemini ({llm.model_name})")
    print("Tool Registry inicializado")
    print(f"Tools registradas: {len(registry.get_all())}\n")

    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]

    while True:
        user_input = input("Tu: ").strip()
        if user_input.lower() in ["salir", "exit", "quit"]:
            break
        if not user_input:
            continue

        bus.publish(Event(name=events.USER_MESSAGE, payload={"text": user_input}, source="cli"))
        messages.append(LLMMessage(role="user", content=user_input))

        response = llm.chat(messages, tools=registry.get_all())
        if response.text:
            messages.append(LLMMessage(role="assistant", content=response.text))

        publish_llm_result(response, bus)


if __name__ == "__main__":
    main()
