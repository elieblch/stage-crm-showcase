#!/bin/bash
# ══════════════════════════════════════════════════════════
# Stage CRM — Script de setup initial
# ══════════════════════════════════════════════════════════

set -e

echo "🚀 Stage CRM — Setup initial"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 1. Copier le .env
if [ ! -f .env ]; then
    cp .env.example .env
    echo "✅ .env créé — PENSE À AJOUTER TES CLÉS API !"
    echo "   → ANTHROPIC_API_KEY (obligatoire)"
    echo "   → GMAIL_CLIENT_ID + SECRET (pour l'envoi de mails)"
else
    echo "⏭️  .env existe déjà"
fi

# 2. Lancer Docker Compose
echo ""
echo "🐳 Lancement des containers Docker..."
docker compose up -d --build

# 3. Attendre que la BDD soit prête
echo "⏳ Attente de PostgreSQL..."
sleep 5

# 4. Installer Playwright pour le scraping
echo "🎭 Installation de Playwright (scraping)..."
docker compose exec backend playwright install chromium --with-deps 2>/dev/null || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Stage CRM est prêt !"
echo ""
echo "  🌐 Frontend  → http://localhost:3000"
echo "  🔌 API       → http://localhost:8000"
echo "  📚 API Docs  → http://localhost:8000/docs"
echo "  🐘 PostgreSQL → localhost:5432"
echo "  🔴 Redis     → localhost:6379"
echo ""
echo "📝 Prochaines étapes :"
echo "  1. Ajoute ta clé ANTHROPIC_API_KEY dans .env"
echo "  2. Configure tes préférences de recherche via le frontend"
echo "  3. Upload ton CV"
echo "  4. Le scan quotidien se lancera automatiquement à 6h !"
echo ""
echo "💡 Commandes utiles :"
echo "  docker compose logs -f backend    # Logs API"
echo "  docker compose logs -f worker     # Logs scraping"
echo "  docker compose exec backend bash  # Shell backend"
echo "  docker compose down               # Arrêter tout"
