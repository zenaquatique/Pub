-- Planifie l'appel quotidien (6h Europe/Paris) de l'Edge Function
-- "refresh-prices" qui met à jour ingredient_price_estimates à partir
-- d'Open Prices (Open Food Facts).
--
-- pg_cron s'exécute en UTC. 6h Europe/Paris = 4h UTC en été (CEST) et
-- 5h UTC en hiver (CET). On planifie les deux horaires ; l'Edge Function
-- ignore l'appel si elle a déjà tourné dans les 12 dernières heures, donc
-- ce doublon saisonnier est sans effet.
--
-- Prérequis avant d'exécuter cette migration sur le projet Supabase réel :
--   1. Activer les extensions "pg_cron" et "pg_net" (Dashboard > Database > Extensions)
--   2. Stocker l'URL du projet et une clé de service dans Vault, puis
--      remplacer <PROJECT_REF> et <SERVICE_ROLE_KEY> ci-dessous (ou les lire
--      depuis vault.decrypted_secrets).

create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.schedule(
  'refresh-ingredient-prices-summer',
  '0 4 * * *',
  $$
  select net.http_post(
    url := 'https://<PROJECT_REF>.supabase.co/functions/v1/refresh-prices',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer <SERVICE_ROLE_KEY>'
    ),
    body := '{}'::jsonb
  );
  $$
);

select cron.schedule(
  'refresh-ingredient-prices-winter',
  '0 5 * * *',
  $$
  select net.http_post(
    url := 'https://<PROJECT_REF>.supabase.co/functions/v1/refresh-prices',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer <SERVICE_ROLE_KEY>'
    ),
    body := '{}'::jsonb
  );
  $$
);
