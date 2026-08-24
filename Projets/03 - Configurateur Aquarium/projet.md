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

## v3 — validé en conditions réelles sur Shopify (thème dupliqué)
Owen a testé le bloc collé sur une vraie copie de thème, en éditeur Shopify — première validation grandeur nature. Deux retours corrigés :

1. **Le widget ne doit jamais forcer la largeur de la page.** La v2 forçait le widget entier à s'élargir selon la cuve choisie (`racine.style.maxWidth = ...`) pour que le bac ait de la place pour grandir. Problème : ça pouvait pousser/casser le conteneur du thème sur une page où il n'y a pas cette place. Supprimé — le widget reste maintenant **toujours à 100% de la largeur que la page lui donne**, jamais plus. Le bac grandit seulement dans la limite de la place réellement disponible (via sa propre `max-width`, toujours plafonnée par la colonne "scène" du widget) : sur une page large, la différence entre une petite et une grande cuve reste bien visible ; sur une page étroite, toutes les cuves se ramènent proportionnellement à l'espace dispo — comportement honnête, jamais de débordement.
2. **Les éléments posés (plantes, déco...) étaient à taille fixe (46px)**, donc minuscules dans un grand bac. Ils s'échelonnent maintenant avec la taille **réellement affichée** du bac (mesurée après mise en page, pas la taille "théorique") — de ~34px sur une petite cuve à ~84px sur une grande, plafonné dans les deux sens. Testé : 43px en 25L → 78px en 375L sur une page large.

**Bug trouvé en creusant #2** : la mise à l'échelle donnait des résultats incohérents au premier essai (les petites cuves donnaient des objets plus gros que les grandes !). Cause : une transition CSS animée sur la largeur du bac (`transition: max-width 0.25s ease`), combinée à une mesure de la largeur faite en JavaScript **immédiatement** après le changement de cuve — donc avant que l'animation ait eu le temps de se terminer. La mesure captait une valeur intermédiaire (parfois même quasi celle de l'ancienne cuve), pas la taille finale. Transition supprimée sur le bac : le changement de taille est maintenant instantané, la mesure est donc toujours fiable.

## v4 — le bloc collé sur Shopify n'affichait plus rien du tout
Après le collage d'une nouvelle version du code, plus rien ne s'affichait sur la page Shopify (avant, la v3 fonctionnait). Diagnostic par étapes :
1. Vérification que le JS n'a pas de faute de syntaxe (`node --check`) — OK, le fichier est valide.
2. Recherche de séquences `{{ }}` ou `{% %}` dans le fichier (ces caractères ont un sens spécial pour le moteur Liquid de Shopify et peuvent faire échouer le rendu de tout le bloc s'ils apparaissent, même par accident, dans un commentaire ou une chaîne JS) — aucune trouvée.
3. Envoi à Owen d'un mini bloc de test isolé (juste un `<div>` + un `<script>` de quelques lignes) pour vérifier que le bloc Custom Liquid lui-même fonctionne bien à cet endroit de son thème — **confirmé fonctionnel**, donc le problème vient bien du contenu du fichier complet, pas de l'emplacement.
4. En comparant le fichier au mini bloc qui marchait : un seul caractère spécial trouvé dans tout le fichier — un emoji (⚠️, avertissement + variateur, un caractère Unicode sur 4 octets) dans le commentaire d'en-tête. Et 152 occurrences d'un caractère de type "tiret de dessin de boîte" (─, différent d'un tiret normal) utilisé comme décoration dans 5 commentaires JS. Ces caractères, contrairement aux accents français classiques (é, à...) qui passent partout, sont plus susceptibles de se faire tronquer ou corrompre silencieusement selon la chaîne d'enregistrement utilisée (éditeur → presse-papier → champ Shopify).
5. **Correctif** : suppression du commentaire d'en-tête (emoji compris, il ne servait qu'à la doc interne) et des tirets décoratifs dans les commentaires JS, remplacés par du texte simple. Le fichier ne contient plus aucun caractère en dehors des accents français, `€`, `×`, `≈`, `—` et `→` — tous utilisés couramment et sans risque connu.
6. Fichier envoyé à Owen **en pièce jointe** (plutôt que collé dans le chat) pour qu'il copie depuis un fichier texte brut plutôt que depuis une bulle de conversation formatée, évitant tout risque de reformatage (guillemets, tirets) au moment du copier-coller.

**Confirmé par Owen** : ça marche, le widget s'affiche et fonctionne sur la vraie boutique (bac 375L testé, glisser-déposer, calcul du sol, panier — tout est opérationnel).

## v5 — retours du premier test grandeur nature réussi
Trois retours après le premier essai fonctionnel sur la vraie boutique :

1. **Le sol (sable/nutritif) ne se voyait plus dans le bac.** Cause probable : sur le vrai thème Shopify (contrairement à mes tests isolés), une couleur de fond ou un habillage de section peut réduire le contraste entre l'eau et le sol. Correctif défensif : `z-index` explicite sur les 3 couches (eau=1, sol=2, recouvrement=3, les objets posés restent au-dessus avec un z-index ≥ 10) pour garantir l'ordre d'empilement quoi qu'il arrive, + une bordure sombre de 2px en haut du sol et du recouvrement pour qu'ils restent visibles même si leur couleur se fond dans l'arrière-plan du thème.
2. **Les photos produit étaient rognées ("pas en entière").** Cause : `object-fit: cover` remplit la case en recadrant l'image si ses proportions ne sont pas carrées — pour des photos détourées (souvent hautes et étroites), ça coupait le haut/bas ou les côtés. Remplacé par `object-fit: contain` : la photo entière est toujours visible, réduite pour tenir dans la case (comme le fait déjà l'icône SVG de secours).
3. **"Impossible de scaler la photo"** — même cause que le point 2 : avec `cover`, l'image semblait "collée" à une taille fixe indépendamment de la case. Avec `contain`, elle suit maintenant correctement `--zaq-item-size` (donc la taille du bac choisi), comme prévu à l'origine.

