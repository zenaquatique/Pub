# Projet 01 — Automatisation Contenu Social

## Objectif
Produire 1 post/jour en automatisant la création de contenu pour convertir des aquariophiles en clients ZenAquatique.

## Décisions techniques
- Stack vidéo : **Remotion** (React → MP4) — `C:\Users\ec\Desktop\zenaquatique-video`
- Voix off : **OpenAI TTS** (onyx) — générée automatiquement par script
- Musique : fichiers MP3 dans `public/audio/music/` (volume 0.18)
- Publication : Meta Graph API v19.0 (Facebook Page + Instagram Reels)
- Instagram : container pré-préparé + **Windows Task Scheduler** (PC toujours allumé = OK)
- Hébergement vidéo Instagram : **Cloudinary** (gratuit)
- Format : 1080×1920 9:16 — 30fps

## Règles de production (IMPORTANT)
- **Jamais générer tout un mois d'un coup** — batch de 7 posts par semaine
- **Jamais écrire du contenu JSON à la main** — toujours un script générateur
- Générer S+1 le mercredi de la semaine en cours

## Pipeline complet (une commande par étape)
```
npm run generate-week -- 2026-05-01   → génère les données S1 (posts 1-7)
npm run batch-voiceover -- week1      → génère les 42 MP3 via OpenAI TTS
npm run durations                     → met à jour audio-durations.json
npm run batch-render -- week1         → render 7 vidéos dans out/
npm run manage                        → Owen valide chaque vidéo
npm run batch-publish -- week1        → programme Facebook + Instagram
```

## Scripts disponibles
| Script | Commande |
|--------|----------|
| Générer une semaine | `npm run generate-week -- YYYY-MM-DD` |
| Voix off batch | `npm run batch-voiceover -- weekN` |
| Calcul durées | `npm run durations` |
| Render batch | `npm run batch-render -- weekN` |
| Preview | `npm run dev` |
| Publier un post | `npm run publish -- --post-id maiXX` |
| Voir le planning | `npm run manage` |
| Annuler | `npm run cancel` |
| Statut | `npm run status` |

## Statut Meta API (27/04/2026)
- App Meta : **811960804887212**
- Page Facebook : **687765537757887** (ZenAquatique)
- Instagram ID : **17841470045036166**
- USER_TOKEN + PAGE_TOKEN : configurés dans `.env`
- Facebook : programmé côté serveurs Meta ✅
- Instagram : Task Scheduler Windows (PC toujours ON) ✅
- Instagram visible dans Business Manager : seulement après publication (pas en "programmé")

## Variables .env
```
META_USER_TOKEN=...
META_PAGE_TOKEN=...
META_PAGE_ID=687765537757887
META_APP_ID=811960804887212
META_APP_SECRET=...
META_IG_ACCOUNT_ID=17841470045036166
CLOUDINARY_CLOUD_NAME=djr0kwlp1
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
OPENAI_API_KEY=...
```

## Calendrier mai 2026
- `content/calendar-2026-05.json` — généré, contient les 7 posts S1 (01→07 mai)
- Compositions Remotion dynamiques : une par post (`20260501`…`20260507`)
- Statuts : `pending` → `voiced` → `rendered` → `approved` → `scheduled` → `published`

## Visibilité Instagram dans Business Manager
- Posts publiés → visibles dans Meta Business Suite > Contenu > Publié
- Posts à venir → **non visibles côté Meta** (Task Scheduler local, pas programmation Meta)
- Pour voir le planning Instagram → `npm run manage`

## Workflow voix off (décision 28/04/2026)

ElevenLabs abandonnée (problèmes de prononciation des noms latins, liaisons françaises incorrectes, voix trop IA).
**Nouveau workflow :**
1. Je rends la vidéo **sans voix** (visuel + musique uniquement) → `out/YYYYMMDD.mp4`
2. Je fournis le **script texte** à lire slide par slide
3. Owen enregistre sa voix et colle sur CapCut
4. Owen dépose la vidéo finale dans **`out/YYYYMMDD-final.mp4`**
5. Je lance la publication via `npm run publish`

## Statut S0 — Avril 2026

| Post | Date | Thème | Template | Publié | Media ID IG |
|------|------|-------|----------|--------|-------------|
| Concept | Mer 29 avr 18h30 | Multiplier ses boutures | 💡 Concept | ✔️ 29/04/2026 | 18035862077603694 |

## Statut S1 — Mai 2026 (mis à jour 08/05/2026)

| Post | Date | Thème | Statut |
|------|------|-------|--------|
| 20260501 | Jeu 1 mai 18h30 | Plantes rouges | 📅 Programmé |
| 20260502 | Ven 2 mai 18h30 | Débutants | 📅 Programmé |
| 20260503 | Sam 3 mai 10h00 | Croissance rapide | 📅 Programmé |
| 20260504 | Dim 4 mai 10h00 | Tapis vert | 📅 Programmé |
| 20260505 | Lun 5 mai 18h30 | Mousses | 📅 Programmé |
| 20260506 | Mar 6 mai 18h30 | Rotala | 📅 Programmé |
| 20260507 | Mer 7 mai 18h30 | Plantes rares | 📅 Programmé |

## Statut S2 — 8→10 mai 2026

| Post | Date | Statut |
|------|------|--------|
| 20260508 | Ven 8 mai 18h30 | 📅 Programmé |
| 20260509 | Sam 9 mai 10h00 | 📅 Programmé |
| 20260510 | Dim 10 mai 10h00 | 📅 Programmé |

## Prochaines étapes
- [x] Script pipeline one-command
- [x] Valider workflow voix Owen + CapCut
- [ ] Rendre posts 3→7 sans voix (même workflow)
- [ ] Publier post 01 et 02 quand vidéos finales prêtes
- [ ] `batch-render.ts` — render en batch
- [ ] `manage.ts` — tableau de bord planning
- [ ] TikTok automation
- [ ] Meta Ads automation

## Community Manager IA (04/09/2026)
Pipeline en pause depuis juin 2026 (aucun calendrier juillet/août/septembre, aucune Routine
récurrente active). Voir `plan-community-manager-ia.md` dans ce même dossier pour la feuille
de route complète (relance V1, DM/commentaires + reporting V2, automatisation progressive V3)
et la base de connaissances associée dans `Contexte/instructions-cm-ia.md` +
`Contexte/faq-sav.md`.
