# Projet 03 — Configurateur d'aquarium

## Objectif
Sur une page dédiée (ou une fiche produit "aquarium"), le client compose visuellement son bac : il choisit sa cuve, son sol, puis glisse des plantes, du sable, de la déco, du matériel et des poissons/crevettes dans un bac virtuel. Il peut les déplacer ou les retirer, puis ajoute toute sa sélection au panier en un clic.

## Décisions de cadrage (validées avec Owen)
- **Interaction** : glisser-déposer libre (pas un simple clic-pour-poser).
- **Panier** : pas de synchro en temps réel — le client compose librement, rien n'est ajouté tant qu'il n'a pas cliqué **"Ajouter tout au panier"** à la fin.
- **v2 (cette itération)** :
  - le bac est **trop petit** dans la v1 → agrandi, et la taille de la scène s'adapte maintenant à la cuve choisie
  - palette organisée en **colonnes rétractables par catégorie** (`<details>`, ouverture/fermeture au clic)
  - catégories alignées sur celles du site (voir note ci-dessous)
  - le **sol** n'est plus un item qu'on glisse : c'est un contrôle dédié (produit + hauteur 3/5 cm) qui remplace tout le fond du bac et calcule automatiquement le nombre de sacs
  - la **cuve** vendue par ZenAquatique est sélectionnable en étape 1 ; ses dimensions réelles pilotent la taille de la scène et le calcul du sol

## ⚠️ Catégories : je n'ai pas pu consulter zen-aquatique.fr en direct
L'accès au site est bloqué depuis cet environnement (proxy réseau). Les catégories utilisées reprennent celles déjà présentes dans le coffre (`Contexte/catalogue-produits.md` : Plantes, Crevettes, Décoration, Substrats, Outillage, Aquariums) + celles qu'il a fallu ajouter pour couvrir la liste envoyée (Éclairage, Chauffage, Filtration, Air & CO2). **À corriger si les vraies collections Shopify sont nommées ou regroupées différemment.**

## Étape 1 — Le bac
Sélecteur avec les 7 tailles de cuve Aquael. Dimensions (L×l×h en cm) utilisées pour la scène et le calcul du sol — **valeurs standard indicatives, à confirmer auprès d'Aquael** (25L, 45L, 54L confirmées par les proportions habituelles du secteur ; 112L/200L/240L/375L estimées par extrapolation) :

| Bac | Dimensions (cm) | Prix |
|---|---|---|
| 25L | 40×25×25 | 25,99€ |
| 45L | 50×30×30 | 39,99€ |
| 54L | 60×30×30 | 49,99€ |
| 112L | 80×35×40 | ≈79,99€ |
| 200L | 100×40×50 | ≈119,99€ |
| 240L | 120×40×50 | ≈149,99€ |
| 375L | 150×50×50 | ≈219,99€ |

Changer de bac redimensionne la scène (largeur max + ratio longueur/hauteur) et recalcule automatiquement le sol si un sol est déjà choisi. Un indicateur "X / ~N éléments conseillés" sous le bac donne une idée de la place disponible selon la cuve (repère indicatif, pas une vraie détection de collision — voir "Hors scope").

## Étape 2 — Le sol
Reprend la formule du **Projet 02** (volume = longueur × largeur × hauteur / 1000, +10% de marge) en utilisant les dimensions du bac choisi à l'étape 1 :
- Produit : Dennerle Substrate 2.5L (sol nutritif), Sable Fin Rivière ou Sable Fin Blanc Neige (sable pur)
- Hauteur totale : 3 cm ou 5 cm
- Résultat : nombre de sacs calculé automatiquement, ajouté au panier, fond du bac recoloré et redimensionné visuellement en conséquence
- Changer de produit ou de hauteur **remplace** le sol précédent (pas d'empilement)

**Sable de recouvrement obligatoire avec un sol nutritif** (demande d'Owen — en aquascaping le sol nutritif se recouvre toujours d'une fine couche de sable, sinon il se disperse/se ternit) : dès que le Dennerle Substrate est choisi, un second sélecteur "sable de recouvrement" apparaît et devient obligatoire (pré-rempli par défaut, modifiable), **avec sa propre hauteur 3 ou 5 cm, indépendante de celle du sol nutritif** — les deux hauteurs s'additionnent (ex. 5 cm de sol + 3 cm de recouvrement = 8 cm de substrat total, jusqu'à 10 cm si les deux sont à 5 cm).

Les deux produits (sol nutritif + sable de recouvrement) sont calculés séparément avec leurs propres contenances et leur propre hauteur, affichés en deux lignes dans le panier, et le fond du bac affiche visuellement les deux couches superposées. Pour un sable pur (pas de sol nutritif), pas de recouvrement : une seule couche, comme avant.

## Palette (étape 3) — colonnes rétractables
8 catégories, chacune un bloc `<details>` que le client ouvre/ferme. Contenu = tout le catalogue envoyé, **hors packs et cartes-cadeaux** (à sa demande) et hors "Formation Standard" (service, pas un produit à poser dans le bac — à confirmer si à inclure ailleurs) :

| Catégorie | Nb produits |
|---|---|
| Plantes | 28 |
| Crevettes & accessoires | 8 |
| Décoration | 5 |
| Éclairage | 11 |
| Chauffage | 9 |
| Filtration | 7 |
| Air & CO2 | 4 |
| Outillage & entretien | 4 |

