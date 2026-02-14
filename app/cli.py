import uvicorn

from app.worker import main as worker_main
from app.worker_v2 import main as worker_v2_main


def api_main() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


def worker_entry() -> None:
    worker_main()


def worker_v2_entry() -> None:
    worker_v2_main()
