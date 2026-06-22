# Journal des modifications - Farm Life

## Format
Chaque entrée indique : date, action (CRÉÉ / MODIFIÉ / SUPPRIMÉ), fichier, description.

---

## 2026-06-22

### Système de Quêtes (indépendant, plug-and-play)

| Action | Fichier | Description |
|--------|---------|-------------|
| CRÉÉ | `src/ServerScriptService/QuestSystem/QuestServer.lua` | Script serveur : génère les quêtes du jour, suit la progression, récompense le joueur, sauvegarde via DataStore |
| CRÉÉ | `src/ReplicatedStorage/QuestSystem/QuestConfig.lua` | Configuration de toutes les quêtes disponibles (objectifs, récompenses) |
| CRÉÉ | `src/ReplicatedStorage/QuestSystem/QuestEvents.lua` | Crée les RemoteEvents dédiés aux quêtes |
| CRÉÉ | `src/StarterGui/QuestSystem/QuestUI.lua` | Interface graphique : panneau quêtes, barres de progression, notifications |
| CRÉÉ | `src/StarterPlayer/StarterPlayerScripts/QuestClient.lua` | Script client : reçoit les mises à jour serveur, met à jour l'UI |

### Instructions d'intégration
Pour signaler une action au système de quêtes depuis tes scripts existants :
```lua
-- Exemple : quand un joueur récolte une culture
local QuestEvents = game.ReplicatedStorage.QuestSystem.QuestEvents
QuestEvents.QuestAction:FireServer("Harvest", { cropType = "Wheat", amount = 1 })
```

---
