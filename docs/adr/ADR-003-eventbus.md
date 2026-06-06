# ADR-003 — EventBus: memoria vs Redis

## Estado
Aceptado — 2026-06-05

## Contexto
Los módulos (LLM, Tools, Memory, Voice, HA) necesitan
comunicarse sin acoplarse entre sí.

## Decisión
Usaremos InMemoryEventBus para las fases 1–4.

## Motivo
- Un solo proceso Python — no hay múltiples servicios aún
- Redis añade complejidad operativa sin beneficio real
  cuando todo corre en el mismo proceso
- La interfaz EventBus permite migrar sin cambiar nada
  fuera de la línea de instanciación

## Regla de migración
Migrar a RedisEventBus solo cuando aparezca alguno de:
  - Múltiples procesos (agente + servidor + voz separados)
  - Múltiples dispositivos (PC + móvil + Raspberry Pi)
  - Necesidad de persistir eventos entre reinicios

## Consecuencias
- Todo módulo recibe el bus por inyección de dependencia
- Nadie instancia EventBus directamente (usar contenedor)
- Migrar = cambiar una línea en el contenedor DI

## Firmantes
Equipo completo — Jarvis v0.1