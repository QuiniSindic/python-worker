# Quinisindic Python Backend

Backend y workers de Quinisindic para scraping, sincronizacion con Supabase y API HTTP con FastAPI.

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
uv run api-dev
uv run api
uv run bootstrap-football
uv run worker-football
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

## Desarrollo local

1. Sincroniza el entorno base.

```bash
uv sync
```

2. Si vas a trabajar en calidad y refactor, instala tambien el grupo de desarrollo.

```bash
uv sync --group dev
```

3. Arranca la API en desarrollo.

```bash
uv run api-dev
```

4. Si partes de una base nueva o acabas de aplicar las migraciones `20260403_*`, puebla fútbol:

```bash
uv run bootstrap-football
```

5. Arranca el worker continuo de fútbol:

```bash
uv run worker-football
```

6. Ejecuta la suite actual.

```bash
uv run test
```

7. Ejecuta la verificacion completa.

```bash
uv run check
```

8. Si necesitas correr cada check por separado.

```bash
uv run ruff check .
uv run ruff format --check .
```

## Nota sobre la `.venv`

Si `uv run ...` falla por una virtualenv rota o movida entre maquinas, elimina `.venv` y vuelve a ejecutar:

```bash
uv sync
```

Ahora mismo este repo tenia una `.venv` apuntando a una instalacion de Python inexistente, asi que `uv sync` es el paso correcto para reconstruirla de forma limpia.

Si ademas `uv` falla por un problema en la cache global de la maquina, usa una cache local temporal del proyecto y luego sincroniza de nuevo:

```powershell
$env:UV_CACHE_DIR=".uv-cache"
uv sync --group dev
uv run check
uv run test
uv run ruff check .
```
