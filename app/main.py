from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.endpoints import matches

# --- ESTA ES LA LÍNEA QUE UVICORN ESTÁ BUSCANDO ---
app = FastAPI(title=settings.PROJECT_NAME)
# --------------------------------------------------

# Configurar CORS (para que tu Next.js pueda conectarse)
origins = [
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir las rutas
app.include_router(matches.router, prefix=f"{settings.API_V1_STR}/matches", tags=["matches"])

@app.get("/")
def root():
    return {"message": "Welcome to Quinisindic API :D"}