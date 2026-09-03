// Configuration à remplir après avoir créé ton projet Supabase (gratuit).
// Voir docs/README.md, section "Mise en place" pour savoir où trouver ces valeurs.
// L'ANON KEY est prévue pour être publique côté client — protégée par les règles RLS
// côté base de données, donc ce n'est pas un secret à cacher.
window.AQUARAPPEL_CONFIG = {
  SUPABASE_URL: "https://frrmyqqqblheoocgvopp.supabase.co",
  SUPABASE_ANON_KEY:
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZycm15cXFxYmxoZW9vY2d2b3BwIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg0MTc1NjksImV4cCI6MjEwMzk5MzU2OX0.CeWYUI67DaRXHZqCTz5QE4TgadMqrswNp9GhtBTYg5w",
  // Clé publique VAPID pour les notifications push (sûre à exposer, c'est sa raison
  // d'être). Sa contrepartie privée est un secret côté serveur, jamais ici.
  VAPID_PUBLIC_KEY:
    "BCwvlh3PXDhVVtQQr7jp8qvv8_lvdxdc14Tp7ZuJIcnA_dln7HP5PYuNwr9e6Px9x4nUAOWzx_vy4mSySzGYTw0",
};
