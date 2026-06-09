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
from llm import CerebrasProvider, GroqProvider
from tools import ToolRegistry

try:
    from voice import VoiceManager
    _VOICE_AVAILABLE = True
except ImportError:
    VoiceManager = None
    _VOICE_AVAILABLE = False

SYSTEM_PROMPT = """
Eres Jarvis, un asistente personal inteligente. Respondes en español, de forma clara, natural y amigable.

INTERPRETACIÓN DE MENSAJES:
- Interpreta SIEMPRE la intención real del usuario, aunque haya errores ortográficos, abreviaciones o lenguaje informal.
- Ejemplos: "apga el tele" = apagar TV, "ke clima ay en bogota" = clima Bogotá, "pone regueton" = reproducir reggaetón, "manda correo a juan" = enviar email a juan.
- Si el mensaje es ambiguo, elige la interpretación más lógica y actúa.
- Si el usuario dice solo el nombre de una aplicación (ej: "Spotify", "Chrome", "Discord"), interpreta que quiere ABRIRLA y usa open_app.

HERRAMIENTAS DISPONIBLES:
- clima / weather: para preguntas sobre el tiempo, temperatura, lluvia de cualquier ciudad.
- noticias / news: para pedir noticias, novedades o qué pasó sobre algún tema o lugar.
- email: para enviar correos electrónicos a alguien.
- spotify: para reproducir, poner o escuchar música en el computador. Parámetros: action=play y query=nombre de canción o artista. NUNCA uses action=search para reproducir.
- open_app: para abrir aplicaciones del computador que NO sean el televisor.
- screenshot: para tomar capturas de pantalla.

REGLAS IMPORTANTES:
- Usa una herramienta SOLO si el usuario pide una acción concreta.
- Para preguntas generales, matemáticas, curiosidades, conversación o información: responde con texto directamente, SIN herramientas.
- Para Spotify: "pon", "reproduce", "escucha", "pone", "dale play", "quero escuchar" → SIEMPRE usa la tool spotify con action=play y query=nombre de la canción.
- Si el usuario dice solo "Spotify" sin más contexto → usa open_app con app=spotify.
- Para correos: usa EXACTAMENTE el destinatario que menciona el usuario.

HERRAMIENTAS DEL HOGAR (Home Assistant):
- Luces → controlar_luz: entity_id, action (on/off), brightness opcional.
- Clima/aire → controlar_clima: entity_id, temperature, mode opcional.
- Consultar dispositivo → consultar_estado_hogar: entity_id.
- Escenas → ejecutar_escena: entity_id.
- Televisor/TV → controlar_tv: SIEMPRE usa esta para encender/apagar/volumen, NUNCA open_app.
  - "apaga el tv / tele / televisor" → controlar_tv action=turn_off
  - "enciende el tv / tele / televisor" → controlar_tv action=turn_on
  - "sube el volumen / más volumen" → controlar_tv action=volume_up
  - "baja el volumen / menos volumen" → controlar_tv action=volume_down
  - "silencia / mutea el tv" → controlar_tv action=mute
  - "pausa el tv" → controlar_tv action=pause
  - "play el tv / reanuda" → controlar_tv action=play
- Abrir app en TV → abrir_app_tv: cuando el usuario pida abrir Netflix, YouTube, Spotify, etc. en el TV.
  - "abre Netflix en el tv" → abrir_app_tv app=netflix
  - "abre YouTube en el tv" → abrir_app_tv app=youtube
- Buscar en YouTube en TV → buscar_youtube_tv: cuando el usuario pida poner algo específico en YouTube en el TV.
  - "pon música de Bad Bunny en el tv" → buscar_youtube_tv query="música de Bad Bunny"
  - "pon videos de risa en el tv" → buscar_youtube_tv query="videos de risa"
  - "pon reggaetón en el tv" → buscar_youtube_tv query="reggaetón"

TONO:
- Responde siempre en español.
- Sé conciso pero amigable, como un asistente real.
- No expliques qué herramienta usaste a menos que el usuario lo pregunte.
""".strip()

