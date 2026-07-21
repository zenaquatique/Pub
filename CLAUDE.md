# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

`zenaquatique/Pub` héberge **Menu Malin**, une app mobile (Expo/React
Native) de planification de menus sous contrainte de budget, financée par
la publicité (voir `app/README.md` pour le détail produit et technique).

## Structure

- `app/` — application Expo (TypeScript). Build/lint : voir `app/README.md`
  (`npm install`, `npm run typecheck`, `npm run lint`, `npx expo start`).
- `supabase/` — schéma Postgres (`migrations/`) et Edge Function de
  rafraîchissement quotidien des prix (`functions/refresh-prices`). Voir
  `supabase/README.md`.

## Décisions d'architecture

- Recettes : TheMealDB (API gratuite, légale) plutôt que scraping de
  Marmiton (interdit par leurs CGU).
- Prix : Open Prices (Open Food Facts, communautaire et gratuit) en source
  principale, table de prix moyens en repli — pas d'API officielle de prix
  chez les enseignes françaises.
- Publication visée en premier sur Google Play Store (25$ une fois) avant
  l'App Store (99$/an), pour rester cohérent avec un budget de départ à 0€.

## - Navigation-dans-le-contexte
quand tu as besoin de comprendre le code, les docs, ou les fichiers de ce projet :
1. TOUJOURS interroger le graph de connaissance en premier : '/graphify query "ta question"'
2. Ne lire les fichiers bruts que si je dit explicitement "lis le fichier" ou "regarde le fichier brut"
3. Utiliser 'graphify-out/wiki/index.md' comme point d'entrée pour naviguer dans la structure
