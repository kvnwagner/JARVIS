#!/usr/bin/env python3
"""
main.py — Punto de entrada de Jarvis
Fase 1: LLM Provider + Tool Registry
"""
from core.container import Container
from core.interfaces import Event, LLMMessage
from infrastructure import events
from llm import GeminiProvider

def main():
    print("\n╔══════════════════════════════════════╗")
    print("║          JARVIS — Fase 1             ║")
    print("║   LLM Provider + Tool Registry     ║")
    print("╚══════════════════════════════════════╝\n")

    # Arrancar Container
    container = Container(log_level="INFO", log_file="logs/jarvis.log")
    bus = container.bus
    config = container.config

    # Inicializar LLM
    llm = None
    
    api_key = config.get("google", {}).get("api_key")
    if not api_key:
        print("❌ ERROR: Falta API key en config.yaml")
        print("   Ve a: https://aistudio.google.com/app/apikey")
        return
    
    llm = GeminiProvider(api_key)
    print(f"✅ LLM: Gemini ({llm.model_name})")

    # Tool Registry
    from tools import ToolRegistry
    registry = ToolRegistry(bus)
    print("✅ Tool Registry inicializado\n")

    # Loop interactivo
    while True:
        user_input = input("Tú: ")
        if user_input.lower() in ["salir", "exit", "quit"]:
            break
        
        # Publicar mensaje
        bus.publish(Event(
            name=events.USER_MESSAGE,
            payload={"text": user_input},
            source="cli"
        ))

        # Respuesta del LLM
        response = llm.chat([LLMMessage(role="user", content=user_input)])

        if response.text:
            print(f"Jarvis: {response.text}")
        elif response.tool_call:
            print(f"🔧 Tool: {response.tool_call}")

if __name__ == "__main__":
    main()