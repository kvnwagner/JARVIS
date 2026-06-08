# JARVIS Frontend - Fase 8

Interfaz Vue 3 para el asistente JARVIS con chat, WebSocket, streaming visual,
estado de microfono, historial local y sincronizacion con el backend FastAPI.

## Ejecutar

```powershell
cd C:\Users\Wagne\Downloads\JARVIS
python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

```powershell
cd C:\Users\Wagne\Downloads\JARVIS\frontend
npm install
npm run dev
```

Por defecto el frontend usa `http://localhost:8000`. Para cambiarlo, copia
`.env.example` a `.env` y ajusta `VITE_API_BASE_URL`.

## Contratos usados

- REST: `POST /chat`, `GET /health`, `GET /tools`, `GET /memory`
- WebSocket: `ws://localhost:8000/ws/chat`
- Eventos WS: `status`, `typing`, `chunk`, `done`, `error`

El cliente intenta usar WebSocket primero y cae a REST si no esta conectado,
lo que facilita la migracion posterior a Tauri sin cambiar el contrato del
backend.
