-- Farm Life - Configuration centrale du jeu
local GameConfig = {}

-- Cultures disponibles
GameConfig.Crops = {
	Wheat = {
		name = "Blé",
		emoji = "🌾",
		growTime = 60,       -- secondes avant récolte
		sellPrice = 10,
		buyPrice = 5,
		xpReward = 5,
	},
	Carrot = {
		name = "Carotte",
		emoji = "🥕",
		growTime = 45,
		sellPrice = 15,
		buyPrice = 8,
		xpReward = 8,
	},
	Potato = {
		name = "Pomme de Terre",
		emoji = "🥔",
		growTime = 90,
		sellPrice = 25,
		buyPrice = 12,
		xpReward = 12,
	},
	Strawberry = {
		name = "Fraise",
		emoji = "🍓",
		growTime = 120,
		sellPrice = 50,
		buyPrice = 20,
		xpReward = 20,
	},
	Corn = {
		name = "Maïs",
		emoji = "🌽",
		growTime = 150,
		sellPrice = 75,
		buyPrice = 30,
		xpReward = 30,
	},
	Pumpkin = {
		name = "Citrouille",
		emoji = "🎃",
		growTime = 200,
		sellPrice = 120,
		buyPrice = 50,
		xpReward = 50,
	},
}

-- Animaux disponibles
GameConfig.Animals = {
	Chicken = {
		name = "Poule",
		emoji = "🐔",
		product = "Egg",
		productName = "Oeuf",
		productEmoji = "🥚",
		productTime = 120,
		productPrice = 20,
		buyCost = 100,
		xpReward = 10,
	},
	Cow = {
		name = "Vache",
		emoji = "🐄",
		product = "Milk",
		productName = "Lait",
		productEmoji = "🥛",
		productTime = 240,
		productPrice = 50,
		buyCost = 300,
		xpReward = 25,
	},
	Sheep = {
		name = "Mouton",
		emoji = "🐑",
		product = "Wool",
		productName = "Laine",
		productEmoji = "🧶",
		productTime = 300,
		productPrice = 80,
		buyCost = 500,
		xpReward = 40,
	},
}

-- Progression par niveaux
GameConfig.Levels = {
	[1]  = { xpRequired = 0,    title = "Jardinier Débutant" },
	[2]  = { xpRequired = 100,  title = "Fermier Apprenti" },
	[3]  = { xpRequired = 300,  title = "Agriculteur" },
	[4]  = { xpRequired = 600,  title = "Fermier Confirmé" },
	[5]  = { xpRequired = 1000, title = "Expert Agricole" },
	[6]  = { xpRequired = 1500, title = "Maître Fermier" },
	[7]  = { xpRequired = 2200, title = "Seigneur de la Ferme" },
	[8]  = { xpRequired = 3000, title = "Légende Agricole" },
	[9]  = { xpRequired = 4000, title = "Champion de la Récolte" },
	[10] = { xpRequired = 5500, title = "Grand Maître Fermier" },
}

-- Économie
GameConfig.Economy = {
	startingMoney = 500,
	startingXP = 0,
	plotsAtStart = 4,
	maxPlots = 36,
	plotUnlockCost = 150,
}

-- Boutique - outils
GameConfig.Tools = {
	WateringCan = {
		name = "Arrosoir",
		description = "Accélère la pousse de 25%",
		cost = 200,
		speedBoost = 0.25,
	},
	Fertilizer = {
		name = "Engrais",
		description = "Double la valeur de la récolte",
		cost = 500,
		priceBoost = 2.0,
	},
	GoldenHoe = {
		name = "Binette d'Or",
		description = "Récolte instantanée",
		cost = 1000,
	},
}

return GameConfig
