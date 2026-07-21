# Menu Malin

Application mobile (Expo / React Native) de planification de menus sous
contrainte de budget : l'utilisateur renseigne son budget hebdomadaire, ses
magasins, son équipement de cuisine et ses préférences alimentaires, puis
compose son menu de la semaine en restant dans son budget. L'app génère
ensuite la liste de courses (avec prix estimés) et les recettes de chaque
plat choisi.

Monétisation prévue : publicités (AdMob), pas d'achat in-app.

## Stack

- **Expo (React Native + TypeScript)**, routing via `expo-router`
- **Supabase** (auth, base Postgres, Edge Functions) — free tier
- **TheMealDB** comme source de recettes (API gratuite, usage légal)
- **Open Prices** (Open Food Facts) comme source de prix communautaire,
  rafraîchie quotidiennement à 6h (Europe/Paris) par une Edge Function
  planifiée avec `pg_cron` — voir `../supabase/`

## Mise en route

1. Créer un projet [Supabase](https://supabase.com) (gratuit) et appliquer
   les migrations du dossier `../supabase/migrations` (SQL Editor ou CLI
   Supabase).
2. Copier `.env.example` vers `.env` et renseigner l'URL et la clé anonyme
   du projet Supabase.
3. Installer les dépendances et lancer le projet :

   ```bash
   npm install
   npx expo start
   ```

4. Vérifications avant commit :

   ```bash
   npm run typecheck
   npm run lint
   ```

## Structure

```
src/
  app/            routes expo-router (4 onglets : index, recipes, shopping-list, account)
  screens/        écrans (logique + UI) montés par les routes
  components/     composants réutilisables (thème, chips…)
  context/        AuthContext (session Supabase)
  hooks/          usePreferences, useStores, useLatestSelection
  lib/
    api/          clients TheMealDB + cache de recettes Supabase
    planner/      sélection hebdomadaire sous budget + génération de la liste de courses
    pricing.ts    estimation du coût des recettes/ingrédients
    supabase.ts   client Supabase
```

## Limites connues (V1)

- **Recettes** : TheMealDB propose surtout de la cuisine internationale, pas
  spécifiquement française. À enrichir plus tard avec d'autres sources
  légales (API, partenariats, ou saisie manuelle) si besoin de plus de
  volume/de cuisine française.
- **Prix** : TheMealDB ne fournit pas de quantités standardisées, donc le
  coût d'une recette est une **estimation**, pas un total de caisse exact
  (voir le commentaire en tête de `src/lib/pricing.ts` pour le détail de la
  méthode). Aucune enseigne française ne propose d'API de prix publique ;
  Open Prices (communautaire) sert de source, avec un tableau de prix
  moyens en repli.
- **Publicités** : non encore intégrées. Ajouter
  `react-native-google-mobile-ads` (config plugin Expo) + créer un compte
  AdMob une fois l'app fonctionnelle, avant la publication.
- **Publication** : viser le **Google Play Store** en premier (inscription
  développeur à 25$, paiement unique) plutôt que l'App Store (99$/an chez
  Apple) — plus cohérent avec un budget de départ à 0€. Build/soumission via
  [EAS](https://docs.expo.dev/eas/) (free tier disponible).
