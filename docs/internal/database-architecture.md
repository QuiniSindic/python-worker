# Database Architecture

Documento interno. El schema actual de referencia es `20260518_v2_reset_schema.sql`.

Para una explicacion tabla por tabla, leer primero `supabase-tables.md`.

## Principios

- El frontend habla con FastAPI, no con Supabase directamente.
- `auth.users` y `profiles` se conservan.
- Las tablas de app viven en `public` y pueden reconstruirse desde cero.
- Los IDs de proveedor son columnas reales, no metadata.
- `metadata` solo se usa cuando aporta valor claro.
- Las vistas `dev_*` son solo para inspeccion humana en Supabase.

## Catalogo

- `sports`: deportes disponibles.
- `competitions`: competiciones como Mundial, La Liga o Champions.
- `seasons`: ediciones concretas de competiciones.
- `phases`: fases de una temporada.
- `groups`: grupos dentro de fases.
- `competitors`: quien compite: seleccion, club, atleta, pareja, driver o rider.
- `group_competitors`: competitors que pertenecen a un grupo.

## Futbol V1

- `football_matches`: una fila por partido de futbol.
- `football_match_events`: timeline normalizado de goles, tarjetas, VAR, etc.
- `standings`: clasificaciones por grupo/fase.

Los partidos futuros sin equipos resueltos se guardan con `home_competitor_id` y
`away_competitor_id` en null. La API debe mostrar `Por decidir`, no labels
tecnicos del proveedor.

## Quiniela Clasica

- `match_predictions`: predicciones de marcador para `football_matches`.

Guarda una fila por usuario y partido.

## Pick'em

- `pickems`: concurso de Pick'em para una temporada.
- `pickem_competitors`: competitors elegibles para un Pick'em.
- `user_pickems`: participacion de usuario en un Pick'em.
- `pickem_group_picks`: picks de orden de grupo.
- `pickem_match_picks`: picks de eliminatorias.
- `pickem_players`: jugadores elegibles para premios de un Pick'em.
- `pickem_award_picks`: picks de MVP, goleador, portero y campeon.
- `pickem_award_results`: resultados reales de premios.

No existe `pickem_award_candidates`: el select de premios se deriva de
`pickem_players` por `pickem_id`.

## Infra

- `provider_refs`: trazabilidad entre proveedor e IDs internos.
- `sync_state`: ultimo estado de workers y bootstrap.

## Vistas Dev

Las vistas `dev_*` son para leer Supabase sin perseguir IDs:

- `dev_seasons`
- `dev_phase_groups`
- `dev_football_matches`
- `dev_standings`
- `dev_match_predictions`
- `dev_pickems`
- `dev_user_pickems`
- `dev_pickem_group_picks`
- `dev_pickem_match_picks`
- `dev_pickem_players`
- `dev_pickem_award_picks`

El backend no debe depender de estas vistas.
