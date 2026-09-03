# AquaRappel — Assistant de tâches conversationnel (français)

Application web (PWA) qui synchronise ta liste de tâches entre tous tes appareils
et te propose un vrai assistant conversationnel en français (tu peux lui parler ou
lui écrire pour ajouter/cocher/supprimer des tâches), qui te relance à voix haute
sur ce qu'il te reste à faire.

- **Gratuit** (comptes gratuits requis, voir plus bas — aucune carte bancaire).
- **Multiplateforme** : une page web → PC, téléphone, ou le PC de n'importe qui.
- **Synchronisé automatiquement** entre tes appareils via ton compte.
- **Installable** (PWA) sur téléphone et PC.
- **Voix française** en sortie (lecture à voix haute) partout ; en entrée (tu
  parles au micro) sur Chrome/Edge/Opera (PC et Android) — sur iPhone/Safari,
  utilise le champ texte, la reconnaissance vocale y est peu fiable.
- **Dates d'échéance** par tâche, avec un récapitulatif quotidien de ce qui est
  prévu le jour même.
- **Vraies notifications push**, reçues même appli fermée, dans une plage
  horaire que tu choisis (ex. 10h-22h — rien pendant tes heures de pause).

## Architecture (pourquoi il y a un dossier `supabase/`)

Contrairement à une simple page statique, la synchronisation entre appareils et
l'assistant conversationnel ont besoin d'un backend :

- **Supabase** (gratuit) : base de données + comptes utilisateurs. Tes tâches y
  sont stockées, protégées par des règles qui garantissent que toi seul peux les
  lire/modifier.
- **Google Gemini** (gratuit) : le modèle d'IA qui comprend tes messages et
  décide quelles actions effectuer (ajouter/cocher/décocher/supprimer une tâche).
- Une **Edge Function** Supabase (`supabase/functions/chat`) sert de pont sécurisé
  entre l'appli et Gemini : ta clé Gemini n'est jamais exposée dans le navigateur.

Le frontend (`docs/`) reste 100% statique et peut toujours être hébergé
gratuitement sur GitHub Pages.

## Mise en place (à faire une seule fois)

### 1. Créer un projet Supabase

