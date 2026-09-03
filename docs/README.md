# AquaRappel — Assistant de tâches (français)

Petite application web (PWA) qui te rappelle, en français et à voix haute si tu le
souhaites, les tâches de ta liste que tu n'as pas encore cochées.

- **Gratuit**, pas de compte, pas de serveur.
- **Multiplateforme** : c'est une simple page web → utilisable sur ton PC, ton
  téléphone, ou le PC de n'importe qui, dans le navigateur.
- **Installable** (PWA) sur téléphone (Android/iOS) et sur PC, pour l'ouvrir comme
  une vraie appli et l'utiliser hors-ligne.
- **Voix française** via la synthèse vocale du navigateur (Web Speech API).
- **Notifications** de rappel tant que l'appli/l'onglet est ouvert (ou installée).

## Utiliser en local

Aucune installation nécessaire, juste un petit serveur statique (les PWA doivent
être servies en HTTP, pas ouvertes en `file://`) :

```bash
cd docs
python3 -m http.server 8080
# puis ouvrir http://localhost:8080
```

## Héberger gratuitement (GitHub Pages)

1. Sur GitHub : `Settings` → `Pages`.
2. `Source` : `Deploy from a branch`.
3. `Branch` : `main`, dossier **`/docs`**.
4. Sauvegarder — la page est publiée sur `https://<utilisateur>.github.io/<repo>/`.

Depuis cette URL, ouvre le lien sur ton téléphone et sur n'importe quel PC : tout le
monde accède à la même appli, gratuitement.

## Limite connue : synchronisation entre appareils

Il n'y a pas de backend, donc pas de compte ni de synchronisation automatique entre
appareils : les tâches sont stockées dans le `localStorage` du navigateur, sur
l'appareil où elles ont été ajoutées. Pour retrouver la même liste ailleurs, utilise
dans les réglages :

- **Exporter/Importer** un fichier `.json`, ou
- **Copier un lien de ma liste** (encode la liste dans l'URL) puis ouvrir ce lien sur
  l'autre appareil.

Une vraie synchronisation automatique (compte + base de données) est possible en
évolution future, mais demande un service backend (potentiellement payant selon le
volume) — à discuter si besoin.

## Limite connue : rappels quand l'appli est fermée

Les rappels (voix + notifications) se déclenchent tant que l'onglet/l'appli est
ouvert. Des notifications *push* qui arrivent même appli fermée demanderaient un
serveur de notifications (ex. Firebase Cloud Messaging) — non inclus dans cette
version 100% gratuite/sans backend.
