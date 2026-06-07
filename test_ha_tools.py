import asyncio
from tools.home_assistant.ha_tools import consultar_estado

async def test():
    # Esto consulta todos los dispositivos que HA detectó
    from tools.home_assistant.ha_client import HomeAssistantClient
    ha = HomeAssistantClient()
    dispositivos = await ha.get_all_states()
    
    print(f"✅ HA tiene {len(dispositivos)} entidades registradas\n")
    print("Primeros 5 dispositivos:")
    for d in dispositivos[:5]:
        print(f"  → {d['entity_id']}: {d['state']}")

asyncio.run(test())