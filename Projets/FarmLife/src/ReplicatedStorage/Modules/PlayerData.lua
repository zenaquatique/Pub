-- Module de gestion des données joueur (côté partagé)
local PlayerData = {}

local GameConfig = require(script.Parent.Parent.Config.GameConfig)

-- Structure de données par défaut d'un nouveau joueur
function PlayerData.GetDefault()
	return {
		money = GameConfig.Economy.startingMoney,
		xp = GameConfig.Economy.startingXP,
		level = 1,
		plots = {}, -- {cropType, plantedAt, fertilized, watered}
		animals = {}, -- {animalType, lastCollected}
		inventory = {}, -- {itemType -> quantity}
		tools = {},    -- {toolName -> owned bool}
		stats = {
			totalHarvests = 0,
			totalSold = 0,
			totalEarned = 0,
			playTime = 0,
		},
		unlockedPlots = GameConfig.Economy.plotsAtStart,
	}
end

-- Calcule le niveau à partir de l'XP totale
function PlayerData.GetLevelFromXP(xp)
	local level = 1
	for lvl, data in pairs(GameConfig.Levels) do
		if xp >= data.xpRequired and lvl > level then
			level = lvl
		end
	end
	return level
end

-- XP nécessaire pour le prochain niveau
function PlayerData.GetXPToNextLevel(xp)
	local currentLevel = PlayerData.GetLevelFromXP(xp)
	local nextLevel = currentLevel + 1
	if GameConfig.Levels[nextLevel] then
		return GameConfig.Levels[nextLevel].xpRequired - xp
	end
	return 0 -- niveau max atteint
end

return PlayerData
