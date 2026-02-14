from app.services.database import DatabaseService

class PointsService:
    def __init__(self):
        self.db = DatabaseService()

    async def calculate_match_points(self, match_id: int, real_home: int, real_away: int):
        print(f"🧮 Calculando puntos para el partido {match_id} ({real_home}-{real_away})...")
        
        # 1. Obtener predicciones de este partido que NO tengan puntos
        response = self.db.supabase.table("predictions")\
            .select("*")\
            .eq("match_id", match_id)\
            .is_("points", "null")\
            .execute()
        
        predictions = response.data
        
        if not predictions:
            print("   -> No hay predicciones pendientes de puntuar.")
            return

        updates = []
        
        # 2. Iterar y aplicar reglas
        for pred in predictions:
            points = 0
            status = "lose" # win, exact, lose
            
            # Usamos .get() por seguridad, aunque deberían existir
            pred_home = pred.get("home_score")
            pred_away = pred.get("away_score")
            
            # --- LÓGICA DE PUNTUACIÓN ---
            
            # Evitamos errores si por alguna razón los scores son None
            if pred_home is not None and pred_away is not None:
                # Regla 1: Acierto Exacto (3 Puntos)
                if pred_home == real_home and pred_away == real_away:
                    points = 3
                    status = "exact"
                
                # Regla 2: Acierto de Resultado/Signo (1 Punto)
                elif (real_home > real_away and pred_home > pred_away) or \
                     (real_home == real_away and pred_home == pred_away) or \
                     (real_home < real_away and pred_home < pred_away):
                    points = 1
                    status = "win"
            
            # --- CORRECCIÓN DEL ERROR 23502 ---
            # Al hacer upsert, enviamos también el user_id y match_id originales
            # para evitar que la DB piense que estamos insertando nulos.
            updates.append({
                "id": pred["id"],
                "user_id": pred["user_id"],   # <--- CLAVE: Campo obligatorio
                "match_id": pred["match_id"], # <--- CLAVE: Campo obligatorio
                "home_score": pred_home,      # <--- Recomendable mantenerlo
                "away_score": pred_away,      # <--- Recomendable mantenerlo
                "points": points,
                "status": status
            })

        # 3. Guardar en bloque (Upsert)
        if updates:
            # Upsert ahora tiene todos los datos necesarios para no fallar
            self.db.supabase.table("predictions").upsert(updates).execute()
            print(f"✅ Puntos actualizados para {len(updates)} usuarios.")