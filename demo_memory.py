# ================================================================
# demo_memory.py
# Demo manual de la Fase 2 — Memory (RAM + SQLite)
# Uso: python demo_memory.py
# ================================================================

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory.memory_manager import MemoryManager


def separator(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


def main():
    separator("JARVIS — Memory Demo")

    # Usar base de datos de prueba (se borra al final)
    manager = MemoryManager(db_path="jarvis_test.db")

    # ── RAM: conversación ──────────────────────────────────────
    separator("RAM — Historial de conversación")

    manager.save_message("Hola Jarvis, ¿cómo estás?", source="user")
    manager.save_message("Hola, estoy listo para ayudarte.", source="assistant")
    manager.save_message("Abre Spotify por favor.", source="user")
    manager.save_message("Abriendo Spotify...", source="assistant")
    manager.save_message("Ahora baja el volumen al 40%.", source="user")
    manager.save_message("Volumen establecido a 40%.", source="assistant")

    print(f"\n  Mensajes en RAM: {manager.ram.count()}")
    print("\n  Contexto para el LLM (últimos 4 mensajes):")
    for msg in manager.get_conversation_context(n=4):
        role_icon = "👤" if msg["role"] == "user" else "🤖"
        print(f"     {role_icon} [{msg['role']}]: {msg['content']}")

    # ── RAM: búsqueda ──────────────────────────────────────────
    separator("RAM — Búsqueda en conversación")

    results = manager.ram.search("volumen")
    print(f"\n  Búsqueda 'volumen' → {len(results)} resultado(s):")
    for r in results:
        print(f"     [{r.source}] {r.content}")

    # ── SQLite: preferencias ───────────────────────────────────
    separator("SQLite — Preferencias (persistentes)")

    manager.save_preference("horario_trabajo", "8am a 5pm")
    manager.save_preference("idioma", "español")
    manager.save_preference("volumen_default", "50")

    print(f"\n  ✅ Preferencias guardadas")
    print(f"     horario_trabajo → {manager.get_preference('horario_trabajo')}")
    print(f"     idioma          → {manager.get_preference('idioma')}")
    print(f"     volumen_default → {manager.get_preference('volumen_default')}")
    print(f"     no_existe       → {manager.get_preference('no_existe')}")

    # ── SQLite: hechos ─────────────────────────────────────────
    separator("SQLite — Hechos (persistentes)")

    manager.save_fact("El usuario se llama Kevin", tags=["usuario", "nombre"])
    manager.save_fact("Kevin trabaja en SENA como aprendiz ADSO", tags=["usuario", "trabajo"])
    manager.save_fact("El proyecto principal es Texticode", tags=["proyecto"])
    manager.save_fact("Kevin prefiere respuestas cortas y directas", tags=["preferencia"])

    print(f"\n  ✅ Hechos guardados en SQLite")
    hechos = manager.get_recent_facts(n=4)
    for h in hechos:
        print(f"     🧠 [{', '.join(h.tags)}] {h.content}")

    # ── SQLite: búsqueda ───────────────────────────────────────
    separator("SQLite — Búsqueda en hechos")

    results = manager.sqlite.search("Kevin")
    print(f"\n  Búsqueda 'Kevin' → {len(results)} resultado(s):")
    for r in results:
        print(f"     [{', '.join(r.tags)}] {r.content}")

    # ── Búsqueda combinada ─────────────────────────────────────
    separator("Búsqueda combinada (RAM + SQLite)")

    results = manager.search("usuario")
    print(f"\n  Búsqueda 'usuario' → {len(results)} resultado(s) combinados:")
    for r in results:
        print(f"     [{r.source}] {r.content}")

    # ── Stats ──────────────────────────────────────────────────
    separator("Estadísticas")

    stats = manager.stats()
    print(f"\n  RAM entries:    {stats['ram_entries']}")
    print(f"  SQLite entries: {stats['sqlite_entries']}")

    # Limpiar base de datos de prueba
    import os
    manager.sqlite._connect().close()
    try:
        os.remove("jarvis_test.db")
    except PermissionError:
        pass  # Windows a veces retiene el archivo, no es crítico
    print(f"\n  🗑️  Base de datos de prueba eliminada.")

    separator("DEMO COMPLETO")
    print("\n  RAM y SQLite funcionando correctamente ✓\n")


if __name__ == "__main__":
    main()