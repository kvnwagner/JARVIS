#!/usr/bin/env python3
"""
main.py - Punto de entrada de Jarvis
"""

from core.container import Container
from core.interfaces import Event, LLMMessage
from infrastructure import events
from llm import GeminiProvider
from tools import ToolRegistry

SYSTEM_PROMPT = """
Eres Jarvis, un asistente local. Responde en español, claro y breve.

REGLAS IMPORTANTES:
- Solo usa una herramienta si el usuario EXPLÍCITAMENTE pide una acción.
- Para preguntas generales, matemáticas, información o conversación: responde con texto directamente, SIN usar herramientas.
- Ejemplos de cuando NO usar herramientas: "cuanto es 2+2", "quien es Blessd", "como estás".
- Ejemplos de cuando SÍ usar herramientas: "abre spotify", "sube el volumen", "apaga la luz del salón", "pon el clima a 22 grados".

HERRAMIENTAS DEL HOGAR:
- Para controlar luces usa: controlar_luz con entity_id, action (on/off) y brightness opcional.
- Para controlar clima usa: controlar_clima con entity_id, temperature y mode opcional.
- Para consultar dispositivos usa: consultar_estado_hogar con entity_id.
- Para activar escenas usa: ejecutar_escena con entity_id.
""".strip()


def build_llm(container: Container) -> GeminiProvider | None:
    config = container.config
    if config.llm_provider != "gemini":
        print(f"ERROR: proveedor LLM no soportado: {config.llm_provider}")
        return None
    if not config.gemini_api_key:
        print("ERROR: Falta GEMINI_API_KEY en .env")
        return None
    return GeminiProvider(api_key=config.gemini_api_key, model=config.llm_model)


def main() -> None:
    print("\nJARVIS")
    print("=" * 30 + "\n")

    container = Container()
    registry: ToolRegistry = container.tool_registry

    llm = build_llm(container)
    if llm is None:
        return

    print(f"LLM: Gemini ({llm.model_name})")
    print(f"Tools registradas: {len(registry.get_all())}\n")

    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]

    while True:
        user_input = input("Tu: ").strip()
        if user_input.lower() in ["salir", "exit", "quit"]:
            break
        if not user_input:
            continue

        messages.append(LLMMessage(role="user", content=user_input))

        # Primera llamada: Gemini decide si usar tool o responder directo
        response = llm.chat(messages, tools=registry.get_all())

        if response.error:
            print(f"Jarvis: Error — {response.error}")
            continue

        if response.tool_call:
            tool_name = response.tool_call.get("tool", "")
            params = response.tool_call.get("params", {})

            # Ejecutar la tool silenciosamente
            result = registry.execute(tool_name, params)
            tool_output = result.output if result.success else f"Error: {result.error}"

            # Segunda llamada: le pedimos a Gemini que interprete el resultado
            # Usamos un mensaje directo sin historial de tools para evitar loop
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
            print(f"Jarvis: {answer}")

        elif response.text:
            messages.append(LLMMessage(role="assistant", content=response.text))
            print(f"Jarvis: {response.text}")


if __name__ == "__main__":
    main()