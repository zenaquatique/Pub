-- QuestServer.lua  (ServerScriptService/QuestSystem/)
-- Gère toute la logique serveur des quêtes :
--   - Attribution des quêtes journalières
--   - Suivi de la progression
--   - Réinitialisation quotidienne
--   - Sauvegarde via DataStore

local Players = game:GetService("Players")
local DataStoreService = game:GetService("DataStoreService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

-- Attendre que QuestEvents soit prêt
local QuestSystem = ReplicatedStorage:WaitForChild("QuestSystem", 10)
	or require(ReplicatedStorage.QuestSystem.QuestEvents)

local QuestConfig = require(ReplicatedStorage.QuestSystem.QuestConfig)

local QuestAction    = QuestSystem:WaitForChild("QuestAction")
local QuestUpdate    = QuestSystem:WaitForChild("QuestUpdate")
local QuestCompleted = QuestSystem:WaitForChild("QuestCompleted")
local GetMyQuests    = QuestSystem:WaitForChild("GetMyQuests")

local QuestStore = DataStoreService:GetDataStore("FarmLife_Quests_v1")

-- Cache en mémoire : { [userId] = questData }
local playerQuests = {}

-- ────────────────────────────────────────────────
-- Utilitaires
-- ────────────────────────────────────────────────

-- Retourne la date du jour sous forme "YYYY-MM-DD" (UTC)
local function getTodayKey()
	local t = os.date("!*t")
	return string.format("%04d-%02d-%02d", t.year, t.month, t.day)
end

-- Mélange une table (Fisher-Yates)
local function shuffle(t)
	local n = #t
	for i = n, 2, -1 do
		local j = math.random(1, i)
		t[i], t[j] = t[j], t[i]
	end
	return t
end

-- Choisit N quêtes aléatoires pour aujourd'hui
local function pickDailyQuests(userId)
	math.randomseed(tonumber(getTodayKey():gsub("-", "")) + userId)
	local pool = {}
	for _, q in ipairs(QuestConfig.DailyQuests) do
		table.insert(pool, q)
	end
	shuffle(pool)
	local chosen = {}
	for i = 1, math.min(QuestConfig.QuestsPerDay, #pool) do
		chosen[i] = {
			id = pool[i].id,
			progress = 0,
			completed = false,
			rewarded = false,
		}
	end
	return chosen
end

-- ────────────────────────────────────────────────
-- Chargement / Sauvegarde
-- ────────────────────────────────────────────────

local function loadQuests(player)
	local userId = player.UserId
	local today = getTodayKey()
	local saved = nil

	local ok, result = pcall(function()
		return QuestStore:GetAsync("quests_" .. userId)
	end)
	if ok then saved = result end

	-- Réinitialiser si nouveau jour ou pas de données
	if not saved or saved.day ~= today then
		saved = {
			day = today,
			quests = pickDailyQuests(userId),
		}
	end

	playerQuests[userId] = saved
	return saved
end

local function saveQuests(player)
	local userId = player.UserId
	local data = playerQuests[userId]
	if not data then return end
	pcall(function()
		QuestStore:SetAsync("quests_" .. userId, data)
	end)
end

-- ────────────────────────────────────────────────
-- Envoi au client
-- ────────────────────────────────────────────────

local function buildQuestPayload(userId)
	local data = playerQuests[userId]
	if not data then return {} end

	local payload = {}
	for _, entry in ipairs(data.quests) do
		-- Retrouver la config de cette quête
		local cfg = nil
		for _, q in ipairs(QuestConfig.DailyQuests) do
			if q.id == entry.id then cfg = q break end
		end
		if cfg then
			table.insert(payload, {
				id = entry.id,
				title = cfg.title,
				description = cfg.description,
				icon = cfg.icon,
				target = cfg.target,
				progress = entry.progress,
				completed = entry.completed,
				rewarded = entry.rewarded,
				reward = cfg.reward,
			})
		end
	end
	return payload
end

local function sendUpdate(player)
	local payload = buildQuestPayload(player.UserId)
	QuestUpdate:FireClient(player, payload)
end

-- ────────────────────────────────────────────────
-- Traitement d'une action de jeu
-- ────────────────────────────────────────────────

local function handleAction(player, actionType, data)
	local userId = player.UserId
	local questData = playerQuests[userId]
	if not questData then return end

	local changed = false

	for _, entry in ipairs(questData.quests) do
		if entry.completed then continue end

		local cfg = nil
		for _, q in ipairs(QuestConfig.DailyQuests) do
			if q.id == entry.id then cfg = q break end
		end
		if not cfg then continue end
		if cfg.action ~= actionType then continue end

		-- Vérifier le filtre optionnel (ex: cropType)
		local passFilter = true
		if cfg.filter then
			for k, v in pairs(cfg.filter) do
				if data[k] ~= v then
					passFilter = false
					break
				end
			end
		end
		if not passFilter then continue end

		-- Incrémenter la progression
		local amount = data.amount or 1
		entry.progress = entry.progress + amount
		changed = true

		-- Quête complétée ?
		if entry.progress >= cfg.target and not entry.rewarded then
			entry.completed = true
			entry.rewarded = true

			-- Donner la récompense via un événement global
			-- (ton jeu doit écouter "QuestReward" côté serveur)
			local rewardEvent = game.ReplicatedStorage:FindFirstChild("QuestReward")
			if rewardEvent then
				rewardEvent:Fire(player, cfg.reward)
			else
				-- Fallback : leaderstats directs
				local ls = player:FindFirstChild("leaderstats")
				if ls then
					local money = ls:FindFirstChild("Money") or ls:FindFirstChild("Coins") or ls:FindFirstChild("Cash")
					if money then money.Value = money.Value + (cfg.reward.money or 0) end
				end
			end

			QuestCompleted:FireClient(player, {
				title = cfg.title,
				reward = cfg.reward,
				icon = cfg.icon,
			})
		end
	end

	if changed then
		saveQuests(player)
		sendUpdate(player)
	end
end

-- ────────────────────────────────────────────────
-- Connexions
-- ────────────────────────────────────────────────

QuestAction.OnServerEvent:Connect(function(player, actionType, data)
	if type(actionType) ~= "string" then return end
	if type(data) ~= "table" then data = {} end
	handleAction(player, actionType, data)
end)

GetMyQuests.OnServerInvoke = function(player)
	return buildQuestPayload(player.UserId)
end

Players.PlayerAdded:Connect(function(player)
	loadQuests(player)
	-- Attendre que le client soit prêt avant d'envoyer
	player.CharacterAdded:Connect(function()
		task.wait(1)
		sendUpdate(player)
	end)
end)

Players.PlayerRemoving:Connect(function(player)
	saveQuests(player)
	playerQuests[player.UserId] = nil
end)

-- Sauvegarde périodique toutes les 2 minutes
task.spawn(function()
	while true do
		task.wait(120)
		for _, player in ipairs(Players:GetPlayers()) do
			saveQuests(player)
		end
	end
end)

print("[QuestServer] Système de quêtes démarré ✓")
