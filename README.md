# Quinisindic Python Backend

Backend `v2` de Quinisindic para futbol: bootstrap estructural, workers de sync y API HTTP con FastAPI.

## Gestor de entorno y paquetes

- El proyecto usa `uv` como herramienta oficial.
- El lockfile fuente de verdad es `uv.lock`.
- Los comandos del proyecto deben ejecutarse con `uv run ...`.
- El tooling de calidad de Python vive en el grupo `dev`.

## Stack

- Python 3.12
- FastAPI
- Uvicorn
- Pydantic Settings
- Supabase Python
- httpx
- Ruff para lint y format

## Comandos

```bash
uv sync
uv sync --group dev
uv run api
uv run api-dev
uv run bootstrap-football
uv run worker-football-live
uv run worker-football-post-match
uv run check
uv run test
uv run ruff check .
uv run ruff format --check .
uv run ruff format .
```

## Variables de entorno

El proyecto necesita al menos estas variables en `.env`:

```env
SUPABASE_URL=
SUPABASE_KEY=
SUPABASE_SERVICE_ROLE_KEY=
```

Para despliegue beta conviene definir tambien:

```env
FRONTEND_ORIGINS=https://tu-frontend.vercel.app
INTERNAL_API_KEY=
```

Notas:

- `FRONTEND_ORIGINS` controla CORS del frontend desplegado. Acepta varias origins separadas por coma.
- `INTERNAL_API_KEY` es opcional y solo hace falta si expones endpoints internos en el futuro.

## Flujo operativo

El backend deportivo actual ya es solo `v2`. El flujo correcto es este:

1. aplicar las migraciones `20260403_*` en Supabase
2. ejecutar `uv run bootstrap-football` una vez sobre una base vacia o recien migrada
3. dejar corriendo `uv run api`
4. dejar corriendo `uv run worker-football-live`
5. dejar corriendo `uv run worker-football-post-match`

`bootstrap-football` puebla catalogo, temporadas, fases, grupos, participantes, eventos y standings iniciales.

`worker-football-live` refresca estados, minuto, marcador y timeline de los partidos del dia o cercanos.

`worker-football-post-match` detecta cierres reales de partidos y relanza el sync estructural de las competiciones afectadas para refrescar standings, calendario y derivados.

## Desarrollo local

1. Sincroniza el entorno base.

```bash
uv sync
```

2. Si vas a trabajar en calidad y refactor, instala tambien el grupo de desarrollo.

```bash
uv sync --group dev
```

3. Si partes de una base nueva o acabas de aplicar las migraciones `20260403_*`, puebla futbol.

```bash
uv run bootstrap-football
```

4. Arranca la API en desarrollo.

```bash
uv run api-dev
```

5. En otra terminal, arranca el worker live.

```bash
uv run worker-football-live
```

6. En otra terminal adicional, arranca el worker de post-partido.

```bash
uv run worker-football-post-match
```

7. Ejecuta la suite actual.

```bash
uv run test
```

8. Ejecuta la verificacion completa.

```bash
uv run check
```

9. Si necesitas correr cada check por separado.

```bash
uv run ruff check .
uv run ruff format --check .
```

## Smoke checks rapidos

Con la API levantada en `http://localhost:8000`, estos endpoints deberian responder:

```bash
curl http://localhost:8000/
curl http://localhost:8000/health
curl http://localhost:8000/api/v2/catalog/sports
curl "http://localhost:8000/api/v2/catalog/competitions?sport_id=1"
curl http://localhost:8000/api/v2/football/events/live
curl http://localhost:8000/api/v2/leaderboard/filters
```

Checks funcionales minimos del flujo actual:

- feed live/results
- standings de liga
- standings por grupos
- bracket knockout
- crear y editar prediccion
- `users/me`
- leaderboard

## Nota sobre la `.venv`

Si `uv run ...` falla por una virtualenv rota o movida entre maquinas, elimina `.venv` y vuelve a ejecutar:

```bash
uv sync
```

Si `uv` falla por un problema en la cache global de la maquina, usa una cache local temporal del proyecto y luego sincroniza de nuevo:

```powershell
$env:UV_CACHE_DIR=".uv-cache"
uv sync --group dev
uv run check
uv run test
uv run ruff check .
```

## Despliegue beta

Objetivo minimo del backend en beta privada:

1. aplicar las migraciones `20260403_*` en Supabase
2. configurar `.env` con Supabase y `FRONTEND_ORIGINS`
3. ejecutar `uv sync --group dev`
4. ejecutar `uv run bootstrap-football`
5. dejar corriendo estos procesos por separado:

```bash
uv run api
uv run worker-football-live
uv run worker-football-post-match
```

Runbook corto de arranque:

1. comprobar que `GET /health` responde `{"status":"ok",...}`
2. comprobar `GET /api/v2/catalog/sports`
3. abrir frontend y validar `/home`, `/events`, `/results`, `/leaderboard` y `/predictions`
4. revisar que live y post-match siguen activos despues del arranque inicial

Si haces redeploy sobre una base nueva o acabas de cambiar el schema:

1. aplica migraciones
2. ejecuta `uv run bootstrap-football`
3. reinicia API y workers

## Checklist antes de tocar otro deporte

Antes de meter motorsport, basket o tenis, este baseline de futbol deberia quedar cerrado:

- migraciones `20260403_*` aplicadas
- `bootstrap-football` funcionando sobre base vacia
- `worker-football-live` estable
- `worker-football-post-match` estable
- tests `v2` en verde
- smoke checks manuales en verde
- frontend consumiendo solo `/api/v2`
