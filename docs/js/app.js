(() => {
  "use strict";

  const A = window.AQUARAPPEL;
  if (!A.isConfigured) return;
  const supabase = A.supabase;

  const SETTINGS_KEY = "aquarappel.settings.v1";
  const DEFAULT_SETTINGS = { voice: false, notif: false };
  const DEFAULT_SERVER_SETTINGS = { interval_minutes: 60, window_start_hour: 10, window_end_hour: 22 };

  const el = {
    addForm: document.getElementById("addForm"),
    taskInput: document.getElementById("taskInput"),
    taskDueDateInput: document.getElementById("taskDueDateInput"),
    taskList: document.getElementById("taskList"),
    taskCount: document.getElementById("taskCount"),
    emptyState: document.getElementById("emptyState"),
    clearDoneBtn: document.getElementById("clearDoneBtn"),
    voiceToggle: document.getElementById("voiceToggle"),
    notifToggle: document.getElementById("notifToggle"),
    intervalSelect: document.getElementById("intervalSelect"),
    windowStartSelect: document.getElementById("windowStartSelect"),
    windowEndSelect: document.getElementById("windowEndSelect"),
    pushEnableBtn: document.getElementById("pushEnableBtn"),
    pushStatusLabel: document.getElementById("pushStatusLabel"),
    exportBtn: document.getElementById("exportBtn"),
    importInput: document.getElementById("importInput"),
    installBtn: document.getElementById("installBtn"),
    signOutBtn: document.getElementById("signOutBtn"),
    remindNowBtn: document.getElementById("remindNowBtn"),
    toast: document.getElementById("toast"),
  };

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

  const settings = loadSettings();
  let serverSettings = { ...DEFAULT_SERVER_SETTINGS };
  let tasks = [];
  let currentUserId = null;
  let channel = null;

  function todayStr() {
    const d = new Date();
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  // ---------- Toast ----------

  let toastTimer = null;
  function showToast(message) {
    el.toast.textContent = message;
    el.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { el.toast.hidden = true; }, 3200);
  }
  A.showToast = showToast;

  // ---------- Task helpers exposed to chat.js ----------

  A.getTasks = () => tasks;
  A.getPendingTasks = () => tasks.filter((t) => !t.done);

  // ---------- Rendering ----------

  function render() {
    const today = todayStr();
    el.taskList.innerHTML = "";
    tasks.forEach((task) => {
      const li = document.createElement("li");
      li.className = "task-item" + (task.done ? " done" : "");

      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = task.done;
      checkbox.setAttribute("aria-label", "Marquer comme fait : " + task.text);
      checkbox.addEventListener("change", () => toggleTask(task.id, checkbox.checked));

      const main = document.createElement("div");
      main.className = "task-main";

      const span = document.createElement("span");
      span.className = "task-text";
      span.textContent = task.text;

      const dueRow = document.createElement("div");
      dueRow.className = "task-due-row";

      const dueLabel = document.createElement("span");
      dueLabel.className = "task-due-label";
      dueLabel.textContent = "📅";

      const dueInput = document.createElement("input");
      dueInput.type = "date";
      dueInput.className = "task-due-input";
      dueInput.value = task.due_date || "";
      dueInput.setAttribute("aria-label", "Échéance de : " + task.text);
      if (task.due_date && !task.done) {
        if (task.due_date === today) dueInput.classList.add("today");
        else if (task.due_date < today) dueInput.classList.add("overdue");
      }
      dueInput.addEventListener("change", () => setDueDate(task.id, dueInput.value));

      dueRow.append(dueLabel, dueInput);
      main.append(span, dueRow);

      const del = document.createElement("button");
      del.className = "task-delete";
      del.type = "button";
      del.setAttribute("aria-label", "Supprimer la tâche : " + task.text);
      del.textContent = "✕";
      del.addEventListener("click", () => deleteTask(task.id));

      li.append(checkbox, main, del);
      el.taskList.appendChild(li);
    });

    const total = tasks.length;
    const pending = A.getPendingTasks().length;
    el.taskCount.textContent =
      total === 0 ? "0 tâche" : `${pending} à faire · ${total - pending} faite(s) · ${total} au total`;
    el.emptyState.classList.toggle("visible", total === 0);

    window.dispatchEvent(new CustomEvent("aquarappel:tasks-changed"));
  }

  // ---------- Supabase CRUD ----------

  async function loadTasks() {
    const { data, error } = await supabase
      .from("tasks")
      .select("*")
      .order("created_at", { ascending: false });
    if (error) {
      showToast("Impossible de charger tes tâches : " + error.message);
      return;
    }
    tasks = data || [];
    render();
  }

  async function getFreshUserId() {
    const { data, error } = await supabase.auth.getUser();
    if (error || !data?.user) return null;
    currentUserId = data.user.id;
    return currentUserId;
  }

  async function addTask(text, dueDate) {
    const clean = text.trim();
    if (!clean) return;
    const userId = await getFreshUserId();
    if (!userId) {
      showToast("Session expirée, reconnecte-toi puis réessaie.");
      return;
    }
    const { error } = await supabase
      .from("tasks")
      .insert({ text: clean, user_id: userId, due_date: dueDate || null });
    if (error) showToast("Erreur lors de l'ajout : " + error.message);
    else await loadTasks();
  }
  A.addTask = addTask;

  async function setDueDate(id, value) {
    const { error } = await supabase.from("tasks").update({ due_date: value || null }).eq("id", id);
    if (error) showToast("Erreur : " + error.message);
    else await loadTasks();
  }

  async function toggleTask(id, done) {
    const { error } = await supabase.from("tasks").update({ done }).eq("id", id);
    if (error) showToast("Erreur : " + error.message);
    else await loadTasks();
  }

  async function deleteTask(id) {
    const { error } = await supabase.from("tasks").delete().eq("id", id);
    if (error) showToast("Erreur : " + error.message);
    else await loadTasks();
  }

  async function clearDone() {
    const doneIds = tasks.filter((t) => t.done).map((t) => t.id);
    if (doneIds.length === 0) return;
    const { error } = await supabase.from("tasks").delete().in("id", doneIds);
    if (error) {
      showToast("Erreur : " + error.message);
    } else {
      await loadTasks();
      showToast("Tâches cochées effacées.");
    }
  }

  // ---------- Assistant reminder phrasing (local, free — no API call) ----------

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
    const pending = A.getPendingTasks();
    if (tasks.length === 0) return pick(GREETINGS_EMPTY);
    if (pending.length === 0) return pick(GREETINGS_ALL_DONE);

    const leadIn = pick(LEAD_INS);
    const shown = pending.slice(0, 4).map((t) => t.text);
    let list = shown.join(", ");
    if (pending.length > shown.length) list += `, et ${pending.length - shown.length} autre(s)`;
    const suffix = pending.length === 1 ? "à faire." : "tâche(s) à faire.";
    return `${leadIn} : ${list} — ${pending.length} ${suffix}`;
  }

  // ---------- Voice (Web Speech API — text to speech) ----------

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
    speechSynthesis.addEventListener("voiceschanged", () => { frenchVoice = pickFrenchVoice(); });
    frenchVoice = pickFrenchVoice();
  }

  function speak(text) {
    if (!("speechSynthesis" in window)) return;
    speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "fr-FR";
    if (frenchVoice) utter.voice = frenchVoice;
    speechSynthesis.speak(utter);
  }
  A.speak = speak;

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
      // Certains navigateurs mobiles exigent un service worker pour les notifications ; on ignore.
    }
  }

  // ---------- Reminder loop ----------

  let lastReminderAt = 0;

  function runReminder({ manual = false } = {}) {
    const pending = A.getPendingTasks();
    if (pending.length === 0 && !manual) return;
    const message = buildReminderMessage();
    if (A.addChatMessage) A.addChatMessage("assistant", message);
    if (settings.notif && pending.length > 0) notify(message);
    if (settings.voice) speak(message);
    lastReminderAt = Date.now();
  }

  function withinReminderWindow() {
    const hour = new Date().getHours();
    return hour >= serverSettings.window_start_hour && hour < serverSettings.window_end_hour;
  }

  function tick() {
    if (!currentUserId) return;
    if (!settings.notif && !settings.voice) return;
    if (!withinReminderWindow()) return;
    const intervalMs = serverSettings.interval_minutes * 60 * 1000;
    if (Date.now() - lastReminderAt >= intervalMs) runReminder();
  }
  setInterval(tick, 30 * 1000);

  // ---------- Settings UI ----------

  function populateHourSelect(select) {
    select.innerHTML = "";
    for (let h = 0; h <= 23; h++) {
      const opt = document.createElement("option");
      opt.value = String(h);
      opt.textContent = `${String(h).padStart(2, "0")}h`;
      select.appendChild(opt);
    }
  }
  populateHourSelect(el.windowStartSelect);
  populateHourSelect(el.windowEndSelect);

  function applySettingsToUI() {
    el.voiceToggle.checked = settings.voice;
    el.notifToggle.checked = settings.notif;
    el.intervalSelect.value = String(serverSettings.interval_minutes);
    el.windowStartSelect.value = String(serverSettings.window_start_hour);
    el.windowEndSelect.value = String(serverSettings.window_end_hour);
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

  async function saveServerSettings(patch) {
    serverSettings = { ...serverSettings, ...patch };
    if (!currentUserId) return;
    const { error } = await supabase
      .from("reminder_settings")
      .upsert({ user_id: currentUserId, ...serverSettings }, { onConflict: "user_id" });
    if (error) showToast("Erreur réglages : " + error.message);
  }

  el.intervalSelect.addEventListener("change", () => {
    saveServerSettings({ interval_minutes: Number(el.intervalSelect.value) });
  });

  el.windowStartSelect.addEventListener("change", () => {
    saveServerSettings({ window_start_hour: Number(el.windowStartSelect.value) });
  });

  el.windowEndSelect.addEventListener("change", () => {
    saveServerSettings({ window_end_hour: Number(el.windowEndSelect.value) });
  });

  // ---------- Push notifications (arrivent même appli fermée) ----------

  function urlBase64ToUint8Array(base64String) {
    const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    const raw = atob(base64);
    return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
  }

  async function refreshPushButton() {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      el.pushEnableBtn.disabled = true;
      el.pushStatusLabel.textContent = "Non supporté par ce navigateur.";
      return;
    }
    try {
      const reg = await navigator.serviceWorker.ready;
      const sub = await reg.pushManager.getSubscription();
      el.pushEnableBtn.textContent = sub ? "Activé ✓" : "Activer";
    } catch {
      // ignore
    }
  }

  el.pushEnableBtn.addEventListener("click", async () => {
    if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
      showToast("Notifications push non supportées sur ce navigateur.");
      return;
    }
    const cfg = window.AQUARAPPEL_CONFIG;
    if (!cfg.VAPID_PUBLIC_KEY) {
      showToast("Clé VAPID manquante côté configuration.");
      return;
    }
    const userId = await getFreshUserId();
    if (!userId) {
      showToast("Session expirée, reconnecte-toi puis réessaie.");
      return;
    }
    const perm = await ensureNotificationPermission();
    if (perm !== "granted") {
      showToast("Autorisation refusée.");
      return;
    }
    try {
      const reg = await navigator.serviceWorker.ready;
      let sub = await reg.pushManager.getSubscription();
      if (!sub) {
        sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(cfg.VAPID_PUBLIC_KEY),
        });
      }
      const json = sub.toJSON();
      const { error } = await supabase.from("push_subscriptions").upsert(
        {
          user_id: userId,
          endpoint: json.endpoint,
          p256dh: json.keys.p256dh,
          auth_key: json.keys.auth,
        },
        { onConflict: "endpoint" }
      );
      if (error) throw error;
      showToast("Notifications push activées sur cet appareil.");
      await refreshPushButton();
    } catch (err) {
      showToast("Impossible d'activer les notifications push : " + err.message);
    }
  });

  // ---------- Form & list events ----------

  el.addForm.addEventListener("submit", (e) => {
    e.preventDefault();
    addTask(el.taskInput.value, el.taskDueDateInput.value);
    el.taskInput.value = "";
    el.taskDueDateInput.value = "";
    el.taskInput.focus();
  });

  el.clearDoneBtn.addEventListener("click", clearDone);
  el.remindNowBtn.addEventListener("click", () => runReminder({ manual: true }));

  // ---------- Export / Import (local backup) ----------

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
      const userId = await getFreshUserId();
      if (!userId) throw new Error("session expirée, reconnecte-toi");
      const cleaned = incoming
        .filter((t) => t && typeof t.text === "string")
        .map((t) => ({ text: t.text, done: !!t.done, user_id: userId }));
      if (cleaned.length === 0) throw new Error("aucune tâche trouvée");
      const { error } = await supabase.from("tasks").insert(cleaned);
      if (error) throw error;
      showToast(`${cleaned.length} tâche(s) importée(s).`);
    } catch (err) {
      showToast("Import impossible : " + err.message);
    } finally {
      el.importInput.value = "";
    }
  });

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

  // ---------- Server-side reminder settings ----------

  async function loadServerSettings() {
    const { data, error } = await supabase
      .from("reminder_settings")
      .select("*")
      .eq("user_id", currentUserId)
      .maybeSingle();
    if (error) {
      showToast("Erreur réglages : " + error.message);
      return;
    }
    if (data) {
      serverSettings = {
        interval_minutes: data.interval_minutes,
        window_start_hour: data.window_start_hour,
        window_end_hour: data.window_end_hour,
      };
    } else {
      serverSettings = { ...DEFAULT_SERVER_SETTINGS };
      await supabase
        .from("reminder_settings")
        .upsert({ user_id: currentUserId, ...serverSettings }, { onConflict: "user_id" });
    }
  }

  // ---------- Session lifecycle ----------

  window.addEventListener("aquarappel:session", async (e) => {
    currentUserId = e.detail.session.user.id;
    el.signOutBtn.hidden = false;
    await loadServerSettings();
    applySettingsToUI();
    await refreshPushButton();
    await loadTasks();

    if (channel) supabase.removeChannel(channel);
    channel = supabase
      .channel("tasks-changes-" + currentUserId)
      .on(
        "postgres_changes",
        { event: "*", schema: "public", table: "tasks", filter: `user_id=eq.${currentUserId}` },
        () => loadTasks()
      )
      .subscribe();
  });

  supabase.auth.onAuthStateChange((event) => {
    if (event === "SIGNED_OUT") {
      currentUserId = null;
      tasks = [];
      render();
      el.signOutBtn.hidden = true;
      if (channel) {
        supabase.removeChannel(channel);
        channel = null;
      }
    }
  });
})();
