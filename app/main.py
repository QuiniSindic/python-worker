from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v2.endpoints import catalog as catalog_v2
from app.api.v2.endpoints import football as football_v2
from app.api.v2.endpoints import leaderboard as leaderboard_v2
from app.api.v2.endpoints import users as users_v2
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(catalog_v2.router, prefix="/api/v2/catalog", tags=["catalog-v2"])
app.include_router(football_v2.router, prefix="/api/v2/football", tags=["football-v2"])
app.include_router(leaderboard_v2.router, prefix="/api/v2/leaderboard", tags=["leaderboard-v2"])
app.include_router(users_v2.router, prefix="/api/v2/users", tags=["users-v2"])


@app.get("/")
def root():
    return {
        "message": "Welcome to Quinisindic API",
        "active": ["/api/v2"],
        "legacy": [],
    }
