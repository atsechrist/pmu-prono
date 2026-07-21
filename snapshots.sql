-- snapshots.sql — Table du "figeage du matin" (dashboard.py + figeage.py).
-- À exécuter UNE FOIS dans Supabase → SQL Editor.
--
-- Une ligne par (utilisateur, date) : la photo des pronos du matin (chevaux + cotes
-- + probas) au format JSONB. L'app y écrit/lit via la clé service_role (comme les
-- droits), donc RLS reste fermé (aucun accès anon).

create table if not exists public.snapshots (
    user_id    uuid        not null,
    date       date        not null,
    frozen_at  timestamptz not null default now(),
    data       jsonb       not null,
    primary key (user_id, date)
);

alter table public.snapshots enable row level security;
-- Pas de policy publique : l'accès se fait uniquement via la clé service_role.
