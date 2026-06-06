# ADR-002 — Base de datos para memoria

## Estado
Aceptado — 2026-06-05

## Contexto
El sistema necesita persistir conversaciones, preferencias
y notas del usuario entre sesiones.

## Decisión
Usaremos SQLite vía SQLAlchemy.

## Motivo
- Aplicación local, usuario único por instancia
- Cero configuración: un archivo .db en el disco
- SQLAlchemy abstrae el motor — migrar es cambiar la URL
- Suficiente para fases 1–7

## Consecuencias
- Toda escritura/lectura pasa por MemoryProvider
- Nada fuera de memory/sqlite_memory.py toca SQLite
  directamente
- Si el proyecto escala a multiusuario o multidispositivo,
  migrar a PostgreSQL = cambiar DB_PATH a una URL de postgres
  en config.py

## Qué NO cubre SQLite
- Múltiples usuarios simultáneos con escrituras concurrentes
- Búsqueda semántica (embeddings) — si se necesita, añadir
  ChromaDB o pgvector como capa separada en fase 4+

## Firmantes
Equipo completo — Jarvis v0.1