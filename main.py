#!/usr/bin/env python3
"""
main.py - Punto de entrada de Jarvis
"""

import os
from dotenv import load_dotenv
load_dotenv()

from core.container import Container
from core.interfaces import Event, EventBus, LLMMessage, LLMResponse
from infrastructure import events
from llm import GeminiProvider, GroqProvider
from tools import ToolRegistry

SYSTEM_PROMPT = """
Eres Jarvis, un asistente local. Responde en español, claro y breve.

HERRAMIENTAS DISPONIBLES:
- clima/weather: cuando pregunten por el tiempo o temperatura de una ciudad
- noticias/news: cuando pidan noticias o qué pasó en algún lugar o tema
- email: cuando pidan enviar un correo a alguien
- spotify con action=play: cuando pidan reproducir, poner o escuchar música. NUNCA uses action=search para reproducir.
- open_app: cuando pidan abrir una aplicación
- screenshot: cuando pidan tomar una captura de pantalla

REGLAS:
- Usa la herramienta correspondiente según lo que el usuario pida.
- Para preguntas generales, matemáticas o conversación: responde con texto directamente.
- Cuando el usuario pida enviar un correo, usa EXACTAMENTE el destinatario que menciona en su mensaje actual.
- Para Spotify: cuando el usuario diga "pon", "reproduce", "escucha" o similar, SIEMPRE usa action=play con el query de la canción.
""".strip()


def build_llm(container: Container):
    groq_key = os.getenv("GROQ_API_KEY", "")
    if groq_key:
        print("LLM: Groq (llama-3.3-70b-versatile)")
        return GroqProvider(api_key=groq_key, model="llama-3.3-70b-versatile")

    config = container.config
    if not config.gemini_api_key:
        print("ERROR: Falta GROQ_API_KEY o GEMINI_API_KEY en el archivo .env")
        return None

    print(f"LLM: Gemini ({config.llm_model})")
    return GeminiProvider(api_key=config.gemini_api_key, model=config.llm_model)


def attach_cli_tool_output(bus: EventBus) -> None:
    def print_tool_success(event: Event) -> None:
        print(f"Jarvis: OK {event.payload.get('output', '')}")

    def print_tool_failure(event: Event) -> None:
        print(f"Jarvis: Tool fallo: {event.payload.get('error', 'error desconocido')}")

    bus.subscribe(events.TOOL_EXECUTED, print_tool_success)
    bus.subscribe(events.TOOL_FAILED, print_tool_failure)


def publish_llm_result(response: LLMResponse, bus: EventBus, registry: ToolRegistry, messages: list) -> None:
    if response.error:
        bus.publish(Event(name=events.LLM_ERROR, payload={"error": response.error}, source="llm"))
        print(f"Jarvis: {response.error}")
        return

    if response.text:
        bus.publish(Event(name=events.LLM_RESPONSE, payload={"text": response.text}, source="llm"))
        print(f"Jarvis: {response.text}")
        return

    if response.tool_call:
        tool_name = response.tool_call.get("tool", "")
        params    = response.tool_call.get("params", {})
        print(f"Tool elegida: {tool_name}({params})")
        bus.publish(Event(name=events.LLM_TOOL_CALL, payload=response.tool_call, source="llm"))
        # El registry ejecuta la tool automáticamente via handle_llm_tool_call
        return

    print("Jarvis: No recibí texto ni llamada a herramienta del LLM.")


def main() -> None:
    print("\nJARVIS")
    print("LLM Provider + Tool Registry\n")

    container = Container()
    bus       = container.bus
    registry: ToolRegistry = container.tool_registry
    attach_cli_tool_output(bus)

    llm = build_llm(container)
    if llm is None:
        return

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

        publish_llm_result(response, bus, registry, messages)

        # Mantener solo system prompt + últimos 6 mensajes para evitar contexto largo
        if len(messages) > 7:
            messages = [messages[0]] + messages[-6:]


if __name__ == "__main__":
    main()