**À confirmer par Owen** : que le sol est maintenant bien visible avec la bordure de contraste, et que les photos s'affichent en entier et à la bonne taille.

## v6 — le sol restait invisible malgré tout, changement d'architecture
Malgré plusieurs correctifs successifs (z-index, bordure de contraste, `!important`, hauteurs en pixels au lieu de %), le sol restait totalement invisible sur le vrai thème Shopify d'Owen — y compris une bordure rouge vif de test qui n'apparaissait toujours pas du tout. Comme même une simple bordure CSS statique (pas dépendante du JS) ne s'affichait pas sur les divs `#zaq-fond` / `#zaq-fond-cap`, le problème ne pouvait plus raisonnablement venir d'un souci de couleur ou de spécificité CSS.

**Changement d'architecture** : au lieu de peindre le sol sur deux divs enfants séparés du bac, tout (eau + recouvrement + sol) est maintenant peint en **un seul dégradé CSS avec paliers nets**, posé directement sur `.zaq-builder__tank` lui-même (`appliquerVisuelBac()` en JS, via `background-image` en `!important`) — c'est l'élément dont on est sûr à 100% qu'il s'affiche, puisque son propre fond (`#dff0e6`) est visible sur toutes les captures d'Owen depuis le début. Les anciens divs `#zaq-fond`/`#zaq-fond-cap`/`.zaq-builder__eau` restent dans le HTML pour ne pas casser la structure, mais sont rendus transparents et ne portent plus aucun visuel.

**À confirmer par Owen** : est-ce que le sol s'affiche enfin avec cette version.

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
- **dépôt précis au pixel près** : `left/top: X%` sur un élément posé se calcule par rapport à la boîte de padding du bac (sans sa bordure de 8px), alors que le point de dépôt était mesuré sur la boîte englobante complète (avec la bordure) — l'élément posé dérivait donc de quelques px vers la droite/le bas selon l'endroit du bac où on lâchait. Corrigé (mesuré : 0px d'écart après correction, contre un écart allant jusqu'à ~8px avant).
- "Ajouter tout au panier" (simulation) → regroupe sol + recouvrement + items avec quantités
- sauvegarde `localStorage` (bac, sol, recouvrement + ses hauteurs, items placés) et restauration après rechargement
- **photo produit** : quand un produit a une `image` renseignée, elle remplace le pictogramme SVG (palette, bac, fantôme de glisser) ; sans image, le pictogramme de secours de la catégorie continue de s'afficher — testé dans les deux cas

