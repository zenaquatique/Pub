#!/bin/bash
set -e

# Install dependencies if needed
if ! python3 -c "import flask" 2>/dev/null; then
  echo "Installation des dépendances..."
  pip install -r requirements.txt
fi

# Copy .env if it doesn't exist
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "⚠️  Fichier .env créé. Remplis ANTHROPIC_API_KEY avant de continuer."
  echo ""
fi

echo "🚀 Démarrage de l'assistant email sur http://localhost:5000"
python3 app.py
