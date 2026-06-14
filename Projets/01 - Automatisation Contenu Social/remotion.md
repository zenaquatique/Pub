# Remotion — Projet vidéo ZenAquatique

## Chemin
`C:\Users\ec\Desktop\zenaquatique-video`

## Lancer le preview
```
cd C:\Users\ec\Desktop\zenaquatique-video
npm run dev
```

## Rendre une vidéo
```
npx remotion render TikTok-Post1-Top3Plantes out/tiktok-post1.mp4
npx remotion render MetaAd-Post1-Boutures out/metaad-post1.mp4
```

## Compositions disponibles
| ID | Format | Durée | Usage |
|----|--------|-------|-------|
| TikTok-Post1-Top3Plantes | 1080x1920 9:16 | ~13s | TikTok / Reels organique |
| MetaAd-Post1-Boutures | 1080x1920 9:16 | ~11.5s | Meta Ads conversion |

## Stack technique
- Remotion (React vidéo)
- TypeScript
- Composants : Hook, ProductSlide, BenefitSlide, CTA

## Licence
Remotion est gratuit jusqu'à 3 personnes. Usage commercial = vérifier https://www.remotion.pro/license

## Workflow posts
1. Claude génère les props (textes, produits, bénéfices) dans Root.tsx
2. `npm run dev` pour prévisualiser
3. `npx remotion render` pour exporter le MP4
4. Upload + programmation via Meta Graph API (à connecter)
