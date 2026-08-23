# Projet 02 — Calculateur de sol nutritif

## Objectif
Répondre automatiquement sur la fiche produit à la question client récurrente : « combien de litres de sol nutritif me faut-il pour mon bac ? »

## Formule
```
volume (L) = longueur (cm) × largeur (cm) × hauteur de sol (cm) / 1000
+ marge 10% optionnelle (pentes d'aquascaping, tassement dans le temps)
nombre de sacs = arrondi supérieur (volume / contenance d'un sac)
```
Hauteurs pré-remplies proposées : 3 cm (fine couche), 5 cm (standard), 8 cm (aquascaping / pente).

## Fichier livré
`calculateur-embed.html` — bloc autonome (HTML + CSS + JS inline, classes préfixées `zaq-calcsol__` pour ne pas entrer en conflit avec le thème). Aucune dépendance, aucun appel réseau. Testé (logique de calcul vérifiée en Node + rendu HTML validé).

## Installation sur Shopify
1. Boutique en ligne → Personnaliser → ouvrir un modèle de **page Produit**
2. Ajouter un bloc → **Liquid personnalisé** (Custom Liquid)
3. Coller tout le contenu de `calculateur-embed.html`
4. **Adapter le bloc `CONFIG` en haut du `<script>`** à la contenance réelle du sac de CETTE fiche (voir ci-dessous)
5. Positionner le bloc sous la description produit, sauvegarder

Un seul bloc par page (le script cible l'ID `zaq-calcsol`, pas conçu pour plusieurs instances sur une même page).

## Adapter la contenance du sac par produit
Le champ "Contenance d'un sac" propose un choix d'unité L / kg (les produits ne sont pas tous étiquetés pareil : le Dennerle Substrate est vendu en L, le sable en kg). Trois valeurs à éditer dans le `CONFIG` du script pour chaque fiche :

```js
var CONFIG = {
  contenanceSacParDefaut: 2.5, // valeur pré-remplie
  uniteParDefaut: 'L',         // 'L' ou 'kg' — celle écrite sur l'emballage du produit
  densiteKgParL: 1.2           // poids (kg) d'1 litre de ce produit — nécessaire pour que le client
                                // puisse aussi basculer sur l'autre unité si besoin
};
```

| Produit | Contenance | Unité par défaut | Densité (kg/L) |
|---|---|---|---|
| Dennerle Substrate 2.5L (3 kg) | 2.5 | `L` | 1.2 (calculé : 3 kg / 2.5 L) |
| Sable Fin Rivière / Blanc Neige, sacs SuperFish 4 kg | 4 | `kg` | ~1.5–1.6 (densité indicative du sable en vrac — **à vérifier sur la fiche technique du fournisseur** avant mise en ligne) |

La densité n'est utilisée que pour convertir si le client bascule sur l'unité non-défaut (ex. il connaît le poids alors que le produit est affiché en L, ou l'inverse) — elle n'a pas besoin d'être parfaite au gramme près, juste réaliste.

## Statut
- [x] Formule + widget autonome
- [x] Validation logique (Node) + rendu HTML
- [ ] Owen : coller le bloc sur les fiches produit substrats (en adaptant le `CONFIG` de chacune) et valider visuellement dans le thème live
- [ ] Owen : vérifier la densité réelle (kg/L) du sable SuperFish sur sa fiche technique avant mise en ligne
- [ ] v2 (optionnel) : bouton « ajouter N sacs au panier » via l'API AJAX Shopify (`/cart/add.js`), nécessite l'ID de variante du produit
