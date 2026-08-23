# Projet 02 — Calculateur de sol nutritif

## Objectif
Répondre automatiquement sur la fiche produit à la question client récurrente : « combien de litres/kg de sol nutritif ou de sable me faut-il pour mon bac ? »

## Formule
```
volume de substrat (L) = longueur (cm) × largeur (cm) × hauteur souhaitée (cm) / 1000
+ marge 10% optionnelle (pentes d'aquascaping, tassement dans le temps)
nombre de sacs = arrondi supérieur (volume / contenance d'un sac)
```
Hauteurs pré-remplies proposées : 3 cm (fine couche), 5 cm (standard), 8 cm (aquascaping / pente).

Pour un produit vendu au poids (sable), le volume est converti en kg via une densité (kg/L) avant d'être comparé à la contenance du sac.

## Fichiers livrés
Deux blocs autonomes, un par produit, **rien à modifier dedans** — HTML + CSS + JS inline, aucune dépendance, aucun appel réseau. Testés (logique de calcul vérifiée en Node).

| Fichier | Produit | Contenance du sac |
|---|---|---|
| `calculateur-embed-dennerle-substrate.html` | Dennerle Substrate 2.5L | 2,5 L (fixe) |
| `calculateur-embed-sable-superfish.html` | Sable Fin Rivière / Blanc Neige (sacs SuperFish 4 kg) | 4 kg (fixe), densité 1,55 kg/L pour la conversion volume → poids |

Chaque fichier a ses propres ID HTML (`zaq-calcsol-dennerle` / `zaq-calcsol-sable`), donc pas de conflit si jamais les deux se retrouvent sur la même page — mais chacun n'est prévu que pour SA fiche produit.

## Installation sur Shopify
1. Boutique en ligne → Personnaliser → ouvrir le modèle de **page Produit** du produit concerné
2. Ajouter un bloc → **Liquid personnalisé** (Custom Liquid)
3. Coller tout le contenu du fichier correspondant à ce produit (voir tableau ci-dessus)
4. Positionner le bloc sous la description produit, sauvegarder

Aucune configuration à toucher dans le code — la contenance du sac est déjà fixée dans chaque fichier.

## Ajouter un nouveau produit substrat plus tard
Dupliquer le fichier le plus proche (Dennerle si vendu en L, Sable si vendu au poids), changer :
- `CONTENANCE_SAC_LITRES` (ou `CONTENANCE_SAC_KG` + `DENSITE_KG_PAR_L`) en haut du `<script>`
- les ID (`zaq-calcsol-...`, `zaq-...-longueur` etc.) pour un nom unique
- le texte "Nombre de sacs conseillé (X L/kg)" pour refléter la nouvelle contenance

## À vérifier avant mise en ligne
- [ ] Owen : coller chaque fichier sur la bonne fiche produit et valider visuellement dans le thème live
- [ ] Owen : vérifier la densité réelle du sable SuperFish (1,55 kg/L utilisé, valeur indicative pour du sable fin aquarium — à ajuster si la fiche technique du fournisseur donne un autre chiffre)

## Statut
- [x] Formule + widgets autonomes (un par produit)
- [x] Validation logique (Node)
- [ ] Owen : installation sur les fiches produit live
- [ ] v2 (optionnel) : bouton « ajouter N sacs au panier » via l'API AJAX Shopify (`/cart/add.js`), nécessite l'ID de variante du produit
