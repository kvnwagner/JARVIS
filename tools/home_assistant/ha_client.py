import httpx
import os
from dotenv import load_dotenv

load_dotenv()

class HomeAssistantClient:
    """Cliente para comunicarse con la API de Home Assistant."""

    def __init__(self):
        self.base_url = os.getenv("HA_URL", "http://localhost:8123")
        self.token = os.getenv("HA_TOKEN", "")
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    async def get_state(self, entity_id: str) -> dict:
        """Consulta el estado de un dispositivo. Ej: 'light.salon'"""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/api/states/{entity_id}",
                headers=self.headers,
                timeout=10,
            )
            r.raise_for_status()
            return r.json()

    async def get_all_states(self) -> list:
        """Devuelve todos los dispositivos y su estado actual."""
        async with httpx.AsyncClient() as client:
            r = await client.get(
                f"{self.base_url}/api/states",
                headers=self.headers,
                timeout=10,
            )
            r.raise_for_status()
            return r.json()

    async def call_service(self, domain: str, service: str, data: dict = None) -> dict:
        """
        Ejecuta una acción en HA.
        Ejemplos:
          domain="light", service="turn_on", data={"entity_id": "light.salon"}
          domain="climate", service="set_temperature", data={"entity_id": "climate.sala", "temperature": 22}
        """
        async with httpx.AsyncClient() as client:
            r = await client.post(
                f"{self.base_url}/api/services/{domain}/{service}",
                headers=self.headers,
                json=data or {},
                timeout=10,
            )
            r.raise_for_status()
            return r.json()