-- AquaRappel — migration 002 : dates d'échéance + notifications push planifiées
-- À exécuter une fois dans : Dashboard Supabase > SQL Editor > New query > coller > Run.
-- (à exécuter après supabase/schema.sql)

-- 1. Date d'échéance sur les tâches (pour le calendrier / "à faire aujourd'hui")
alter table public.tasks
  add column if not exists due_date date;

create index if not exists tasks_due_date_idx on public.tasks (due_date);

-- 2. Abonnements aux notifications push (un par appareil)
create table if not exists public.push_subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  endpoint text not null,
  p256dh text not null,
  auth_key text not null,
  created_at timestamptz not null default now(),
  unique (endpoint)
);

alter table public.push_subscriptions enable row level security;

drop policy if exists "Users manage their own push subscriptions" on public.push_subscriptions;
create policy "Users manage their own push subscriptions"
  on public.push_subscriptions
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- 3. Réglages des rappels (plage horaire, fréquence) — un par utilisateur
create table if not exists public.reminder_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  window_start_hour smallint not null default 10 check (window_start_hour between 0 and 23),
  window_end_hour smallint not null default 22 check (window_end_hour between 0 and 23),
  interval_minutes int not null default 60,
  last_reminder_at timestamptz,
  last_digest_date date,
  updated_at timestamptz not null default now()
);

alter table public.reminder_settings enable row level security;

drop policy if exists "Users manage their own reminder settings" on public.reminder_settings;
create policy "Users manage their own reminder settings"
  on public.reminder_settings
  for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- Le job planifié (service role) doit pouvoir lire/écrire tous les réglages ;
-- le service role contourne RLS de toute façon, donc rien à ajouter ici.

drop trigger if exists reminder_settings_set_updated_at on public.reminder_settings;
create trigger reminder_settings_set_updated_at
  before update on public.reminder_settings
  for each row
  execute function public.set_updated_at();

-- 4. Planification : appelle la fonction "send-reminders" toutes les 15 minutes.
-- Nécessite les extensions pg_cron et pg_net (disponibles sur tous les projets Supabase).
create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.unschedule('aquarappel-send-reminders')
where exists (select 1 from cron.job where jobname = 'aquarappel-send-reminders');

select cron.schedule(
  'aquarappel-send-reminders',
  '*/15 * * * *',
  $$
  select net.http_post(
    url := 'https://frrmyqqqblheoocgvopp.supabase.co/functions/v1/clever-handler',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'x-cron-secret', 'REPLACE_WITH_CRON_SECRET'
    ),
    body := '{}'::jsonb
  );
  $$
);

-- Remplace REPLACE_WITH_CRON_SECRET ci-dessus par la même valeur que le secret
-- CRON_SECRET configuré sur la fonction send-reminders (Edge Functions >
-- send-reminders > Secrets) avant d'exécuter ce script. Ce secret n'est écrit
-- nulle part ailleurs dans ce dépôt.
-- L'URL ci-dessus est déjà celle du projet Supabase d'Owen (identique à
-- docs/js/config.js) et ne contient rien de secret.
