-- QuestEvents.lua
-- Crée tous les RemoteEvents nécessaires au système de quêtes.
-- Ce script doit s'exécuter en premier (placé dans ReplicatedStorage).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local folder = ReplicatedStorage:FindFirstChild("QuestSystem")
if not folder then
	folder = Instance.new("Folder")
	folder.Name = "QuestSystem"
	folder.Parent = ReplicatedStorage
end

local function makeEvent(name)
	if not folder:FindFirstChild(name) then
		local e = Instance.new("RemoteEvent")
		e.Name = name
		e.Parent = folder
	end
end

local function makeFunction(name)
	if not folder:FindFirstChild(name) then
		local f = Instance.new("RemoteFunction")
		f.Name = name
		f.Parent = folder
	end
end

-- Client -> Serveur : signaler une action de jeu
makeEvent("QuestAction")

-- Serveur -> Client : envoyer les quêtes du jour et la progression
makeEvent("QuestUpdate")

-- Serveur -> Client : notification quête complétée
makeEvent("QuestCompleted")

-- Client -> Serveur : demander ses quêtes actuelles
makeFunction("GetMyQuests")

return folder
