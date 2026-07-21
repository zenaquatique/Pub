# Backend Supabase — Menu Malin

## Migrations

Appliquer dans l'ordre (SQL Editor du dashboard Supabase, ou `supabase db push`
avec la CLI) :

1. `migrations/0001_init.sql` — schéma (profils, magasins, préférences,
   cache de recettes, prix moyens, sélections hebdomadaires, listes de
   courses) avec RLS activée sur toutes les tables.
2. `migrations/0002_daily_refresh_schedule.sql` — planifie l'appel
   quotidien (6h Europe/Paris) de l'Edge Function `refresh-prices`. À
   adapter avant exécution : activer `pg_cron`/`pg_net`, remplacer
   `<PROJECT_REF>` et `<SERVICE_ROLE_KEY>` (idéalement via Vault plutôt
   qu'en clair).

## Edge Function

`functions/refresh-prices` interroge l'API Open Prices (Open Food Facts)
pour une liste d'ingrédients génériques et met à jour
`ingredient_price_estimates`. Déploiement :

```bash
supabase functions deploy refresh-prices
```

Elle peut aussi être appelée manuellement pour un premier remplissage de la
table avant le premier passage du cron :

```bash
supabase functions invoke refresh-prices
```
