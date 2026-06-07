import httpx
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()

HA_URL = os.getenv("HA_URL")
HA_TOKEN = os.getenv("HA_TOKEN")

async def test():
    headers = {
        "Authorization": f"Bearer {HA_TOKEN}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{HA_URL}/api/", headers=headers)
        if r.status_code == 200:
            print("✅ Conexión con Home Assistant exitosa")
        else:
            print(f"❌ Error: {r.status_code}")

asyncio.run(test())