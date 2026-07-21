-- Schéma initial: préférences utilisateur, magasins, cache de recettes,
-- estimations de prix, sélections hebdomadaires et listes de courses.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Profils (miroir léger de auth.users)
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,
  created_at timestamptz not null default now()
);

alter table public.profiles enable row level security;

create policy "profiles: lecture de son propre profil"
  on public.profiles for select
  using (auth.uid() = id);

create policy "profiles: écriture de son propre profil"
  on public.profiles for all
  using (auth.uid() = id)
  with check (auth.uid() = id);

-- ---------------------------------------------------------------------------
-- Magasins (liste de référence, lecture publique)
-- ---------------------------------------------------------------------------
create table if not exists public.stores (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null
);

alter table public.stores enable row level security;

create policy "stores: lecture publique"
  on public.stores for select
  using (true);

insert into public.stores (slug, name) values
  ('carrefour', 'Carrefour'),
  ('leclerc', 'E.Leclerc'),
  ('auchan', 'Auchan'),
  ('intermarche', 'Intermarché'),
  ('lidl', 'Lidl'),
  ('casino', 'Casino'),
  ('monoprix', 'Monoprix'),
  ('systeme-u', 'Système U')
on conflict (slug) do nothing;

-- ---------------------------------------------------------------------------
-- Préférences utilisateur (issues de l'onboarding)
-- ---------------------------------------------------------------------------
create table if not exists public.user_preferences (
  user_id uuid primary key references auth.users (id) on delete cascade,
  weekly_budget_cents integer not null check (weekly_budget_cents >= 0),
  preferred_store_ids uuid[] not null default '{}',
  equipment text[] not null default '{}',
  disliked_ingredients text[] not null default '{}',
  meal_types text[] not null default '{}',
  updated_at timestamptz not null default now()
);

alter table public.user_preferences enable row level security;

create policy "user_preferences: accès à ses propres préférences"
  on public.user_preferences for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Cache de recettes (alimenté par TheMealDB et, plus tard, d'autres sources)
-- ---------------------------------------------------------------------------
create table if not exists public.recipes (
  id text primary key, -- ex: "mealdb:52772"
  source text not null default 'themealdb',
  title text not null,
  image_url text,
  category text,
  area text,
  instructions text,
  ingredients jsonb not null default '[]', -- [{ name, quantity, unit }]
  equipment_required text[] not null default '{}',
  meal_types text[] not null default '{}',
  cached_at timestamptz not null default now()
);

alter table public.recipes enable row level security;

create policy "recipes: lecture publique"
  on public.recipes for select
  using (true);

create index if not exists recipes_meal_types_idx on public.recipes using gin (meal_types);
create index if not exists recipes_equipment_idx on public.recipes using gin (equipment_required);

-- ---------------------------------------------------------------------------
-- Estimations de prix moyens par ingrédient (repli quand Open Prices n'a pas
-- de donnée exploitable pour l'ingrédient/magasin demandé)
-- ---------------------------------------------------------------------------
create table if not exists public.ingredient_price_estimates (
  ingredient_name text primary key,
  unit text not null,
  avg_price_cents integer not null check (avg_price_cents >= 0),
  currency text not null default 'EUR',
  source text not null default 'manual',
  updated_at timestamptz not null default now()
);

alter table public.ingredient_price_estimates enable row level security;

create policy "ingredient_price_estimates: lecture publique"
  on public.ingredient_price_estimates for select
  using (true);

-- ---------------------------------------------------------------------------
-- Sélections hebdomadaires
-- ---------------------------------------------------------------------------
create table if not exists public.weekly_selections (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users (id) on delete cascade,
  week_start date not null,
  budget_cents integer not null,
  total_cost_cents integer not null default 0,
  store_id uuid references public.stores (id),
  created_at timestamptz not null default now()
);

alter table public.weekly_selections enable row level security;

create policy "weekly_selections: accès à ses propres sélections"
  on public.weekly_selections for all
  using (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create table if not exists public.weekly_selection_recipes (
  selection_id uuid not null references public.weekly_selections (id) on delete cascade,
  recipe_id text not null references public.recipes (id),
  position integer not null default 0,
  primary key (selection_id, recipe_id)
);

alter table public.weekly_selection_recipes enable row level security;

create policy "weekly_selection_recipes: accès via la sélection parente"
  on public.weekly_selection_recipes for all
  using (
    exists (
      select 1 from public.weekly_selections ws
      where ws.id = selection_id and ws.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.weekly_selections ws
      where ws.id = selection_id and ws.user_id = auth.uid()
    )
  );

-- ---------------------------------------------------------------------------
-- Liste de courses générée pour une sélection hebdomadaire
-- ---------------------------------------------------------------------------
create table if not exists public.shopping_list_items (
  id uuid primary key default gen_random_uuid(),
  selection_id uuid not null references public.weekly_selections (id) on delete cascade,
  ingredient_name text not null,
  quantity numeric not null,
  unit text not null,
  unit_price_cents integer not null default 0,
  total_price_cents integer not null default 0,
  store_id uuid references public.stores (id),
  purchased boolean not null default false
);

alter table public.shopping_list_items enable row level security;

create policy "shopping_list_items: accès via la sélection parente"
  on public.shopping_list_items for all
  using (
    exists (
      select 1 from public.weekly_selections ws
      where ws.id = selection_id and ws.user_id = auth.uid()
    )
  )
  with check (
    exists (
      select 1 from public.weekly_selections ws
      where ws.id = selection_id and ws.user_id = auth.uid()
    )
  );
