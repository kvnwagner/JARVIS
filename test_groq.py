import sys, json, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
import requests
from core.container import Container

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
- Para preguntas generales, matemáticas o conversación: responde con texto directamente, SIN usar herramientas.
- Cuando el usuario pida enviar un correo, usa EXACTAMENTE el destinatario que menciona en su mensaje actual.
- Para Spotify: cuando el usuario diga "pon", "reproduce", "escucha" o similar, SIEMPRE usa action=play con el query de la canción.
""".strip()

c = Container()
tools_payload = [
    {
        'type': 'function',
        'function': {
            'name': t.name,
            'description': t.description,
            'parameters': t.parameters_schema
        }
    }
    for t in c.tool_registry.get_all()
]

messages = [
    {'role': 'system', 'content': SYSTEM_PROMPT},
    {'role': 'user', 'content': 'noticias de Colombia'}
]

r = requests.post(
    'https://api.groq.com/openai/v1/chat/completions',
    headers={
        'Authorization': f'Bearer {os.getenv("GROQ_API_KEY")}',
        'Content-Type': 'application/json'
    },
    json={
        'model': 'llama-3.1-8b-instant',
        'messages': messages,
        'tools': tools_payload,
        'tool_choice': 'auto'
    }
)
print(r.status_code)
print(json.dumps(r.json(), indent=2)[:5000])