TOOL_CONFIRMATIONS = {
    "open_app": lambda p: f"Listo, abriendo {p.get('app', 'la aplicacion')}",
    "close_app": lambda p: f"Cerrando {p.get('app', 'la aplicacion')}",
    "spotify": lambda p: (
        f"Reproduciendo {p.get('query', 'musica')} en Spotify"
        if p.get("action") == "play"
        else "Controlando Spotify"
    ),
    "weather": lambda p: f"Consultando el clima en {p.get('city', 'tu ciudad')}",
    "news": lambda p: f"Buscando noticias sobre {p.get('query', 'el tema')}",
    "email": lambda p: f"Enviando correo a {p.get('to', 'el destinatario')}",
    "screenshot": lambda p: "Tomando captura de pantalla",
    "volume_control": lambda p: "Ajustando el volumen",
    "controlar_luz": lambda p: (
        "Encendiendo la luz" if p.get("action") == "on" else "Apagando la luz"
    ),
    "controlar_tv": lambda p: "Controlando el televisor",
    "controlar_clima": lambda p: "Ajustando el clima",
    "ejecutar_escena": lambda p: "Activando la escena",
    "consultar_estado_hogar": lambda p: "Consultando el dispositivo",
}


def get_confirmation(tool_name: str, params: dict) -> str:
    confirmation = TOOL_CONFIRMATIONS.get(tool_name)
    if confirmation:
        return confirmation(params)
    return f"Ejecutando {tool_name}"


def build_llm(container: Container):
    provider = container.config.llm_provider.lower().strip()
    model = container.config.llm_model

    if provider == "groq":
        groq_key = container.config.groq_api_key or os.getenv("GROQ_API_KEY", "")
        if not groq_key:
            print("ERROR: Falta GROQ_API_KEY en el archivo .env")
            return None
        print(f"LLM: Groq ({model})")
        return GroqProvider(api_key=groq_key, model=model)

    if provider == "cerebras":
        cerebras_key = container.config.cerebras_api_key or os.getenv("CEREBRAS_API_KEY", "")
        if not cerebras_key:
            print("ERROR: Falta CEREBRAS_API_KEY en el archivo .env")
            return None
        print(f"LLM: Cerebras ({model})")
        return CerebrasProvider(api_key=cerebras_key)

    print(f"ERROR: LLM_PROVIDER no soportado en main.py: {provider}")
    print("Usa LLM_PROVIDER=groq o LLM_PROVIDER=cerebras")
    return None


def attach_cli_tool_output(bus: EventBus) -> None:
    def print_tool_success(event: Event) -> None:
        output = event.payload.get("output", "")
        print(f"Jarvis: {output}")

    def print_tool_failure(event: Event) -> None:
        print(f"Jarvis: Tool falló: {event.payload.get('error', 'error desconocido')}")

    bus.subscribe(events.TOOL_EXECUTED, print_tool_success)
    bus.subscribe(events.TOOL_FAILED, print_tool_failure)


def build_voice():
    if not _VOICE_AVAILABLE or VoiceManager is None:
        print("Voz: no disponible")
        return None

    try:
        voice = VoiceManager(
            tts_enabled=True,
            stt_enabled=True,
            prefer_edge_tts=True,
            language="es-CO",
        )
        status = "activada" if voice.tts_available else "TTS no disponible"
        mic = "activo" if voice.stt_available else "sin microfono"
        print(f"Voz: {status} | Microfono: {mic}")
        return voice
    except Exception as exc:
        print(f"Voz: error ({exc})")
        return None


def _toggle_pause(voice) -> None:
    """Pausa o reanuda el TTS si está disponible."""
    tts = getattr(voice, "tts", None)
    if tts and hasattr(tts, "toggle_pause"):
        paused = tts.toggle_pause()
        print("Jarvis: Voz pausada." if paused else "Jarvis: Voz reanudada.")
    else:
        # Fallback: si el TTS no tiene toggle_pause, al menos detiene el hilo
        print("Jarvis: Pausa no soportada en este modo de voz.")


