(() => {
  "use strict";

  const A = window.AQUARAPPEL;
  const supabase = A.supabase;

  const el = {
    setupScreen: document.getElementById("setupScreen"),
    authScreen: document.getElementById("authScreen"),
    appScreen: document.getElementById("appScreen"),
    authForm: document.getElementById("authForm"),
    authEmail: document.getElementById("authEmail"),
    authPassword: document.getElementById("authPassword"),
    authError: document.getElementById("authError"),
    authSubmitBtn: document.getElementById("authSubmitBtn"),
    authToggleModeBtn: document.getElementById("authToggleModeBtn"),
    authTitle: document.getElementById("authTitle"),
    signOutBtn: document.getElementById("signOutBtn"),
    userEmailLabel: document.getElementById("userEmailLabel"),
  };

  function showScreen(name) {
    el.setupScreen.hidden = name !== "setup";
    el.authScreen.hidden = name !== "auth";
    el.appScreen.hidden = name !== "app";
  }

  if (!A.isConfigured) {
    showScreen("setup");
    return;
  }

  let mode = "signin"; // or "signup"

  function setMode(next) {
    mode = next;
    el.authTitle.textContent = mode === "signin" ? "Connexion" : "Créer un compte";
    el.authSubmitBtn.textContent = mode === "signin" ? "Se connecter" : "Créer mon compte";
    el.authToggleModeBtn.textContent =
      mode === "signin" ? "Pas encore de compte ? En créer un" : "Déjà un compte ? Se connecter";
    el.authError.hidden = true;
  }

  el.authToggleModeBtn.addEventListener("click", () => setMode(mode === "signin" ? "signup" : "signin"));

  el.authForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    el.authError.hidden = true;
    el.authSubmitBtn.disabled = true;
    const email = el.authEmail.value.trim();
    const password = el.authPassword.value;

    try {
      const { error } =
        mode === "signin"
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password });

      if (error) throw error;

      if (mode === "signup") {
        el.authError.hidden = false;
        el.authError.textContent =
          "Compte créé. Si Supabase demande une confirmation par e-mail, clique sur le lien reçu puis reviens te connecter.";
        el.authError.classList.add("info");
        setMode("signin");
      }
    } catch (err) {
      el.authError.hidden = false;
      el.authError.classList.remove("info");
      el.authError.textContent = translateAuthError(err.message);
    } finally {
      el.authSubmitBtn.disabled = false;
    }
  });

  el.signOutBtn.addEventListener("click", async () => {
    await supabase.auth.signOut();
  });

  function translateAuthError(message) {
    if (/invalid login credentials/i.test(message)) return "E-mail ou mot de passe incorrect.";
    if (/user already registered/i.test(message)) return "Un compte existe déjà avec cet e-mail.";
    if (/password should be at least/i.test(message)) return "Mot de passe trop court (6 caractères minimum).";
    return message;
  }

  supabase.auth.onAuthStateChange((_event, session) => {
    if (session && session.user) {
      el.userEmailLabel.textContent = session.user.email || "";
      showScreen("app");
      window.dispatchEvent(new CustomEvent("aquarappel:session", { detail: { session } }));
    } else {
      el.userEmailLabel.textContent = "";
      showScreen("auth");
    }
  });

  setMode("signin");
})();
