# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

This repository is Owen's Obsidian vault (business notes for ZenAquatique) plus one code project:

- `docs/` — **AquaRappel**, a static PWA (no build step, no backend). Plain HTML/CSS/JS reminder assistant that speaks French (Web Speech API) to nudge Owen about unchecked to-do items. See `docs/README.md` for how to run/host it. It lives in `docs/` so it can be served for free via GitHub Pages (Settings → Pages → Deploy from branch → `main` / `docs`).
- Everything else (`Contexte/`, `Projets/`, `Calendrier Publication/`, `Mémoire Agent/`, `Scripts/`, `Analyse Marché/`, `Références/`) is Markdown notes, not code.

Update this file as the project grows to document build commands, test runners, and architecture decisions.

## - Navigation-dans-le-contexte
quand tu as besoin de comprendre le code, les docs, ou les fichiers de ce projet :
1. TOUJOURS interroger le graph de connaissance en premier : '/graphify query "ta question"'
2. Ne lire les fichiers bruts que si je dit explicitement "lis le fichier" ou "regarde le fichier brut"
3. Utiliser 'graphify-out/wiki/index.md' comme point d'entrée pour naviguer dans la structure
