from fastapi import APIRouter, HTTPException
from typing import List
from app.services.scraper import ScraperService
from app.schemas.match import CompetitionData
from app.services.database import DatabaseService

router = APIRouter()

# Instanciamos el servicio (en apps grandes usaríamos Depends() para inyectarlo)
scraper_service = ScraperService()
database_service = DatabaseService()

@router.get("/live", response_model=List[CompetitionData])
async def get_live_matches_endpoint():
    """
    Devuelve los partidos de hoy agrupados por liga (LIVE/NS/FT).
    Útil para testear el ScraperService.
    """
    try:
        data = await scraper_service.get_live_matches_fotmob()
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sync")
async def sync_matches_manual():
    """
    Dispara manualmente la actualización de datos:
    Scraper (FotMob) -> Python -> Supabase
    """
    try:
        # 1. Obtener datos en vivo
        data = await scraper_service.get_live_matches_fotmob()
        
        if not data:
            return {"status": "warning", "message": "No matches found to sync"}

        # 2. Guardar en Supabase
        count = database_service.save_matches(data)
        
        return {"status": "success", "matches_synced": count}
    
    except Exception as e:
        print(f"Error en sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))