from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Quinisindic Backend API"
    API_V1_STR: str = "/api/v1"
    
    # Aquí pondrás tus claves de Supabase o Oracle en el futuro
    SUPABASE_URL: str
    SUPABASE_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: str

    class Config:
        env_file = ".env"

settings = Settings()

# IDs de competiciones a incluir en el scraper de FotMob
## Alemania
### Bundesliga: 54
### DFB Pokal: 209
### Supercup: 8924

## España
### LaLiga: 87
### Copa del Rey: 138
### Supercopa: 139

## Francia
### Ligue 1: 53
### Coupe de France: 134
### Trophée des champions: 207

## Inglaterra
### Premier League: 47
### FA Cup: 132
### EFL Cup: 133
### Community Shield: 247

## Italia
### Serie A: 55
### Coppa Italia: 141
### Super Cup: 222

## Europa
### Champions League: 42
### Europa League: 73
### Conference League: 10216
### Supercopa de Europa: 74
### Eurocopa: 50
### Nations League A: 9806

## Sudamerica
### Copa Libertadores: 45
### Copa America: 44

## Internacional
### Mundial de clubes: 78
### Intercontinental: 10703
### Finalissima: 10304
### JJOO: 66
### Mundial: 77

FOTMOB_TARGET_LEAGUE_IDS = {
    # Alemania
    54, 209, 8924,
    # España
    87, 138, 139,
    # Francia
    53, 134, 207,
    # Inglaterra
    47, 132, 133, 247,
    # Italia
    55, 141, 222,
    # Europa
    42, 73, 10216, 74, 50, 9806,
    # Sudamérica
    45, 44,
    # Internacional
    78, 10703, 10304, 66, 77,
}
