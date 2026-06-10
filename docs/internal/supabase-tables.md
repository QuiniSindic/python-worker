# Supabase Tables

Documento interno. Describe las tablas actuales del schema v2 y para que sirve
cada una.

Schema de referencia: `20260518_v2_reset_schema.sql`.

## Lectura Rapida

- `profiles`: usuarios de la app. Se conserva fuera del reset.
- `sports`, `competitions`, `seasons`, `phases`, `groups`: catalogo deportivo.
- `competitors`: equipos, selecciones, atletas, pilotos o riders.
- `football_matches`, `football_match_events`, `standings`: datos de futbol.
- `match_predictions`: quiniela clasica de marcadores.
- `pickems`, `user_pickems`, `pickem_*`: Pick'em de torneos.
- `provider_refs`, `sync_state`: tablas tecnicas de sincronizacion.
- `dev_*`: vistas legibles para inspeccionar Supabase.

## Usuarios

### `profiles`

Perfil publico/interno del usuario. No la crea la migracion v2 porque depende
de `auth.users`.

- La escribe: auth/signup o logica de usuarios.
- La lee: rankings, predicciones y vistas dev.
- Tocar manualmente: solo para corregir datos de usuario.

## Catalogo Deportivo

### `sports`

Lista de deportes soportados. Ahora mismo existe `football`.

- La escribe: migracion/seed.
- La lee: bootstrap y API.
- Tocar manualmente: casi nunca.

### `competitions`

Competicion estable: Mundial, La Liga, Champions, NBA, Wimbledon.

No representa una edicion concreta. El Mundial como competicion vive aqui; el
Mundial 2026 vive en `seasons`.

- La escribe: bootstrap.
- La lee: API, bootstrap y vistas dev.
- Tocar manualmente: solo si el proveedor trae un nombre mal.

### `seasons`

Edicion concreta de una competicion: Mundial 2026, La Liga 2025-26.

- La escribe: bootstrap.
- La lee: casi todo el backend.
- Tocar manualmente: fechas, `is_current` o nombre si hace falta.

### `phases`

Fases de una temporada: grupos, dieciseisavos, octavos, cuartos, semifinales,
tercer puesto, final.

- La escribe: bootstrap.
- La lee: partidos, grupos, Pick'em y vistas dev.
- Tocar manualmente: raro.

### `groups`

Grupos dentro de una fase de grupos: Grupo A, Grupo B, etc.

- La escribe: bootstrap.
- La lee: standings y Pick'em.
- Tocar manualmente: raro.

## Competidores

### `competitors`

Quien compite. En futbol son clubes o selecciones. A futuro tambien puede
representar atletas de tenis, pilotos de F1 o riders de MotoGP.

- La escribe: bootstrap.
- La lee: partidos, standings, Pick'em.
- Tocar manualmente: nombres, abreviaturas o escudos si FotMob falla.

Campos importantes:

- `kind`: `club`, `national_team`, `athlete`, `pair`, `driver`, `rider`.
- `provider_name` y `provider_id`: identificador externo.
- `badge_url`: escudo/foto.

### `group_competitors`

Relaciona un grupo con sus competidores. Ejemplo: Espana esta en Grupo H.

- La escribe: bootstrap al guardar standings.
- La lee: Pick'em de grupos.
- Tocar manualmente: solo si el sorteo/grupo esta mal.

## Futbol

### `football_matches`

Partidos de futbol. Es la tabla principal para calendario, estado y marcador.

- La escribe: bootstrap, live sync y post-match sync.
- La lee: API de partidos, quiniela y Pick'em eliminatorio.
- Tocar manualmente: solo para corregir un resultado puntual.

Notas:

- `home_competitor_id` y `away_competitor_id` pueden ser `null` si el partido
  futuro aun no tiene equipos resueltos.
- La UI debe mostrar `Por decidir`, no placeholders tecnicos del proveedor.
- `winner_competitor_id` es el ganador real si el partido esta terminado.

### `football_match_events`

Timeline de un partido: goles, tarjetas, VAR, cambios, etc.

- La escribe: live sync/post-match sync cuando FotMob trae timeline.
- La lee: detalles de partido.
- Tocar manualmente: normalmente no.

### `standings`

Clasificaciones por grupo/fase.

- La escribe: bootstrap y futuras sincronizaciones.
- La lee: API de clasificaciones y Pick'em.
- Tocar manualmente: solo si el proveedor falla.

## Quiniela Clasica

### `match_predictions`

Predicciones de marcador de usuarios para partidos concretos.

- La escribe: usuario via API.
- La lee: rankings y feeds.
- Tocar manualmente: no, salvo soporte.

Guarda una fila por usuario y partido.

## Pick'em

### `pickems`

Concurso Pick'em para una temporada. Ejemplo: Pick'em Mundial 2026.

- La escribe: bootstrap/script de setup.
- La lee: API Pick'em.
- Tocar manualmente: deadlines, nombre o scoring.

### `pickem_competitors`

Competidores elegibles para ganar el Pick'em. Para el Mundial, son las
selecciones reales, no placeholders como `1A` o `Winner QF`.

- La escribe: setup Pick'em.
- La lee: select de campeon.
- Tocar manualmente: si falta o sobra una seleccion.

### `user_pickems`

Entrada de un usuario en un Pick'em. Una fila por usuario y concurso.

- La escribe: usuario via API.
- La lee: leaderboard y picks del usuario.
- Tocar manualmente: no, salvo soporte.

### `pickem_group_picks`

Prediccion del orden de grupo. Una fila por equipo predicho.

Aunque genere muchas filas, es el modelo correcto porque permite puntuar,
validar duplicados y consultar por posicion sin JSON complejo.

- La escribe: usuario via API.
- La lee: scoring y pantalla de picks.
- Tocar manualmente: no.

### `pickem_match_picks`

Prediccion de ganador y marcador en eliminatorias.

- La escribe: usuario via API.
- La lee: scoring y pantalla de picks.
- Tocar manualmente: no.

### `pickem_players`

Jugadores elegibles para premios individuales de un Pick'em.

No es una tabla global de todos los jugadores del mundo. Para el Mundial 2026
solo guarda jugadores de selecciones que participan en ese Pick'em.

- La escribe: `sync-pickem-players`.
- La lee: selects de MVP, goleador y mejor portero.
- Tocar manualmente: si falta un jugador importante.

### `pickem_award_picks`

Picks de premios del usuario: campeon, MVP, goleador y mejor portero.

- La escribe: usuario via API.
- La lee: scoring y pantalla de picks.
- Tocar manualmente: no.

### `pickem_award_results`

Resultados reales de premios al terminar el torneo.

- La escribe: admin/script/manual.
- La lee: scoring.
- Tocar manualmente: si, al final del torneo si no hay fuente automatica.

## Infraestructura

### `provider_refs`

Trazabilidad entre IDs internos y IDs de proveedor. Ayuda a depurar problemas
de sincronizacion.

- La escribe: bootstrap/sync.
- La lee: debug.
- Tocar manualmente: no.

### `sync_state`

Estado de workers y bootstrap: ultima ejecucion, errores y payload de resumen.

- La escribe: bootstrap, live sync y post-match sync.
- La lee: debug/operacion.
- Tocar manualmente: solo para forzar una resincronizacion concreta.

## Vistas Dev

Las vistas `dev_*` existen para revisar Supabase sin hacer joins mentales.

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

No escribas contra estas vistas. No las uses desde backend ni frontend.

## Contrato API

La API puede exponer nombres historicos como `participant_id` porque el
frontend ya los consume. Eso es contrato HTTP, no nombres de tablas Supabase.
