(() => {
  "use strict";

  const cfg = window.AQUARAPPEL_CONFIG || {};
  const isConfigured =
    cfg.SUPABASE_URL &&
    cfg.SUPABASE_ANON_KEY &&
    !cfg.SUPABASE_URL.includes("YOUR-PROJECT") &&
    !cfg.SUPABASE_ANON_KEY.includes("YOUR-ANON-PUBLIC-KEY");

  window.AQUARAPPEL = window.AQUARAPPEL || {};
  window.AQUARAPPEL.isConfigured = isConfigured;
  window.AQUARAPPEL.supabase = isConfigured
    ? window.supabase.createClient(cfg.SUPABASE_URL, cfg.SUPABASE_ANON_KEY)
    : null;
})();
