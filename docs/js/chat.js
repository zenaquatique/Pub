(() => {
  "use strict";

  const A = window.AQUARAPPEL;
  if (!A.isConfigured) return;
  const supabase = A.supabase;
  const cfg = window.AQUARAPPEL_CONFIG;

  const el = {
    chatLog: document.getElementById("chatLog"),
    chatForm: document.getElementById("chatForm"),
    chatInput: document.getElementById("chatInput"),
    micBtn: document.getElementById("micBtn"),
  };

  const HISTORY_KEY = "aquarappel.chatHistory.v1";
  const MAX_HISTORY = 20;

  function loadHistory() {
    try {
      return JSON.parse(sessionStorage.getItem(HISTORY_KEY)) || [];
    } catch {
      return [];
    }
  }
  function saveHistory(history) {
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(-MAX_HISTORY)));
  }

  let history = loadHistory();

  function addChatMessage(role, text) {
    const div = document.createElement("div");
    div.className = "chat-msg " + role;
    div.textContent = text;
    el.chatLog.appendChild(div);
    el.chatLog.scrollTop = el.chatLog.scrollHeight;

    if (role === "user" || role === "assistant") {
      history.push({ role, text });
      saveHistory(history);
    }
  }
  A.addChatMessage = addChatMessage;

  function renderStoredHistory() {
    if (history.length === 0) {
      addChatMessageNoStore(
        "assistant",
        "Salut ! Je suis ton assistant. Dis-moi ou écris-moi ce que tu veux ajouter, cocher ou supprimer dans ta liste — ou demande-moi simplement ce qu'il te reste à faire."
      );
      return;
    }
    history.forEach((m) => addChatMessageNoStore(m.role, m.text));
  }
  function addChatMessageNoStore(role, text) {
    const div = document.createElement("div");
    div.className = "chat-msg " + role;
    div.textContent = text;
    el.chatLog.appendChild(div);
    el.chatLog.scrollTop = el.chatLog.scrollHeight;
  }

  async function sendToAssistant(message) {
    addChatMessage("user", message);
    const typingId = "typing-" + Date.now();
    const typingEl = document.createElement("div");
    typingEl.id = typingId;
    typingEl.className = "chat-msg assistant";
    typingEl.textContent = "…";
    el.chatLog.appendChild(typingEl);
    el.chatLog.scrollTop = el.chatLog.scrollHeight;

    try {
      const { data: sessionData } = await supabase.auth.getSession();
      const token = sessionData?.session?.access_token;
      if (!token) throw new Error("Session expirée, reconnecte-toi.");

      const res = await fetch(`${cfg.SUPABASE_URL}/functions/v1/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
          apikey: cfg.SUPABASE_ANON_KEY,
        },
        body: JSON.stringify({
          message,
          tasks: A.getTasks().map((t) => ({ id: t.id, text: t.text, done: t.done })),
          history: history.slice(-MAX_HISTORY, -1),
        }),
      });

      const data = await res.json();
      typingEl.remove();

      if (!res.ok) throw new Error(data.error || "Erreur de l'assistant.");

      addChatMessage("assistant", data.reply);
      if (document.getElementById("voiceToggle").checked) A.speak(data.reply);
    } catch (err) {
      typingEl.remove();
      addChatMessage("system", "⚠️ " + err.message);
      A.showToast("Assistant indisponible : " + err.message);
    }
  }

  el.chatForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = el.chatInput.value.trim();
    if (!text) return;
    el.chatInput.value = "";
    sendToAssistant(text);
  });

  // ---------- Voice input (speech to text) ----------

  const SpeechRecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (SpeechRecognitionCtor) {
    el.micBtn.hidden = false;
    const recognition = new SpeechRecognitionCtor();
    recognition.lang = "fr-FR";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    let listening = false;

    recognition.addEventListener("result", (e) => {
      const transcript = e.results[0][0].transcript;
      el.chatInput.value = transcript;
      sendToAssistant(transcript);
      el.chatInput.value = "";
    });
    recognition.addEventListener("end", () => {
      listening = false;
      el.micBtn.classList.remove("listening");
    });
    recognition.addEventListener("error", () => {
      listening = false;
      el.micBtn.classList.remove("listening");
    });

    el.micBtn.addEventListener("click", () => {
      if (listening) {
        recognition.stop();
        return;
      }
      try {
        recognition.start();
        listening = true;
        el.micBtn.classList.add("listening");
      } catch {
        // déjà démarré, ignorer
      }
    });
  } else {
    el.micBtn.hidden = true;
  }

  window.addEventListener("aquarappel:session", () => {
    if (el.chatLog.childElementCount === 0) renderStoredHistory();
  });
})();
