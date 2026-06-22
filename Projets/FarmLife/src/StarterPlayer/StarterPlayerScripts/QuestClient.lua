-- QuestClient.lua  (StarterPlayerScripts/)
-- Reçoit les mises à jour du serveur et met à jour l'UI des quêtes.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")

local QuestSystem    = ReplicatedStorage:WaitForChild("QuestSystem", 10)
local QuestUpdate    = QuestSystem:WaitForChild("QuestUpdate")
local QuestCompleted = QuestSystem:WaitForChild("QuestCompleted")
local GetMyQuests    = QuestSystem:WaitForChild("GetMyQuests")

-- ────────────────────────────────────────────────
-- Création de l'interface
-- ────────────────────────────────────────────────

local screenGui = Instance.new("ScreenGui")
screenGui.Name = "QuestGui"
screenGui.ResetOnSpawn = false
screenGui.ZIndexBehavior = Enum.ZIndexBehavior.Sibling
screenGui.Parent = playerGui

-- Bouton d'ouverture (coin haut-droit)
local toggleBtn = Instance.new("TextButton")
toggleBtn.Name = "QuestToggle"
toggleBtn.Size = UDim2.new(0, 110, 0, 40)
toggleBtn.Position = UDim2.new(1, -120, 0, 10)
toggleBtn.BackgroundColor3 = Color3.fromRGB(255, 200, 50)
toggleBtn.TextColor3 = Color3.fromRGB(30, 30, 30)
toggleBtn.Font = Enum.Font.GothamBold
toggleBtn.TextSize = 16
toggleBtn.Text = "📋 Quêtes"
toggleBtn.Parent = screenGui
Instance.new("UICorner", toggleBtn).CornerRadius = UDim.new(0, 8)

-- Panneau principal
local panel = Instance.new("Frame")
panel.Name = "QuestPanel"
panel.Size = UDim2.new(0, 320, 0, 360)
panel.Position = UDim2.new(1, -335, 0, 60)
panel.BackgroundColor3 = Color3.fromRGB(30, 35, 45)
panel.BorderSizePixel = 0
panel.Visible = false
panel.Parent = screenGui
Instance.new("UICorner", panel).CornerRadius = UDim.new(0, 12)

-- Ombre
local shadow = Instance.new("ImageLabel")
shadow.Size = UDim2.new(1, 20, 1, 20)
shadow.Position = UDim2.new(0, -10, 0, -10)
shadow.BackgroundTransparency = 1
shadow.Image = "rbxassetid://1316045217"
shadow.ImageColor3 = Color3.new(0, 0, 0)
shadow.ImageTransparency = 0.5
shadow.ScaleType = Enum.ScaleType.Slice
shadow.SliceCenter = Rect.new(10, 10, 118, 118)
shadow.ZIndex = -1
shadow.Parent = panel

-- Titre du panneau
local title = Instance.new("TextLabel")
title.Size = UDim2.new(1, 0, 0, 45)
title.BackgroundColor3 = Color3.fromRGB(255, 200, 50)
title.BorderSizePixel = 0
title.Font = Enum.Font.GothamBold
title.TextSize = 18
title.TextColor3 = Color3.fromRGB(30, 30, 30)
title.Text = "📋 Quêtes du Jour"
title.Parent = panel
Instance.new("UICorner", title).CornerRadius = UDim.new(0, 12)

-- Conteneur des quêtes (scrollable)
local scrollFrame = Instance.new("ScrollingFrame")
scrollFrame.Size = UDim2.new(1, -16, 1, -55)
scrollFrame.Position = UDim2.new(0, 8, 0, 50)
scrollFrame.BackgroundTransparency = 1
scrollFrame.BorderSizePixel = 0
scrollFrame.ScrollBarThickness = 4
scrollFrame.CanvasSize = UDim2.new(0, 0, 0, 0)
scrollFrame.AutomaticCanvasSize = Enum.AutomaticSize.Y
scrollFrame.Parent = panel

