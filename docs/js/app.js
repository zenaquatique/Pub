(() => {
  "use strict";

  const TASKS_KEY = "aquarappel.tasks.v1";
  const SETTINGS_KEY = "aquarappel.settings.v1";
  const DEFAULT_SETTINGS = { voice: false, notif: false, intervalMinutes: 60 };

  const el = {
    assistantText: document.getElementById("assistantText"),
    speakNowBtn: document.getElementById("speakNowBtn"),
    remindNowBtn: document.getElementById("remindNowBtn"),
    addForm: document.getElementById("addForm"),
    taskInput: document.getElementById("taskInput"),
    taskList: document.getElementById("taskList"),
    taskCount: document.getElementById("taskCount"),
    emptyState: document.getElementById("emptyState"),
    clearDoneBtn: document.getElementById("clearDoneBtn"),
    voiceToggle: document.getElementById("voiceToggle"),
    notifToggle: document.getElementById("notifToggle"),
    intervalSelect: document.getElementById("intervalSelect"),
    exportBtn: document.getElementById("exportBtn"),
    importInput: document.getElementById("importInput"),
    shareLinkBtn: document.getElementById("shareLinkBtn"),
    installBtn: document.getElementById("installBtn"),
    toast: document.getElementById("toast"),
  };

  // ---------- Persistence ----------

  function loadTasks() {
    try {
      const raw = localStorage.getItem(TASKS_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  function saveTasks(tasks) {
    localStorage.setItem(TASKS_KEY, JSON.stringify(tasks));
  }

  function loadSettings() {
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      return raw ? { ...DEFAULT_SETTINGS, ...JSON.parse(raw) } : { ...DEFAULT_SETTINGS };
    } catch {
      return { ...DEFAULT_SETTINGS };
    }
  }

  function saveSettings(settings) {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  }

  let tasks = loadTasks();
  let settings = loadSettings();

  // ---------- Toast ----------

  let toastTimer = null;
  function showToast(message) {
    el.toast.textContent = message;
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.toast.hidden = true; }, 3200);
  }

  // ---------- Rendering ----------

  function pendingTasks() {
    return tasks.filter((t) => !t.done);
  }

  function render() {
    el.taskList.innerHTML = "";
    tasks.forEach((task) => {
      const li = document.createElement("li");
      li.className = "task-item" + (task.done ? " done" : "");

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = task.done;
      checkbox.setAttribute("aria-label", "Marquer comme fait : " + task.text);
      checkbox.addEventListener("change", () => toggleTask(task.id));

      const span = document.createElement("span");
      span.className = "task-text";
      span.textContent = task.text;

      const del = document.createElement("button");
      del.className = "task-delete";
      del.type = "button";
      del.setAttribute("aria-label", "Supprimer la tâche : " + task.text);
      del.textContent = "✕";
      del.addEventListener("click", () => deleteTask(task.id));

      li.append(checkbox, span, del);
      el.taskList.appendChild(li);
    });

    const total = tasks.length;
    const pending = pendingTasks().length;
    el.taskCount.textContent =
      total === 0 ? "0 tâche" : `${pending} à faire · ${total - pending} faite(s) · ${total} au total`;
    el.emptyState.classList.toggle("visible", total === 0);
  }

  function persistAndRender() {
    saveTasks(tasks);
    render();
    updateAssistantBubble();
  }

  function addTask(text) {
    const clean = text.trim();
    if (!clean) return;
    tasks.unshift({ id: crypto.randomUUID(), text: clean, done: false, createdAt: Date.now() });
    persistAndRender();
  }

  function toggleTask(id) {
    const task = tasks.find((t) => t.id === id);
    if (task) {
      task.done = !task.done;
      persistAndRender();
    }
  }

  function deleteTask(id) {
    tasks = tasks.filter((t) => t.id !== id);
    persistAndRender();
  }

  function clearDone() {
    const before = tasks.length;
    tasks = tasks.filter((t) => !t.done);
    if (tasks.length !== before) {
      persistAndRender();
      showToast("Tâches cochées effacées.");
    }
  }

  // ---------- Assistant messages ----------

  const GREETINGS_EMPTY = [
    "Ta liste est vide. Ajoute une tâche et je veillerai à te la rappeler.",
    "Rien à faire pour l'instant ! Ajoute une tâche quand tu veux.",
  ];

  const GREETINGS_ALL_DONE = [
    "Bravo, tout est coché ! Rien à te rappeler pour le moment.",
    "Tout est fait ! Tu peux souffler un peu.",
    "Liste terminée, bien joué !",
  ];

  const LEAD_INS = [
    "Petit rappel : il te reste",
    "N'oublie pas, il te reste encore",
    "Coucou, tu n'as pas encore coché",
    "Pense à finir",
    "Petit point d'étape : il reste",
  ];

  function pick(arr) {
    return arr[Math.floor(Math.random() * arr.length)];
  }

  function buildReminderMessage() {
    const pending = pendingTasks();
    if (tasks.length === 0) return pick(GREETINGS_EMPTY);
    if (pending.length === 0) return pick(GREETINGS_ALL_DONE);

    const leadIn = pick(LEAD_INS);
    const shown = pending.slice(0, 4).map((t) => t.text);
    let list = shown.join(", ");
    if (pending.length > shown.length) {
      list += `, et ${pending.length - shown.length} autre(s)`;
    }
    const suffix = pending.length === 1 ? "à faire." : "tâche(s) à faire.";
    return `${leadIn} : ${list} — ${pending.length} ${suffix}`;
  }

  function updateAssistantBubble() {
    el.assistantText.textContent = buildReminderMessage();
  }

  // ---------- Voice (Web Speech API) ----------

  let frenchVoice = null;
  function pickFrenchVoice() {
    if (!("speechSynthesis" in window)) return null;
    const voices = speechSynthesis.getVoices();
    return (
      voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("fr") && /female|amélie|audrey|marie/i.test(v.name)) ||
      voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("fr")) ||
      null
    );
  }

  if ("speechSynthesis" in window) {
    speechSynthesis.addEventListener("voiceschanged", () => {
      frenchVoice = pickFrenchVoice();
    });
    frenchVoice = pickFrenchVoice();
  }

  function speak(text) {
    if (!("speechSynthesis" in window)) {
      showToast("La voix n'est pas disponible sur ce navigateur.");
      return;
    }
    speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "fr-FR";
    if (frenchVoice) utter.voice = frenchVoice;
    utter.rate = 1;
    utter.pitch = 1;
    speechSynthesis.speak(utter);
  }

  // ---------- Notifications ----------

  async function ensureNotificationPermission() {
    if (!("Notification" in window)) return "unsupported";
    if (Notification.permission === "granted") return "granted";
    if (Notification.permission === "denied") return "denied";
    return Notification.requestPermission();
  }

  function notify(text) {
    if (!("Notification" in window) || Notification.permission !== "granted") return;
    try {
      const n = new Notification("AquaRappel", { body: text, icon: "icons/icon-192.png" });
      n.onclick = () => window.focus();
    } catch {
      // Some mobile browsers require a service worker to show notifications; ignore silently.
    }
  }

  // ---------- Reminder loop ----------

  let lastReminderAt = 0;

  function runReminder({ manual = false } = {}) {
    updateAssistantBubble();
    const pending = pendingTasks();
    if (pending.length === 0 && !manual) return;

    const message = el.assistantText.textContent;
    if (settings.notif && pending.length > 0) notify(message);
    if (settings.voice) speak(message);
    lastReminderAt = Date.now();
  }

  function tick() {
    if (!settings.notif && !settings.voice) return;
    const intervalMs = settings.intervalMinutes * 60 * 1000;
    if (Date.now() - lastReminderAt >= intervalMs) {
      runReminder();
    }
  }

  setInterval(tick, 30 * 1000);

  // ---------- Settings UI ----------

  function applySettingsToUI() {
    el.voiceToggle.checked = settings.voice;
    el.notifToggle.checked = settings.notif;
    el.intervalSelect.value = String(settings.intervalMinutes);
  }

  el.voiceToggle.addEventListener("change", () => {
    settings.voice = el.voiceToggle.checked;
    saveSettings(settings);
    if (settings.voice) speak("Voix activée. Je te préviendrai à voix haute.");
  });

  el.notifToggle.addEventListener("change", async () => {
    if (el.notifToggle.checked) {
      const perm = await ensureNotificationPermission();
      if (perm !== "granted") {
        el.notifToggle.checked = false;
        settings.notif = false;
        saveSettings(settings);
        showToast(perm === "unsupported" ? "Notifications non supportées ici." : "Autorisation refusée.");
        return;
      }
    }
    settings.notif = el.notifToggle.checked;
    saveSettings(settings);
  });

  el.intervalSelect.addEventListener("change", () => {
    settings.intervalMinutes = Number(el.intervalSelect.value);
    saveSettings(settings);
  });

  // ---------- Form & list events ----------

  el.addForm.addEventListener("submit", (e) => {
    e.preventDefault();
    addTask(el.taskInput.value);
    el.taskInput.value = "";
    el.taskInput.focus();
  });

  el.clearDoneBtn.addEventListener("click", clearDone);

  el.speakNowBtn.addEventListener("click", () => {
    updateAssistantBubble();
    speak(el.assistantText.textContent);
  });

  el.remindNowBtn.addEventListener("click", () => runReminder({ manual: true }));

  // ---------- Export / Import / Share link ----------

  el.exportBtn.addEventListener("click", () => {
    const blob = new Blob([JSON.stringify({ tasks, exportedAt: new Date().toISOString() }, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `aquarappel-taches-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });

  el.importInput.addEventListener("change", async () => {
    const file = el.importInput.files[0];
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      const incoming = Array.isArray(data) ? data : data.tasks;
      if (!Array.isArray(incoming)) throw new Error("format invalide");
      const replace = confirm(
        `Importer ${incoming.length} tâche(s) ?\nOK = remplacer ma liste actuelle\nAnnuler = ajouter à la liste actuelle`
      );
      const cleaned = incoming
        .filter((t) => t && typeof t.text === "string")
        .map((t) => ({ id: t.id || crypto.randomUUID(), text: t.text, done: !!t.done, createdAt: t.createdAt || Date.now() }));
      tasks = replace ? cleaned : [...cleaned, ...tasks];
      persistAndRender();
      showToast("Import terminé.");
    } catch {
      showToast("Fichier invalide.");
    } finally {
      el.importInput.value = "";
    }
  });

  el.shareLinkBtn.addEventListener("click", async () => {
    const payload = encodeURIComponent(btoa(unescape(encodeURIComponent(JSON.stringify(tasks)))));
    const url = `${location.origin}${location.pathname}#import=${payload}`;
    try {
      await navigator.clipboard.writeText(url);
      showToast("Lien copié ! Ouvre-le sur ton autre appareil pour récupérer la liste.");
    } catch {
      prompt("Copie ce lien :", url);
    }
  });

  function importFromLocationHash() {
    const match = location.hash.match(/import=([^&]+)/);
    if (!match) return;
    try {
      const json = decodeURIComponent(escape(atob(decodeURIComponent(match[1]))));
      const incoming = JSON.parse(json);
      if (!Array.isArray(incoming)) return;
      const replace = confirm(
        `Ce lien contient ${incoming.length} tâche(s).\nOK = remplacer ma liste actuelle\nAnnuler = ajouter à la liste actuelle`
      );
      const cleaned = incoming
        .filter((t) => t && typeof t.text === "string")
        .map((t) => ({ id: t.id || crypto.randomUUID(), text: t.text, done: !!t.done, createdAt: t.createdAt || Date.now() }));
      tasks = replace ? cleaned : [...cleaned, ...tasks];
      persistAndRender();
      showToast("Liste importée depuis le lien.");
    } catch {
      showToast("Lien de partage invalide.");
    } finally {
      history.replaceState(null, "", location.pathname + location.search);
    }
  }

  // ---------- Install prompt (PWA) ----------

  let deferredPrompt = null;
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    deferredPrompt = e;
    el.installBtn.hidden = false;
  });

  el.installBtn.addEventListener("click", async () => {
    if (!deferredPrompt) return;
    deferredPrompt.prompt();
    await deferredPrompt.userChoice;
    deferredPrompt = null;
    el.installBtn.hidden = true;
  });

  window.addEventListener("appinstalled", () => {
    el.installBtn.hidden = true;
    showToast("Appli installée !");
  });

  // ---------- Service worker ----------

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("service-worker.js").catch(() => {});
    });
  }

  // ---------- Init ----------

  importFromLocationHash();
  applySettingsToUI();
  render();
  updateAssistantBubble();
})();
