# Guía de contribución — Jarvis

## Ramas

main         — siempre estable y deployable
develop      — integración continua del equipo
feat/<nombre> — una rama por funcionalidad
fix/<nombre>  — correcciones puntuales

## Flujo estándar

1. Crear rama desde develop:
   git checkout -b feat/windows-tools

2. Commits atómicos con prefijo:
   feat: agrega open_app tool
   fix:  corrige timeout en LLM provider
   docs: actualiza ADR-001
   test: añade tests para ToolRegistry

3. PR hacia develop — al menos 1 aprobación requerida

4. Merge a main solo cuando develop esté estable

## Regla de interfaces.py

NADIE modifica core/interfaces.py sin aprobación
unánime del equipo. Abrir issue + discusión antes de PR.

## División de módulos por persona

Persona 1 — core/, llm/, infrastructure/event_bus.py
Persona 2 — tools/windows/, tools/filesystem/
Persona 3 — memory/, infrastructure/logger.py
Persona 4 — tests/, docs/, CI/CD, tools/integrations/

## Tests

Cada módulo nuevo lleva su test en tests/<módulo>/.
Persona 4 es responsable de la cobertura global.
CI falla si cobertura baja del 70%.

## Antes de cada PR

[ ] Tests pasan localmente
[ ] No se modifica interfaces.py sin aprobación
[ ] ADR actualizado si se tomó una decisión de arquitectura
[ ] Sin claves API en el código (usar .env)