1. Va sur [supabase.com](https://supabase.com) → *Start your project* → connecte-toi
   (avec GitHub par exemple) → **New project**.
2. Choisis un nom, un mot de passe de base de données (garde-le de côté), une
   région proche de toi. Attends ~2 minutes que le projet se crée.

### 2. Récupérer les clés du projet

Dans le projet Supabase : **Project Settings → API**.

- Copie **Project URL**.
- Copie la clé **anon public**.

Ouvre `docs/js/config.js` dans ce dépôt et remplace :

```js
window.AQUARAPPEL_CONFIG = {
  SUPABASE_URL: "https://xxxxxxxx.supabase.co",   // ton Project URL
  SUPABASE_ANON_KEY: "eyJ...",                     // ta clé anon public
};
```

(Cette clé "anon" est faite pour être publique côté client — la sécurité vient des
règles RLS créées à l'étape suivante, pas du secret de cette clé.)

### 3. Créer la table des tâches

Dans Supabase : **SQL Editor → New query**, colle le contenu de
[`supabase/schema.sql`](../supabase/schema.sql), puis **Run**.

Ensuite, active le temps réel : **Database → Replication**, active la table
`tasks` (pour que tes appareils se mettent à jour automatiquement).

### 4. Vérifier l'authentification par e-mail

**Authentication → Providers → Email** doit être activé (c'est le cas par
défaut). Pour un usage strictement personnel, tu peux désactiver *Confirm email*
dans les réglages du provider Email pour éviter l'étape de confirmation par mail
à l'inscription — sinon, confirme une fois via le mail reçu après ton inscription.

### 5. Créer une clé API Gemini (gratuite, sans carte)

1. Va sur [Google AI Studio](https://aistudio.google.com/apikey) (connecte-toi
   avec un compte Google).
2. **Create API key** → copie la clé générée.
3. Le palier gratuit a des limites de débit (nombre de requêtes par minute/jour) —
   largement suffisantes pour un usage personnel. Vérifie les conditions actuelles
   sur [ai.google.dev/pricing](https://ai.google.dev/pricing).

### 6. Déployer l'Edge Function `chat`

**Option A — depuis le tableau de bord (aucun terminal requis, recommandé) :**

1. Dans Supabase : **Edge Functions → Create a new function**, nomme-la `chat`.
2. Colle le contenu de
   [`supabase/functions/chat/index.ts`](../supabase/functions/chat/index.ts).
3. **Deploy**.
4. Ajoute le secret : dans les réglages de la fonction (ou **Project Settings →
   Edge Functions → Secrets**), ajoute `GEMINI_API_KEY` avec la clé créée à
   l'étape 5.

**Option B — via la CLI Supabase** (si tu es à l'aise avec un terminal) :

```bash
npm install -g supabase
supabase login
supabase link --project-ref <ton-project-ref>
supabase secrets set GEMINI_API_KEY=<ta-clé-gemini>
supabase functions deploy chat
```

### 7. Dates d'échéance + notifications push planifiées

Cette étape ajoute : une date d'échéance par tâche, et de vraies notifications
push qui arrivent **même appli fermée** — un récapitulatif de ce qui est prévu
le jour même une fois par jour au début de ta plage horaire, puis un rappel des
tâches non cochées à l'intervalle choisi, uniquement pendant cette plage.

**a. Exécuter la migration SQL**

Dans **SQL Editor → New query**, copie tout le contenu de
[`supabase/migration_002_reminders_calendar.sql`](../supabase/migration_002_reminders_calendar.sql)
(déjà rempli avec l'URL et la clé anon de ton projet) et **Run**. Ça crée les tables
`push_subscriptions` et `reminder_settings`, ajoute une colonne `due_date` aux
tâches, et planifie l'appel de la fonction `send-reminders` toutes les 15 min
(via les extensions `pg_cron`/`pg_net`, activées automatiquement par le script).

**b. Déployer l'Edge Function `send-reminders`**

Même méthode qu'à l'étape 6 :
1. **Edge Functions → Create a new function**, nomme-la exactement `send-reminders`.
2. Colle le contenu de
   [`supabase/functions/send-reminders/index.ts`](../supabase/functions/send-reminders/index.ts).
3. **Deploy**.

   ⚠️ Vérifie l'URL réelle de la fonction une fois déployée (onglet **Settings**
   de la fonction, ou l'exemple `curl` affiché) : Supabase attribue parfois un
   nom d'URL (le "slug") différent du nom que tu as tapé, qui ne peut plus être
   changé ensuite. Si l'URL affichée ne se termine pas par `.../send-reminders`,
   remplace `send-reminders` par le nom réel dans l'URL du job `cron.schedule`
   de `migration_002_reminders_calendar.sql`, puis relance ce script (il est
   conçu pour être exécuté plusieurs fois sans problème).
4. Ajoute ces secrets à la fonction (Secrets, comme pour `GEMINI_API_KEY`
   précédemment) :
   - `VAPID_PUBLIC_KEY` (déjà présente, en clair, dans `docs/js/config.js` —
     copie-la de là, c'est la même valeur, elle est publique par conception)
   - `VAPID_PRIVATE_KEY` — un **secret**, à générer toi-même (jamais stocké
     dans ce dépôt) : le plus simple est de me demander de te la redonner dans
     la conversation, ou de la régénérer via `npx web-push generate-vapid-keys`
     sur ta machine si tu préfères la créer toi-même.
   - `VAPID_SUBJECT` = `mailto:contact@zen-aquatique.fr`

   (`SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY` sont fournis automatiquement
   par Supabase à toutes les Edge Functions, rien à faire pour ceux-là.)

**c. Activer les notifications push dans l'appli**

Une fois le site republié (voir étape suivante), ouvre-le sur chaque appareil
où tu veux recevoir les rappels, et dans **Réglages de l'assistant → Notifications
push (même appli fermée) → Activer**. Choisis aussi ta **plage horaire** (10h-22h
par défaut) et la **fréquence** — ces réglages sont maintenant partagés entre tes
appareils.

### 8. Héberger le site (GitHub Pages, gratuit)

1. Commit/push `docs/js/config.js` avec tes vraies valeurs.
2. Sur GitHub : **Settings → Pages → Source : Deploy from a branch → Branch :
   `main` / dossier `/docs`**.
3. Ouvre l'URL générée (`https://<utilisateur>.github.io/<repo>/`) sur ton PC et
   ton téléphone, crée ton compte (e-mail + mot de passe), et c'est prêt.

## Tester en local

```bash
cd docs
python3 -m http.server 8080
# puis ouvrir http://localhost:8080
```

(Après avoir rempli `docs/js/config.js` — sinon un écran de configuration
s'affiche à la place.)

## Ce que peut faire l'assistant

Écris ou dis-lui par exemple :

- « Ajoute préparer les colis du lundi »
- « Coche répondre aux clients Shopify »
- « Qu'est-ce qu'il me reste à faire ? »
- « Supprime la tâche sur le SAV »

Il agit directement sur ta liste (via l'Edge Function) puis te répond en
français, à l'oral si la voix est activée dans les réglages.

## Confidentialité

Le contenu de tes messages et de ta liste de tâches transite par l'API Gemini de
Google pour générer les réponses de l'assistant (uniquement quand tu lui parles
ou lui écris — les rappels automatiques et périodiques restent 100% locaux, sans
appel réseau). Pour un usage business (ex. tâches ZenAquatique), garde ça en tête
si certaines tâches contiennent des informations sensibles.

## Limites connues

- **Fuseau horaire** : la plage horaire et le récapitulatif quotidien sont
  calculés côté serveur en heure de Paris (fixe) — pas de réglage de fuseau
  pour l'instant, pensé pour un usage à un seul utilisateur en France.
- **Palier gratuit Gemini** : en cas d'usage très intensif, les limites de débit
  du palier gratuit peuvent être atteintes ; l'assistant affichera alors un
  message d'erreur temporaire.
- **Saisie vocale sur iPhone** : non fiable dans Safari — utilise le clavier.
