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
4. Positionner le bloc sous la description produit, sauvegarder
5. Appliquer sur les fiches concernées : Dennerle Substrate 2.5L, Sable Fin Rivière, Sable Fin Blanc Neige (contenance du sac pré-remplie à 2,5 L, modifiable par le client si besoin)

Un seul bloc par page (le script cible l'ID `zaq-calcsol`, pas conçu pour plusieurs instances sur une même page).

## Statut
- [x] Formule + widget autonome
- [x] Validation logique (Node) + rendu HTML
- [ ] Owen : coller le bloc sur les fiches produit substrats et valider visuellement dans le thème live
- [ ] v2 (optionnel) : bouton « ajouter N sacs au panier » via l'API AJAX Shopify (`/cart/add.js`), nécessite l'ID de variante du produit
