-- QuestConfig.lua
-- Toutes les quêtes disponibles dans le jeu.
-- Pour ajouter une quête : copier un bloc et modifier les valeurs.

local QuestConfig = {}

-- Types d'actions reconnues par le système :
--   "Harvest"  : récolter une culture   (data: cropType, amount)
--   "Sell"     : vendre des objets       (data: amount = argent gagné)
--   "Plant"    : planter une graine      (data: cropType, amount)
--   "Collect"  : collecter produit animal (data: animalType, amount)

QuestConfig.DailyQuests = {

	-- === RÉCOLTE ===
	{
		id = "harvest_any_5",
		title = "Première Récolte",
		description = "Récolte 5 cultures",
		icon = "🌾",
		action = "Harvest",
		target = 5,
		reward = { money = 50, xp = 20 },
	},
	{
		id = "harvest_any_20",
		title = "Gros Travail",
		description = "Récolte 20 cultures",
		icon = "🌾",
		action = "Harvest",
		target = 20,
		reward = { money = 150, xp = 60 },
	},
	{
		id = "harvest_wheat_10",
		title = "Moissonneur de Blé",
		description = "Récolte 10 blés",
		icon = "🌾",
		action = "Harvest",
		target = 10,
		filter = { cropType = "Wheat" },
		reward = { money = 80, xp = 30 },
	},
	{
		id = "harvest_carrot_10",
		title = "Amateur de Carottes",
		description = "Récolte 10 carottes",
		icon = "🥕",
		action = "Harvest",
		target = 10,
		filter = { cropType = "Carrot" },
		reward = { money = 100, xp = 40 },
	},
	{
		id = "harvest_strawberry_5",
		title = "Cueilleur de Fraises",
		description = "Récolte 5 fraises",
		icon = "🍓",
		action = "Harvest",
		target = 5,
		filter = { cropType = "Strawberry" },
		reward = { money = 200, xp = 80 },
	},

	-- === VENTE ===
	{
		id = "sell_100",
		title = "Petit Commerce",
		description = "Gagne 100 pièces en vendant",
		icon = "💰",
		action = "Sell",
		target = 100,
		reward = { money = 50, xp = 25 },
	},
	{
		id = "sell_500",
		title = "Marchand Sérieux",
		description = "Gagne 500 pièces en vendant",
		icon = "💰",
		action = "Sell",
		target = 500,
		reward = { money = 200, xp = 80 },
	},
	{
		id = "sell_1000",
		title = "Riche Fermier",
		description = "Gagne 1000 pièces en vendant",
		icon = "💎",
		action = "Sell",
		target = 1000,
		reward = { money = 500, xp = 150 },
	},

	-- === PLANTATION ===
	{
		id = "plant_5",
		title = "Jardinier du Matin",
		description = "Plante 5 graines",
		icon = "🌱",
		action = "Plant",
		target = 5,
		reward = { money = 30, xp = 15 },
	},
	{
		id = "plant_15",
		title = "Grand Jardinier",
		description = "Plante 15 graines",
		icon = "🌱",
		action = "Plant",
		target = 15,
		reward = { money = 100, xp = 50 },
	},
}

-- Nombre de quêtes proposées chaque jour au joueur
QuestConfig.QuestsPerDay = 3

-- Heure de réinitialisation (en heure UTC, 0 = minuit)
QuestConfig.ResetHour = 0

return QuestConfig
