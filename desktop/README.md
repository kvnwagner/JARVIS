# Jarvis Desktop - Fase 8

App Tauri v2 para Jarvis con UI futurista, WebSocket, streaming de eventos, tray icon, hotkeys globales y backend local en segundo plano.

## Requisitos

- Node.js + npm
- Rust/Cargo con MSVC toolchain
- Python instalado y accesible con `py`
- Dependencias Python del proyecto: `py -m pip install -r ..\requirements.txt`
- Para wake word real con Porcupine: define `PICOVOICE_ACCESS_KEY`. Opcionalmente define `PORCUPINE_KEYWORD_PATHS` con rutas `.ppn` separadas por `;`.
- Para voz local continua con Vosk: define `VOSK_MODEL_PATH` apuntando a un modelo Vosk en espanol. Si Porcupine/Vosk no existen, Jarvis usa el STT actual como fallback por bloques.

## Desarrollo

```powershell
cd desktop
npm install
npm run tauri:dev
```

## Sidecar Python

Tauri empaqueta binarios sidecar, no scripts `.py`. Antes de `tauri build`, genera el ejecutable:

```powershell
cd desktop
.\scripts\build-sidecar.ps1
npm run tauri:build
```

El sidecar levanta `api.app:app` en `127.0.0.1:8000`. La UI se conecta por `ws://127.0.0.1:8000/ws`.

## Hotkeys

- `Ctrl+Shift+J`: alternar escucha.
- `Ctrl+Shift+Space`: enfocar la caja de comando.
