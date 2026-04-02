begin;

drop view if exists public.leaderboard_global cascade;
drop view if exists public.leaderboard_sport cascade;
drop view if exists public.leaderboard_competition cascade;

drop materialized view if exists public.leaderboard_global cascade;
drop materialized view if exists public.leaderboard_sport cascade;
drop materialized view if exists public.leaderboard_competition cascade;

drop table if exists public.football_predictions cascade;
drop table if exists public.football_standings_rows cascade;
drop table if exists public.football_events cascade;
drop table if exists public.motorsport_predictions cascade;
drop table if exists public.motorsport_results cascade;
drop table if exists public.motorsport_events cascade;

drop table if exists public.scoring_runs cascade;
drop table if exists public.sync_state cascade;
drop table if exists public.provider_refs cascade;
drop table if exists public.event_participants cascade;
drop table if exists public.events cascade;
drop table if exists public.competition_season_participants cascade;
drop table if exists public.participant_members cascade;
drop table if exists public.participants cascade;
drop table if exists public.phase_groups cascade;
drop table if exists public.competition_phases cascade;
drop table if exists public.competition_seasons cascade;
drop table if exists public.predictions cascade;
drop table if exists public.competitions cascade;
drop table if exists public.sports cascade;

drop table if exists public.competition_stage_groups cascade;
drop table if exists public.competition_standing_rows cascade;
drop table if exists public.competition_stages cascade;
drop table if exists public.matches cascade;
drop table if exists public.competition_editions cascade;

drop table if exists public.f1_predictions cascade;
drop table if exists public.f1_session_results cascade;
drop table if exists public.f1_session_drivers cascade;
drop table if exists public.f1_sessions cascade;
drop table if exists public.f1_grand_prix cascade;
drop table if exists public.f1_drivers cascade;

commit;