**Point de méthode retenu** : le premier correctif de la taille du bac avait été validé uniquement sur le fichier `configurateur-embed.html` isolé, qui a fonctionné — mais la page d'aperçu qui l'entoure (bannière + cadre) a sa propre largeur maximale, qui bridait silencieusement l'effet. Les tests portent maintenant sur la page d'aperçu complète, comme le lien qu'Owen ouvre réellement.

## ⚠️ Ce qui reste simulé (à remplacer avant mise en ligne)
1. **Visuels produits** : le code sait afficher une vraie photo (champ `image`, 5e argument de `pr(...)`) mais **je n'ai pas accès à tes vraies photos produit depuis cet environnement** (pas d'accès à Shopify ni à internet) — tous les produits sont donc encore sur le pictogramme SVG de secours. Deux façons de les ajouter, voir section dédiée ci-dessous.
2. **`variantId`** : `null` partout — à récupérer dans l'admin Shopify pour chaque produit qu'on veut inclure.
3. **`MODE_SHOPIFY = false`** : le vrai appel à `/cart/add.js` est déjà écrit dans le code, juste désactivé par défaut.
4. **Prix approximatifs** : voir tableau ci-dessus.
5. **Dimensions des bacs** : valeurs indicatives, à confirmer auprès d'Aquael.
6. **Catégories** : à confirmer/corriger, le site n'a pas pu être consulté en direct.

## Ajouter les vraies photos produit
Le code accepte déjà un champ `image` par produit (URL) — dès qu'il est renseigné, il remplace automatiquement le pictogramme partout (palette, bac, glisser-déposer), sans autre modification. Deux façons de le remplir :

**⚠️ Les photos ne s'afficheront pas dans l'aperçu Artifact (claude.ai)** — la première photo réelle ajoutée (Hygrophila Polysperma) a été testée, mais l'aperçu publié sur claude.ai bloque le chargement de toute image externe par sécurité (seules les polices Google Fonts passent). Ce n'est pas un bug ni une mauvaise URL : ça ne se produira pas sur la vraie fiche Shopify, où les images se chargent normalement. Pour voir les photos en vrai avant publication : dupliquer le thème Shopify (Boutique en ligne → Thèmes → Dupliquer), coller le bloc sur la copie, et utiliser le bouton "Aperçu" de l'éditeur de thème — lien privé, invisible pour les clients, jusqu'à publication volontaire de cette copie.

Bug corrigé au passage : quand une photo ne charge pas, le texte alternatif débordait de la petite case au lieu de rester propre (repéré grâce au retour d'Owen sur l'aperçu). Le visuel (photo ou pictogramme) est maintenant dans un conteneur avec `overflow:hidden` séparé du bouton "×" (qui doit lui rester visible en dehors de la case) — testé avec une image volontairement cassée : la case reste à sa taille normale, rien ne déborde, le bouton de suppression reste cliquable.

**A. À la main (rapide à démarrer, long pour 76 produits)** — pour chaque produit à illustrer : dans l'admin Shopify → Produits → [le produit] → clic droit sur la photo → copier l'adresse de l'image (ou ouvrir l'image en grand et copier son URL `cdn.shopify.com/...`) → coller dans le 5e argument de son `pr(...)` dans `configurateur-embed.html`, ex. :
```js
pr('crypto-lucens', 'Cryptocoryne Lucens', 1.99, false, 'https://cdn.shopify.com/s/files/.../crypto-lucens.jpg'),
```

**B. Automatique via Shopify Liquid (recommandé pour la mise en ligne)** — plutôt que de copier 76 URLs (+ 76 prix + 76 variantId) à la main, le bloc peut, une fois posé sur Shopify, boucler sur une vraie collection en Liquid et générer le tableau JS automatiquement à partir des vraies données produit :
```liquid
{% for product in collections['nom-de-la-collection'].products %}
  pr('{{ product.handle }}', '{{ product.title | escape }}', {{ product.price | money_without_currency }}, false, '{{ product.featured_image | image_url: width: 200 }}'){% unless forloop.last %},{% endunless %}
{% endfor %}
```
Ça résout en une fois photo, prix réel ET `variantId` (via `product.selected_or_first_available_variant.id`), sans plus jamais avoir à les tenir à jour à la main. Je peux la préparer quand tu es prêt à passer à cette étape — il faudra juste me confirmer le nom de la collection Shopify à utiliser pour chaque catégorie.

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
