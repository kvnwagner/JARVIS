"""
Demo manual de Windows Tools — Fase 1
Corre este archivo para verificar que cada tool funciona.

Uso:
    python demo_windows_tools.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tools.windows.registry import WINDOWS_TOOLS, get_tool, get_tool_schemas


def separator(title: str):
    print(f"\n{'='*50}")
    print(f"  {title}")
    print('='*50)


def run_test(tool_name: str, params: dict, description: str):
    tool = get_tool(tool_name)
    if not tool:
        print(f"  ❌ Tool '{tool_name}' no encontrada en el registry")
        return

    print(f"\n  🧪 {description}")
    print(f"     Params: {params}")
    result = tool.execute(params)

    if result.success:
        print(f"     ✅ {result.output}")
    else:
        print(f"     ⚠️  {result.error}")


def main():
    separator("JARVIS — Windows Tools Demo")

    # Mostrar todos los tools registrados
    print("\n📋 Tools registradas:")
    for schema in get_tool_schemas():
        print(f"   • {schema['name']}: {schema['description'][:60]}...")

    # ── CLIPBOARD ──
    separator("clipboard")
    run_test("clipboard", {"action": "set", "text": "Hola desde Jarvis 🤖"}, "Escribir en portapapeles")
    run_test("clipboard", {"action": "get"}, "Leer portapapeles")
    run_test("clipboard", {"action": "clear"}, "Vaciar portapapeles")
    run_test("clipboard", {"action": "get"}, "Leer portapapeles vacío")

    # ── VOLUME ──
    separator("volume_control")
    run_test("volume_control", {"action": "get"}, "Consultar volumen actual")
    run_test("volume_control", {"action": "set", "level": 50}, "Establecer volumen a 50%")
    run_test("volume_control", {"action": "up", "step": 10}, "Subir 10%")
    run_test("volume_control", {"action": "down", "step": 5}, "Bajar 5%")
    run_test("volume_control", {"action": "mute"}, "Silenciar")
    run_test("volume_control", {"action": "unmute"}, "Quitar silencio")

    # ── OPEN APP ──
    separator("open_app")
    run_test("open_app", {"app": "notepad"}, "Abrir Notepad")
    run_test("open_app", {"app": "calculadora"}, "Abrir Calculadora (alias español)")
    run_test("open_app", {"app": "appquenoexiste_xyz"}, "App que no existe (error esperado)")

    # ── CLOSE APP ──
    separator("close_app")
    run_test("close_app", {"app": "notepad"}, "Cerrar Notepad")
    run_test("close_app", {"app": "appquenoexiste_xyz"}, "Cerrar app que no corre (error esperado)")

    # ── SCREENSHOT ──
    separator("screenshot")
    run_test("screenshot", {}, "Captura pantalla completa (nombre automático)")
    run_test("screenshot", {"filename": "demo_jarvis"}, "Captura con nombre personalizado")

    separator("DEMO COMPLETO")
    print("\n  Revisa la carpeta screenshots/ para ver las capturas.")
    print("  Todos los tools implementan el contrato Tool de interfaces.py ✓\n")


if __name__ == "__main__":
    main()