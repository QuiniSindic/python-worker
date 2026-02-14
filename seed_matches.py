# seed_season.py
import asyncio
from app.core.config import FOTMOB_TARGET_LEAGUE_IDS
from app.services.scraper import ScraperService
from app.services.database import DatabaseService

TARGET_LEAGUES = FOTMOB_TARGET_LEAGUE_IDS

async def seed():
    print("🌱 Iniciando SEED de temporada completa...")
    
    scraper = ScraperService()
    db = DatabaseService()

    for league_id in TARGET_LEAGUES:
        print(f"\n--- Procesando Liga ID: {league_id} ---")
        
        # 1. Obtener TODOS los partidos (J1 a J38)
        competitions_data = await scraper.get_all_season_matches(league_id)
        
        if competitions_data:
            total_matches = len(competitions_data[0].matches)
            print(f"📥 Descargados {total_matches} partidos.")
            
            # 2. Guardar en Supabase
            # Tu función save_matches ya hace "upsert", así que si el partido existe, lo actualiza; si no, lo crea.
            db.save_matches(competitions_data)
            print("💾 Guardados en base de datos.")
                
        else:
            print("⚠️ No se encontraron datos.")
            
        # Pausa para ser amables con la API
        await asyncio.sleep(2)

    print("\n✅ Proceso de seed terminado exitosamente.")

if __name__ == "__main__":
    asyncio.run(seed())