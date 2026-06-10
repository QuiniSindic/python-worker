from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PICKEM_SCORING_CONFIG = {
    "group_position_points": 1,
    "perfect_group_bonus": 3,
    "exact_score_bonus": 2,
    "knockout_winner_points": {
        "round_of_32": 3,
        "round_of_16": 5,
        "quarterfinals": 10,
        "semifinals": 15,
        "third_place": 20,
        "final": 25,
    },
    "award_points": {
        "mvp": 10,
        "top_scorer": 10,
        "best_goalkeeper": 10,
        "champion": 20,
    },
}


@dataclass(frozen=True)
class GroupPickScore:
    points_by_participant_id: dict[int, int] # {user_id: puntos}
    exact_participant_ids: set[int] # user_ids que aciertan el grupo entero
    total_points: int # puntos del grupo
    is_perfect_group: bool  # indicador de grupo perfecto


@dataclass(frozen=True)
class MatchPickScore:
    points: int
    winner_points: int # winner match
    exact_score_points: int # marcador acertado
    is_winner_hit: bool # indicador de que has acertado el ganador
    is_exact_score: bool # indicador de que has acertado el marcador


# puntuar prediccion de grupo
def score_group_order_pick(
    predicted_order: list[int], # user group prediction (index 0 posicion 1 de la seleccion_id, etc) ej:[españa_id, uruguay_id...]
    actual_positions_by_participant_id: dict[int, int], # resultado del grupo id: posicion ej:{españa_id: 1, uruguay_id: 2, ...}
    *, # los siguientes params deben usarse con el nombre
    position_points: int = 1,
    perfect_group_bonus: int = 3,
) -> GroupPickScore:
    points_by_participant_id: dict[int, int] = {} # {user_id: 3points}, {user_id: 1point}
    exact_participant_ids: set[int] = set()
    
    # enumerate devuelve pares (index, seleccion_id)
    for index, participant_id in enumerate(predicted_order, start=1):
        is_exact = actual_positions_by_participant_id.get(participant_id) == index # posicion indicada por el user coincide con la posicion real de cada seleccion?
        points_by_participant_id[participant_id] = position_points if is_exact else 0 # sumamos puntos (1) sino 0
        if is_exact: #
            exact_participant_ids.add(participant_id) # registro de ids que el user ha acertado posicion

    is_perfect_group = len(predicted_order) > 0 and len(exact_participant_ids) == len(
        actual_positions_by_participant_id
    )
    
    total_points = sum(points_by_participant_id.values())
    if is_perfect_group:
        total_points += perfect_group_bonus

    return GroupPickScore(
        points_by_participant_id=points_by_participant_id,
        exact_participant_ids=exact_participant_ids,
        total_points=total_points,
        is_perfect_group=is_perfect_group,
    )

# puntuar predicción de partido
def score_match_pick(
    *, # los siguientes params deben usarse con el nombre
    predicted_winner_id: int,
    actual_winner_id: int | None,
    round_key: str,
    predicted_home_score: int | None,
    predicted_away_score: int | None,
    actual_home_score: int | None,
    actual_away_score: int | None,
    winner_points_by_round: dict[str, int], # {semis: 15}
    exact_score_bonus: int,
) -> MatchPickScore:
    is_winner_hit = actual_winner_id is not None and predicted_winner_id == actual_winner_id # acierto si el partido tiene resultado y coincide con el del user
    winner_points = winner_points_by_round.get(round_key, 0) if is_winner_hit else 0 # si hay acierto obtenemos los puntos de la ronda (semis, cuartos, octvos...)
    
    is_exact_score = (
        is_winner_hit # hay acierto
        and predicted_home_score is not None # hay prediccion resultado local
        and predicted_away_score is not None # hay prediccion resultado visitante
        and predicted_home_score == actual_home_score # acierto resultado local
        and predicted_away_score == actual_away_score # acierto resultado visitante
    )
    exact_score_points = exact_score_bonus if is_exact_score else 0 # añadir bonus
    
    return MatchPickScore(
        points=winner_points + exact_score_points,
        winner_points=winner_points,
        exact_score_points=exact_score_points,
        is_winner_hit=is_winner_hit,
        is_exact_score=is_exact_score,
    )

# puntuar predicción de premio
def score_award_pick(
    *, # los siguientes params deben usarse con el nombre
    award_key: str,
    candidate_id: int | None,
    participant_id: int | None,
    result_candidate_id: int | None,
    result_participant_id: int | None,
    award_points: dict[str, int],
) -> tuple[int, bool]:
    if award_key == "champion": # compara la seleccion
        is_hit = participant_id is not None and participant_id == result_participant_id
    else: # comapra el jugador
        is_hit = candidate_id is not None and candidate_id == result_candidate_id
    return (award_points.get(award_key, 0) if is_hit else 0, is_hit)
