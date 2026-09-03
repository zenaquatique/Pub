# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

This repository is Owen's Obsidian vault (business notes for ZenAquatique) plus one code project:

- `docs/` — **AquaRappel**, a PWA (plain HTML/CSS/JS, no build step) that reminds
  Owen in French about unchecked to-do items and speaks them aloud (Web Speech
  API), plus a real conversational assistant (Google Gemini, via a Supabase Edge
  Function) that can add/check/uncheck/delete tasks from natural-language
  French messages or voice input. Tasks sync across devices via Supabase
  (Postgres + Auth + Realtime). See `docs/README.md` for full setup (Supabase
  project, Gemini API key, Edge Function deploy) — those need Owen's own free
  accounts, so `docs/js/config.js` ships with placeholder values until he fills
  them in. Static frontend hosted for free via GitHub Pages (Settings → Pages →
  Deploy from branch → `main` / `docs`).
- `supabase/` — `schema.sql` (tasks table + RLS policies) and
  `functions/chat/index.ts` (the Gemini bridge Edge Function). Deployed via the
  Supabase dashboard or CLI, not via this repo's CI (there isn't one).
- Everything else (`Contexte/`, `Projets/`, `Calendrier Publication/`, `Mémoire Agent/`, `Scripts/`, `Analyse Marché/`, `Références/`) is Markdown notes, not code.

Update this file as the project grows to document build commands, test runners, and architecture decisions.

## - Navigation-dans-le-contexte
quand tu as besoin de comprendre le code, les docs, ou les fichiers de ce projet :
1. TOUJOURS interroger le graph de connaissance en premier : '/graphify query "ta question"'
2. Ne lire les fichiers bruts que si je dit explicitement "lis le fichier" ou "regarde le fichier brut"
3. Utiliser 'graphify-out/wiki/index.md' comme point d'entrée pour naviguer dans la structure
