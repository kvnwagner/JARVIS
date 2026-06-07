"""
Tool: weather
Consulta el clima actual de cualquier ciudad usando OpenWeatherMap.
"""
import os
import requests
from dotenv import load_dotenv
from core.interfaces import Tool, ToolResult

load_dotenv()


class WeatherTool(Tool):
    name = "weather"
    description = (
        "Consulta el clima actual de una ciudad. Usa esto cuando el usuario "
        "pregunte por el tiempo, temperatura, lluvia o clima de cualquier lugar."
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "city": {
                "type": "string",
                "description": "Nombre de la ciudad, por ejemplo: Bogotá, Madrid, New York"
            }
        },
        "required": ["city"]
    }

    def execute(self, params: dict) -> ToolResult:
        city = params.get("city", "").strip()
        if not city:
            return ToolResult.fail("Debes indicar una ciudad.")

        api_key = os.getenv("OPENWEATHER_API_KEY", "")
        if not api_key:
            return ToolResult.fail("No se encontró la API key de OpenWeatherMap en el .env.")

        try:
            url = "https://api.openweathermap.org/data/2.5/weather"
            response = requests.get(url, params={
                "q": city,
                "appid": api_key,
                "units": "metric",
                "lang": "es"
            }, timeout=10)

            if response.status_code == 404:
                return ToolResult.fail(f"No se encontró la ciudad '{city}'.")

            if response.status_code != 200:
                return ToolResult.fail(f"Error al consultar el clima (código {response.status_code}).")

            data = response.json()
            temp        = data["main"]["temp"]
            feels_like  = data["main"]["feels_like"]
            humidity    = data["main"]["humidity"]
            description = data["weather"][0]["description"].capitalize()
            city_name   = data["name"]
            country     = data["sys"]["country"]

            output = (
                f"Clima en {city_name}, {country}:\n"
                f"🌡️  Temperatura: {temp}°C (sensación {feels_like}°C)\n"
                f"🌤️  Condición: {description}\n"
                f"💧 Humedad: {humidity}%"
            )
            return ToolResult.ok(output)

        except requests.Timeout:
            return ToolResult.fail("La consulta del clima tardó demasiado. Intenta de nuevo.")
        except Exception as e:
            return ToolResult.fail(f"Error inesperado: {e}")