## ⚠️ Prix approximatifs — à vérifier avant mise en ligne
Les prix venant du catalogue connu (`Contexte/catalogue-produits.md`) sont exacts. Pour tout le reste (produits nouveaux dans la liste envoyée, tout l'Éclairage, tout le Chauffage sauf 25W, toute la Filtration, les 4 grandes cuves...), j'ai mis des **prix indicatifs** (préfixés `≈` dans l'interface) pour que le prototype reste utilisable — ce ne sont pas de vrais prix Shopify. Liste complète des produits marqués `prixApprox: true` dans le fichier, à corriger avec les vrais prix + `variantId` avant mise en ligne.

## Fichier livré
`configurateur-embed.html` — prototype fonctionnel autonome (HTML + CSS + JS inline, aucune dépendance). Glisser-déposer en Pointer Events (souris + tactile).

Testé automatiquement (Playwright), **dans la page d'aperçu telle qu'elle est réellement vue** (pas seulement le widget nu — un premier passage de tests sur le widget seul n'avait pas détecté que le cadre d'aperçu bridait l'effet, cf. ci-dessous) :
- changement de bac → le bac est **réellement** plus grand pour une plus grande cuve (556px de large en 25L vs 981px en 375L, mesuré dans la page d'aperçu complète), capacité indicative mise à jour
- sélection sol + hauteur du sol → fond du bac recoloré/redimensionné, sacs calculés, ligne ajoutée au panier
- sol nutritif → sable de recouvrement obligatoire affiché avec sa propre hauteur 3/5cm, deux lignes calculées séparément dans le panier (hauteurs indépendantes, ex. 5cm + 3cm), deux couches visibles dans le bac
- changement du produit et/ou de la hauteur de recouvrement → recalcul immédiat de sa ligne, indépendamment de la hauteur du sol
- retour à un sable pur → la ligne de recouvrement se cache réellement (bug de spécificité CSS corrigé : une classe partagée forçait `display:flex` et empêchait `hidden` de fonctionner)
- changement de bac avec sol déjà choisi → recalcul avec les nouvelles dimensions
- ouverture/fermeture d'une catégorie (colonne rétractable)
- **la palette défile réellement sur tout son contenu** (les 28 plantes, pas seulement les 7 premières) : la palette était en `display:flex; flex-direction:column` avec `overflow-y:auto`, un conteneur flex-column ne réduit pas toujours ses enfants correctement quand le contenu dépasse sa hauteur, ce qui empêchait le défilement de s'activer et laissait le contenu déborder hors du cadre au lieu de défiler dedans (silencieusement — le HTML et le texte étaient corrects, seul l'affichage était cassé). Passé en conteneur bloc simple.
- glisser-déposer d'un produit (dépôt, déplacement, retrait) — toujours fonctionnel comme en v1
- "Ajouter tout au panier" (simulation) → regroupe sol + recouvrement + items avec quantités
- sauvegarde `localStorage` (bac, sol, recouvrement + ses hauteurs, items placés) et restauration après rechargement

**Point de méthode retenu** : le premier correctif de la taille du bac avait été validé uniquement sur le fichier `configurateur-embed.html` isolé, qui a fonctionné — mais la page d'aperçu qui l'entoure (bannière + cadre) a sa propre largeur maximale, qui bridait silencieusement l'effet. Les tests portent maintenant sur la page d'aperçu complète, comme le lien qu'Owen ouvre réellement.

## ⚠️ Ce qui reste simulé (à remplacer avant mise en ligne)
1. **Visuels produits** : formes SVG par catégorie, pas de vraies photos détourées. Le code n'a pas encore de champ `image` par produit dans cette v2 (à ajouter en même temps que les vrais visuels).
2. **`variantId`** : `null` partout — à récupérer dans l'admin Shopify pour chaque produit qu'on veut inclure.
3. **`MODE_SHOPIFY = false`** : le vrai appel à `/cart/add.js` est déjà écrit dans le code, juste désactivé par défaut.
4. **Prix approximatifs** : voir tableau ci-dessus.
5. **Dimensions des bacs** : valeurs indicatives, à confirmer auprès d'Aquael.
6. **Catégories** : à confirmer/corriger, le site n'a pas pu être consulté en direct.

## Hors scope pour l'instant (pistes v2)
- Vraie détection de collision/espace occupé dans le bac (l'indicateur de capacité est juste un repère, pas une contrainte)
- Redimensionner/pivoter les éléments posés
- Suggestions automatiques ("plantes compatibles avec ce poisson")
- Sauvegarde de la composition sur le compte client (au lieu du navigateur)
- Export d'une image de la composition (pour partager sur les réseaux, cf. Projet 01)

## Statut
- [x] Bac agrandi + scène qui s'adapte à la cuve choisie
- [x] Palette en colonnes rétractables par catégorie
- [x] Sol dédié (produit + hauteur) qui remplace tout le fond et calcule les sacs
- [x] Catalogue complet envoyé par Owen intégré (hors packs/cartes-cadeaux)
- [x] Tests automatisés (Playwright) de toutes les nouvelles interactions
- [ ] Owen : confirmer/corriger les catégories par rapport au vrai site
- [ ] Owen : fournir les vrais prix pour tout ce qui est marqué `≈`
- [ ] Rassembler visuels détourés + variantId pour le catalogue final
- [ ] Vérifier les dimensions réelles des cuves Aquael 112/200/240/375L
