-- PoulaillerServer
-- Place dans : ServerScriptService
-- Ne touche a rien d'autre que le systeme poulailler

local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local MAX_OEUFS = 5
local MAX_DEDANS = 3
local DUREE_DEDANS = 20 -- secondes
local RAYON_ENCLOS = 60 -- distance max pour chercher des poules

-- Trouve le Poulailler dans le workspace (peut etre dans n'importe quel dossier)
local poulailler = nil
for _, obj in ipairs(workspace:GetDescendants()) do
	if obj.Name == "Poulailler" and obj:IsA("Model") then
		poulailler = obj
		break
	end
end

if not poulailler then
	warn("PoulaillerServer: Poulailler introuvable dans le workspace")
	return
end

-- Pond_Avant = la partie avant du poulailler (porte entree/sortie)
local pondAvant = poulailler:FindFirstChild("Pond_Avant")
if not pondAvant then
	warn("PoulaillerServer: Pond_Avant introuvable dans Poulailler")
	return
end

-- Attribut NbOeufs sur le poulailler (persiste tant que le serveur tourne)
if not poulailler:GetAttribute("NbOeufs") then
	poulailler:SetAttribute("NbOeufs", 0)
end

-- Table des poules actuellement dans le poulailler
local poulesDedan = {} -- { poule = model, timer = nb secondes restantes }

-- Verrou pour empecher qu'une meme poule soit envoyee deux fois
local poulesEnRoute = {} -- set de modeles poule

local function getNbDedans()
	return #poulesDedan
end

-- Trouve toutes les poules libres dans les Enclos proches du Poulailler
local function trouverPoulesDisponibles()
	local portePos = pondAvant.Position
	local disponibles = {}

	for _, obj in ipairs(workspace:GetDescendants()) do
		if obj.Name == "Enclos" and obj:IsA("Model") then
			local primary = obj.PrimaryPart or obj:FindFirstChildWhichIsA("BasePart")
			if primary then
				local dist = (primary.Position - portePos).Magnitude
				if dist <= RAYON_ENCLOS then
					-- Cherche les poules dans cet enclos
					for _, child in ipairs(obj:GetChildren()) do
						if child.Name == "Poule" and child:IsA("Model") then
							-- Poule libre = pas en route et pas dedans
							local dejaOccupee = poulesEnRoute[child]
							if not dejaOccupee then
								table.insert(disponibles, child)
							end
						end
					end
				end
			end
		end
	end

	return disponibles
end

-- Fait marcher une poule vers une position cible en utilisant le BodyVelocity existant
-- (la poule a deja un BodyVelocity cree par PouleAnimScript)
local function deplacerPouleVers(poule, cible, onArrivee)
	local poulePart = poule.PrimaryPart or poule:FindFirstChildWhichIsA("BasePart")
	if not poulePart then return end

	-- On pose un attribut pour que PouleAnimScript sache que la poule est "commandee"
	poule:SetAttribute("PoulaillerMode", true)
	poule:SetAttribute("PoulaillerCibleX", cible.X)
	poule:SetAttribute("PoulaillerCibleY", cible.Y)
	poule:SetAttribute("PoulaillerCibleZ", cible.Z)

	-- Boucle de deplacement cote serveur
	local connexion
	connexion = RunService.Heartbeat:Connect(function()
		if not poule or not poule.Parent then
			connexion:Disconnect()
			return
		end

		local part = poule.PrimaryPart or poule:FindFirstChildWhichIsA("BasePart")
		if not part then
			connexion:Disconnect()
			return
		end

		local pos = part.Position
		local dir = (Vector3.new(cible.X, pos.Y, cible.Z) - pos)
		local dist = dir.Magnitude

		if dist < 1.5 then
			connexion:Disconnect()
			poule:SetAttribute("PoulaillerMode", false)
			if onArrivee then onArrivee() end
			return
		end

		local vitesse = 4
		local dirNorm = dir.Unit
		part.CFrame = CFrame.new(pos + dirNorm * vitesse * (1/60))
			* CFrame.Angles(0, math.atan2(-dirNorm.X, -dirNorm.Z) + math.rad(-90), 0)
	end)
end

-- Envoie une poule dans le poulailler
local function envoyerPouleDedans(poule)
	poulesEnRoute[poule] = true
	local portePos = pondAvant.Position

	-- Position d'entree devant la porte
	local entreePos = portePos + Vector3.new(0, 0, 2)
	-- Position interieure (un peu dans le poulailler)
	local interieurePos = portePos + Vector3.new(0, 0, -2)

	-- Etape 1 : marche jusqu'a la porte
	deplacerPouleVers(poule, entreePos, function()
		-- Etape 2 : entre dans le poulailler (position interieure)
		deplacerPouleVers(poule, interieurePos, function()
			-- Poule est dedans
			local entree = { poule = poule, tempsRestant = DUREE_DEDANS }
			table.insert(poulesDedan, entree)

			-- Rend la poule invisible (elle est "dans" le poulailler)
			for _, part in ipairs(poule:GetDescendants()) do
				if part:IsA("BasePart") then
					part.Transparency = 1
				end
			end

			-- Attendre DUREE_DEDANS secondes puis faire sortir
			task.delay(DUREE_DEDANS, function()
				if not poule or not poule.Parent then
					-- Poule disparue, on la retire juste
					for i, entry in ipairs(poulesDedan) do
						if entry.poule == poule then
							table.remove(poulesDedan, i)
							break
						end
					end
					poulesEnRoute[poule] = nil
					return
				end

				-- Rend la poule visible
				for _, part in ipairs(poule:GetDescendants()) do
					if part:IsA("BasePart") then
						part.Transparency = 0
					end
				end

				-- Teleporte la poule devant la porte pour sortir
				local poulePart = poule.PrimaryPart or poule:FindFirstChildWhichIsA("BasePart")
				if poulePart then
					poulePart.CFrame = CFrame.new(interieurePos)
				end

				-- Etape 3 : sort du poulailler
				deplacerPouleVers(poule, entreePos + Vector3.new(0, 0, 3), function()
					-- Poule dehors, ajoute un oeuf
					local nbOeufs = poulailler:GetAttribute("NbOeufs") or 0
					if nbOeufs < MAX_OEUFS then
						poulailler:SetAttribute("NbOeufs", nbOeufs + 1)
					end

					-- Retire la poule de la liste dedans
					for i, entry in ipairs(poulesDedan) do
						if entry.poule == poule then
							table.remove(poulesDedan, i)
							break
						end
					end
					poulesEnRoute[poule] = nil
				end)
			end)
		end)
	end)
end

-- Boucle principale : toutes les 5 secondes, envoie des poules si possible
task.spawn(function()
	while true do
		task.wait(5)

		local nbOeufs = poulailler:GetAttribute("NbOeufs") or 0
		if nbOeufs >= MAX_OEUFS then
			-- Poulailler plein, on attend que le joueur collecte
			continue
		end

		local places = MAX_DEDANS - getNbDedans()
		if places <= 0 then
			continue
		end

		local disponibles = trouverPoulesDisponibles()
		for i = 1, math.min(places, #disponibles) do
			envoyerPouleDedans(disponibles[i])
		end
	end
end)
