# ADR-001 — Proveedor LLM inicial

## Estado
Aceptado — 2026-06-05

## Contexto
El agente necesita un LLM para razonamiento y tool calling.
Opciones evaluadas: Gemini 1.5, GPT-4o, modelos locales (Ollama).

## Decisión
Usaremos Gemini 1.5 Flash como proveedor inicial.

## Motivo
- Plan gratuito con cuota suficiente para desarrollo
- Soporte nativo de function calling (tool calling)
- Context window largo (1M tokens) útil para memoria
- Fácil de reemplazar gracias a la interfaz LLMProvider

## Consecuencias
- Toda integración con el LLM pasa por LLMProvider
- Nada fuera de llm/gemini.py importa el SDK de Google
- Migrar a GPT-4o o Ollama = implementar LLMProvider,
  cambiar una línea en config.py

## Revisión
Revisar si la cuota gratuita resulta insuficiente en fase 3+.
Si el modelo local (Ollama) alcanza calidad suficiente,
considerar migración para privacidad y costo cero.

## Firmantes
Equipo completo — Jarvis v0.1