local listLayout = Instance.new("UIListLayout")
listLayout.Padding = UDim.new(0, 8)
listLayout.SortOrder = Enum.SortOrder.LayoutOrder
listLayout.Parent = scrollFrame

-- ────────────────────────────────────────────────
-- Création d'une carte de quête
-- ────────────────────────────────────────────────

local function createQuestCard(quest, order)
	local card = Instance.new("Frame")
	card.Name = "Quest_" .. quest.id
	card.Size = UDim2.new(1, 0, 0, 90)
	card.BackgroundColor3 = quest.completed
		and Color3.fromRGB(40, 80, 40)
		or  Color3.fromRGB(45, 50, 65)
	card.BorderSizePixel = 0
	card.LayoutOrder = order
	card.Parent = scrollFrame
	Instance.new("UICorner", card).CornerRadius = UDim.new(0, 8)

	-- Icône
	local icon = Instance.new("TextLabel")
	icon.Size = UDim2.new(0, 40, 0, 40)
	icon.Position = UDim2.new(0, 8, 0, 8)
	icon.BackgroundColor3 = Color3.fromRGB(60, 65, 80)
	icon.Font = Enum.Font.GothamBold
	icon.TextSize = 22
	icon.Text = quest.icon
	icon.TextColor3 = Color3.new(1, 1, 1)
	icon.Parent = card
	Instance.new("UICorner", icon).CornerRadius = UDim.new(0, 6)

	-- Titre
	local titleLbl = Instance.new("TextLabel")
	titleLbl.Size = UDim2.new(1, -60, 0, 20)
	titleLbl.Position = UDim2.new(0, 55, 0, 8)
	titleLbl.BackgroundTransparency = 1
	titleLbl.Font = Enum.Font.GothamBold
	titleLbl.TextSize = 14
	titleLbl.TextColor3 = Color3.new(1, 1, 1)
	titleLbl.TextXAlignment = Enum.TextXAlignment.Left
	titleLbl.Text = quest.title .. (quest.completed and " ✅" or "")
	titleLbl.Parent = card

	-- Description
	local desc = Instance.new("TextLabel")
	desc.Size = UDim2.new(1, -60, 0, 16)
	desc.Position = UDim2.new(0, 55, 0, 28)
	desc.BackgroundTransparency = 1
	desc.Font = Enum.Font.Gotham
	desc.TextSize = 12
	desc.TextColor3 = Color3.fromRGB(180, 180, 200)
	desc.TextXAlignment = Enum.TextXAlignment.Left
	desc.Text = quest.description
	desc.Parent = card

	-- Récompense
	local reward = Instance.new("TextLabel")
	reward.Size = UDim2.new(1, -60, 0, 14)
	reward.Position = UDim2.new(0, 55, 0, 46)
	reward.BackgroundTransparency = 1
	reward.Font = Enum.Font.Gotham
	reward.TextSize = 11
	reward.TextColor3 = Color3.fromRGB(255, 200, 50)
	reward.TextXAlignment = Enum.TextXAlignment.Left
	reward.Text = string.format("💰 +%d pièces   ⭐ +%d XP",
		quest.reward.money or 0,
		quest.reward.xp or 0)
	reward.Parent = card

	-- Barre de progression
	local barBg = Instance.new("Frame")
	barBg.Size = UDim2.new(1, -16, 0, 10)
	barBg.Position = UDim2.new(0, 8, 1, -18)
	barBg.BackgroundColor3 = Color3.fromRGB(25, 28, 38)
	barBg.BorderSizePixel = 0
	barBg.Parent = card
	Instance.new("UICorner", barBg).CornerRadius = UDim.new(0, 5)

	local ratio = math.clamp(quest.progress / quest.target, 0, 1)
	local barFill = Instance.new("Frame")
	barFill.Size = UDim2.new(ratio, 0, 1, 0)
	barFill.BackgroundColor3 = quest.completed
		and Color3.fromRGB(80, 200, 80)
		or  Color3.fromRGB(255, 200, 50)
	barFill.BorderSizePixel = 0
	barFill.Parent = barBg
	Instance.new("UICorner", barFill).CornerRadius = UDim.new(0, 5)

	-- Texte progression
	local progressTxt = Instance.new("TextLabel")
	progressTxt.Size = UDim2.new(0, 80, 0, 10)
	progressTxt.Position = UDim2.new(1, -88, 1, -18)
	progressTxt.BackgroundTransparency = 1
	progressTxt.Font = Enum.Font.GothamBold
	progressTxt.TextSize = 10
	progressTxt.TextColor3 = Color3.new(1, 1, 1)
	progressTxt.TextXAlignment = Enum.TextXAlignment.Right
	progressTxt.Text = math.min(quest.progress, quest.target) .. "/" .. quest.target
	progressTxt.Parent = card

	return card
