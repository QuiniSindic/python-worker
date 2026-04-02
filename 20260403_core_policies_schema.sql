begin;

alter table public.sports enable row level security;
alter table public.competitions enable row level security;
alter table public.competition_seasons enable row level security;
alter table public.competition_phases enable row level security;
alter table public.phase_groups enable row level security;
alter table public.participants enable row level security;
alter table public.participant_members enable row level security;
alter table public.competition_season_participants enable row level security;
alter table public.events enable row level security;
alter table public.event_participants enable row level security;
alter table public.predictions enable row level security;
alter table public.provider_refs enable row level security;
alter table public.sync_state enable row level security;
alter table public.scoring_runs enable row level security;
alter table public.football_events enable row level security;
alter table public.football_standings_rows enable row level security;
alter table public.football_predictions enable row level security;

commit;
