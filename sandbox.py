from __future__ import annotations

import asyncio
from typing import Any


def run() -> Any:
    """
    Pega aqui pruebas sincronas.
    Devuelve algo si quieres que se imprima al final.
    """
    return "Sandbox listo. Edita run() o run_async() en sandbox.py"


async def run_async() -> Any:
    """
    Pega aqui pruebas asincronas.
    Si no necesitas async, puedes dejar esto en None.
    """
    return None


def _print_result(result: Any) -> None:
    if result is None:
        return
    print(result)


if __name__ == "__main__":
    sync_result = run()
    _print_result(sync_result)

    async_result = asyncio.run(run_async())
    _print_result(async_result)