end

-- ────────────────────────────────────────────────
-- Mise à jour de l'affichage
-- ────────────────────────────────────────────────

local function refreshUI(quests)
	-- Supprimer les anciennes cartes
	for _, child in ipairs(scrollFrame:GetChildren()) do
		if child:IsA("Frame") then child:Destroy() end
	end
	-- Recréer
	for i, quest in ipairs(quests) do
		createQuestCard(quest, i)
	end
end

-- ────────────────────────────────────────────────
-- Notification de quête complétée
-- ────────────────────────────────────────────────

local function showNotification(data)
	local notif = Instance.new("Frame")
	notif.Size = UDim2.new(0, 280, 0, 70)
	notif.Position = UDim2.new(0.5, -140, 1, 0)
	notif.BackgroundColor3 = Color3.fromRGB(40, 80, 40)
	notif.BorderSizePixel = 0
	notif.Parent = screenGui
	Instance.new("UICorner", notif).CornerRadius = UDim.new(0, 10)

	local lbl = Instance.new("TextLabel")
	lbl.Size = UDim2.new(1, -10, 1, 0)
	lbl.Position = UDim2.new(0, 5, 0, 0)
	lbl.BackgroundTransparency = 1
	lbl.Font = Enum.Font.GothamBold
	lbl.TextSize = 14
	lbl.TextColor3 = Color3.new(1, 1, 1)
	lbl.TextWrapped = true
	lbl.Text = string.format("%s Quête complétée !\n%s  +%d💰  +%d⭐",
		data.icon or "✅",
		data.title,
		data.reward.money or 0,
		data.reward.xp or 0)
	lbl.Parent = notif

	-- Animation montée
	TweenService:Create(notif,
		TweenInfo.new(0.4, Enum.EasingStyle.Back, Enum.EasingDirection.Out),
		{ Position = UDim2.new(0.5, -140, 1, -90) }
	):Play()

	task.wait(3)

	-- Animation descente
	TweenService:Create(notif,
		TweenInfo.new(0.3, Enum.EasingStyle.Quad, Enum.EasingDirection.In),
		{ Position = UDim2.new(0.5, -140, 1, 0) }
	):Play()
	task.wait(0.3)
	notif:Destroy()
end

-- ────────────────────────────────────────────────
-- Toggle panneau
-- ────────────────────────────────────────────────

toggleBtn.MouseButton1Click:Connect(function()
	panel.Visible = not panel.Visible
end)

-- ────────────────────────────────────────────────
-- Écoute des événements serveur
-- ────────────────────────────────────────────────

QuestUpdate.OnClientEvent:Connect(function(quests)
	refreshUI(quests)
end)

QuestCompleted.OnClientEvent:Connect(function(data)
	task.spawn(showNotification, data)
end)

-- Chargement initial
task.spawn(function()
	task.wait(1.5)
	local quests = GetMyQuests:InvokeServer()
	if quests then refreshUI(quests) end
end)
