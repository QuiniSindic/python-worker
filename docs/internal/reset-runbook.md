# Reset Runbook

## Objetivo

Reconstruir las tablas de app con el modelo v2 manteniendo `auth.users` y
`profiles`.

## Pasos

1. Hacer backup del proyecto Supabase.
2. Ejecutar `20260518_v2_reset_schema.sql` en Supabase SQL Editor.
3. Ejecutar bootstrap:

```bash
uv run bootstrap-football
```

4. Confirmar que existe el Pick'em del Mundial 2026.
5. Sincronizar jugadores del Pick'em:

```bash
uv run sync-pickem-players 1
```

6. Revisar vistas dev en Supabase:

- `dev_football_matches`
- `dev_standings`
- `dev_pickems`
- `dev_pickem_players`

7. Ejecutar checks backend:

```bash
uv run check
```

## Validaciones Manuales

- No borrar `profiles`.
- `dev_football_matches` debe mostrar equipos o `Por decidir`.
- `dev_pickem_players` debe mostrar jugador, seleccion y posicion.
- `/api/v2/pickem/contests/current` debe devolver grupos y candidatos.
- El frontend no debe ver labels tecnicos como `1A`, `3F` o `Winner QF`.
