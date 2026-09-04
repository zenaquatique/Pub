---
type: guide
usage: Config du module IA dans Make — Scénario A (nouveau produit Shopify → contenu)
---

# Brancher Claude dans Make (à la place d'OpenAI)

## 1. Récupérer une clé API Claude

1. Aller sur https://console.anthropic.com → créer un compte si besoin.
2. **Settings → API Keys → Create Key**. Copier la clé (elle ne se réaffiche plus après).
3. **Settings → Billing** : ajouter un moyen de paiement, vérifier les tarifs actuels du
   modèle (ils changent — ne pas se fier à un chiffre mémorisé, toujours checker la page
   pricing avant de fixer un budget mensuel).
4. Coller cette clé dans Make : **Add another app → API key** (variable, pas en dur dans
   le scénario) plutôt que de la coller dans chaque module.

## 2. Dans Make : module HTTP au lieu du module OpenAI

Make n'a pas toujours un connecteur "Anthropic/Claude" aussi mature que celui d'OpenAI
selon les régions/versions. Solution garantie à 100% : le module générique
**HTTP → Make a request**, qui appelle l'API Claude directement.

**Configuration du module HTTP :**

- URL : `https://api.anthropic.com/v1/messages`
- Method : `POST`
- Headers :
  | Nom | Valeur |
  |---|---|
  | `x-api-key` | `{{votre clé API}}` |
  | `anthropic-version` | `2023-06-01` |
  | `content-type` | `application/json` |
- Body type : `Raw` / JSON
- Body (exemple pour le Scénario A — nouveau produit Shopify) :

```json
{
  "model": "claude-sonnet-5",
  "max_tokens": 1024,
  "system": "VOIR SECTION 3 CI-DESSOUS",
  "messages": [
    {
      "role": "user",
      "content": "Nouveau produit Shopify.\nNom : {{1.title}}\nPrix : {{1.price}}€\nDescription : {{1.body_html}}\n\nGénère, en respectant strictement les règles ci-dessus :\n1. Une légende Instagram (rendu humain, pas un listing)\n2. Un angle de post (ex: éducatif, versus, promo, concept)\n3. Un CTA court\n4. Une idée de script de Reel en 1 phrase\n\nRéponds UNIQUEMENT en JSON strict avec les clés : legende, angle, cta, idee_reel. Pas de texte avant/après le JSON."
    }
  ]
}
```

(Remplacer `{{1.title}}` etc. par les champs réels renvoyés par le module Shopify
"Watch Products" placé avant celui-ci dans le scénario.)

## 3. Le "system prompt" — coller le contenu de la base de connaissances

Le champ `"system"` ci-dessus doit contenir le ton de marque et les règles factuelles
déjà écrites dans ce vault, pour que Claude ne les réinvente pas à chaque appel. Copier-coller
le contenu de :
- `Contexte/instructions-cm-ia.md` (ton + faits vérifiés)
- `Contexte/faq-sav.md`, section "Ce que l'IA a le droit de faire" (pour rappeler les limites)

Exemple condensé à coller dans `"system"` (à réajuster si ces fichiers changent) :

```
Tu es le community manager IA de ZenAquatique (aquariophilie, vente de boutures de
plantes et matériel). Ton : humain, aquariophile passionné 15 ans d'expérience, jamais
un listing froid. Registre "tu", direct, sans exagération.

Faits interdits à contredire :
- Les plantes ne meurent PAS en 2 semaines.
- Un pot en animalerie coûte environ 5€, pas 10€.
- Les plantes de magasin peuvent aussi se multiplier.
- Les plantes de magasin ne sont PAS traitées au pesticide.

Différenciateurs réels à utiliser : cultivé en milieu aquatique (pas d'adaptation
hors-eau), origine France/Europe, expédition chaque lundi, emballage protégé, vente
directe sans intermédiaire.

Ne jamais inventer un prix, un stock ou une caractéristique produit non fournie dans
le message. Si une info manque, laisse un champ vide plutôt que d'inventer.
```

## 4. Parser la réponse Claude

La réponse HTTP de l'API Claude a cette forme :

```json
{
  "content": [
    { "type": "text", "text": "{\"legende\": \"...\", \"angle\": \"...\", \"cta\": \"...\", \"idee_reel\": \"...\"}" }
  ]
}
```

Dans Make, après le module HTTP :
1. Ajouter un module **JSON → Parse JSON** sur `{{2.data.content[1].text}}` (ou l'index
   correspondant selon la sortie du module HTTP) pour extraire le JSON généré par Claude.
2. Un second Parse JSON n'est utile que si le premier niveau contient du texte échappé —
   sinon un seul suffit puisque Claude renvoie déjà du JSON dans `text`.
3. Mapper `legende`, `angle`, `cta`, `idee_reel` vers les colonnes du Google Sheet /
   `Calendrier Publication/` du mois en cours.

## 5. Test

1. Dans Make, cliquer **Run once** sur le scénario.
2. Ajouter/modifier un produit test sur Shopify pour déclencher le trigger.
3. Vérifier la ligne créée dans le Sheet : légende cohérente avec le ton, pas de prix/stock
   inventé, CTA présent.
4. Ne pas activer la publication automatique tant que ce test n'est pas validé plusieurs
   fois de suite (garde-fou "validation humaine" du plan).

## Note — alternative sans Make

Le pipeline `Projets/01 - Automatisation Contenu Social/projet.md` fait déjà cet appel à
Claude nativement (c'est moi qui génère les props des vidéos Remotion). Si le seul besoin
est "produit Shopify → légende/angle/CTA/idée de Reel", il est possible de le faire sans
Make du tout, avec un script Node qui appelle l'API Claude directement — évite l'abonnement
Make si le volume est faible. À utiliser Make surtout si tu veux une interface visuelle pour
modifier le scénario toi-même sans coder.
