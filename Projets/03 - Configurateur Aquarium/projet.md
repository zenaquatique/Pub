# Projet 03 — Configurateur d'aquarium

## Objectif
Sur une page dédiée (ou une fiche produit "aquarium"), le client compose visuellement son bac : il glisse des plantes, du sable, de la déco, du matériel et des poissons/crevettes dans un bac virtuel, peut les déplacer ou les retirer, puis ajoute toute sa sélection au panier en un clic.

## Décisions de cadrage (validées avec Owen)
- **Interaction** : glisser-déposer libre (pas un simple clic-pour-poser) — le client positionne où il veut, superpose, retire en sortant l'élément du bac.
- **Visuels produits** : Owen a déjà la plupart des photos détourées (fond transparent) → le prototype peut viser un catalogue large, pas juste 10-15 produits.
- **Panier** : pas de synchro en temps réel avec le panier Shopify. Le client compose librement, rien n'est ajouté tant qu'il n'a pas cliqué **"Ajouter tout au panier"** à la fin.

## Fichier livré
`configurateur-embed.html` — prototype fonctionnel autonome (HTML + CSS + JS inline, aucune dépendance externe). Glisser-déposer implémenté avec les Pointer Events (souris + tactile, contrairement à l'API HTML5 Drag&Drop qui gère mal le mobile).

Testé automatiquement (simulation de glisser-déposer avec Playwright) :
- dépôt d'un produit de la palette dans le bac → apparaît + entre dans le panier
- déplacement d'un élément posé → reste dans le bac à sa nouvelle position
- glisser un élément hors du bac → il est retiré du bac ET du panier
- bouton "×" sur un élément posé → même effet, plus accessible au tactile
- "Ajouter tout au panier" → regroupe par produit avec quantités et prix
- la composition est sauvegardée dans le navigateur du client (`localStorage`) et restaurée s'il revient sur la page

## ⚠️ Ce qui est simulé dans le prototype (à remplacer avant mise en ligne)
1. **Visuels produits** : des formes SVG de couleur (feuille, roche, sable...) remplacent les vraies photos détourées. Le code accepte déjà un champ `image` (URL) par produit — dès qu'une vraie photo PNG/WebP détourée est disponible, il suffit de la renseigner, pas besoin de retoucher le code.
2. **Catalogue** : seulement ~12 produits de démonstration (extraits de `Contexte/catalogue-produits.md`), pas tout le catalogue Shopify.
3. **`variantId`** : `null` pour tous les produits. C'est l'ID de variante Shopify qui permet d'ajouter le bon produit au panier — à récupérer pour chaque produit qu'on veut rendre "posable".
4. **`MODE_SHOPIFY = false`** en haut du script : le bouton "Ajouter au panier" affiche juste un résumé texte au lieu d'appeler le panier Shopify. Une fois les `variantId` renseignés, passer ce booléen à `true` active le vrai appel à `/cart/add.js` (le code est déjà écrit, pas mocké — juste désactivé par défaut pour que le prototype tourne n'importe où, y compris hors Shopify).

## Étapes avant une V1 en ligne
1. **Détourer/récupérer les visuels** des produits qu'on veut inclure (Owen dit en avoir déjà la plupart — à rassembler dans un format utilisable, ex. PNG transparent).
2. **Récupérer les `variantId` Shopify** de ces produits (visibles dans l'admin Shopify, sur chaque variante).
3. **Choisir l'emplacement** : une page dédiée type `/pages/composez-votre-aquarium` (recommandé — plus de place, pas contraint par le layout d'une fiche produit) ou un bloc sur une fiche "aquarium nu".
4. Remplir le tableau `CATEGORIES` avec le vrai catalogue + `image` + `variantId`, passer `MODE_SHOPIFY = true`.
5. Test réel sur le thème Shopify (le panier `/cart/add.js` ne peut être testé que depuis le domaine Shopify lui-même).

## Hors scope pour l'instant (pistes v2)
- Redimensionner/pivoter les éléments posés
- Suggestions automatiques ("plantes compatibles avec ce poisson")
- Sauvegarde de la composition sur le compte client (au lieu du navigateur) pour la retrouver sur un autre appareil
- Export d'une image de la composition (pour partager sur les réseaux, cf. le projet 01 Automatisation Contenu Social)

## Statut
- [x] Cadrage des décisions produit (interaction, visuels, panier)
- [x] Prototype fonctionnel avec catalogue de démo
- [x] Tests automatisés du glisser-déposer (Playwright)
- [ ] Owen : tester le prototype, valider l'expérience avant d'investir dans les vrais visuels/variantId
- [ ] Rassembler visuels détourés + variantId pour le catalogue final
- [ ] Choisir l'emplacement sur le site et intégrer