def read_user_input(voice) -> tuple[str, str]:
    print("Tu (Enter=teclado | 'm'=microfono | 'p'=pausar/reanudar): ", end="", flush=True)
    raw = input().strip()

    # ── Pausa / reanuda con 'p' ───────────────────────────────
    if raw.lower() == "p":
        if voice:
            _toggle_pause(voice)
        else:
            print("Jarvis: Voz no disponible.")
        return "", "text"

    # ── Entrada por micrófono con 'm' ─────────────────────────
    if raw.lower() == "m":
        if not voice or not voice.stt_available:
            print("Jarvis: El microfono no esta disponible.")
            return "", "text"

        print("Escuchando... habla ahora.")
        heard = voice.listen()
        if not heard:
            print("Jarvis: No se escucho nada. Intenta de nuevo.")
            return "", "voice"

        print(f"Tu (voz): {heard}")
        return heard, "voice"

    return raw, "text"


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

    voice = build_voice()
    print(f"Tools registradas: {len(registry.get_all())}\n")
    print("Comandos: m=microfono | p=pausar/reanudar voz | voz on/off | salir\n")

    if voice and voice.tts_available:
        voice.speak_async("Jarvis activo. En que te ayudo?")

    messages = [LLMMessage(role="system", content=SYSTEM_PROMPT)]

    while True:
        try:
            user_input, input_source = read_user_input(voice)
        except KeyboardInterrupt:
            if voice:
                voice.speak("Hasta luego.")
            print("\nHasta luego.")
            break

        if user_input.lower() in ["salir", "exit", "quit"]:
            if voice:
                voice.speak("Hasta luego.")
            break
        if not user_input:
            continue
        if user_input.lower() == "voz off" and voice:
            voice.toggle_voice()
            print("Jarvis: Voz desactivada.")
            continue
        if user_input.lower() == "voz on" and voice:
            voice.toggle_voice()
            print("Jarvis: Voz activada.")
            continue

        txt_low = user_input.lower()

        # ── Modo trabajo ──────────────────────────────────────
        if txt_low in ["hora de trabajar", "modo trabajo"]:
            import subprocess
            apps = [
                r"C:\Users\qandr\AppData\Local\Programs\Microsoft VS Code\Code.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "spotify"
            ]
            for app in apps:
                try:
                    subprocess.Popen(app, shell=True)
                except Exception as e:
                    print(f"Error abriendo {app}: {e}")
            resp = "Iniciando modo trabajo."
            print(f"Jarvis: {resp}")
            if voice:
                voice.speak_async(resp)
            continue

        # ── Apps por nombre ───────────────────────────────────
        if txt_low in ["abre whatsapp", "abrir whatsapp"]:
            import subprocess
            subprocess.Popen(
                ["explorer.exe", "shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"]
            )
            resp = "Abriendo WhatsApp."
            print(f"Jarvis: {resp}")
            if voice:
                voice.speak_async(resp)
            continue

        if txt_low in ["abre chrome", "abrir chrome"]:
            import subprocess
            subprocess.Popen(
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                shell=True
            )
            resp = "Abriendo Chrome."
            print(f"Jarvis: {resp}")
            if voice:
                voice.speak_async(resp)
            continue

        # ── Carpetas del sistema ──────────────────────────────
        if txt_low == "abre documentos":
            import os
            os.startfile(r"C:\Users\qandr\Documents")
            continue

        if txt_low == "abre descargas":
            import os
            os.startfile(r"C:\Users\qandr\Downloads")
            continue

        if txt_low == "abre escritorio":
            import os
            os.startfile(r"C:\Users\qandr\Desktop")
            continue

        if txt_low == "abre jarvis":
            import os
            os.startfile(r"C:\Users\qandr\OneDrive\Desktop\JARVIS")
            continue

        # ── Sitios web ────────────────────────────────────────
        _SITES = {
            "abre facebook":    "https://facebook.com",
            "abre youtube":     "https://youtube.com",
            "abre gmail":       "https://mail.google.com",
            "abre instagram":   "https://instagram.com",
            "abre disney":      "https://www.disneyplus.com",
            "abre netflix":     "https://www.netflix.com",
            "abre prime video": "https://www.primevideo.com",
        }
        if txt_low in _SITES:
            import webbrowser
            webbrowser.open(_SITES[txt_low])
            continue

        # ── Busquedas Google ──────────────────────────────────
        if txt_low.startswith("busca ") or txt_low.startswith("buscar "):
            import webbrowser, urllib.parse
            prefix_len = 7 if txt_low.startswith("buscar ") else 6
            query = user_input[prefix_len:].strip()
            webbrowser.open("https://www.google.com/search?q=" + urllib.parse.quote(query))
            resp = f"Buscando {query}"
            print(f"Jarvis: {resp}")
            if voice:
                voice.speak_async(resp)
            continue

        # ── YouTube en PC ─────────────────────────────────────
        if txt_low.startswith("youtube "):
            import webbrowser, urllib.parse
            query = user_input[8:].strip()
            webbrowser.open(
                "https://www.youtube.com/results?search_query=" + urllib.parse.quote(query)
            )
            continue

        # ── Solo TV si se especifica explicitamente ───────────
        if "en el televisor" in txt_low or "en la tv" in txt_low:
            print("Jarvis: Ejecutando comando para el televisor")
            continue

        # ── Control del sistema ───────────────────────────────
        if txt_low == "apaga el computador":
            import os
            os.system("shutdown /s /t 30")
            resp = "El computador se apagara en 30 segundos"
            print(f"Jarvis: {resp}")
            if voice:
                voice.speak_async(resp)
            continue

        if txt_low == "cancelar apagado":
            import os
            os.system("shutdown /a")
            resp = "Apagado cancelado"
            print(f"Jarvis: {resp}")
            if voice:
                voice.speak_async(resp)
            continue

        if txt_low == "reinicia el computador":
            import os
            os.system("shutdown /r /t 30")
            resp = "El computador se reiniciara en 30 segundos"
            print(f"Jarvis: {resp}")
            if voice:
                voice.speak_async(resp)
            continue

        if txt_low == "suspende el computador":
            import os
            os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")
            continue

        if txt_low == "bloquea el computador":
            import os
            os.system("rundll32.exe user32.dll,LockWorkStation")
            continue

        # ── Carpetas nuevas ───────────────────────────────────
        if txt_low.startswith("crea carpeta "):
            from pathlib import Path
            nombre = user_input[13:].strip()
            ruta = Path.home() / "Desktop" / nombre
            ruta.mkdir(parents=True, exist_ok=True)
            resp = f"Carpeta creada: {nombre}"
            print(f"Jarvis: {resp}")
            if voice:
                voice.speak_async(resp)
            continue
        event_name = events.USER_VOICE_INPUT if input_source == "voice" else events.USER_MESSAGE
        bus.publish(Event(name=event_name, payload={"text": user_input}, source="cli"))
        messages.append(LLMMessage(role="user", content=user_input))

        response = llm.chat(messages, tools=registry.get_all())

        if response.error:
            bus.publish(Event(name=events.LLM_ERROR, payload={"error": response.error}, source="llm"))
            print(f"Jarvis: Error — {response.error}")
            if voice:
                voice.speak_async("Hubo un error, intenta de nuevo.")
            continue

        if response.tool_call:
            tool_name = response.tool_call.get("tool", "")
            params = response.tool_call.get("params", {})
            confirmation = get_confirmation(tool_name, params)
            print(f"Jarvis: {confirmation}")
            if voice:
                voice.speak_async(confirmation)

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
            if voice:
                voice.speak_async(answer)

        elif response.text:
            messages.append(LLMMessage(role="assistant", content=response.text))
            bus.publish(Event(name=events.LLM_RESPONSE, payload={"text": response.text}, source="llm"))
            print(f"Jarvis: {response.text}")
            if voice:
                voice.speak_async(response.text)

        else:
            print("Jarvis: No recibí texto ni llamada a herramienta del LLM.")

        if len(messages) > 7:
            messages = [messages[0]] + messages[-6:]


if __name__ == "__main__":
    main()