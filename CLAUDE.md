# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Status

This is a new, empty repository (`zenaquatique/Pub`). Only an empty `README.md` exists so far. No build system, language, or tooling has been configured yet.

Update this file as the project grows to document build commands, test runners, and architecture decisions.

## Wiki-Brain Knowledge System

This project uses wiki-brain with a vault at `{{VAULT_PATH}}`.

### Structure du vault

- **wiki/** — pages de connaissance maintenues par Claude
- **raw/** — sources originales immuables
- **graphify-out/** — index auto-générés
- **log.md** — journal d'activité de session

### Workflow principal

Quand du contexte est nécessaire :
1. Interroger le graphe de connaissances en premier avec `graphify query`
2. Consulter `wiki/index.md` pour la navigation
3. Référencer `graphify-out/wiki/index.md` si disponible
4. Lire les fichiers raw uniquement si explicitement demandé ou si les requêtes du graphe ne répondent pas

### Règles de gestion de session

**Ingestion :** Quand des sources sont ajoutées dans `raw/`, les résumer, créer des pages wiki avec des liens croisés agressifs en syntaxe `[[Nom de Page]]`, mettre à jour l'index et journaliser l'activité.

**Journal de session :** Terminer chaque session avec une entrée dans `log.md` :
```
## [YYYY-MM-DD HH:MM] session | <titre 3-8 mots>
Touchées : <pages modifiées séparées par des virgules ou "aucune">
```

**Persistance des connaissances :** Ne mettre à jour les pages wiki que si la session a produit des connaissances durables. Les sessions triviales n'ont besoin que d'une entrée de log.

### Principes clés

- Les fichiers raw sont immuables
- Claude est pleinement responsable de la structure wiki
- Toujours maintenir `wiki/index.md`
- Créer des liens bidirectionnels librement pour éviter les pages isolées
