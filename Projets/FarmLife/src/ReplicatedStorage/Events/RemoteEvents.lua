-- Liste centralisée des RemoteEvents et RemoteFunctions
-- Ce module retourne les noms ; la création réelle se fait côté serveur
local RemoteEvents = {}

-- RemoteEvents (Server -> Client ou Client -> Server)
RemoteEvents.EventNames = {
	"PlantCrop",
	"HarvestCrop",
	"BuyAnimal",
	"CollectAnimalProduct",
	"SellInventory",
	"UnlockPlot",
	"BuyTool",
	"UseWateringCan",
	"UseFertilizer",
	"UpdateData",       -- Server -> Client : synchro des données
	"ShowNotification", -- Server -> Client : notification UI
	"LevelUp",          -- Server -> Client : montée de niveau
}

-- RemoteFunctions (Client demande, Server répond)
RemoteEvents.FunctionNames = {
	"GetPlayerData",
	"GetLeaderboard",
}

return RemoteEvents
