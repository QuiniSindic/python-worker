# Pick'em Architecture

Documento interno. El modelo actual usa `pickems`, `user_pickems` y tablas
con prefijo `pickem_*`.

## Flujo

```txt
FotMob bootstrap
  -> competitions / seasons / phases / groups / competitors
  -> football_matches / standings

Pick'em bootstrap
  -> pickems
  -> pickem_competitors

FotMob squads
  -> pickem_players

Users
  -> user_pickems
  -> pickem_group_picks
  -> pickem_match_picks
  -> pickem_award_picks

Admin/final
  -> pickem_award_results
  -> score-pickem
```

## Reglas V1

- Grupos: 1 punto por posicion acertada.
- Grupo perfecto: 3 puntos extra.
- Eliminatorias: el usuario predice ganador y marcador.
- Marcador exacto: 2 puntos extra.
- Premios: MVP 10, goleador 10, portero 10, campeon 20.

Puntos por ganador de eliminatoria:

- `round_of_32`: 3
- `round_of_16`: 5
- `quarterfinals`: 10
- `semifinals`: 15
- `third_place`: 20
- `final`: 25

## Jugadores

`pickem_players` contiene solo jugadores elegibles para un Pick'em concreto.

No es una tabla global de todos los jugadores de FotMob. Si hay Mundial 2026,
Euro 2028 y Champions 2027, todos viven en `pickem_players`, separados por
`pickem_id`.

Posiciones permitidas:

- `GK`
- `DF`
- `MF`
- `FW`

El select de mejor portero debe filtrar `position = 'GK'`.

## Comandos

```bash
uv run bootstrap-football
uv run sync-pickem-players 1
uv run score-pickem 1
```

El modelo nuevo no guarda `award_candidates`; la API deriva esos candidatos de
`pickem_players`.

## API

Las rutas publicas se mantienen para no romper frontend:

- `/api/v2/pickem/contests/current`
- `/api/v2/pickem/contests/{contest_id}/me`
- `/api/v2/pickem/contests/{contest_id}/groups`
- `/api/v2/pickem/contests/{contest_id}/awards`
- `/api/v2/pickem/contests/{contest_id}/matches/{event_id}`
- `/api/v2/pickem/contests/{contest_id}/leaderboard`
