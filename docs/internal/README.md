# Internal Docs

Documentacion privada para entender el backend y Supabase sin tener que leer
todo el codigo.

## Por Donde Empezar

1. `supabase-tables.md`: mapa tabla por tabla de Supabase.
2. `database-architecture.md`: principios del modelo de datos actual.
3. `pickem-architecture.md`: como funciona el Pick'em.
4. `reset-runbook.md`: pasos para reconstruir Supabase desde cero.

## Estado Actual

El schema de referencia es:

```txt
20260518_v2_reset_schema.sql
```

El frontend debe hablar con FastAPI. No debe leer ni escribir Supabase
directamente para quinielas, Pick'em, partidos o clasificaciones.

## Regla Practica

Si una tabla empieza por `dev_`, es una vista para humanos en Supabase. No debe
ser dependencia del backend ni del frontend.

