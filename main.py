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
from llm import GroqProvider
from tools import ToolRegistry

SYSTEM_PROMPT = """
Eres Jarvis, un asistente local. Responde en español, claro y breve.

HERRAMIENTAS DISPONIBLES:
- clima/weather: cuando pregunten por el tiempo o temperatura de una ciudad
- noticias/news: cuando pidan noticias o qué pasó en algún lugar o tema
- email: cuando pidan enviar un correo a alguien
- spotify con action=play: cuando pidan reproducir, poner o escuchar música. NUNCA uses action=search para reproducir.
- open_app: cuando pidan abrir una aplicación que NO sea el televisor.
- screenshot: cuando pidan tomar una captura de pantalla

REGLAS IMPORTANTES:
- Solo usa una herramienta si el usuario EXPLÍCITAMENTE pide una acción.
- Para preguntas generales, matemáticas, información o conversación: responde con texto directamente, SIN usar herramientas.
- Cuando el usuario pida enviar un correo, usa EXACTAMENTE el destinatario que menciona en su mensaje actual.
- Para Spotify: cuando el usuario diga "pon", "reproduce", "escucha" o similar, SIEMPRE usa action=play con el query de la canción.

HERRAMIENTAS DEL HOGAR:
- Para controlar luces usa: controlar_luz con entity_id y action (on/off) y brightness opcional.
- Para controlar clima usa: controlar_clima con entity_id, temperature y mode opcional.
- Para consultar dispositivos usa: consultar_estado_hogar con entity_id.
- Para activar escenas usa: ejecutar_escena con entity_id.
- Para controlar el televisor/TV usa SIEMPRE: controlar_tv con action. NUNCA uses open_app para el TV.
  - "apaga el televisor" → controlar_tv action=turn_off
  - "enciende el televisor" → controlar_tv action=turn_on
  - "sube el volumen del TV" → controlar_tv action=volume_up
  - "baja el volumen del TV" → controlar_tv action=volume_down
  - "silencia el TV" → controlar_tv action=mute
  - "pausa el TV" → controlar_tv action=pause
  - "reproduce el TV" → controlar_tv action=play
""".strip()


def build_llm(container: Container):
    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        print("ERROR: Falta GROQ_API_KEY en el archivo .env")
        return None
    print("LLM: Groq (llama-3.3-70b-versatile)")
    return GroqProvider(api_key=groq_key, model="llama-3.3-70b-versatile")


def attach_cli_tool_output(bus: EventBus) -> None:
    def print_tool_success(event: Event) -> None:
        output = event.payload.get("output", "")
        print(f"Jarvis: {output}")

    def print_tool_failure(event: Event) -> None:
        print(f"Jarvis: Tool falló: {event.payload.get('error', 'error desconocido')}")

    bus.subscribe(events.TOOL_EXECUTED, print_tool_success)
    bus.subscribe(events.TOOL_FAILED, print_tool_failure)


def main() -> None:
    print("\nJARVIS")
    print("=" * 30 + "\n")

    container = Container()
    bus = container.bus
    registry: ToolRegistry = container.tool_registry
    attach_cli_tool_output(bus)

    llm = build_llm(container)
    if llm is None:
        return

    print(f"Tools registradas: {len(registry.get_all())}\n")

    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]

    while True:
        try:
            user_input = input("Tu: ").strip()
        except KeyboardInterrupt:
            print("\nHasta luego.")
            break

        if user_input.lower() in ["salir", "exit", "quit"]:
            break
        if not user_input:
            continue

        bus.publish(Event(name=events.USER_MESSAGE, payload={"text": user_input}, source="cli"))
        messages.append(LLMMessage(role="user", content=user_input))

        response = llm.chat(messages, tools=registry.get_all())

        if response.error:
            bus.publish(Event(name=events.LLM_ERROR, payload={"error": response.error}, source="llm"))
            print(f"Jarvis: Error — {response.error}")
            continue

        if response.tool_call:
            tool_name = response.tool_call.get("tool", "")
            params = response.tool_call.get("params", {})
            print(f"Tool elegida: {tool_name}({params})")
            bus.publish(Event(name=events.LLM_TOOL_CALL, payload=response.tool_call, source="llm"))

            result = registry.execute(tool_name, params)
            tool_output = result.output if result.success else f"Error: {result.error}"

            interpretation_messages = [
                LLMMessage(role="system", content=SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_input),
                LLMMessage(
                    role="user",
                    content=(
                        f"La herramienta '{tool_name}' devolvió este resultado: {tool_output}. "
                        f"Responde al usuario en español natural y amigable basándote en ese resultado. "
                        f"No uses herramientas, solo responde con texto."
                    )
                ),
            ]
            final = llm.chat(interpretation_messages, tools=None)
            answer = final.text or tool_output
            messages.append(LLMMessage(role="assistant", content=answer))
            bus.publish(Event(name=events.LLM_RESPONSE, payload={"text": answer}, source="llm"))
            print(f"Jarvis: {answer}")

        elif response.text:
            messages.append(LLMMessage(role="assistant", content=response.text))
            bus.publish(Event(name=events.LLM_RESPONSE, payload={"text": response.text}, source="llm"))
            print(f"Jarvis: {response.text}")

        else:
            print("Jarvis: No recibí texto ni llamada a herramienta del LLM.")

        if len(messages) > 7:
            messages = [messages[0]] + messages[-6:]


if __name__ == "__main__":
    main()