---
type: plan
statut: en cours d'adaptation
source: retranscription d'un échange ChatGPT + audit Claude du 04/09/2026
---

# Plan Community Manager IA — version adaptée à l'existant

## Constat de départ

ChatGPT a proposé une architecture générique : Shopify → **Make** → **OpenAI API** →
**Canva** / **CapCut** → Instagram + Facebook → Google Sheets. C'est un bon plan pour
quelqu'un qui part de zéro. **Ce n'est pas le cas ici.**

Le projet `01 - Automatisation Contenu Social` (voir `projet.md` et `remotion.md`) a déjà
construit une chaîne équivalente, en mieux sur plusieurs points :

| Brique ChatGPT | Outil proposé | Ce qui existe déjà chez ZenAquatique |
|---|---|---|
| Cerveau IA | OpenAI API (à payer, à connecter) | **Claude**, déjà utilisé en session, déjà lit le contexte business via ce vault |
| Design + vidéo | Canva + CapCut (abonnements) | **Remotion** (React → MP4, gratuit) + voix Owen enregistrée sur CapCut |
| Automatisation | Make (abonnement, no-code) | Scripts npm (`generate-week`, `batch-render`, `batch-publish`…) — gratuit, versionné dans le dépôt vidéo |
| Publication | "Publication automatique" générique | **Meta Graph API v19.0** déjà connectée (Page FB 687765537757887, IG 17841470045036166) |
| Hébergement vidéo IG | — | **Cloudinary** (gratuit) |
| Suivi | Google Sheets | `Calendrier Publication/*.md` + statuts dans ce vault |
| Base de connaissances | Google Drive/Notion | Ce vault Obsidian (déjà le but de `Contexte/`, voir `owen-contexte.md`) |

**Conclusion : ne pas payer Make + Canva + OpenAI API en plus.** Le pipeline existant fait
déjà tourner les étapes 6 à 9 du plan ChatGPT (templates, 1ère automatisation, contenu
récurrent, publication) pour un coût logiciel quasi nul (Cloudinary gratuit, Remotion
gratuit jusqu'à 3 personnes, OpenAI TTS = seul poste payant réel). Le vrai coût de la CM
humaine était le temps, pas les outils — et ce temps est déjà largement repris par ce
pipeline.

## Ce qui manque réellement (le vrai gap vs le plan ChatGPT)

1. **Le pipeline s'est arrêté.** Dernier calendrier généré : `Calendrier Publication/mai-2026.md`
   et `juin-2026.md` (24 posts planifiés en juin, statuts encore `⏳` = jamais rendus/publiés
   au-delà de S1-S2 mai d'après `projet.md`). Aucun calendrier juillet/août/septembre.
   Aucune Routine récurrente active actuellement (`list_triggers` vide), alors que
   `Mémoire Agent/memoire.md` trace une "Routine marketing quotidienne" exécutée les
   1 et 5 juin — elle a disparu ou n'a pas été reconduite.
2. **Étapes 10 (DM/commentaires) et 12 (analyse hebdo)** du plan ChatGPT n'existent pas
   encore ici, ni côté outillage ni côté process.
3. **La base de connaissances (étapes 3-4 : ton, règles SAV, FAQ)** existait seulement de
   façon informelle et dispersée (`Mémoire Agent/memoire.md`). Elle vient d'être formalisée
   dans `Contexte/instructions-cm-ia.md` et `Contexte/faq-sav.md` (créés le 04/09/2026) —
   à relire et corriger si besoin, c'est la pièce qui garantit qu'aucune IA n'invente un
   prix ou une promesse.
4. **`Contexte/catalogue-produits.md` et `Références/catalogue-prix.md` datent du
   27/04/2026** — stock et disponibilités obsolètes. Toute réponse automatique aux DM
   ("vous avez encore X ?") doit interroger Shopify en direct, pas ce fichier.

## Feuille de route adaptée

### V1 — Relancer l'existant (aucun nouvel outil, aucun nouveau coût)
- [ ] Reprendre le pipeline Remotion là où il s'est arrêté : générer S+1 (semaine courante),
      `npm run generate-week`, valider, publier.
- [ ] Recréer une Routine récurrente (ce Claude Code Routine, pas besoin de Make) qui relance
      `generate-week` chaque mercredi pour la semaine suivante — c'était déjà le rythme
      documenté dans `projet.md`.
- [ ] Mettre à jour `Contexte/catalogue-produits.md` (stock/prix) avant de relancer la
      génération de contenu, pour éviter toute promesse produit fausse.

### V2 — Combler le vrai gap (DM/commentaires + reporting)
- [ ] **DM/commentaires (étape 10)** : le Meta Graph API est déjà connecté pour publier —
      il permet aussi de lire les commentaires/messages (webhooks Messenger/IG). Construire
      un petit scénario : webhook Meta → classification (FAQ connue vs SAV vs inconnu) →
      réponse auto si FAQ (`Contexte/faq-sav.md`) → sinon alerte Owen. Peut réutiliser
      l'infra Supabase Edge Functions déjà en place pour AquaRappel (`supabase/functions/`)
      plutôt qu'un nouvel outil.
- [ ] **Reporting hebdo (étape 12 / scénario E)** : script qui interroge les Insights de
      l'API Meta (portée, engagement, clics) + les commandes Shopify attribuées, écrit un
      résumé dans `Calendrier Publication/` et propose des ajustements de calendrier.
- [ ] Étendre `Calendrier Publication/` avec juillet → septembre 2026 une fois V1 relancée.

### V3 — Automatisation progressive (étape 13 du plan ChatGPT)
- [ ] Une fois plusieurs semaines stables : lever la validation humaine sur les contenus
      à faible risque (posts éducatifs, stories) ; garder la validation humaine sur toute
      promotion/prix (déjà la règle dans `Contexte/faq-sav.md`).
- [ ] Reels à partir de vraies vidéos (bibliothèque à constituer : bacs de culture, colis,
      crevettes) — cf. les scripts déjà écrits dans `Scripts/16-scripts-conversion.md`.

## Ce qui ne change pas du plan ChatGPT

Les garde-fous proposés (section "ce qu'elle ne doit pas décider seule") restent valables
tels quels et sont repris dans `Contexte/faq-sav.md` : pas de remboursement, pas de litige,
pas de modification de prix, pas d'affirmation de stock non vérifiée, aucune décision seule
sur un produit vivant reçu mort/malade — toujours transmis à Owen.

## Décisions à prendre par Owen

1. Confirmer qu'on relance le pipeline Remotion existant plutôt que d'introduire Make —
   sinon préciser pourquoi Make apporterait quelque chose que les scripts npm actuels
   n'ont pas.
2. Valider si le futur module DM/commentaires doit passer par Supabase (déjà payé/en place
   pour AquaRappel) ou par un nouvel outil dédié.
3. Relire `Contexte/instructions-cm-ia.md` et `Contexte/faq-sav.md` et corriger tout ce qui
   ne correspond pas exactement à la réalité du business avant de les laisser piloter des
   réponses automatiques aux clients.
