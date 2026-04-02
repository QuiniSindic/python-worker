begin;

insert into public.sports (slug, name, is_active)
values ('football', 'Football', true)
on conflict (slug) do update
set name = excluded.name,
    is_active = excluded.is_active,
    updated_at = timezone('utc', now());

commit;
