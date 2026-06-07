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
from llm import CerebrasProvider
from tools import ToolRegistry

SYSTEM_PROMPT = """
Eres Jarvis, un asistente personal inteligente. Respondes en español, de forma clara, natural y amigable.

INTERPRETACIÓN DE MENSAJES:
- Interpreta SIEMPRE la intención real del usuario, aunque haya errores ortográficos, abreviaciones o lenguaje informal.
- Ejemplos: "apga el tele" = apagar TV, "ke clima ay en bogota" = clima Bogotá, "pone regueton" = reproducir reggaetón, "manda correo a juan" = enviar email a juan.
- Si el mensaje es ambiguo, elige la interpretación más lógica y actúa.

HERRAMIENTAS DISPONIBLES:
- clima / weather: para preguntas sobre el tiempo, temperatura, lluvia de cualquier ciudad.
- noticias / news: para pedir noticias, novedades o qué pasó sobre algún tema o lugar.
- email: para enviar correos electrónicos a alguien.
- spotify: para reproducir, poner o escuchar música. Parámetros: action=play y query=nombre de canción o artista. NUNCA uses action=search para reproducir.
- open_app: para abrir aplicaciones del computador que NO sean el televisor.
- screenshot: para tomar capturas de pantalla.

REGLAS IMPORTANTES:
- Usa una herramienta SOLO si el usuario pide una acción concreta.
- Para preguntas generales, matemáticas, curiosidades, conversación o información: responde con texto directamente, SIN herramientas.
- Para Spotify: "pon", "reproduce", "escucha", "pone", "dale play", "quero escuchar" → SIEMPRE usa la tool spotify con action=play y query=nombre de la canción.
- Para correos: usa EXACTAMENTE el destinatario que menciona el usuario.

HERRAMIENTAS DEL HOGAR (Home Assistant):
- Luces → controlar_luz: entity_id, action (on/off), brightness opcional.
- Clima/aire → controlar_clima: entity_id, temperature, mode opcional.
- Consultar dispositivo → consultar_estado_hogar: entity_id.
- Escenas → ejecutar_escena: entity_id.
- Televisor/TV → controlar_tv: SIEMPRE usa esta para el TV, NUNCA open_app.
  - "apaga el tv / tele / televisor" → controlar_tv action=turn_off
  - "enciende el tv / tele / televisor" → controlar_tv action=turn_on
  - "sube el volumen / más volumen" → controlar_tv action=volume_up
  - "baja el volumen / menos volumen" → controlar_tv action=volume_down
  - "silencia / mutea el tv" → controlar_tv action=mute
  - "pausa el tv" → controlar_tv action=pause
  - "play el tv / reanuda" → controlar_tv action=play

TONO:
- Responde siempre en español.
- Sé conciso pero amigable, como un asistente real.
- No expliques qué herramienta usaste a menos que el usuario lo pregunte.
""".strip()


def build_llm(container: Container):
    cerebras_key = os.getenv("CEREBRAS_API_KEY", "")
    if not cerebras_key:
        print("ERROR: Falta CEREBRAS_API_KEY en el archivo .env")
        return None
    print("LLM: Cerebras (llama-3.3-70b)")
    return CerebrasProvider(api_key=cerebras_key)


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